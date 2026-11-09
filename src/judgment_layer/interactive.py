"""Human terminal workflows. Preview exact revisions before atomic owner actions."""
import copy
import json
import os
import shlex
import subprocess
import tempfile
import tomllib
from pathlib import Path
from .model import JudgmentError, digest
from .store import Store
from .presentation import color, review_advice_text, status


def edit_document(record):
    """Edit a small TOML form; retain provenance and immutable revision metadata."""
    q = lambda x: json.dumps(x, ensure_ascii=False)
    j = record['judgment']; app = record['applicability']
    lines = ['# Save and close to preview a new candidate. Leave unchanged to cancel.',
             'name = '+q(record['name']), 'statement = '+q(j['statement']),
             'why = '+q(j['rationale'] or ''), 'scope = '+q(app['scope']),
             '# Conditions: a JSON list of {"field": "...", "equals": value}. Missing facts exclude reuse.',
             'conditions = '+q(json.dumps(app['when'], ensure_ascii=False)),
             'limits = '+q(app['limits']), 'situation = '+q(record.get('context', {}).get('situation', '')),
             'goal = '+q(record.get('context', {}).get('goal', '')),
             'constraints = '+q(record.get('context', {}).get('constraints', [])),
             'expected_outcome = '+q(record.get('expected_outcome', {}).get('description', '')),
             'verification = '+q(record.get('expected_outcome', {}).get('verification', ''))]
    original = '\n'.join(lines)+'\n'
    with tempfile.TemporaryDirectory(prefix='proofpress-edit-') as folder:
        path = Path(folder)/'judgment.toml'; path.write_text(original)
        command = shlex.split(os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'vi')
        if not command: raise JudgmentError('Set EDITOR to your preferred editor')
        if subprocess.run([*command, str(path)]).returncode: raise JudgmentError('Editor failed; no candidate created')
        if path.read_text() == original: return None
        fields = tomllib.loads(path.read_text())
    required = {'name', 'statement', 'why', 'scope', 'conditions', 'limits', 'situation', 'goal', 'constraints', 'expected_outcome', 'verification'}
    if set(fields) != required: raise JudgmentError('Keep the named editor fields; no candidate created')
    doc = copy.deepcopy(record)
    doc.pop('id'); doc.pop('version')
    doc['name'] = fields['name']; doc['judgment'].update(statement=fields['statement'], rationale=fields['why'] or None)
    doc['applicability'].update(scope=fields['scope'], when=json.loads(fields['conditions']), limits=fields['limits'])
    if fields['situation']:
        doc['ajf_version'] = '0.3-draft'
        doc.setdefault('context', {})['situation'] = fields['situation']
        for name in ('goal','constraints'):
            if fields[name]:doc['context'][name]=fields[name]
            else:doc['context'].pop(name,None)
    elif doc.get('context'): doc.pop('context')
    if fields['expected_outcome']:
        doc['ajf_version']='0.3-draft'
        doc['expected_outcome']={'description':fields['expected_outcome']}
        if fields['verification']:doc['expected_outcome']['verification']=fields['verification']
    else:doc.pop('expected_outcome',None)
    return doc


def revise_in_editor(workspace, jid):
    s = Store(workspace)
    try:
        with s.transaction(): base = s.record(jid); base_hash = digest(base)
    finally: s.close()
    doc = edit_document(base)
    if doc is None: return None
    s = Store(workspace)
    try:
        from .review_policy import review_assist
        with s.transaction():
            item = s.capture(doc, jid, 'Edited in Proofpress CLI', base_hash)
        advice = review_assist(s, jid, item["digest"], automatic=True)
        if advice is not None:
            item["review_advice"] = advice
        return item
    finally: s.close()


