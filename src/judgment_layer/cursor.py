"""Cursor wire adapters. stop is a post-response review, not a display veto."""
import json
import sqlite3
from pathlib import Path
from .model import JudgmentError, digest
from .runtime import hook


def deny(reason):
    return {'permission':'deny','user_message':reason,'agent_message':reason}


def normalize(event):
    if not isinstance(event,dict) or event.get('hook_event_name')!='preToolUse':
        raise JudgmentError('Expected a native Cursor preToolUse event')
    tool=event.get('tool_name');args=event.get('tool_input');cwd=event.get('cwd')
    # Cursor CLI omits cwd in observed native events. Use a single explicit host
    # workspace root; multiroot ambiguity must not be guessed from task prose.
    if cwd is None:
        roots=event.get('workspace_roots')
        if isinstance(roots,list) and len(roots)==1:cwd=roots[0]
    if not isinstance(tool,str) or not isinstance(args,dict) or not isinstance(cwd,str) or not Path(cwd).is_absolute():
        raise JudgmentError('Missing Cursor tool, input or absolute working directory')
    result={'tool_name':tool,'tool_input':args,'cwd':cwd,'host':'cursor','session_id':event.get('conversation_id')}
    if tool in {'Write','Edit','StrReplace','Delete','Read'}:
        paths=[args[k] for k in ('file_path','path') if k in args]
        if not paths or any(not isinstance(x,str) or not x for x in paths) or len(set(paths))!=1:
            raise JudgmentError('Missing or ambiguous Cursor file target')
        path=Path(paths[0]);path=path if path.is_absolute() else Path(cwd)/path
        contents=[args[k] for k in ('content','contents') if k in args]
        if any(not isinstance(x,str) for x in contents) or len(set(contents))>1:
            raise JudgmentError('Ambiguous Cursor write content')
        mapped={'Write':'Write','Read':'Read','Edit':'Edit','StrReplace':'Edit','Delete':'Edit'}[tool]
        result.update(tool_name=mapped,tool_input={'file_path':str(path)})
        if contents:result['tool_input']['content']=contents[0]
    elif tool=='Shell':result['tool_name']='Bash'
    return result


def handle(workspace,event):
    try:
        response=hook(workspace,normalize(event),managed=True)
    except (JudgmentError,ValueError,TypeError):
        return deny('Proofpress could not validate the Cursor tool event; action paused')
    if response.get('hookSpecificOutput',{}).get('permissionDecision')=='deny':
        return deny(response['hookSpecificOutput']['permissionDecisionReason'])
    return {'permission':'allow'}


def lifecycle_failure(event, reason):
    kind = event.get('hook_event_name') if isinstance(event, dict) else None
    message = 'Proofpress delivery remains unapproved: ' + reason
    if kind == 'preToolUse':
        return deny(message)
    if kind == 'beforeSubmitPrompt':
        return {'continue': False, 'user_message': message}
    if kind == 'stop' and event.get('status') == 'completed' and event.get('loop_count') == 0:
        return {'followup_message': message + '. Ask the user for review; do not claim successful delivery.'}
    return {}  # Observer hooks cannot block; repeated stop must not loop forever.


def _native(event):
    if not isinstance(event, dict):
        raise JudgmentError('Missing Cursor lifecycle event')
    roots = event.get('workspace_roots')
    if not isinstance(roots, list) or len(roots) != 1 or not isinstance(roots[0], str) or not Path(roots[0]).is_absolute():
        raise JudgmentError('Cursor lifecycle requires one explicit workspace root')
    for key in ('conversation_id', 'generation_id'):
        if not isinstance(event.get(key), str) or not event[key].strip():
            raise JudgmentError('Missing Cursor ' + key)
    return {**event, 'cwd': event.get('cwd') or roots[0], 'host': 'cursor',
            'session_id': event['conversation_id']}


def _current(store, native):
    from .behavior import connection
    from .tasks import latest
    from .workflows import attached
    root = Path(connection(store)['project_root'])
    if not Path(native['cwd']).resolve().is_relative_to(root) or Path(native['workspace_roots'][0]).resolve() != root:
        raise JudgmentError('Cursor lifecycle event belongs to another project')
    task_id = attached(store, native)
    turn = latest(store, task_id, 'task_host_turn') if task_id else None
    if (not turn or turn['data']['host'] != 'cursor'
            or turn['data']['session_id'] != native['session_id']
            or turn['data']['turn_id'] != native['generation_id']):
        raise JudgmentError('No prepared task for this Cursor generation')
    return task_id


def _cache(store, directory, record, value):
    from .hosts import atomic_json
    from .setup import check_path
    path = store.root.resolve() / directory / (record['event_id'] + '.json')
    check_path(path, store.root.resolve())
    atomic_json(path, value)
    return str(path)


def _read_cache(store, directory, record):
    from .setup import check_path
    path = store.root.resolve() / directory / (record['event_id'] + '.json')
    check_path(path, store.root.resolve())
    if path.stat().st_size > 1_000_000:
        raise JudgmentError('Native context/response exceeds the bounded cache limit')
    value = json.loads(path.read_text())
    if digest(value) != record['data']['content_digest']:
        raise JudgmentError('Native context/response cache changed')
    return value


