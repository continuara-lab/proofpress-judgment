"""Explicit task boundaries for cooperative workflow integrations.

Model calls occur at start and finish, never in action_check/check_release.
The caller must block actual delivery on check_release and supply complete artifacts.
"""
import json

from .assessment import assess
from .model import JudgmentError, digest, validate_facts

OPTIONS = {
    "pass": "All supplied judgments are satisfied, with sufficient supplied evidence.",
    "violation": "At least one supplied judgment is violated.",
    "unknown": "Applicability, compliance or evidence is insufficient or ambiguous.",
}


def latest(store, task_id, kind):
    return next((e for e in reversed(store.events())
                 if e["kind"] == kind and e["data"].get("task_id") == task_id), None)


def identity(task_id):
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise JudgmentError("task_id must be a nonempty string of at most 200 characters")


def items(store, scope, facts):
    selected = []
    for row in store.db.execute("SELECT body FROM revisions ORDER BY id,version"):
        record = json.loads(row[0])
        if record["applicability"]["scope"] == scope and not store.eligible(record, scope, facts):
            selected.append({"id": record["id"], "version": record["version"], "digest": digest(record)})
    return selected


def freshness(store, start, facts):
    data = start["data"]
    reasons = []
    for receipt in data.get("receipts", [data["receipt"]]):
        reasons.extend(store.check(receipt["receipt_id"], facts)["reasons"])
        if not data.get('behavior_task') and items(store, receipt["scope"], facts) != receipt["items"]:
            reasons.append("judgment_set_changed")
    if "prepare_id" in data:
        prepared = latest(store, data["task_id"], "task_prepared")
        if prepared is None or prepared["event_id"] != data["prepare_id"]:
            reasons.append("task_context_replaced")
        from .workflows import configuration
        policy = configuration(store, data["workflow_id"])
        if digest(policy) != data["workflow_digest"]:
            reasons.append('judgment_behavior_or_connection_changed' if data.get('behavior_task') else 'workflow_changed')
    if data["assessment"]["choice"] != "pass":
        reasons.append("task_start_not_passed")
    return {"ok": not reasons, "reasons": reasons}


def records(store, snapshot):
    return [store.record(x["id"], x["version"]) for x in snapshot]


def start_task(store, task_id, scope, facts, plan, actor="agent:task"):
    identity(task_id)
    validate_facts(facts)
    if not isinstance(plan, str) or not plan.strip():
        raise JudgmentError("A nonempty task plan is required")
    packet = store.context(scope, facts, actor, "Task start: " + task_id)
    receipt = packet["receipt"]
    # Empty/held context never becomes a vacuous semantic pass.
    assessment = {"choice": "unknown", "reason": "empty_or_held_context"}
    if receipt["items"] and not packet["holds"]:
        assessment = assess(
            {"stage": "task_start", "plan": plan, "facts": facts,
             "judgments": records(store, receipt["items"])},
            "Does this task plan concretely satisfy every supplied judgment, including conditions, "
            "exceptions and limits? A promise to comply without a sufficient plan is unknown.",
            OPTIONS)
    data = {"task_id": task_id, "scope": scope, "receipt": receipt,
            "plan": plan, "assessment": assessment}
    event = store.append("task_started", actor, data=data)
    return {"ok": assessment["choice"] == "pass", "task_id": task_id,
            "start_id": event["event_id"], "assessment": assessment,
            "judgments": packet["judgments"],
            "boundary": "Workflow must honor this result; no host lifecycle interception installed."}


def started(store, task_id):
    identity(task_id)
    event = latest(store, task_id, "task_started")
    if event is None:
        raise JudgmentError("Task has not started")
    return event


def artifacts(value):
    if (not isinstance(value, dict) or not value or
            any(not isinstance(k, str) or not k.strip() or not isinstance(v, str)
                for k, v in value.items())):
        raise JudgmentError("Artifacts must be a nonempty JSON object of names to full text content")
    return value


