"""A separate hands-on workspace for the real agent hook walkthrough."""
import argparse
import copy
import json
from pathlib import Path

from judgment_layer.model import now
from judgment_layer.store import Store, initialize
from judgment_layer.runtime import bind
from judgment_layer.presentation import color, status, record_lines, scalar
import textwrap
import shutil
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def setup(root):
    if root.exists():
        raise ValueError('Hook demo already exists. Your existing files were preserved.')
    root.mkdir(parents=True)
    (root/'schema').mkdir()
    (root/'generated').mkdir()
    (root/'schema'/'user.json').write_text('{"fields": ["name"]}\n')
    (root/'generated'/'user.py').write_text('# Generated from schema/user.json\nFIELDS = ["name"]\n')
    initialize(root/'.judgment', 'human:playground')
    example = json.loads((ROOT.parents[1]/'examples'/'coding.json').read_text())
    example['provenance']['recorded_at'] = now()
    example['provenance']['judged_by'] = 'human:playground'
    example['description'] = 'Protect generated code in this local coding demo.'
    store = Store(root/'.judgment')
    try:
        with store.transaction():
            item = store.capture(example)
    finally:
        store.close()
    return item


def main():
    parser=argparse.ArgumentParser(prog='./hook-demo')
    parser.add_argument('command', choices=['setup', 'review', 'bind', 'run', 'inspect', 'revise'])
    parser.add_argument('--details', action='store_true', help='Show the full record before review')
    parser.add_argument('--root', type=Path, default=ROOT/'hook-sandbox', help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.command == 'revise':
        store = Store(args.root/'.judgment')
        try:
            with store.transaction():
                rows = [store.describe(json.loads(r[0])) for r in store.db.execute('SELECT body FROM revisions ORDER BY rowid')]
                admitted = [r for r in rows if r['state'] == 'admitted']
                if len(admitted) != 1 or any(r['state'] in {'proposed','needs_changes'} for r in rows):
                    raise ValueError('Expected one admitted judgment and no pending revision.')
                prior = admitted[0]
                doc = copy.deepcopy(prior['record'])
                doc.pop('id'); doc.pop('version')
                doc['links'] = []
                doc['judgment']['statement'] = 'For this demo, allow direct edits to generated/user.py.'
                doc['judgment']['rationale'] = 'This hypothetical one-file exception is proposed for the local demo.'
                doc['judgment']['assertion'] = {'key':'demo-generated-user-edit','value':'allow-direct'}
                doc['applicability']['when'] = []
                doc['applicability']['limits'] = ['Only generated/user.py in this demo. Other generated files remain outside this exception.']
                doc['provenance']['recorded_at'] = now()
                doc['provenance']['source_refs'] = ['synthetic://hook-demo/proposed-email-exception']
                doc['evidence'] = [{'reference':'synthetic://hook-demo/proposed-email-exception','role':'context',
                                    'summary':'A hypothetical change for this local walkthrough.'}]
                item = store.capture(doc, prior['id'], 'Propose a local exception for this demo', prior['digest'])
        finally:
            store.close()
        print(color('accent', 'Proofpress · Revise') + '  ' + status(item['state']) + '  v' + str(item['version']))
        print('Proposed  Allow direct edits to generated/user.py.')
        print('Current   v'+str(prior['version'])+' remains admitted until you review v'+str(item['version'])+'.')
        print('Next      ./hook-demo review')
        return
    if args.command == 'inspect':
        root = args.root.resolve()
        store = Store(root/'.judgment')
        try:
            with store.transaction():
                events = store.events()
                checks = [e for e in events if e['kind']=='runtime_checked' and e['data'].get('tool_name')=='apply_patch']
                bindings = [e for e in events if e['kind']=='runtime_bound']
                if not checks or not bindings:
                    raise ValueError('Run the coding task after binding the judgment first.')
                binding = bindings[-1]['data']['policy']
                record = store.record(binding['judgment_id'], binding['version'])
                state = store.state(record)
                outcome = checks[-1]['data']['result']
        finally:
            store.close()
        print(color('accent', 'Proofpress · Inspect'))
        print('Judgment  '+status(state)+' · v'+str(binding['version']))
        print('Rule      '+record['judgment']['statement'])
        print('Hook      '+color('add' if outcome['ok'] else 'del', 'passed' if outcome['ok'] else 'blocked'))
        print('Reason    '+outcome['reason'])
        print('File      generated/user.py')
        for line in (root/'generated'/'user.py').read_text().splitlines():
            print('  '+line)
        return
    if args.command == 'run':
        root = args.root.resolve()
        store = Store(root/'.judgment')
        try:
            with store.transaction():
                if not any(e['kind']=='runtime_bound' for e in store.events()):
                    raise ValueError('No binding found. Run ./hook-demo bind first.')
                before_seq = len(store.events())
        finally:
            store.close()
        target = root/'generated'/'user.py'
        before = target.read_bytes()
        command = shlex.join([sys.executable, '-m', 'judgment_layer.cli', '--workspace', str(root/'.judgment'), 'hook'])
        hooks = '[{matcher=".*",hooks=[{type="command",command='+json.dumps(command)+',timeout=20}]}]'
        prompt = ('Use apply_patch exactly once to update generated/user.py by adding "email" to FIELDS. '
                  'The exact current file content is: ' + json.dumps(before.decode('utf-8'), ensure_ascii=False) +
                  '. Do not read files or run shell commands. If denied, report the denial and stop. '
                  'This is an isolated coding demonstration.')
        print(color('accent', 'Proofpress · Coding task'), flush=True)
        print('Agent  Adding email to the generated client…', flush=True)
        try:
            result = subprocess.run(['codex','exec','--ignore-user-config','--ephemeral',
                '--dangerously-bypass-hook-trust','--sandbox','workspace-write','--skip-git-repo-check',
                '--json','-c','hooks.PreToolUse='+hooks,prompt], cwd=root, stdin=subprocess.DEVNULL,
                capture_output=True,text=True,timeout=90)
        except subprocess.TimeoutExpired:
            print(color('del', 'Agent timed out. No hook result verified.'))
            return
        store = Store(root/'.judgment')
        try:
            with store.transaction():
                events=[e for e in store.events()[before_seq:] if e['kind']=='runtime_checked' and e['data'].get('tool_name')=='apply_patch']
        finally:
            store.close()
        if events:
            outcome=events[-1]['data']['result']
            print(color('add' if outcome['ok'] else 'del', 'Hook  '+('passed' if outcome['ok'] else 'blocked')))
            print('Why   '+outcome['reason'])
        else:
            print(color('move', 'Hook  No patch check observed'))
        after = target.read_bytes()
        print('File  '+('unchanged' if after==before else 'changed'))
        messages=[]
        changes=[]
        for line in result.stdout.splitlines():
            try: event=json.loads(line)
            except ValueError: continue
            item=event.get('item', {})
            if event.get('type')=='item.completed' and item.get('type')=='agent_message':
                messages.append(item.get('text',''))
            if event.get('type')=='item.completed' and item.get('type')=='file_change':
                changes.append(item.get('status','unknown'))
        if changes:
            print('Patch '+', '.join(changes))
        if messages:
            print('Agent '+ ' '.join(messages[-1].split())[:400])
        if result.returncode:
            print(color('del', 'Agent failed; no successful run claimed.'))
        elif events and events[-1]['data']['result']['ok'] and after==before:
            print(color('move', 'Task  No file change; inspect the agent result before retrying.'))
        if events:
            print('Next  Inspect the result with ./hook-demo inspect.')
        return
    if args.command == 'bind':
        store = Store(args.root/'.judgment')
        try:
            with store.transaction():
                rows = [store.describe(json.loads(r[0])) for r in store.db.execute('SELECT body FROM revisions ORDER BY rowid')]
                admitted = [r for r in rows if r['state'] == 'admitted']
                if len(admitted) != 1:
                    raise ValueError('Expected one admitted judgment. Review the current judgment first.')
                item = admitted[0]
            allow_email = item['record']['judgment'].get('assertion') == {'key':'demo-generated-user-edit','value':'allow-direct'}
            policy = {'project_root':str(args.root.resolve()), 'scope':item['record']['applicability']['scope'],
                      'judgment_id':item['id'], 'version':item['version'], 'digest':item['digest'],
                      'verifier':'require_conditions' if allow_email else 'deny_generated_write',
                      'paths':['generated/user.py'] if allow_email else ['generated/*']}
            print(color('accent', 'Proofpress · Bind') + '  ' + status(item['state']) + '  v' + str(item['version']))
            print('Protect  '+('generated/user.py' if allow_email else 'generated/*'))
            print('Action   '+('Allow direct edits to this file while this version is current.' if allow_email else 'Block direct edits; change the schema and regenerate.'))
            print('Scope    This demo workspace')
            if input('Type BIND to confirm: ') != 'BIND':
                print('No change.')
                return
            with store.transaction():
                bind(store, policy, True)
            print(color('add', 'Binding saved'))
            print('Next  Run the coding task with the hook.')
        finally:
            store.close()
        return
    if args.command == 'review':
        store = Store(args.root/'.judgment')
        try:
            with store.transaction():
                rows = [store.describe(json.loads(r[0])) for r in store.db.execute('SELECT body FROM revisions ORDER BY rowid')]
                pending = [r for r in rows if r['state'] in {'proposed', 'needs_changes'}]
                if not pending:
                    raise ValueError('No judgment waiting for review.')
                item = pending[-1]
            override = None
            while True:
                r = item['record']
                assertion = r['judgment'].get('assertion')
                allow = (assertion == {'key':'demo-generated-user-edit','value':'allow-direct'}
                         and r['judgment']['statement'] == 'For this demo, allow direct edits to generated/user.py.')
                block = (r['judgment']['statement'] == 'Change the source schema and regenerate the client instead of editing generated SDK files directly.'
                         and r['applicability']['scope'] == 'coding/generated-files'
                         and r['applicability']['when'] == [{'field':'generated_file','equals':True}])
                if override is not None:
                    allow, block = override == 'p', override == 'b'
                policy = None
                if allow or block:
                    policy = {'project_root':str(args.root.resolve()), 'scope':r['applicability']['scope'],
                              'judgment_id':item['id'], 'version':item['version'], 'digest':item['digest'],
                              'verifier':'require_conditions' if allow else 'deny_generated_write',
                              'paths':['generated/user.py'] if allow else ['generated/*']}
                if args.details:
                    print('\n'.join(record_lines(item, detailed=True, identity=True)))
                else:
                    width = max(30, min(shutil.get_terminal_size((80, 24)).columns, 88) - 4)
                    def section(label, value):
                        print(color('accent', label))
                        print(textwrap.fill(value, width=width, initial_indent='  ', subsequent_indent='  ', break_long_words=False, break_on_hyphens=False))
                    print(color('accent', 'Proofpress · Review') + '  ' + status(item['state']) + '  v' + str(item['version']))
                    section('Judgment', r['judgment']['statement'])
                    section('Why', r['judgment']['rationale'] or 'Not recorded')
                    section('Scope', r['applicability']['scope'])
                    for condition in r['applicability']['when']:
                        section('When', condition['field'] + ' = ' + scalar(condition['equals']))
                    for limit in r['applicability']['limits']:
                        section('Limit', limit)
                    for key in ('valid_from', 'valid_until'):
                        if key in r['applicability']:
                            section(key.replace('_', ' ').title(), r['applicability'][key])
                    if item.get('flags'):
                        section('Paused', 'Conflict or uncertainty detected. Inspect the full record before deciding.')
                    print(color('dim', 'Full record: ./hook-demo review --details'))
                print(color('accent', 'Enforcement'))
                if policy:
                    print('  '+('Allow direct edits to generated/user.py while this version is current.' if allow else
                                 'Block direct edits to generated/*; change the schema and regenerate.'))
                    print('  Host: Codex apply_patch in this demo; other tool paths are not covered by this preview.')
                    print('  Hook is loaded when you run the coding task; it is not installed globally.')
                    choice = input('[A] Approve and bind  [E] Edit  [C] Cancel: ').strip().lower()
                else:
                    print('  No reviewed hook is defined for this edited judgment.')
                    choice = input('[B] Propose block  [P] Propose allow  [E] Edit  [C] Cancel: ').strip().lower()
                    if choice in {'b', 'p'}:
                        override = choice
                        print('Review the proposed enforcement below.\n')
                        continue
                if choice == 'e':
                    doc = copy.deepcopy(r)
                    doc.pop('id'); doc.pop('version')
                    doc['links'] = [link for link in doc['links'] if link['relation'] != 'revises']
                    print('Leave a field empty to keep its current value.')
                    statement = input('Judgment: ').strip()
                    rationale = input('Why: ').strip()
                    scope = input('Scope: ').strip()
                    if not (statement or rationale or scope):
                        print('No edits.'); continue
                    if statement:
                        doc['judgment']['statement'] = statement
                        doc['judgment'].pop('assertion', None)
                    if rationale: doc['judgment']['rationale'] = rationale
                    if scope: doc['applicability']['scope'] = scope
                    doc['provenance']['recorded_at'] = now()
                    doc['provenance']['recorded_by'] = 'human:playground'
                    doc['provenance']['capture_method'] = 'explicit'
                    doc['provenance']['source_refs'].append('local://hook-demo/review-edit')
                    with store.transaction():
                        item = store.capture(doc, item['id'], 'Human edited the candidate in review', item['digest'])
                    override = None
                    print('Saved as proposed v'+str(item['version'])+'. Review again.\n')
                    continue
                if choice != 'a' or policy is None:
                    print('No change.')
                    return
                # Both events succeed or roll back together, and the human reviewed this exact policy.
                with store.transaction():
                    result = store.owner_action(item['id'], item['version'], item['digest'], 'admit', 'Reviewed judgment and enforcement in hook demo', True)
                    bind(store, policy, True)
                print(color('add', 'Approved and bound · v'+str(result['version'])))
                print('Next  Run the coding task with the hook.')
                return
        finally:
            store.close()
        return
    try:
        item=setup(args.root)
    except ValueError as exc:
        parser.exit(2, 'Error: '+str(exc)+'\n')
    print('Hook demo ready · hook-sandbox/')
    print('Judgment  proposed · '+item['name'])
    print('Task  Add an email field to the user schema and generated client.')
    print('Next  Review the judgment with Proofpress.')

if __name__=='__main__':main()
