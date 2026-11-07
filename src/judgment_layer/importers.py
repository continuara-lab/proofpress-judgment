"""Bounded TRACE bridge: source disposition never becomes local admission."""
import json
from urllib.parse import quote

from .model import JudgmentError, canonical, digest, now


def from_trace(session, event_id, template, recorder):
    if not isinstance(session, dict) or session.get("trace_version") not in {"0.5.0", "0.5.1"}:
        raise JudgmentError("TRACE importer supports explicit 0.5.0/0.5.1 session exports only")
    if not isinstance(session.get("id"), str) or not session["id"].strip():
        raise JudgmentError("TRACE session ID required")
    events = session.get("events")
    if not isinstance(events, list):
        raise JudgmentError("TRACE events must be an array")
    matches = [e for e in events if isinstance(e, dict) and e.get("id") == event_id]
    if len(matches) != 1:
        raise JudgmentError("Select exactly one TRACE event")
    event = matches[0]
    if event.get("type") != "decision" or event.get("session_id") != session["id"]:
        raise JudgmentError("Selected event must be a decision belonging to this session")
    decision = event.get("decision")
    if not isinstance(decision, dict) or not isinstance(decision.get("description"), str) or not decision["description"].strip():
        raise JudgmentError("TRACE decision description required")
    proposer = decision.get("proposed_by")
    if not isinstance(proposer, dict) or proposer.get("type") not in {"human", "ai"} or not isinstance(proposer.get("id"), str) or not proposer["id"].strip():
        raise JudgmentError("TRACE proposed_by must explicitly identify a human or AI proposer")
    if not isinstance(recorder, str) or not recorder.strip():
        raise JudgmentError("Importer recorder identity required")
    if not isinstance(template, dict) or set(template) != {"name", "description", "kind", "applicability", "evidence"}:
        raise JudgmentError("Template requires only name, description, kind, applicability and evidence")
    result = json.loads(canonical(template))
    kind = result.pop("kind")
    result["judgment"] = {"statement": decision["description"], "kind": kind,
                          "rationale": decision.get("rationale") or None}
    result["provenance"] = {
        "origin": "human_judgment" if proposer["type"] == "human" else "agent_judgment",
        "decision_maker": proposer["id"], "recorded_by": recorder, "recorded_at": now(),
        "capture_method": "imported",
        "source_refs": ["trace://" + quote(session["id"], safe="") + "/event/" + quote(event_id, safe="")]
    }
    result["extensions"] = {"trace": {
        "trace_version": session["trace_version"], "session_id": session["id"], "event_id": event_id,
        "session_digest": digest(session), "event_digest": digest(event),
        "historical_disposition": decision.get("disposition"),
        "original_timestamp": event.get("timestamp"), "resolved_by": decision.get("resolved_by"),
        "boundary": "Imported provenance only; no authenticated identity or local admission."
    }}
    return result
