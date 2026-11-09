"""Cursor's native preToolUse wire adapter. Unknown routes remain conservative."""
from pathlib import Path
from .model import JudgmentError
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
