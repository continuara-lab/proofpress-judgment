"""Owner-configured scope resolution, context-first planning and release recovery.

All APIs run inside the caller's Store transaction. Local authority is cooperative.
"""
import fnmatch
import json
import os
import shlex
import uuid
from pathlib import Path

from .assessment import assess
from .model import JudgmentError, digest, validate_facts
from .tasks import (OPTIONS, artifacts, check_release, finish_task, freshness,
                    identity, latest, records, started)


def configuration(store, workflow_id):
    event = next((e for e in reversed(store.events()) if e['kind'] == 'workflow_configured'
                  and e['data']['policy']['id'] == workflow_id), None)
    if event is None:
        raise JudgmentError('Workflow not configured')
    return event['data']['policy']


def configure(store, policy, confirmed=False):
    required = {'id', 'project_root', 'mandatory_scopes', 'scope_criteria', 'facts',
                'paths', 'artifacts', 'allow_exceptions'}
    if not isinstance(policy, dict) or set(policy) != required:
        raise JudgmentError('Workflow requires: ' + ', '.join(sorted(required)))
    identity(policy['id'])
    root = Path(policy['project_root'])
    if not root.is_absolute() or not root.is_dir() or str(root.resolve()) != str(root):
        raise JudgmentError('Workflow project_root must be an existing canonical absolute directory')
    validate_facts(policy['facts'])
    if type(policy['allow_exceptions']) is not bool:
        raise JudgmentError('allow_exceptions must be a boolean')
    mandatory = policy['mandatory_scopes']
    criteria = policy['scope_criteria']
    if (not isinstance(mandatory, list) or not isinstance(criteria, dict)
            or any(not isinstance(s, str) or not s.strip() for s in [*mandatory, *criteria])
            or any(not isinstance(c, str) or not c.strip() for c in criteria.values())
            or not (mandatory or criteria) or len(mandatory) != len(set(mandatory))):
        raise JudgmentError('Define nonempty mandatory scopes and/or explicit scope criteria')
    for key in ('paths', 'artifacts'):
        values = policy[key]
        if (not isinstance(values, list) or not values or len(values) != len(set(values))
                or any(not isinstance(p, str) or not p or Path(p).is_absolute()
                       or '..' in Path(p).parts or '.judgment' in Path(p).parts for p in values)):
            raise JudgmentError(key + ' must contain project-relative paths outside .judgment')
    if any((root / p).resolve().is_relative_to(store.root.resolve()) for p in policy['artifacts']):
        raise JudgmentError('Artifacts cannot include the judgment workspace')
    # Artifact files are explicit; expanding a glob at finish could omit a deleted file.
    if any(any(c in p for c in '*?[') for p in policy['artifacts']):
        raise JudgmentError('artifacts must list exact files, not globs')
    if any(not any(fnmatch.fnmatchcase(p, pattern) for pattern in policy['paths'])
           for p in policy['artifacts']):
        raise JudgmentError('Every artifact must be covered by workflow paths')
    result = {'ok': True, 'confirmed': confirmed, 'workflow': policy,
              'provider_inputs': 'Task text, scope criteria, admitted judgments, plans and artifacts'}
    if confirmed:
        store.append('workflow_configured', store.config['owner'], data={'policy': policy})
    return result


