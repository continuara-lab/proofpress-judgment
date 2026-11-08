"""Small terminal and agent projections. Full immutable records remain in the store."""
import json
import os
import sys

PALETTE = {"accent":"5FB3C4", "add":"6FBF8E", "del":"C87E82", "move":"D7B56D", "dim":"ADB0BA"}


def color(role, text):
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return str(text)
    h = PALETTE[role]
    rgb = ";".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))
    return f"\x1b[1;38;2;{rgb}m{text}\x1b[0m"


def status(value):
    role = "add" if value in {"admitted", "completed"} else "del" if value in {"withdrawn", "rejected", "failed"} else "move"
    return color(role, value)


def scalar(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def applicability(app):
    lines = ["Scope  " + app["scope"]]
    lines += ["When   " + c["field"] + " = " + scalar(c["equals"]) for c in app["when"]]
    lines += ["Limit  " + x for x in app["limits"]]
    lines += [key.replace("_", " ").title() + "  " + app[key] for key in ("valid_from", "valid_until") if key in app]
    return lines


def record_lines(item, detailed=False, identity=True):
    r = item["record"]
    lines = [f"{status(item['state'])}  {item['name']} v{item['version']}", r["judgment"]["statement"]]
    if r["judgment"].get("assertion"):
        a = r["judgment"]["assertion"]
        lines.append("Assertion  " + a["key"] + " = " + scalar(a["value"]))
    if detailed:
        if r.get("description") and r["description"] != r["judgment"]["statement"]:
            lines.append("About  " + r["description"])
        if r.get("context"):
            lines.append("Situation  " + r["context"]["situation"])
            if r["context"].get("goal"): lines.append("Goal  " + r["context"]["goal"])
            lines += ["Constraint  " + x for x in r["context"].get("constraints",[])]
            if r["context"].get("facts"): lines.append("Background facts  " + scalar(r["context"]["facts"]))
        for alternative in r.get("alternatives",[]):
            lines.append("Alternative  " + alternative["option"] + " · " + (alternative["reason_not_chosen"] or "Reason unknown"))
        if r.get("expected_outcome"):
            lines.append("Expected  " + r["expected_outcome"]["description"])
            if r["expected_outcome"].get("verification"): lines.append("Verify  " + r["expected_outcome"]["verification"])
        if r["judgment"].get("polarity"): lines.append("Polarity  " + r["judgment"]["polarity"])
        lines += ["Kind   " + r["judgment"]["kind"], "Why    " + (r["judgment"]["rationale"] or "Not recorded")]
        lines += applicability(r["applicability"])
        p = r["provenance"]
        lines += ["Origin " + p["origin"], "By     " + p.get("judged_by", p.get("decision_maker", "Not recorded")),
                  "Recorded  " + p["recorded_by"] + " · " + p["recorded_at"] + " · " + p["capture_method"]]
        lines += ["Source " + ref for ref in p["source_refs"]]
        for e in r["evidence"]:
            lines.append("Evidence " + e["role"] + " · " + e["reference"] + (" · " + e["summary"] if e.get("summary") else ""))
        for link in r["links"]:
            lines.append(f"Link   {link['relation']} {link['id']} v{link['version']} {link['digest']}")
        if r.get("extensions"):
            lines.append("Source metadata: available with --json")
    if item.get("flags"):
        lines.append("Paused · conflicting or uncertain judgment; inspect --json")
    if identity:
        lines += ["ID     " + item["id"], "Digest " + item["digest"]]
    return lines


def agent_projection(command, result):
    if command == "context":
        return {"receipt_id":result["receipt"]["receipt_id"],
                "judgments":[{**{k:x[k] for k in ("id","version","name")},
                              "judgment":x["record"]["judgment"],
                              "applicability":x["record"]["applicability"],
                              **{k:x["record"][k] for k in ("context","alternatives","expected_outcome") if k in x["record"]}} for x in result["judgments"]],
                "boundary":result["boundary"], "holds":result.get("holds",[])}
    if isinstance(result, dict) and "record" in result:
        return {**{k:result[k] for k in ("id","version","name","state","digest")}, "flags":result.get("flags",[])}
    if command == "inbox":
        return {"judgments":[agent_projection("show", x) for x in result["judgments"]]}
    return result


def render_text(command, result):
    if "record" in result:
        return "\n".join(record_lines(result, detailed=command == "show"))
    if command == "context":
        lines = [f"Context  {len(result['judgments'])} applicable judgments", "Receipt  " + result["receipt"]["receipt_id"],
                 "Advice only; not action authorization."]
        if result.get("holds"):
            lines.append("Paused · conflicting or uncertain judgments; resolve before reuse")
        for item in result["judgments"]:
            lines += record_lines(item, identity=False)
            lines += ["Why    " + (item["record"]["judgment"]["rationale"] or "Not recorded")]
            if item["record"].get("context"): lines.append("Situation  " + item["record"]["context"]["situation"])
            if item["record"].get("expected_outcome"): lines.append("Expected  " + item["record"]["expected_outcome"]["description"])
            lines += applicability(item["record"]["applicability"])
        return "\n".join(lines)
    if command == "inbox":
        return "\n".join(f"{status(x['state'])}  {x['name']} v{x['version']}  {x['id']}" for x in result['judgments']) or "No pending judgments."
    if command == "onboard":
        p=result['capture_policy']
        return "\n".join(["Proofpress · "+result['status'],"Project  "+result['project'],"Capture  "+", ".join(p['triggers']),
                          "Review   manual", "History  "+p["history"], "Hooks    not installed",
                          "Enabled" if result['status']=='enabled' else "Next  Repeat with --owner human:NAME --confirm to enable"])
    if command == "capture-policy":
        p=result['capture_policy']
        return "\n".join(["Capture  "+", ".join(p['triggers']),"Extraction  "+p['extraction'],"Review  manual","History  "+p["history"]])
    if command == "history" and "sessions" in result:
        return "\n".join(x["session_id"]+"  "+x["path"] for x in result["sessions"]) or "No matching sessions."
    if command == "history":
        return "History · "+str(result['messages'])+" messages · "+str(result['pending_bytes'])+" bytes pending"+ (" · local import" if result.get('ok') else " · preview only")
    if command == "consolidate":
        return ("Pending  "+str(result['pending_batches'])+" batches · add --model-assessment to extract candidates") if 'pending_batches' in result else ("Captured  "+str(len(result['candidates']))+" candidates · manual review required")
    if command == "observe":
        return "Observation recorded · "+result['event_id']
    if command == "observations":
        return "\n".join(e['data']['observation']['kind']+" · "+e['data']['observation']['result']+" · "+e['data']['observation']['summary'] for e in result['observations']) or "No observations."
    if command == "review-assist":
        return "Review assistance · "+result['assessment']['choice']+" · "+str(len(result['flags']))+" flags · manual admission required"
    if command == "assess":
        return "No conflict flagged · candidate still needs review" if result["ok"] else "Paused · conflicting or uncertain judgment; inspect --json"
    if command == "bind":
        return "Runtime binding saved · install the host hook separately"
    if command == "check":
        return "Eligible · advice only" if result["ok"] else "Ineligible · " + "; ".join(result["reasons"])
    if command == "audit":
        return f"Verified · {result['revisions']} revisions · {result['events']} events"
    if command == "validate":
        return "Valid AJF · shape only; not admitted"
    if command == "explain":
        lines = [f"{status(x['state'])}  {x['name']} v{x['version']}" for x in result['revisions']]
        lines += [f"{e['kind']} · {e['actor']}" + (" · " + e["reason"] if e.get("reason") else "") for e in result['events']]
        return "\n".join(lines)
    if command == "policy":
        return "\n".join(["Admission  manual", "Owner  " + result["owner"], *result["capture"]["guidance"]])
    if command == "init":
        return "Workspace ready · manual admission"
    return scalar(result)
