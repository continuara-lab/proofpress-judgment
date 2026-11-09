"""Project-local host registration; never writes host trust or removes user hooks."""
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from .model import JudgmentError, digest
from .setup import check_path, AGENTS


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.proofpress-')
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, ensure_ascii=False, indent=2); out.write('\n')
        os.replace(temp, path)
    finally:
        if Path(temp).exists(): Path(temp).unlink()


def registration(project, workspace, host, env_file=None):
    root = Path(project).resolve()
    if host not in {'codex', 'claude-code'}: raise JudgmentError('Hook installation supports codex and claude-code')
    path = root / ('.codex/hooks.json' if host == 'codex' else '.claude/settings.local.json')
    check_path(path, root)
    command = [sys.executable, '-m', 'judgment_layer.cli']
    if env_file:
        env_file = str(Path(env_file).resolve())
        if not Path(env_file).is_file(): raise JudgmentError('Environment file does not exist')
        command += ['--env-file', env_file]
    command += ['--workspace', str(Path(workspace).resolve()), 'managed-hook']
    # A missing Python/package must emit a host denial rather than a shell error.
    denial = json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': 'Proofpress could not start; run proofpress doctor'}})
    shell = shlex.join(command) + ' || printf ' + shlex.quote('%s\n') + ' ' + shlex.quote(denial)
    entry = {'matcher': '.*', 'hooks': [{'type': 'command', 'command': shell, 'timeout': 60}]}
    return path, entry


def install(store, project, host, confirmed=False, env_file=None):
    path, entry = registration(project, store.root, host, env_file)
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict) or not isinstance(value.get('hooks', {}), dict): raise JudgmentError('Unsupported host settings; no changes made')
    entries = value.setdefault('hooks', {}).setdefault('PreToolUse', [])
    if not isinstance(entries, list): raise JudgmentError('PreToolUse must be an array')
    manifest = store.root / ('host-' + host + '.json')
    previous = json.loads(manifest.read_text()) if manifest.exists() else None
    if previous and previous['path'] != str(path): raise JudgmentError('Host already registered for another project in this store')
    result = {'host_setup': True, 'host': host, 'path': str(path), 'confirmed': confirmed,
              'trust': 'Restart Codex and review /hooks; project and exact hook must be trusted.' if host == 'codex' else 'Restart Claude Code and review project trust and hooks.',
              'command': entry['hooks'][0]['command']}
    if not confirmed: return result
    if previous and previous['entry'] in entries: entries.remove(previous['entry'])
    if entry not in entries: entries.append(entry)
    atomic_json(path, value)
    atomic_json(manifest, {'path': str(path), 'entry': entry})
    store.append('host_installed', store.config['owner'], data={'host': host, 'path': str(path), 'entry_digest': digest(entry)})
    return result


def remove(store, host, confirmed=False):
    manifest = store.root / ('host-' + host + '.json')
    if not manifest.exists(): raise JudgmentError('No managed hook registration for this host')
    previous = json.loads(manifest.read_text()); path = Path(previous['path'])
    check_path(path, path.parent.parent)
    value = json.loads(path.read_text()) if path.exists() else {}
    entries = value.get('hooks', {}).get('PreToolUse', [])
    if previous['entry'] not in entries: raise JudgmentError('Hook changed or is missing; inspect host settings manually')
    if confirmed:
        entries.remove(previous['entry'])
        atomic_json(path, value); manifest.unlink()
        store.append('host_removed', store.config['owner'], data={'host': host})
    return {'host_setup': True, 'host': host, 'path': str(path), 'confirmed': confirmed, 'removed': True,
            'trust': 'Restart the agent. Existing judgments and other hooks are preserved.'}


def bindings(store):
    current = {}
    for event in store.events():
        if event['kind'] == 'runtime_bound': current[event['judgment_id']] = event['data']['policy']
        if event['kind'] == 'runtime_unbound': current.pop(event['judgment_id'], None)
    return list(current.values())


def paused(store):
    events = [e for e in store.events() if e['kind'] == 'runtime_paused']
    return bool(events and events[-1]['data']['paused'])


def doctor(store, project):
    root = Path(project).resolve(); checks = []
    for host in ('codex', 'claude-code'):
        manifest = store.root / ('host-' + host + '.json')
        if not manifest.exists(): continue
        m = json.loads(manifest.read_text()); path = Path(m['path'])
        try: present = m['entry'] in json.loads(path.read_text()).get('hooks', {}).get('PreToolUse', [])
        except (OSError, ValueError, AttributeError): present = False
        checks.append({'host': host, 'configured': present, 'path': str(path), 'trust': 'Check in host; Proofpress does not grant or infer trust.'})
    rules = []
    for b in bindings(store):
        r = store.record(b['judgment_id'], b['version'])
        rules.append({'id': r['id'], 'name': r['name'], 'version': r['version'], 'state': store.state(r), 'paths': b['paths'], 'verifier': b['verifier'], 'project_root': b['project_root']})
    events = [e for e in store.events() if e['kind'] == 'runtime_checked']
    last = events[-1] if events else None
    return {'doctor': True, 'project': str(root), 'workspace': str(store.root.resolve()), 'paused': paused(store),
            'skills': [a for a, p in AGENTS.items() if (root/p/'proofpress/SKILL.md').is_file()],
            'hosts': checks, 'bindings': rules, 'last_check': {'at': last['at'], **last['data']['result']} if last else None,
            'audit': store.audit()}


def uninstall(store, project, confirmed=False):
    import hashlib
    root=Path(project).resolve(); removed=[]; preserved=[]
    manifest=store.root/'skills.json'
    files=json.loads(manifest.read_text()) if manifest.exists() else {}
    for name, expected in files.items():
        path=Path(name)
        if not path.is_relative_to(root): raise JudgmentError('Skill manifest belongs to another project')
        check_path(path,root)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                preserved.append(name); continue
            removed.append(name)
    hosts=[h for h in ('codex','claude-code') if (store.root/('host-'+h+'.json')).exists()]
    for host in hosts:
        m=json.loads((store.root/('host-'+host+'.json')).read_text())
        if not Path(m['path']).is_relative_to(root): raise JudgmentError('Hook belongs to another project')
        remove(store,host,False)  # Preflight before changing any files.
    if confirmed:
        for host in hosts: remove(store,host,True)
        for name in removed: Path(name).unlink()
        if manifest.exists(): atomic_json(manifest,{k:v for k,v in files.items() if k not in removed})
    return {'review_result':('Removed integration. Restart your agent. Judgment store preserved.' if confirmed else 'Preview: '+str(len(removed))+' skill files and '+str(len(hosts))+' hooks. Repeat with --confirm.')+(' Edited skill files preserved: '+', '.join(preserved) if preserved else '')}