def prepare(store, task_id, workflow_id, task):
    identity(task_id)
    if not isinstance(task, str) or not task.strip():
        raise JudgmentError('Task description must be nonempty')
    policy = configuration(store, workflow_id)
    selected = set(policy['mandatory_scopes'])
    decisions, reasons = [], []
    for scope, criteria in sorted(policy['scope_criteria'].items()):
        if scope in selected:
            continue  # Jev cannot exclude mandatory scope.
        result = assess({'task': task, 'criteria': criteria, 'facts': policy['facts']},
                        'Does this task fall within these workflow scope criteria? '
                        'Do not invent task facts; uncertainty must remain unknown.',
                        {'applicable': 'Criteria apply.', 'not_applicable': 'Criteria do not apply.',
                         'unknown': 'Cannot establish whether criteria apply.'})
        decisions.append({'scope': scope, 'assessment': result})
        if result['choice'] == 'applicable':
            selected.add(scope)
        elif result['choice'] != 'not_applicable':
            reasons.append('scope_uncertain:' + scope)
    packets = [store.context(s, policy['facts'], 'system:workflow', 'Task context: ' + task_id)
               for s in sorted(selected)]
    if not packets:
        reasons.append('no_scope_selected')
    for packet in packets:
        if packet['holds'] or not packet['receipt']['items']:
            reasons.append('scope_context_unavailable:' + packet['receipt']['scope'])
        # Missing applicability facts must not silently discard an admitted judgment.
        for blocked in packet['blocked']:
            record = store.record(blocked['id'], blocked['version'])
            if store.state(record) == 'admitted' and blocked['reason'].startswith('missing_fact:'):
                reasons.append(blocked['reason'])
    data = {'task_id': task_id, 'workflow_id': workflow_id, 'workflow_digest': digest(policy),
            'task': task, 'facts': policy['facts'], 'scopes': sorted(selected),
            'receipts': [p['receipt'] for p in packets], 'decisions': decisions,
            'initial_files': covered_files(store, policy), 'ok': not reasons, 'reasons': reasons}
    event = store.append('task_prepared', 'system:workflow', data=data)
    return {'ok': not reasons, 'task_id': task_id, 'context_id': event['event_id'],
            'scopes': sorted(selected), 'reasons': reasons, 'scope_decisions': decisions,
            'judgments': [j for p in packets for j in p['judgments']],
            'plan_path': str(plan_path(store, task_id)),
            'next': 'Read the judgments before planning. Submit task-plan with this context id.'}


def plan_path(store, task_id):
    identity(task_id)
    return store.root.resolve() / 'task-plans' / (digest(task_id).split(':')[1] + '.txt')


def plan(store, task_id, context_id, text):
    if not isinstance(text, str) or not text.strip():
        raise JudgmentError('Plan must be nonempty')
    prepared = latest(store, task_id, 'task_prepared')
    if prepared is None or prepared['event_id'] != context_id:
        raise JudgmentError('Read the latest task context before submitting a plan')
    p = prepared['data']
    policy = configuration(store, p['workflow_id'])
    reasons = list(p['reasons'])
    if digest(policy) != p['workflow_digest']:
        reasons.append('workflow_changed')
    for receipt in p['receipts']:
        reasons.extend(store.check(receipt['receipt_id'], p['facts'])['reasons'])
        from .tasks import items
        if items(store, receipt['scope'], p['facts']) != receipt['items']:
            reasons.append('judgment_set_changed')
    snapshot = [item for receipt in p['receipts'] for item in receipt['items']]
    result = {'choice': 'unknown', 'reason': 'task_context_unavailable'}
    if not reasons:
        result = assess({'task': p['task'], 'plan': text, 'facts': p['facts'],
                         'judgments': records(store, snapshot)},
                        'Does the concrete plan satisfy the task and every judgment, including '
                        'conditions and exceptions? Unsupported assumptions or a mere promise '
                        'to comply are unknown.', OPTIONS)
    data = {**p, 'scope': p['scopes'][0] if p['scopes'] else '',
            'receipt': p['receipts'][0] if p['receipts'] else {},
            'prepare_id': context_id, 'plan': text, 'items': snapshot,
            'assessment': result, 'plan_reasons': reasons}
    event = store.append('task_started', 'agent:workflow', data=data)
    return {'ok': not reasons and result['choice'] == 'pass', 'task_id': task_id,
            'start_id': event['event_id'], 'assessment': result, 'reasons': reasons}


def attach(store, task_id, host, session_id):
    if host not in {'claude-code', 'codex', 'cursor'} or not isinstance(session_id, str) or not session_id.strip():
        raise JudgmentError('Select a supported host and explicit session id')
    prepared = latest(store, task_id, 'task_prepared')
    if prepared is None:
        raise JudgmentError('Prepare task context before attaching a host session')
    store.append('task_attached', 'agent:workflow', data={
        'task_id': task_id, 'host': host, 'session_id': session_id})
    return {'ok': True, 'task_id': task_id, 'host': host, 'session_id': session_id}


