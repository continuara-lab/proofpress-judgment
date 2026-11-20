"""AJF-owned behavior declarations; authority and run receipts remain local.

No user-authored workflow or binding is needed. There is no arbitrary-code loader.
All store operations run in the caller's transaction.
"""
import fnmatch
import json
from pathlib import Path

from .assessment import assess
from .model import JudgmentError, applies, digest, validate_facts

AUTOMATIC = '@judgments'


def validate_behavior(record):
    behavior = record['behavior']
    delivery = any(h['event'] == 'before_delivery' for h in behavior['hooks'])
    if delivery and 'artifacts' not in behavior:
        raise JudgmentError('before_delivery requires behavior.artifacts paths and required files')
    artifacts = behavior.get('artifacts', {'paths': [], 'required': []})
    for hook in behavior['hooks']:
        for path in hook.get('match', {}).get('paths', []):
            validate_path(path)
    for path in [*artifacts['paths'], *artifacts['required']]:
        validate_path(path)
    for name in artifacts['required']:
        if any(c in name for c in '*?[') or not matches(name, artifacts['paths']):
            raise JudgmentError('Required artifacts must be exact files covered by artifact paths')


def validate_path(value):
    parts = Path(value).parts
    if (Path(value).is_absolute() or value.startswith('@') or '\\' in value or '..' in parts
            or any(p in {'.git', '.judgment', '.claude', '.codex', '.cursor'} or p.startswith('.env')
                   for p in parts) or value.strip() != value):
        raise JudgmentError('Behavior paths must be project-relative and outside private integration paths')


def matches(path, patterns):
    # Also let **/ match zero directories. No code or expression evaluation.
    return any(fnmatch.fnmatchcase(path, pattern) or
               ('**/' in pattern and fnmatch.fnmatchcase(path, pattern.replace('**/', '')))
               for pattern in patterns)


def inventory(store):
    result = []
    for row in store.db.execute('SELECT body FROM revisions ORDER BY id,version'):
        record = json.loads(row[0])
        if 'behavior' in record and store.state(record) == 'admitted':
            result.append(record)
    return result


def connection(store):
    event = next((e for e in reversed(store.events()) if e['kind'] == 'behavior_connected'), None)
    return event['data'] if event else {'project_root': str(store.root.resolve().parent), 'facts': {}}


def connect(store, project, facts, confirmed=False):
    root = Path(project).resolve()
    validate_facts(facts)
    if not root.is_dir() or not store.root.resolve().is_relative_to(root) or root == store.root.resolve():
        raise JudgmentError('Use a project-local judgment workspace inside this project')
    previous = connection(store)
    if previous['project_root'] != str(root) and any(
            e['kind'] == 'behavior_connected' for e in store.events()):
        raise JudgmentError('This workspace is already connected to another project')
    data = {'project_root': str(root), 'facts': facts}
    if confirmed:
        store.append('behavior_connected', store.config['owner'], data=data)
    return {'ok': True, 'confirmed': confirmed, **data}


def policy(store):
    """Internal snapshot derived from admitted JSON, never an editable workflow."""
    records = inventory(store)
    return {'id': AUTOMATIC, **connection(store), 'mandatory_scopes': [], 'scope_criteria': {},
            'paths': ['*'], 'artifacts': [], 'allow_exceptions': False,
            'judgments': [{'id': r['id'], 'version': r['version'], 'digest': digest(r)} for r in records]}


def effective_policy(base, records):
    delivery = [r for r in records if any(h['event'] == 'before_delivery' for h in r['behavior']['hooks'])]
    return {**base,
            'paths': sorted({p for r in delivery for p in r['behavior']['artifacts']['paths']}),
            'artifacts': sorted({p for r in delivery for p in r['behavior']['artifacts']['required']}),
            'allow_exceptions': bool(delivery) and all(r['behavior'].get('allow_exceptions', False) for r in delivery)}


