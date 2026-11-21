"""Bounded normalization of logged text/tool events; never reconstruct missing execution."""
import re

from .model import canonical


def redact(value):
    from .history import scrub
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        sensitive = {'apikey', 'token', 'password', 'secret', 'clientsecret', 'authorization',
                     'accesstoken', 'refreshtoken', 'privatekey'}
        return {key: '[REDACTED]' if re.sub('[^a-z]', '', key.lower()) in sensitive else redact(item)
                for key, item in value.items()}
    return value


def content_text(value):
    # JSON arguments are often encoded as strings; decode only for redaction,
    # then preserve their structure as canonical JSON, not executable content.
    import json
    if isinstance(value, str):
        try:
            structured = json.loads(value)
        except ValueError:
            return redact(value)
        return canonical(redact(structured))
    return canonical(redact(value))


def normalize(record, agent, role, content):
    """Return events in native record/block order and visible omission counters."""
    events = []
    omitted = 0

    def text(value, message_role):
        nonlocal omitted
        if isinstance(value, str) and value:
            events.append({'kind': 'message', 'role': message_role, 'text': redact(value)})
        elif value is not None and not isinstance(value, str):
            omitted += 1

    def tool(kind, name, call_id, value, is_error=None):
        nonlocal omitted
        if kind == 'tool_result' and isinstance(value, list) and any(isinstance(p, dict) and 'type' in p for p in value):
            text_values = []
            for part in value:
                if isinstance(part, dict) and part.get('type') in {'text', 'input_text', 'output_text'} and isinstance(part.get('text'), str):
                    text_values.append(part['text'])
                else:
                    omitted += 1
            value = '\n'.join(text_values)
        events.append({'kind': kind, 'tool_name': redact(name) if isinstance(name, str) else None,
                       'call_id': redact(call_id) if isinstance(call_id, str) else None,
                       'text': content_text(value),
                       'is_error': is_error if isinstance(is_error, bool) else None})

    if agent == 'codex' and record.get('type') == 'response_item':
        payload = record.get('payload', {})
        kind = payload.get('type')
        if kind in {'function_call', 'custom_tool_call'}:
            tool('tool_call', payload.get('name'), payload.get('call_id'),
                 payload.get('arguments') if kind == 'function_call' else payload.get('input'))
            return events, omitted
        if kind in {'function_call_output', 'custom_tool_call_output'}:
            tool('tool_result', payload.get('name'), payload.get('call_id'), payload.get('output'), payload.get('is_error'))
            return events, omitted
        if kind != 'message':
            return [], 1  # Including reasoning/nontext response items; never import private reasoning.
    if agent == 'claude-code' and (record.get('isSidechain') or record.get('isMeta')):
        return [], 1
    if role not in {'user', 'assistant'}:
        return [], omitted
    if isinstance(content, str):
        text(content, role)
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                omitted += 1
                continue
            kind = part.get('type')
            if kind in {'input_text', 'output_text', 'text'}:
                text(part.get('text'), role)
            elif agent in {'claude-code', 'cursor'} and kind == 'tool_use':
                tool('tool_call', part.get('name'), part.get('id'), part.get('input'))
            elif agent in {'claude-code', 'cursor'} and kind == 'tool_result':
                tool('tool_result', part.get('name'), part.get('tool_use_id'), part.get('content'), part.get('is_error'))
            else:
                omitted += 1
    return events, omitted


def coverage(include_tools):
    return {'mode': 'text_and_tools' if include_tools else 'text_only',
            'complete_trajectory': False,
            'boundary': 'Selected logged excerpts only; not a complete trajectory audit or verified execution.',
            'excluded': ['system/developer messages', 'private reasoning', 'recognized images/nontext blocks', 'Claude sidechains/meta records',
                         'unsupported event shapes', 'events absent from the selected local log']}


def entries(batch):
    return batch.get('events', batch['messages'])


def source_entries(batch):
    # Both immutable representations can be cited. Extraction still consumes only
    # the ordered normalized view when tools were explicitly included.
    return list({item['source_ref']: item for item in [*batch['messages'], *batch.get('events', [])]}.values())


def tool_links(events):
    """Batch-local links from explicit native ids, with no invented success verdict."""
    links = {}
    unlinked = []
    for event in events:
        kind = event.get('kind')
        if kind not in {'tool_call', 'tool_result'}:
            continue
        call_id = event.get('call_id')
        if not call_id:
            unlinked.append(event['source_ref'])
            continue
        item = links.setdefault(call_id, {'call_id': call_id, 'calls': [], 'results': []})
        item['calls' if kind == 'tool_call' else 'results'].append(event['source_ref'])
    return {'by_call_id': list(links.values()), 'without_call_id': unlinked,
            'boundary': 'Links within selected excerpt only. Missing counterparts may occur in other batches or be absent; execution success is not verified.'}
