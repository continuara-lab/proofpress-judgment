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
            capture = r['extensions'].get('proofpress_capture',{})
            if capture.get('trigger'): lines.append('Captured  '+capture['trigger'].replace('_',' '))
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
    if 'review_result' in result: return result['review_result']
    if result.get('host_setup'):
        action = 'Removed' if result.get('removed') else 'Installed'
        return '\n'.join([color('accent','Proofpress · Hooks'), color('accent','Host')+'  '+result['host'], color('accent','Config')+'  '+result['path'], (action if result['confirmed'] else 'Preview only; repeat with --confirm to change host configuration.'), result['trust'], *(['Command  '+result['command']] if not result['confirmed'] and 'command' in result else [])])
    if result.get('doctor'):
        lines=[color('accent','Proofpress · Doctor'), color('accent','Project')+'  '+result['project'], color('accent','Store')+'  '+result['workspace'], color('accent','Skills')+'  '+(', '.join(result['skills']) or 'None; run proofpress onboard'), color('accent','Enforcement')+'  '+('Paused by owner' if result['paused'] else 'Enabled for configured bindings')]
        for host in result['hosts']:
            lines += ['Hook  '+host['host']+' · '+('configured' if host['configured'] else 'missing or changed; reinstall'), 'Trust  '+host['trust']]
        if not result['hosts']: lines += ['Hook  Not installed; preview with proofpress hooks install']
        for b in result['bindings']: lines += ['Binding  '+b['name']+' v'+str(b['version'])+' · '+b['state']+' · '+', '.join(b['paths'])]
        if not result['bindings']: lines += ['Bindings  None; review a judgment and choose enforcement.']
        last=result['last_check']
        lines += ['Observed  '+(last['at']+' · '+('passed' if last['ok'] else 'blocked')+' · '+last['reason'] if last else 'No runtime check recorded; host execution is not verified.')]
        return '\n'.join(lines)
    if 'matches' in result:
        return '\n'.join([color('accent','Proofpress · Applicability'), *[x['name']+' v'+str(x['version'])+' · '+x['reason'] for x in result['matches']]])
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
        p = result['capture_policy']
        triggers = p['triggers']
        labels = {'human_judgment':'your judgments', 'human_correction':'your corrections', 'agent_judgment':'agent judgments', 'task_end':'task-end lessons'}
        capture = ', '.join(labels[x] for x in triggers) if triggers else 'off'
        history = 'Import a project’s past Codex sessions when you choose.' if p['history'] == 'selected_only' else 'Disabled.'
        lines = [color('accent', 'Proofpress · ' + ('Setup' if result['status'] == 'preview' else 'Ready')),
                 color('accent', 'Project') + '  ' + result['project'],
                 color('accent', 'Capture policy') + '  What your agent may save as a proposed judgment.',
                 color('accent', 'Capture') + '  ' + capture + '.',
                 '         Keep useful choices, reasons and conditions; skip routine messages.',
                 '         Agent guidance; no automatic listener is installed.',
                 color('accent', 'Review') + '   You approve judgments before reuse.',
                 color('accent', 'History') + '  ' + history,
                 color('accent', 'Hooks') + '    Setup does not install hooks. Check status with proofpress doctor.',
                 color('accent', 'Change') + '   Run proofpress configure anytime.']
        if result['status'] == 'preview' and not (sys.stdin.isatty() and sys.stdout.isatty()):
            lines.append('To enable: repeat with --owner human:NAME --confirm.')
        return "\n".join(lines)
    if command == "capture-policy":
        p=result['capture_policy']
        labels={'human_judgment':'your judgments','human_correction':'your corrections','agent_judgment':'agent judgments','task_end':'task-end lessons'}
        return '\n'.join([color('accent','Capture policy')+'  What your agent may propose for review.',color('accent','Capture')+'  '+(', '.join(labels[x] for x in p['triggers']) or 'Off'),color('accent','Review')+'   You approve before reuse.',color('accent','History')+'  '+('Selected projects only' if p['history']=='selected_only' else 'Off'),color('accent','Change')+'   proofpress configure'])
    if command == "history" and result.get('project_history'):
        lines = [color('accent', 'Proofpress · Project history'),
                 color('accent','Project')+'  ' + result['project'],
                 color('accent','History')+'  ' + str(result['sessions']) + ' Codex sessions · modified in last ' + str(result['days']) + ' days']
        if result['imported']:
            lines.append('Imported  ' + str(result['messages']) + ' messages locally · ' + str(result['pending_bytes']) + ' bytes pending')
            if result['errors']:
                lines.append(color('move','Needs attention')+'  ' + str(len(result['errors'])) + ' sessions; other imports are preserved')
                lines += ['  '+x['source_key']+' · '+x['reason'] for x in result['errors']]
            lines.append('Next  Extract candidates separately; nothing has been approved.')
        else:
            lines.append('Import  Redacted excerpts stored locally; no model call or approval.')
            lines.append('Note  Redaction may not catch every sensitive detail.')
        return '\n'.join(lines)
    if command == "history" and "sessions" in result:
        from datetime import datetime
        if not result['sessions']: return "No matching sessions."
        lines=[color('accent','Codex sessions')+' · '+str(len(result['sessions']))+' sources']
        for x in result['sessions']:
            date=datetime.fromtimestamp(x['modified_at']).strftime('%b %d')
            title=x['title']
            if title.startswith('# Files mentioned by the user:'):
                title='Untitled session'
            if title=='Untitled session':
                title = 'First message: '+x['preview'] if x.get('preview') else 'Untitled session · '+x['session_id'][:8]
            if len(title)>72:title=title[:71]+'…'
            lines.append(color('accent',x['source_key'])+'  '+date+'  '+title)
        lines.append('Preview: history preview --project PROJECT --session KEY')
        return "\n".join(lines)
    if command == "history":
        return "History · "+str(result['messages'])+" messages · "+str(result['pending_bytes'])+" bytes pending"+ (" · local import" if result.get('ok') else " · preview only")
    if command == "consolidate":
        return ("Pending  "+str(result['pending_batches'])+" batches · add --model-assessment to send excerpts to Codex and extract candidates") if 'pending_batches' in result else ("Captured  "+str(len(result['candidates']))+" candidates · manual review required\nRemaining  "+str(result['remaining_batches'])+" batches\nNext  proofpress inbox, then proofpress review ID")
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
