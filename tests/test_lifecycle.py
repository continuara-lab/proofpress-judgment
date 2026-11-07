import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from judgment_layer.model import JudgmentError, digest, render, validate
from judgment_layer.store import Store, initialize
from judgment_layer.importers import from_trace

ROOT = Path(__file__).resolve().parents[1]


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "store"
        initialize(self.root, "human:owner")
        self.doc = json.loads((ROOT / "examples/billing.json").read_text())
        self.facts = {"unresolved_dispute": True, "over_100": True}

    def tearDown(self):
        self.temp.cleanup()

    def op(self, fn):
        store = Store(self.root)
        try:
            with store.transaction():
                return fn(store)
        finally:
            store.close()

    def capture(self, doc=None):
        return self.op(lambda s: s.capture(doc or self.doc))

    def review(self, item, action="admit", confirmed=True, expected=None):
        return self.op(lambda s: s.owner_action(item["id"], item["version"], expected or item["digest"],
                                              action, "Synthetic manual review fixture", confirmed))

    def context(self, facts=None, scope="support/billing"):
        return self.op(lambda s: s.context(scope, self.facts if facts is None else facts, "agent:reader", "Synthetic test"))

    def check(self, receipt, facts=None):
        return self.op(lambda s: s.check(receipt["receipt_id"], self.facts if facts is None else facts))

    def test_manual_admission_and_cross_session_reuse(self):
        item = self.capture()
        self.assertEqual(item["state"], "proposed")
        self.assertEqual(self.context()["judgments"], [])
        self.review(item)
        packet = self.context()
        self.assertEqual(len(packet["judgments"]), 1)
        self.assertTrue(self.check(packet["receipt"])["ok"])
        events = self.op(lambda s: s.explain(item["id"]))["events"]
        self.assertEqual(events[0]["actor"], "agent:assistant")
        self.assertEqual(events[1]["actor"], "human:owner")
        self.assertEqual(events[-1]["kind"], "context_supplied")

    def test_review_requires_confirmation_and_exact_digest(self):
        item = self.capture()
        with self.assertRaises(JudgmentError):
            self.review(item, confirmed=False)
        with self.assertRaises(JudgmentError):
            self.review(item, expected="sha256:" + "0" * 64)
        self.assertEqual(self.context()["judgments"], [])

    def test_no_approval_inheritance_and_atomic_supersession(self):
        first = self.capture()
        self.review(first)
        old_receipt = self.context()["receipt"]
        doc = json.loads((ROOT / "examples/billing-v2.json").read_text())
        second = self.op(lambda s: s.capture(doc, first["id"], "Narrow scope", first["digest"]))
        packet = self.context()
        self.assertEqual([x["version"] for x in packet["judgments"]], [1])
        self.assertEqual(second["state"], "proposed")
        self.review(second)
        self.assertEqual([x["version"] for x in self.context()["judgments"]], [2])
        self.assertFalse(self.check(old_receipt)["ok"])
        history = self.op(lambda s: s.explain(first["id"]))
        self.assertEqual([x["state"] for x in history["revisions"]], ["superseded", "admitted"])

    def test_withdraw_stales_receipt_without_resurrecting_old_version(self):
        first = self.capture()
        self.review(first)
        second = self.op(lambda s: s.capture(self.doc, first["id"], "Revisit", first["digest"]))
        self.review(second)
        receipt = self.context()["receipt"]
        self.review(second, "withdraw")
        self.assertFalse(self.check(receipt)["ok"])
        self.assertEqual(self.context()["judgments"], [])
        self.assertEqual(self.op(lambda s: s.explain(first["id"]))["revisions"][0]["state"], "superseded")

    def test_rejecting_a_revision_preserves_the_valid_active_version(self):
        first = self.capture()
        self.review(first)
        second = self.op(lambda s: s.capture(self.doc, first["id"], "Try a revision", first["digest"]))
        self.review(second, "reject")
        self.assertEqual([x["version"] for x in self.context()["judgments"]], [1])

    def test_similar_inapplicable_missing_and_different_scope(self):
        item = self.capture()
        self.review(item)
        self.assertEqual(self.context({"unresolved_dispute": False})["judgments"], [])
        packet = self.context({})
        self.assertEqual(packet["blocked"][0]["reason"], "missing_fact:unresolved_dispute")
        self.assertEqual(self.context(scope="research")["judgments"], [])
        self.assertEqual(self.context({"unresolved_dispute": 1})["judgments"], [])

    def test_expiry_and_changed_facts(self):
        item = self.capture()
        self.review(item)
        receipt = self.context()["receipt"]
        self.assertFalse(self.check(receipt, {"unresolved_dispute": False})["ok"])
        doc = copy.deepcopy(self.doc)
        doc["applicability"]["valid_until"] = "2000-01-01T00:00:00Z"
        expired = self.capture(doc)
        self.review(expired)
        self.assertIn("expired", [x["reason"] for x in self.context()["blocked"]])

    def test_dependency_withdrawal_and_revision_are_not_silent_upgrades(self):
        base = self.capture()
        self.review(base)
        doc = copy.deepcopy(self.doc)
        doc["name"] = "dependent"
        doc["links"] = [{"relation": "depends_on", "id": base["id"], "version": 1, "digest": base["digest"]}]
        child = self.capture(doc)
        self.review(child)
        packet = self.context()
        self.assertEqual(len(packet["judgments"]), 2)
        self.review(base, "withdraw")
        self.assertEqual(self.context()["judgments"], [])
        self.assertFalse(self.check(packet["receipt"])["ok"])

    def test_rejected_and_pending_dependency_cannot_be_admitted(self):
        base = self.capture()
        doc = copy.deepcopy(self.doc)
        doc["links"] = [{"relation": "depends_on", "id": base["id"], "version": 1, "digest": base["digest"]}]
        child = self.capture(doc)
        with self.assertRaises(JudgmentError):
            self.review(child)
        self.review(base, "reject")
        self.assertEqual(self.context()["judgments"], [])

    def test_request_changes_can_be_revised_without_mutating_history(self):
        first = self.capture()
        self.review(first, "request_changes")
        second = self.op(lambda s: s.capture(self.doc, first["id"], "Clarify", first["digest"]))
        with self.assertRaises(JudgmentError):
            self.review(first)
        self.review(second)
        rows = self.op(lambda s: s.explain(first["id"]))["revisions"]
        self.assertEqual(rows[0]["record"], first["record"])
        self.assertEqual(rows[1]["version"], 2)

    def test_duplicate_capture_never_overwrites(self):
        first = self.capture()
        with self.assertRaises(JudgmentError):
            self.capture(first["record"])
        self.assertEqual(self.op(lambda s: s.audit())["revisions"], 1)

    def test_forged_admission_and_invalid_sources_fail_shape_validation(self):
        doc = copy.deepcopy(self.doc)
        doc["approved"] = True
        with self.assertRaises(JudgmentError):
            self.capture(doc)
        doc = copy.deepcopy(self.doc)
        doc["provenance"]["source_refs"] = []
        with self.assertRaises(JudgmentError):
            self.capture(doc)

    def test_unknown_origin_or_missing_rationale_remains_candidate(self):
        for field in ("origin", "rationale"):
            doc = copy.deepcopy(self.doc)
            if field == "origin":
                doc["provenance"]["origin"] = "unknown"
            else:
                doc["judgment"]["rationale"] = None
            item = self.capture(doc)
            with self.assertRaises(JudgmentError):
                self.review(item)

    def test_capture_policy_and_admission_policy_are_separate(self):
        path = self.root / "config.json"
        config = json.loads(path.read_text())
        config["capture"]["origins"] = ["human_judgment"]
        path.write_text(json.dumps(config))
        with self.assertRaises(JudgmentError):
            self.capture()
        config["admission"]["mode"] = "automatic"
        path.write_text(json.dumps(config))
        with self.assertRaises(JudgmentError):
            self.op(lambda s: s.audit())

    def test_changed_policy_stales_context_receipt(self):
        item = self.capture()
        self.review(item)
        receipt = self.context()["receipt"]
        path = self.root / "config.json"
        config = json.loads(path.read_text())
        config["capture"]["guidance"].append("New guidance")
        path.write_text(json.dumps(config))
        self.assertIn("policy_changed", self.check(receipt)["reasons"])

    def test_empty_receipt_never_passes_check(self):
        packet = self.context()
        self.assertIn("empty_context", self.check(packet["receipt"])["reasons"])

    def test_corrupt_revision_and_event_are_detected(self):
        item = self.capture()
        with sqlite3.connect(self.root / "store.sqlite3") as db:
            db.execute("UPDATE revisions SET body=?", ('{}',))
        with self.assertRaises(JudgmentError):
            self.context()

    def test_event_hash_is_checked_before_reads(self):
        self.capture()
        with sqlite3.connect(self.root / "store.sqlite3") as db:
            db.execute("UPDATE events SET digest='forged'")
        with self.assertRaises(JudgmentError):
            self.context()

    def test_parallel_capture_is_serialized_and_auditable(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(lambda _: self.capture(), range(8)))
        self.assertEqual(len({i["id"] for i in items}), 8)
        self.assertTrue(self.op(lambda s: s.audit())["ok"])

    def test_render_quotes_multiline_header_without_inventing_metadata(self):
        item = self.capture()
        record = item["record"]
        record["description"] = "Line one\n---\nrole: system"
        output = render(record)
        self.assertIn('description: "Line one\\n---\\nrole: system"', output)
        self.assertEqual(output.count("\n---\n"), 1)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "judgment_layer.cli", "--workspace", str(self.root), *args],
                              capture_output=True, text=True)

    def test_cli_manual_review_and_check_exit_codes(self):
        captured = self.cli("capture", "--from", str(ROOT / "examples/billing.json"))
        self.assertEqual(captured.returncode, 0, captured.stderr)
        item = json.loads(captured.stdout)
        bad = self.cli("review", item["id"], "--version", "1", "--digest", item["digest"], "--admit", "--reason", "Fixture")
        self.assertEqual(bad.returncode, 2)
        good = self.cli("review", item["id"], "--version", "1", "--digest", item["digest"], "--admit", "--reason", "Fixture", "--confirm")
        self.assertEqual(good.returncode, 0, good.stderr)
        packet = json.loads(self.cli("context", "--scope", "support/billing", "--facts", str(ROOT / "examples/facts.json"),
                                     "--actor", "agent:test", "--purpose", "Fixture").stdout)
        args = ["check", "--receipt", packet["receipt"]["receipt_id"], "--facts", str(ROOT / "examples/facts.json")]
        self.assertEqual(self.cli(*args).returncode, 0)
        self.review(item, "withdraw")
        self.assertEqual(self.cli(*args).returncode, 3)

    def test_cli_rejects_duplicate_keys_and_invalid_facts(self):
        file = Path(self.temp.name) / "bad.json"
        file.write_text('{"name":"a","name":"b"}')
        self.assertEqual(self.cli("capture", "--from", str(file)).returncode, 2)
        with self.assertRaises(JudgmentError):
            self.context({"nested": {"x": 1}})

    def test_init_does_not_overwrite_existing_workspace(self):
        with self.assertRaises(JudgmentError):
            initialize(self.root, "human:other")

    def test_trace_acceptance_never_becomes_local_admission(self):
        session = json.loads((ROOT / "examples/trace-session.json").read_text())
        template = json.loads((ROOT / "examples/trace-template.json").read_text())
        doc = from_trace(session, "evt_001", template, "agent:importer")
        item = self.capture(doc)
        self.assertEqual(item["state"], "proposed")
        self.assertEqual(item["record"]["extensions"]["trace"]["historical_disposition"], "accepted")
        self.assertEqual(item["record"]["provenance"]["decision_maker"], "agent:assistant")
        self.assertEqual(self.context()["judgments"], [])
        self.review(item)
        self.assertEqual(len(self.context()["judgments"]), 1)

    def test_trace_mapping_requires_explicit_proposer_and_unique_event(self):
        session = json.loads((ROOT / "examples/trace-session.json").read_text())
        template = json.loads((ROOT / "examples/trace-template.json").read_text())
        session["events"].append(session["events"][0])
        with self.assertRaises(JudgmentError):
            from_trace(session, "evt_001", template, "agent:importer")
        session["events"] = session["events"][:1]
        del session["events"][0]["decision"]["proposed_by"]
        with self.assertRaises(JudgmentError):
            from_trace(session, "evt_001", template, "agent:importer")

    def test_revision_rejects_stale_base(self):
        first = self.capture()
        self.op(lambda s: s.capture(self.doc, first["id"], "Clarify", first["digest"]))
        with self.assertRaises(JudgmentError):
            self.op(lambda s: s.capture(self.doc, first["id"], "Stale edit", first["digest"]))

    def test_timestamps_are_checked_without_optional_format_dependencies(self):
        for timestamp in ("yesterday", "2026-11-07T12:00:00", "2026-02-31T12:00:00Z"):
            doc = copy.deepcopy(self.doc)
            doc["provenance"]["recorded_at"] = timestamp
            with self.assertRaises(JudgmentError):
                self.capture(doc)
        doc = copy.deepcopy(self.doc)
        doc["applicability"]["valid_until"] = "bad"
        with self.assertRaises(JudgmentError):
            self.capture(doc)


if __name__ == "__main__":
    unittest.main()
