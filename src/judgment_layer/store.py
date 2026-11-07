"""Small transactional ledger; local identities are cooperative, not credentials."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .model import JudgmentError, applies, canonical, digest, now, validate, validate_facts


DEFAULT_CAPTURE = {
    "origins": ["human_guidance", "human_judgment", "agent_judgment", "agent_assumption", "unknown"],
    "guidance": ["Capture meaningful choices, corrections, conditions and exceptions.",
                 "Skip routine tool output and duplicated notes.",
                 "Do not invent rationale or turn a local instruction into a permanent rule."]
}


def read_config(root):
    try:
        config = json.loads((root / "config.json").read_text())
    except (OSError, ValueError) as exc:
        raise JudgmentError("Workspace not initialized or config invalid; run judgment init") from exc
    if set(config) != {"schema_version", "owner", "admission", "capture"} or config["schema_version"] != 1:
        raise JudgmentError("Unsupported workspace configuration")
    if not isinstance(config["owner"], str) or not config["owner"].startswith("human:") or not config["owner"][6:].strip():
        raise JudgmentError("Owner must be a human:<name> identity")
    if config["admission"] != {"mode": "manual"}:
        raise JudgmentError("Only manual admission is supported; config cannot enable auto-admission")
    capture = config["capture"]
    if not isinstance(capture, dict) or set(capture) != {"origins", "guidance"}:
        raise JudgmentError("Invalid capture policy")
    if not isinstance(capture["origins"], list) or not capture["origins"] or any(
            x not in DEFAULT_CAPTURE["origins"] for x in capture["origins"]):
        raise JudgmentError("Invalid capture origins")
    if not isinstance(capture["guidance"], list) or any(not isinstance(x, str) for x in capture["guidance"]):
        raise JudgmentError("Invalid capture guidance")
    return config


def initialize(root, owner):
    root = Path(root)
    if root.exists():
        raise JudgmentError("Workspace already exists; refusing to overwrite it")
    if not owner.startswith("human:") or not owner[6:].strip():
        raise JudgmentError("Use --owner human:<name>")
    root.mkdir(parents=True, mode=0o700)
    config = {"schema_version": 1, "owner": owner, "admission": {"mode": "manual"}, "capture": DEFAULT_CAPTURE}
    (root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    with sqlite3.connect(root / "store.sqlite3") as db:
        db.executescript("""
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO metadata VALUES ('version', '1');
            CREATE TABLE revisions (
                id TEXT NOT NULL, version INTEGER NOT NULL, digest TEXT NOT NULL,
                body TEXT NOT NULL, PRIMARY KEY(id, version));
            CREATE TABLE events (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL);
        """)
    return {"workspace": str(root.resolve()), "owner": owner, "admission": "manual"}


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.config = read_config(self.root)
        path = self.root / "store.sqlite3"
        if not path.is_file() or path.is_symlink():
            raise JudgmentError("Workspace database missing or is a symlink")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("SELECT value FROM metadata WHERE key='version'").fetchone()[0] != "1":
            self.close()
            raise JudgmentError("Unsupported database version")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.config = read_config(self.root)
            self.audit()
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def events(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT body FROM events ORDER BY seq")]

    def append(self, kind, actor, record=None, reason=None, data=None):
        row = self.db.execute("SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        event = {"seq": row[0] + 1 if row else 1, "event_id": "evt_" + uuid.uuid4().hex,
                 "kind": kind, "at": now(), "actor": actor, "identity_basis": "self_asserted_local",
                 "reason": reason, "data": data or {}, "previous_hash": row[1] if row else None}
        if record:
            event.update(judgment_id=record["id"], version=record["version"], record_digest=digest(record))
        self.db.execute("INSERT INTO events VALUES (?,?,?)", (event["seq"], canonical(event), digest(event)))
        return event

    def record(self, jid, version=None):
        if version is None:
            row = self.db.execute("SELECT body FROM revisions WHERE id=? ORDER BY version DESC LIMIT 1", (jid,)).fetchone()
        else:
            row = self.db.execute("SELECT body FROM revisions WHERE id=? AND version=?", (jid, version)).fetchone()
        if not row:
            raise JudgmentError("Judgment revision not found")
        return json.loads(row[0])

    def audit(self):
        previous = None
        captured = {}
        for expected_seq, row in enumerate(self.db.execute("SELECT seq,body,digest FROM events ORDER BY seq"), 1):
            e = json.loads(row[1])
            if row[0] != expected_seq or e["seq"] != expected_seq or e["previous_hash"] != previous or digest(e) != row[2]:
                raise JudgmentError("Ledger integrity check failed")
            previous = row[2]
            if "judgment_id" in e:
                record = self.record(e["judgment_id"], e["version"])
                if digest(record) != e["record_digest"]:
                    raise JudgmentError("Event is not bound to its revision")
                if e["kind"] == "captured":
                    captured[(e["judgment_id"], e["version"])] = e["record_digest"]
        count = 0
        for row in self.db.execute("SELECT id,version,digest,body FROM revisions"):
            record = validate(json.loads(row[3]))
            if (record["id"], record["version"]) != (row[0], row[1]) or digest(record) != row[2] or captured.get((row[0], row[1])) != row[2]:
                raise JudgmentError("Revision integrity check failed")
            count += 1
        return {"ok": True, "revisions": count, "events": len(self.events()), "head": previous}

    def state(self, record):
        state = "proposed"
        for e in self.events():
            if e.get("judgment_id") == record["id"] and e.get("version") == record["version"]:
                state = {"admitted": "admitted", "rejected": "rejected", "changes_requested": "needs_changes",
                         "withdrawn": "withdrawn", "superseded": "superseded",
                         "candidate_replaced": "superseded"}.get(e["kind"], state)
        return state

    def eligible(self, record, scope, facts, seen=None):
        seen = set() if seen is None else seen
        key = (record["id"], record["version"])
        if key in seen:
            return "dependency_cycle"
        if self.state(record) != "admitted":
            return self.state(record)
        reason = applies(record, scope, facts)
        if reason:
            return reason
        for link in record["links"]:
            if link["relation"] != "depends_on":
                continue
            dep = self.record(link["id"], link["version"])
            if digest(dep) != link["digest"] or self.eligible(dep, scope, facts, seen | {key}):
                return "invalid_dependency:" + link["id"]
        return None

    def capture(self, document, jid=None, reason=None, base_digest=None):
        record = json.loads(canonical(document))
        if jid:
            prior = self.record(jid)
            if base_digest != digest(prior):
                raise JudgmentError("Revision base changed; inspect the latest record and pass its --base-digest")
            for reserved in ("id", "version"):
                if reserved in record:
                    raise JudgmentError("Revision input must omit id and version")
            record.update(id=jid, version=prior["version"] + 1)
            record["links"] = record.get("links", []) + [{"relation": "revises", "id": jid,
                "version": prior["version"], "digest": digest(prior)}]
            if not reason or not reason.strip():
                raise JudgmentError("Revision requires a reason")
        else:
            record.setdefault("id", "jgm_" + uuid.uuid4().hex)
            record.setdefault("version", 1)
            if record["version"] != 1:
                raise JudgmentError("Capture starts at version 1; use revise")
        record.setdefault("ajf_version", "0.1-draft")
        record.setdefault("links", [])
        validate(record)
        if record["provenance"]["origin"] not in self.config["capture"]["origins"]:
            raise JudgmentError("Origin excluded by capture policy")
        for link in record["links"]:
            target = self.record(link["id"], link["version"])
            if digest(target) != link["digest"]:
                raise JudgmentError("Link digest does not match the stored revision")
        try:
            self.db.execute("INSERT INTO revisions VALUES (?,?,?,?)", (record["id"], record["version"], digest(record), canonical(record)))
        except sqlite3.IntegrityError as exc:
            raise JudgmentError("Revision exists; use revise instead of overwriting") from exc
        self.append("captured", record["provenance"]["recorded_by"], record, reason)
        if jid and self.state(prior) in {"proposed", "needs_changes"}:
            self.append("candidate_replaced", record["provenance"]["recorded_by"], prior, reason,
                        {"by_version": record["version"], "by_digest": digest(record)})
        return self.describe(record)

    def describe(self, record):
        return {"id": record["id"], "version": record["version"], "name": record["name"],
                "digest": digest(record), "state": self.state(record), "record": record}

    def owner_action(self, jid, version, expected_digest, decision, reason, confirmed):
        if not confirmed:
            raise JudgmentError("Manual owner action requires --confirm after inspecting the record")
        record = self.record(jid, version)
        if digest(record) != expected_digest:
            raise JudgmentError("Digest mismatch; inspect the exact revision before review")
        if not reason or not reason.strip():
            raise JudgmentError("Owner action requires a reason")
        state = self.state(record)
        if decision == "withdraw":
            if state != "admitted":
                raise JudgmentError("Only an admitted revision can be withdrawn")
            self.append("withdrawn", self.config["owner"], record, reason)
        else:
            if record["version"] != self.record(jid)["version"] or state not in {"proposed", "needs_changes"}:
                raise JudgmentError("Review requires the latest pending revision")
            if decision not in {"admit", "reject", "request_changes"}:
                raise JudgmentError("Unknown review decision")
            if decision == "admit":
                # Source validation is a human review, not a structural-check claim.
                if record["judgment"]["rationale"] is None or record["provenance"]["origin"] == "unknown":
                    raise JudgmentError("Admission requires recorded rationale and known origin")
                for link in record["links"]:
                    if link["relation"] == "depends_on":
                        dep = self.record(link["id"], link["version"])
                        if self.state(dep) != "admitted" or digest(dep) != link["digest"]:
                            raise JudgmentError("Dependency must be admitted at the exact linked revision")
                for row in self.db.execute("SELECT body FROM revisions WHERE id=?", (jid,)).fetchall():
                    old = json.loads(row[0])
                    if self.state(old) == "admitted":
                        self.append("superseded", self.config["owner"], old, reason,
                                    {"by_version": version, "by_digest": expected_digest})
            kind = {"admit": "admitted", "reject": "rejected", "request_changes": "changes_requested"}[decision]
            self.append(kind, self.config["owner"], record, reason,
                        {"authority": "manual_owner", "policy_digest": digest(self.config)})
        return self.describe(record)

    def context(self, scope, facts, actor, purpose):
        validate_facts(facts)
        if not scope.strip() or not actor.strip() or not purpose.strip():
            raise JudgmentError("Scope, actor and purpose must be nonempty")
        selected, blocked = [], []
        for row in self.db.execute("SELECT body FROM revisions ORDER BY id,version"):
            record = json.loads(row[0])
            if record["applicability"]["scope"] != scope:
                continue
            reason = self.eligible(record, scope, facts)
            if reason:
                blocked.append({"id": record["id"], "version": record["version"], "reason": reason})
            else:
                selected.append(self.describe(record))
        receipt = {"schema_version": "judgment/context/v1", "receipt_id": "ctx_" + uuid.uuid4().hex,
                   "created_at": now(), "scope": scope, "facts": facts, "actor": actor, "purpose": purpose,
                   "policy_digest": digest(self.config),
                   "items": [{k: x[k] for k in ("id", "version", "digest")} for x in selected]}
        self.append("context_supplied", actor, data={"receipt": receipt})
        return {"receipt": receipt, "judgments": selected, "blocked": blocked,
                "boundary": "Supplied advice, not proof of use or permission to execute."}

    def check(self, receipt_id, facts):
        validate_facts(facts)
        receipt = next((e["data"]["receipt"] for e in self.events()
                        if e["kind"] == "context_supplied" and e["data"]["receipt"]["receipt_id"] == receipt_id), None)
        if receipt is None:
            raise JudgmentError("Receipt not found")
        reasons = []
        if not receipt["items"]:
            reasons.append("empty_context")
        if canonical(facts) != canonical(receipt["facts"]):
            reasons.append("facts_changed")
        if receipt["policy_digest"] != digest(self.config):
            reasons.append("policy_changed")
        for item in receipt["items"]:
            record = self.record(item["id"], item["version"])
            reason = self.eligible(record, receipt["scope"], facts)
            if reason or digest(record) != item["digest"]:
                reasons.append(item["id"] + ":" + (reason or "digest_changed"))
        return {"ok": not reasons, "receipt_id": receipt_id, "reasons": reasons,
                "boundary": "Fresh eligibility only; check and external action are not atomic."}

    def explain(self, jid):
        revisions = [self.describe(json.loads(row[0])) for row in self.db.execute(
            "SELECT body FROM revisions WHERE id=? ORDER BY version", (jid,))]
        if not revisions:
            raise JudgmentError("Judgment not found")
        history = []
        for e in self.events():
            if e.get("judgment_id") == jid or (e["kind"] == "context_supplied" and any(
                    x["id"] == jid for x in e["data"]["receipt"]["items"])):
                history.append(e)
        return {"revisions": revisions, "events": history}