def prepare(store, task_id, task):
    from .runtime import active_flags
    from .tasks import identity
    from .workflows import covered_files, plan_path
    identity(task_id)
    if not isinstance(task, str) or not task.strip():
        raise JudgmentError('Task description must be nonempty')
    base = policy(store)
    selected, decisions, reasons = [], [], []
    for record in inventory(store):
        reason = applies(record, record['applicability']['scope'], base['facts'])
        if reason:
            if reason.startswith('missing_fact:'):
                reasons.append(reason + ':' + record['id'])
            continue
        if store.eligible(record, record['applicability']['scope'], base['facts']) or active_flags(store, record):
            reasons.append('judgment_unavailable:' + record['id'])
            continue
        criteria = record['applicability'].get('task_criteria')
        if criteria:
            result = assess({'task': task, 'criteria': criteria, 'facts': base['facts']},
                            'Does this task satisfy these judgment applicability criteria? '
                            'Do not invent facts. Missing evidence is unknown.',
                            {'applicable': 'Criteria apply.', 'not_applicable': 'Criteria do not apply.',
                             'unknown': 'Insufficient evidence.'})
            decisions.append({'judgment_id': record['id'], 'assessment': result})
            if result['choice'] == 'not_applicable':
                continue
            if result['choice'] != 'applicable':
                reasons.append('task_match_uncertain:' + record['id'])
                continue
        selected.append(record)
    scopes = sorted({r['applicability']['scope'] for r in selected})
    packets = [store.context(scope, base['facts'], 'system:judgment-behavior', 'Task context: ' + task_id,
                             {r['id'] for r in selected}) for scope in scopes]
    for packet in packets:
        if packet['holds'] or not packet['receipt']['items']:
            reasons.append('judgment_context_unavailable:' + packet['receipt']['scope'])
    effective = effective_policy(base, selected)
    data = {'task_id': task_id, 'workflow_id': AUTOMATIC, 'workflow_digest': digest(base),
            'behavior_task': True, 'artifact_policy': effective, 'task': task,
            'facts': base['facts'], 'scopes': scopes, 'receipts': [p['receipt'] for p in packets],
            'decisions': decisions, 'initial_files': covered_files(store, effective),
            'ok': not reasons, 'reasons': reasons}
    event = store.append('task_prepared', 'system:judgment-behavior', data=data)
    needs_plan = any(h['event'] == 'before_execution' for r in selected for h in r['behavior']['hooks'])
    if not needs_plan and not reasons:
        from .workflows import plan
        plan(store, task_id, event['event_id'], 'No before_execution hook requested for this task.')
    return {'ok': not reasons, 'task_id': task_id, 'context_id': event['event_id'],
            'scopes': scopes, 'reasons': reasons, 'scope_decisions': decisions,
            'judgments': [j for p in packets for j in p['judgments']],
            'context': [r['behavior']['context'] for r in selected if 'context' in r['behavior']],
            'coverage': 'declared_hooks' if selected else 'no_applicable_judgments',
            'requires_plan': needs_plan,
            'plan_path': str(plan_path(store, task_id)),
            'next': ('Read supplied judgments and context. Submit task-plan with this context id.' if needs_plan
                     else 'No plan check requested. Read context; declared action and delivery checks still apply.')}


def assess_stage(records, event, state):
    checks = [{'judgment_id': r['id'], 'version': r['version'], 'digest': digest(r),
               'criteria': h['verifier']['criteria']}
              for r in records for h in r.get('behavior', {}).get('hooks', []) if h['event'] == event]
    if not checks:
        return {'choice': 'pass', 'reason': 'no_hook_requested', 'coverage': 'not_requested'}
    from .tasks import OPTIONS
    result = assess({**state, 'judgments': records, 'checks': checks},
                    'Evaluate every declared check against the actual supplied plan/artifacts and evidence. '
                    'A promise or self-reported success is not evidence. Missing context is unknown.', OPTIONS)
    return {**result, 'checks': checks}


def action(store, event):
    """Deterministic file checks independent of probabilistic task recognition."""
    from .runtime import active_flags
    records = inventory(store)
    if not records:
        return None
    root = Path(connection(store)['project_root'])
    cwd = event.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).resolve().is_relative_to(root):
        return {'ok': False, 'reason': 'Judgment action belongs to another project'}
    tool = event['tool_name']
    if tool == 'apply_patch':
        return None  # The existing parser checks every source/destination recursively.
    if tool in {'Read', 'Glob', 'Grep'}:
        return {'ok': True, 'reason': 'Read-only action; no behavior verifier requested'}
    action_records = [r for r in records if any(h['event'] == 'before_action' for h in r['behavior']['hooks'])]
    if tool not in {'Write', 'Edit'}:
        return {'ok': False, 'reason': 'Action route is not covered by judgment checks; inspect task-status or ask the owner'} if action_records else None
    target = event['tool_input'].get('file_path')
    if not isinstance(target, str) or not Path(target).is_absolute():
        return {'ok': False, 'reason': 'Judgment check requires an absolute target path'}
    from .setup import check_path
    check_path(Path(target), root)
    path = Path(target).resolve()
    if not path.is_relative_to(root) or path.is_relative_to(store.root.resolve()):
        return {'ok': False, 'reason': 'Write outside connected project or into protected judgment workspace'}
    relative = path.relative_to(root).as_posix()
    for record in action_records:
        hooks = [h for h in record['behavior']['hooks'] if h['event'] == 'before_action'
                 and matches(relative, h['match']['paths'])]
        if not hooks:
            continue
        reason = applies(record, record['applicability']['scope'], connection(store)['facts'])
        if reason and not reason.startswith('missing_fact:'):
            continue
        if reason or store.eligible(record, record['applicability']['scope'], connection(store)['facts']) or active_flags(store, record):
            return {'ok': False, 'reason': record['name'] + ': applicability or judgment validity unavailable'}
        for hook in hooks:
            verdict = {'ok': hook['verifier']['name'] != 'deny_action', 'reason':
                       hook['verifier'].get('message', record['judgment']['statement'])}
            store.append('behavior_action_checked', 'system:judgment-behavior', record,
                         data={'result': verdict, 'event_digest': digest(event)})
            if not verdict['ok']:
                return verdict
    return {'ok': True, 'reason': 'Applicable declared action checks passed'}