def attached(store, event):
    explicit = event.get('proofpress_task_id')
    if explicit:
        return explicit
    # Match only the host explicitly supplied by its adapter; no cross-host guessing.
    return next((e['data']['task_id'] for e in reversed(store.events())
                 if e['kind'] == 'task_attached'
                 and e['data']['host'] == event.get('host')
                 and e['data']['session_id'] == event.get('session_id')), None)


def control_command(store, task_id, event):
    """Narrow shell control channel. No operators, expansion, env changes or owner actions."""
    command = event.get('tool_input', {}).get('command')
    if not isinstance(command, str) or any(c in command for c in '\n\r;$`|&<>()'):
        return False
    try:
        words = shlex.split(command)
        if not words or words[0] != 'proofpress':
            return False
        from .cli import parser
        args = parser().parse_args(words[1:])
        if args.command not in {'task-plan', 'task-status', 'task-finish-files'} or args.task != task_id:
            return False
        if Path(args.workspace).resolve() != store.root.resolve():
            return False
        if args.env_file:
            from .lifecycle import manifest_path
            allowed_env = {store.root.resolve() / 'jev.env'}
            manifest = manifest_path(store)
            if manifest.exists():
                configured_env = json.loads(manifest.read_text()).get('env_file')
                if configured_env:
                    allowed_env.add(Path(configured_env))
            if Path(args.env_file).resolve() not in allowed_env:
                return False
        if args.command == 'task-plan' and Path(args.plan).resolve() != plan_path(store, task_id):
            return False
        return True
    except (ValueError, SystemExit):
        return False


def action(store, event):
    task_id = attached(store, event)
    if not task_id:
        return None
    prepared = latest(store, task_id, 'task_prepared')
    if prepared is None:
        return None  # Legacy explicit task API is handled by the binding gate.
    policy = configuration(store, prepared['data']['workflow_id'])
    tool = event['tool_name']
    if tool in {'Read', 'Glob', 'Grep'}:
        return {'ok': True, 'reason': 'Read-only; normal host permissions apply'}
    if tool == 'Bash' and control_command(store, task_id, event):
        return {'ok': True, 'reason': 'Workflow control command; normal host permissions apply'}
    if tool not in {'Write', 'Edit', 'apply_patch'}:
        return {'ok': False, 'reason': 'Workflow route unsupported; use covered file tools or ask the owner. '
                'Reading and planning remain available. Inspect task-status.'}
    if tool == 'apply_patch':
        return None  # Shared parser checks every normalized target recursively.
    target = event['tool_input'].get('file_path')
    if not isinstance(target, str) or not Path(target).is_absolute():
        return {'ok': False, 'reason': 'Workflow requires an absolute write target'}
    path = Path(target).resolve()
    if path == plan_path(store, task_id) and tool == 'Write':
        return {'ok': True, 'control': True, 'reason': 'Plan draft only; source execution is still gated'}
    root = Path(policy['project_root'])
    if not path.is_relative_to(root) or path.is_relative_to(store.root.resolve()):
        return {'ok': False, 'reason': 'Workflow write outside project or into protected workspace'}
    relative = path.relative_to(root).as_posix()
    if not any(fnmatch.fnmatchcase(relative, p) for p in policy['paths']):
        return {'ok': False, 'reason': 'Write outside declared workflow paths; expand scope through owner review'}
    begin = latest(store, task_id, 'task_started')
    if begin is None or 'prepare_id' not in begin['data']:
        return {'ok': False, 'reason': 'Source write paused: submit task-plan for the prepared context first'}
    fresh = freshness(store, begin, policy['facts'])
    if not fresh['ok']:
        return {'ok': False, 'reason': 'Source write paused: ' + ', '.join(fresh['reasons']) + '. Reprepare context or revise the plan.'}
    store.append('task_action', 'system:workflow', data={
        'task_id': task_id, 'start_id': begin['event_id'], 'event_digest': digest(event)})
    return {'ok': True, 'reason': 'Plan current; repair writes allowed, delivery requires separate review'}