def review_preview(item, enforcement):
    r = item['record']; app = r['applicability']; lines = [color('accent', 'Proofpress · Review')+'  '+status(item['state'])+f"  v{item['version']}",
        color('accent', 'Judgment'), '  '+r['judgment']['statement'], color('accent', 'Why'), '  '+(r['judgment']['rationale'] or 'Not recorded')]
    if r.get('context'): lines += [color('accent', 'Situation'), '  '+r['context']['situation']]
    lines += [color('accent', 'Applies'), '  Scope: '+app['scope']]
    lines += ['  '+c['field']+' = '+json.dumps(c['equals'], ensure_ascii=False) for c in app['when']]
    if not app['when']: lines += ['  No factual conditions recorded. Review whether this scope is narrow enough.']
    lines += ['  Limit: '+x for x in app['limits']]
    lines += [color('accent', 'Source')]+['  '+x for x in r['provenance']['source_refs']]
    if 'deterministic_issues' in item:
        lines += [color('accent', 'Admission checks'), '  ' + (' '.join(item['deterministic_issues']) or 'Local checks passed.')]
        lines += [color('accent', 'Review criteria'), '  ' + item['review_criteria']]
        lines += [color('accent', 'Model advice'), '  ' + review_advice_text(item.get('review_advice'))]
        advice = item.get('review_advice') or {}
        assessment = advice.get('assessment', {})
        probabilities = assessment.get('probabilities', {})
        if probabilities:
            labels = {'supported': 'Evidence supported', 'unknown': 'Needs human judgment',
                      'scope_too_broad': 'Scope too broad', 'unsupported_evidence': 'Evidence unsupported',
                      'criteria_unmet': 'Criteria unmet'}
            choice = max(probabilities, key=probabilities.get)
            lines += ['  Highest model choice: ' + labels.get(choice, choice) + f" ({probabilities[choice]:.0%}).",
                      f"  Model confidence: {assessment['confidence']:.0%}. Thresholds: 95% choice, 90% confidence.",
                      '  This check returns a choice and scores; no written explanation was requested.']
        lines += [color('accent', 'Approval'), '  You decide whether to approve this revision.']
    lines += [color('accent', 'Proposed enforcement')]
    if enforcement:
        descriptions = {'deny_generated_write': 'Block direct edits to these generated paths.', 'require_conditions': 'Check lifecycle and factual conditions only; does not judge output.', 'decision_model_output': 'Send complete new-file content and this judgment to the configured decision model; violations, uncertainty and provider errors pause writes.'}
        lines += ['  '+color('accent', 'Hook')+'   Before tool use in '+enforcement['project_root'],
                  '  '+color('accent', 'Paths')+'  '+', '.join(enforcement['paths']),
                  '  '+color('accent', 'Check')+'  '+descriptions[enforcement['verifier']],
                  '  Shell, MCP and unsupported tool routes pause while bindings are active.',
                  '  Host installation and trust are required; run proofpress doctor.']
    else: lines += ['  Advice only. No enforcement binding will be created.']
    if item.get('flags'): lines += [color('del', 'Paused: conflicting or uncertain judgment. Resolve before approval.')]
    return '\n'.join(lines)


def interactive_review(workspace, jid, enforcement=None, input_fn=input):
    from .review_policy import DEFAULT_CRITERIA, admission_issues, current_advice, review_assist, review_policy
    while True:
        s = Store(workspace)
        try:
            with s.transaction():
                item = s.describe(s.record(jid))
                item["deterministic_issues"] = admission_issues(s, item["record"])
                item["review_advice"] = current_advice(s, item["record"])
                item["review_criteria"] = review_policy(s)["criteria"] or DEFAULT_CRITERIA
                from .hosts import bindings
                old_binding=next((b for b in bindings(s) if b['judgment_id']==jid),None)
        finally: s.close()
        print(review_preview(item, enforcement))
        if old_binding:
            print('Existing protection: v'+str(old_binding['version'])+'. Choose Enforcement to review its replacement; approval alone does not upgrade it.')
        answer = input_fn('[A] Approve'+(' and bind' if enforcement else '')+'  [J] Check evidence  [E] Edit  [H] Enforcement  [R] Reject  [C] Cancel: ').strip().lower()
        if answer in {'c', ''}: return {'review_result': 'Cancelled; no approval made.'}
        if answer == 'j':
            if input_fn('Send the candidate and any policy-enabled referenced excerpts to TypeSafe? [y/N]: ').strip().lower() == 'y':
                s = Store(workspace)
                try:
                    review_assist(s, jid, item["digest"])
                finally:
                    s.close()
            continue
        if answer == 'e':
            revised = revise_in_editor(workspace, jid)
            if revised is not None: enforcement = None  # Changed meaning needs a fresh explicit enforcement choice.
            continue
        if answer == 'h':
            kind = input_fn('Enforcement: [N] Advice only  [G] Generated paths  [L] Lifecycle/conditions  [M] Decision model: ').strip().lower()
            if kind == 'n': enforcement = None; continue
            choices = {'g':'deny_generated_write','l':'require_conditions','m':'decision_model_output'}
            if kind not in choices: continue
            root = Path(input_fn('Project directory [.]: ').strip() or '.').resolve()
            paths = [x.strip() for x in input_fn('Protected paths (comma-separated, e.g. generated/*): ').split(',') if x.strip()]
            enforcement = {'project_root':str(root),'paths':paths,'verifier':choices[kind]}
            continue
        if answer not in {'a','r'}: continue
        s = Store(workspace)
        try:
            with s.transaction():
                result = s.owner_action(jid, item['version'], item['digest'], 'admit' if answer=='a' else 'reject', 'Reviewed in Proofpress CLI', True)
                if answer=='a' and enforcement:
                    from .runtime import bind
                    bind(s, {**enforcement, 'judgment_id':jid,'version':item['version'],'digest':item['digest'],'scope':item['record']['applicability']['scope']}, True)
                return {'review_result': ('Approved and bound.' if enforcement else 'Approved for applicable reuse.') if answer=='a' else 'Rejected.', 'item':result}
        finally: s.close()


