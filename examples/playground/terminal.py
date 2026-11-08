"""Proofpress demo views. Detailed data is explicit, even when piped."""
import json
from judgment_layer.presentation import color, status, record_lines, applicability


def brief(text, size=160):
    line = " ".join(str(text).split())
    return line if len(line) <= size else line[:size-1] + "…"


def display(command, result, as_json=False, details=False):
    if as_json:
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
        return
    print(color('accent', 'Proofpress · ' + command))
    if command == 'inspect':
        print(f"{len(result['records'])} judgment revisions · {len(result['runs'])} runs")
        for item in result['records']:
            if details:
                print("\n".join(record_lines(item, detailed=True)))
            else:
                print(f"{status(item['state'])}  {item['name']} v{item['version']}")
        if result['runs']:
            last = result['runs'][-1]
            count = len(last['input']['context']['judgments'])
            print(f"Latest  {status(last['status'])} · Context {count} · {last['id']}")
        print('Details  ./proofpress inspect --details')
    elif command == 'history':
        sessions = result if isinstance(result, list) else [result]
        if not sessions:
            print('No sessions. Start with ./proofpress run')
        visible = sessions if details else sessions[-3:]
        for session in visible:
            label = session['id'] if details else 'Session'
            print(label + ' · ' + session['metadata'].get('description', ''))
            if not details:
                corrections = [e['annotation']['content'] for e in session['events'] if (e.get('annotation') or {}).get('category') == 'correction']
                judgments = [e['decision']['description'] for e in session['events'] if e.get('decision')]
                if corrections or judgments:
                    print('  ' + brief((corrections or judgments)[-1], 100))
                continue
            for event in session['events']:
                body = event.get('decision') or event.get('annotation') or event.get('contribution') or event.get('tool_call') or {}
                label = {'decision':'judgment', 'annotation':'correction' if body.get('category') == 'correction' else 'note'}.get(event['type'], event['type'])
                text = body.get('description') or body.get('content') or body.get('name', '')
                print('  ' + label + ' · ' + (text if details else brief(text)))
        if len(sessions) > len(visible):
            print(f'{len(sessions)-len(visible)} older sessions · use --details')
        print('Full records  ./proofpress history --json')
    elif command == 'install':
        print('Workspace ready · manual admission')
        print('Next  ./proofpress run')
    elif command == 'run':
        print(status(result['status']) + ' · ' + result['id'])
        print(f"Context {len(result['input']['context']['judgments'])} · applicable judgments supplied")
        if result.get('error'):
            print(color('del', result['error']))
        if result.get('output'):
            output = result['output']
            print('Judgment  ' + (output['choice'] if details else brief(output['choice'])))
            if details:
                print('Why  ' + output['rationale'])
                print(output['code'])
            print('Code and tests saved; not executed.')
        print('Files  sandbox/runs/' + result['id'])
    elif 'record' in result:
        reviewing = command in {'review', 'withdraw'}
        print("\n".join(record_lines(result, detailed=reviewing or details, identity=details)))
        if not reviewing and not details:
            print("\n".join(applicability(result['record']['applicability'])))
        if not reviewing and result['state'] == 'proposed':
            print('Next  ./proofpress review')
    else:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