def covered_files(store, policy):
    """Enumerate actual covered files, not an agent-picked subset. Never traverse store/git."""
    root = Path(policy['project_root'])
    selected = []
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(directories):
            path = parent / name
            relative = path.relative_to(root).as_posix()
            if name == '.git' or path.resolve().is_relative_to(store.root.resolve()):
                directories.remove(name)
            elif path.is_symlink() and any(fnmatch.fnmatchcase(relative, p) or p.startswith(relative + '/')
                                           for p in policy['paths']):
                raise JudgmentError('Symlink directory in covered paths: ' + relative)
        for name in files:
            path = parent / name
            relative = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatchcase(relative, p) for p in policy['paths']):
                if path.is_symlink() or path.resolve().is_relative_to(store.root.resolve()):
                    raise JudgmentError('Unsafe artifact: ' + relative)
                selected.append(relative)
    return sorted(selected)


def snapshot(store, task_id):
    begin = started(store, task_id)
    policy = configuration(store, begin['data']['workflow_id'])
    root = Path(policy['project_root'])
    outputs = {}
    names = covered_files(store, policy)
    for name in policy['artifacts']:
        if name not in names:
            raise JudgmentError('Required artifact missing or unsafe: ' + name)
    for name in names:
        path = root / name
        from .setup import check_path
        check_path(path, root)
        if (not path.resolve().is_relative_to(root) or path.resolve().is_relative_to(store.root.resolve())
                or not path.is_file()):
            raise JudgmentError('Required artifact missing or unsafe: ' + name)
        if path.stat().st_size > 64000:
            raise JudgmentError('Required artifact exceeds review limit: ' + name)
        outputs[name] = path.read_text()
    prepared = latest(store, task_id, 'task_prepared')
    for deleted in set(prepared['data']['initial_files']) - set(names):
        outputs['@deleted/' + deleted] = 'File deleted since task context preparation.'
    return outputs


def finish_files(store, task_id, response=None, evidence=''):
    outputs = snapshot(store, task_id)
    if response is not None:
        if not isinstance(response, str):
            raise JudgmentError('Response must be text')
        outputs['@response'] = response
    begin = started(store, task_id)
    policy = configuration(store, begin['data']['workflow_id'])
    result = finish_task(store, task_id, policy['facts'], outputs, evidence)
    from .hosts import atomic_json
    directory = store.root.resolve() / 'reviews'
    directory.mkdir(exist_ok=True)
    if directory.is_symlink():
        raise JudgmentError('Unsafe review directory')
    path = directory / (result['finish_id'] + '.json')
    atomic_json(path, outputs)
    result['review_path'] = str(path)
    return result, outputs


def exception(store, task_id, outputs, reason, confirmed=False):
    outputs = artifacts(outputs)
    begin = started(store, task_id)
    policy = configuration(store, begin['data']['workflow_id'])
    if not policy['allow_exceptions'] or not freshness(store, begin, policy['facts'])['ok']:
        raise JudgmentError('Exceptions disabled or task context stale; cannot override')
    finish = latest(store, task_id, 'task_finished')
    if (finish is None or finish['data']['start_id'] != begin['event_id']
            or finish['data']['artifacts_digest'] != digest(outputs)
            or not finish['data']['freshness']['ok']):
        raise JudgmentError('Review these exact artifacts before considering an exception')
    if not isinstance(reason, str) or not reason.strip():
        raise JudgmentError('A human exception requires a reason')
    result = {'ok': True, 'confirmed': confirmed, 'task_id': task_id,
              'start_id': begin['event_id'], 'finish_id': finish['event_id'],
              'artifacts_digest': digest(outputs), 'reason': reason}
    if confirmed:
        store.append('task_exception', store.config['owner'], data=result)
    return result