def lifecycle_handle(workspace, event):
    """Prepare automatically; capture actual response; review it on native stop.

    Cursor cannot inject prompt context from beforeSubmitPrompt. The first tool
    is denied once with its context packet, before any tool is executed. A stop
    hook can request a bounded follow-up, but cannot retract the displayed text.
    """
    from .behavior import AUTOMATIC
    from .lifecycle import handle as shared
    from .store import Store
    from .tasks import latest
    native = None
    store = None
    try:
        native = _native(event)
        kind = event.get('hook_event_name')
        if kind == 'beforeSubmitPrompt':
            response = shared(workspace, AUTOMATIC, {**native, 'hook_event_name': 'UserPromptSubmit'}, 'cursor')
            packet = response.get('hookSpecificOutput', {}).get('additionalContext')
            if not isinstance(packet, str):
                return lifecycle_failure(event, response.get('reason', 'Task preparation unavailable'))
            store = Store(workspace)
            with store.transaction():
                task_id = _current(store, native)
                record = store.append('cursor_context_ready', 'system:cursor-lifecycle', data={
                    'task_id': task_id, 'generation_id': native['generation_id'], 'content_digest': digest(packet)})
                _cache(store, 'host-contexts', record, packet)
                notice = latest(store, task_id, 'cursor_handoff_requested')
                if notice and notice['data'].get('message_digest') == digest(event.get('prompt')):
                    store.append('cursor_handoff_active', 'system:cursor-lifecycle', data={
                        'task_id': task_id, 'generation_id': native['generation_id']})
            return {'continue': True}
        store = Store(workspace)
        with store.transaction():
            task_id = _current(store, native)
            if kind == 'preToolUse':
                context = latest(store, task_id, 'cursor_context_ready')
                delivered = latest(store, task_id, 'cursor_context_delivered')
                if not context or context['data']['generation_id'] != native['generation_id']:
                    raise JudgmentError('Cursor task context unavailable')
                if not delivered or delivered['data']['context_id'] != context['event_id']:
                    packet = _read_cache(store, 'host-contexts', context)
                    store.append('cursor_context_delivered', 'system:cursor-lifecycle', data={
                        'task_id': task_id, 'context_id': context['event_id']})
                    return deny('Proofpress context before tools. Read this packet and follow its plan/check requirements: ' + packet)
            elif kind == 'afterAgentResponse':
                text = event.get('text')
                if not isinstance(text, str) or len(text.encode()) > 64000:
                    raise JudgmentError('Missing or oversized actual Cursor response')
                record = store.append('cursor_response_captured', 'system:cursor-lifecycle', data={
                    'task_id': task_id, 'generation_id': native['generation_id'], 'content_digest': digest(text)})
                _cache(store, 'host-responses', record, text)
                return {}
            elif kind == 'stop':
                if event.get('status') != 'completed':
                    store.append('task_host_paused', 'system:cursor-lifecycle', data={
                        'task_id': task_id, 'reason': 'Cursor stopped without completing'})
                    return {}
                if type(event.get('loop_count')) is not int or event['loop_count'] < 0:
                    raise JudgmentError('Missing Cursor stop loop count')
                handoff = latest(store, task_id, 'cursor_handoff_active')
                if handoff and handoff['data']['generation_id'] == native['generation_id']:
                    return {}  # Human handoff text is not new compliance evidence.
                captured = latest(store, task_id, 'cursor_response_captured')
                if not captured or captured['data']['generation_id'] != native['generation_id']:
                    raise JudgmentError('No actual response captured for this Cursor generation')
                text = _read_cache(store, 'host-responses', captured)
                native = {**native, 'last_assistant_message': text,
                          'stop_hook_active': event['loop_count'] > 0}
            else:
                raise JudgmentError('Unsupported Cursor lifecycle event')
        store.close()
        store = None
        if kind == 'preToolUse':
            normalized = normalize(event)
            response = shared(workspace, AUTOMATIC, {**native, **normalized, 'hook_event_name': 'PreToolUse'}, 'cursor')
            reason = response.get('hookSpecificOutput', {}).get('permissionDecisionReason')
            return deny(reason) if reason else {'permission': 'allow'}
        response = shared(workspace, AUTOMATIC, {**native, 'hook_event_name': 'Stop'}, 'cursor')
        if response.get('decision') == 'block':
            return {'followup_message': response['reason']}
        if response.get('continue') is False:
            # No native stop veto exists. Keep the receipt unapproved and record
            # the pause for task-status/export instead of inventing output fields.
            store = Store(workspace)
            with store.transaction():
                store.append('task_host_paused', 'system:cursor-lifecycle', data={
                    'task_id': task_id, 'reason': response['stopReason']})
                notice = latest(store, task_id, 'cursor_handoff_requested')
                if event['loop_count'] == 0 and not notice:
                    message = ('proofpress resume task ' + task_id + '\n' + response['stopReason'] +
                               ' Ask the user for missing context or review; do not claim successful delivery.')
                    store.append('cursor_handoff_requested', 'system:cursor-lifecycle', data={
                        'task_id': task_id, 'message_digest': digest(message)})
                    return {'followup_message': message}
        return {}
    except (JudgmentError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        if store:
            store.close()
            store = None
        # A missing response/cache/status must not inherit an earlier approval.
        if native:
            paused = None
            try:
                paused = Store(workspace)
                with paused.transaction():
                    task_id = _current(paused, native)
                    paused.append('task_host_paused', 'system:cursor-lifecycle', data={
                        'task_id': task_id, 'reason': 'Cursor context/response/check unavailable'})
            except (JudgmentError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                pass
            finally:
                if paused:
                    paused.close()
        return lifecycle_failure(event, 'Native context, response or check unavailable; inspect task-status')
    finally:
        if store:
            store.close()