def choose_capture_policy(current, input_fn=input):
    value = copy.deepcopy(current)
    print(color('accent', 'Proofpress · Customize capture'))
    print('Choose which moments may produce a candidate. Press Enter to keep each setting.')
    labels = [
        ('human_judgment', 'Your reusable judgment, such as when to bypass a cache'),
        ('human_correction', 'Your correction after an agent makes a wrong call'),
        ('agent_judgment', "An agent's consequential choice and its tradeoff"),
        ('task_end', 'A reusable lesson from a finished or failed task'),
    ]
    selected = []
    for key, label in labels:
        default = key in value['triggers']
        answer = input_fn(label + (' [Y/n/q]: ' if default else ' [y/N/q]: ')).strip().lower()
        if answer == 'q':
            return None
        if (not answer and default) or answer == 'y':
            selected.append(key)
    value['triggers'] = selected
    default = value['history'] == 'selected_only'
    answer = input_fn('Allow import from projects you explicitly select?' + (' [Y/n/q]: ' if default else ' [y/N/q]: ')).strip().lower()
    if answer == 'q':
        return None
    value['history'] = 'selected_only' if answer == 'y' or (not answer and default) else 'none'
    return value


def configure(workspace, input_fn=input):
    from .intake import policy, set_policy
    from .presentation import render_text
    s = Store(workspace)
    try:
        with s.transaction():
            current = policy(s)
        value = choose_capture_policy(current, input_fn)
        if value is None:
            return {'review_result': 'Settings unchanged.'}
        print(render_text('capture-policy', {'capture_policy': value}))
        if input_fn('Save these settings? [y/N]: ').strip().lower() != 'y':
            return {'review_result': 'Settings unchanged.'}
        with s.transaction():
            if policy(s) != current:
                raise JudgmentError("Capture policy changed during setup; rerun proofpress configure")
            return set_policy(s, value, True)
    finally:
        s.close()


def review_inbox(workspace, input_fn=input):
    while True:
        s=Store(workspace)
        try:
            with s.transaction():
                items=[s.describe(json.loads(row[0])) for row in s.db.execute('SELECT body FROM revisions ORDER BY id,version')]
                items=[x for x in items if x['state'] in {'proposed','needs_changes'}]
        finally:s.close()
        if not items:return {'review_result':'Inbox clear.'}
        print(color('accent','Proofpress · Inbox'))
        for n,item in enumerate(items,1): print(str(n)+'. '+item['name']+' · v'+str(item['version']))
        answer=input_fn('Choose a judgment number, or [Q] Quit: ').strip().lower()
        if answer in {'q',''}:return {'review_result':'Remaining candidates saved for later.'}
        if not answer.isdigit() or not 1<=int(answer)<=len(items):continue
        interactive_review(workspace,items[int(answer)-1]['id'],input_fn=input_fn)


def withdraw_interactive(workspace,jid,input_fn=input):
    s=Store(workspace)
    try:
        with s.transaction():
            records=[json.loads(row[0]) for row in s.db.execute('SELECT body FROM revisions WHERE id=? ORDER BY version DESC',(jid,))]
            active=next((r for r in records if s.state(r)=='admitted'),None)
            if active is None:raise JudgmentError('No admitted revision to withdraw')
            item=s.describe(active)
        print(color('accent','Proofpress · Withdraw')+'  v'+str(item['version']))
        print(item['record']['judgment']['statement'])
        print('Stops reuse. Existing protection keeps blocking until explicitly rebound or unbound.')
        if input_fn('Withdraw this judgment? [y/N]: ').strip().lower()!='y':return {'review_result':'No change.'}
        reason=input_fn('Reason: ').strip()
        with s.transaction():result=s.owner_action(jid,item['version'],item['digest'],'withdraw',reason,True)
        return {'review_result':'Withdrawn. Use proofpress doctor to inspect any remaining protection.','item':result}
    finally:s.close()