def export(store, task_id):
    """Gate the concrete local delivery bundle; never execute a model-provided command."""
    outputs = snapshot(store, task_id)
    begin = started(store, task_id)
    policy = configuration(store, begin['data']['workflow_id'])
    result = check_release(store, task_id, policy['facts'], outputs)
    if not result['ok']:
        return result
    from .hosts import atomic_json
    directory = store.root.resolve() / 'deliveries'
    directory.mkdir(exist_ok=True)
    if directory.is_symlink():
        raise JudgmentError('Unsafe delivery directory')
    path = directory / (uuid.uuid4().hex + '.json')
    atomic_json(path, {'task_id': task_id, 'artifacts': outputs, 'receipt': result})
    store.append('task_exported', 'system:workflow', data={
        'task_id': task_id, 'path': str(path), 'artifacts_digest': digest(outputs)})
    return {**result, 'path': str(path), 'boundary': 'Exact reviewed local bundle exported; no deployment or message sent.'}


def status(store, task_id):
    prepared = latest(store, task_id, 'task_prepared')
    if prepared is None:
        raise JudgmentError('No prepared workflow task')
    p = prepared['data']
    begin = latest(store, task_id, 'task_started')
    finish = latest(store, task_id, 'task_finished')
    state, reasons, outcome = 'planning', list(p['reasons']), None
    policy = configuration(store, p['workflow_id'])
    if digest(policy) != p['workflow_digest']:
        reasons.append('workflow_changed')
    if reasons:
        state = 'context_paused'
    elif begin is not None and begin['data'].get('prepare_id') == prepared['event_id']:
        fresh = freshness(store, begin, policy['facts'])
        reasons = fresh['reasons']
        if not fresh['ok']:
            state = 'plan_paused'
        else:
            state = 'executing'
            if finish and finish['data']['start_id'] == begin['event_id']:
                outcome = finish['data']['assessment']['choice']
                state = 'ready' if outcome == 'pass' else 'delivery_paused'
                if outcome != 'pass':
                    reasons = [finish['data']['assessment'].get('reason', outcome)]
                try:
                    current = snapshot(store, task_id)
                    expected = finish['data'].get('artifact_digests', {})
                    unchanged = all(expected.get(name) == digest(text) for name, text in current.items())
                    if not unchanged:
                        state = 'delivery_paused'
                        reasons.append('artifacts_changed')
                    approved = latest(store, task_id, 'task_exception')
                    if (unchanged and approved and approved['data']['finish_id'] == finish['event_id']
                            and approved['data']['start_id'] == begin['event_id']):
                        state = 'ready'
                        reasons = ['human_exception_for_this_artifact_revision']
                    action_event = latest(store, task_id, 'task_action')
                    if action_event and action_event['seq'] > finish['seq']:
                        state = 'delivery_paused'
                        reasons.append('action_after_finish')
                except (OSError, ValueError) as exc:
                    state = 'delivery_paused'
                    reasons.append(str(exc))
    action_labels = {
        'context_paused': ['Clarify scope/facts with the owner, then task-prepare again'],
        'planning': ['Read supplied judgments; write plan draft; run task-plan'],
        'plan_paused': ['Revise plan or reprepare changed context; source writes paused'],
        'executing': ['Work within declared paths; run task-finish-files before delivery'],
        'delivery_paused': ['Repair working files and recheck', 'Supply missing evidence/context',
                            'Ask owner for an exact-artifact exception if enabled'],
        'ready': ['Deliver only the checked revision; task-export exports file-only reviewed bundles']}
    return {'ok': state == 'ready', 'task_id': task_id, 'state': state,
            'paused_boundary': 'delivery' if state == 'delivery_paused' else 'execution' if state in {'context_paused', 'plan_paused', 'planning'} else None,
            'assessment': outcome, 'reasons': reasons, 'next': action_labels[state],
            'artifacts': finish['data'].get('artifact_digests', {}) if finish else {},
            'review_id': finish['event_id'] if finish else None,
            'review_path': str(store.root.resolve() / 'reviews' / (finish['event_id'] + '.json')) if finish else None,
            'attribution': 'Aggregate model assessment; no unsupported per-judgment violation attribution.',
            'scopes': p['scopes'], 'scope_decisions': p['decisions'],
            'judgments': records(store, [i for r in p['receipts'] for i in r['items']]),
            'limits': 'Model verdicts are assessments, not proof. Read access remains available.'}