def finish_task(store, task_id, facts, outputs, evidence="", actor="agent:task"):
    outputs = artifacts(outputs)
    validate_facts(facts)
    if not isinstance(evidence, str):
        raise JudgmentError("Evidence must be text")
    start = started(store, task_id)
    fresh = freshness(store, start, facts)
    assessment = {"choice": "unknown", "reason": "task_context_stale"}
    if fresh["ok"]:
        data = start["data"]
        if data.get('behavior_task'):
            from .behavior import assess_stage
            assessment = assess_stage(records(store, data['items']), 'before_delivery',
                                      {'stage': 'task_finish', 'plan': data['plan'], 'facts': facts,
                                       'artifacts': outputs, 'evidence': evidence})
        else:
            assessment = assess(
                {"stage": "task_finish", "plan": data["plan"], "facts": facts,
                 "judgments": records(store, data.get("items", data["receipt"]["items"])),
                 "artifacts": outputs, "evidence": evidence},
                "Do the actual supplied artifacts satisfy every judgment and the task plan? "
                "Evaluate the artifacts and supporting evidence. Self-reported success is not proof. "
                "Return unknown when required context or evidence is missing.",
                OPTIONS)
    event = store.append("task_finished", actor, data={
        "task_id": task_id, "start_id": start["event_id"],
        "artifacts_digest": digest(outputs), "evidence_digest": digest(evidence),
        "artifact_digests": {name: digest(content) for name, content in outputs.items()},
        "assessment": assessment, "freshness": fresh})
    return {"ok": fresh["ok"] and assessment["choice"] == "pass",
            "task_id": task_id, "finish_id": event["event_id"],
            "artifacts_digest": digest(outputs), "assessment": assessment,
            "reasons": fresh["reasons"],
            "boundary": "Assessment covers only supplied artifacts; workflow must gate delivery."}


def check_release(store, task_id, facts, outputs):
    outputs = artifacts(outputs)
    validate_facts(facts)
    start = started(store, task_id)
    fresh = freshness(store, start, facts)
    reasons = list(fresh["reasons"])
    finish = latest(store, task_id, "task_finished")
    if finish is None:
        reasons.append("task_finish_missing")
    else:
        data = finish["data"]
        if data["start_id"] != start["event_id"]:
            reasons.append("task_restarted")
        if not data["freshness"]["ok"] or data["assessment"]["choice"] != "pass":
            reasons.append("task_finish_not_passed")
        if data["artifacts_digest"] != digest(outputs):
            reasons.append("artifacts_changed")
        action = latest(store, task_id, "task_action")
        if action and action["seq"] > finish["seq"]:
            reasons.append("action_after_finish")
        turn = latest(store, task_id, 'task_host_turn')
        if turn and turn['seq'] > finish['seq']:
            reasons.append('completion_turn_changed')
        paused = latest(store, task_id, 'task_host_paused')
        if paused and paused['seq'] > finish['seq']:
            reasons.append('completion_paused:' + paused['data']['reason'])
    if finish and "workflow_id" in start["data"] and "task_finish_not_passed" in reasons:
        exception = latest(store, task_id, "task_exception")
        if (exception and exception["data"]["finish_id"] == finish["event_id"]
                and exception["data"]["artifacts_digest"] == digest(outputs)
                and exception["data"]["start_id"] == start["event_id"]):
            reasons.remove("task_finish_not_passed")
    return {"ok": not reasons, "task_id": task_id, "reasons": reasons,
            "delivery_coverage": (finish['data']['assessment'].get('coverage', 'assessed') if finish else 'not_checked'),
            "artifacts_digest": digest(outputs),
            "boundary": "Caller must deliver these exact artifacts; external release is not atomic."}


def action_check(store, event, policy):
    # A host session is not automatically a task. Workflow adapters must attach
    # an explicit task id; raw host hooks fail closed until that bridge exists.
    task_id = event.get("proofpress_task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return {"ok": False, "reason": "Task-boundary binding requires an explicit proofpress_task_id"}
    try:
        start = started(store, task_id)
    except JudgmentError as exc:
        return {"ok": False, "reason": str(exc)}
    data = start["data"]
    expected = {"id": policy["judgment_id"], "version": policy["version"], "digest": policy["digest"]}
    if (policy["scope"] not in data.get("scopes", [data["scope"]])
            or expected not in data.get("items", data["receipt"]["items"])):
        return {"ok": False, "reason": "Task does not cover this bound judgment"}
    fresh = freshness(store, start, data["receipt"]["facts"])
    if not fresh["ok"]:
        return {"ok": False, "reason": "Task must restart: " + ", ".join(fresh["reasons"])}
    # Conservative invalidation: even a later host denial requires re-review.
    store.append("task_action", "system:runtime", data={
        "task_id": task_id, "start_id": start["event_id"], "event_digest": digest(event)})
    return {"ok": True, "reason": "Task start current; semantic output review deferred to finish"}
