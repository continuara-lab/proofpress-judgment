"""Synthetic logs only. Importing a tool result does not verify execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from judgment_layer.cli import parser, run
from judgment_layer.history import consolidate, ingest, preview, read_source
from judgment_layer.history_events import entries, tool_links
from judgment_layer.model import JudgmentError, digest
from judgment_layer.review_policy import review_assist, update_review_policy
from judgment_layer.store import Store, initialize

ROOT = Path(__file__).resolve().parents[1]


class ToolHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        initialize(self.root / 'store', 'human:synthetic-tool-history')
        self.store = Store(self.root / 'store')
        self.path = self.root / 'fixture.jsonl'
        self.rows = [
            {'type': 'session_meta', 'payload': {'id': 'synthetic-tool-log', 'cwd': str(self.root)}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
             'content': [{'type': 'input_text', 'text': 'Check the actual result before claiming success.'}]}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'read_file', 'call_id': 'call-fixture',
             'arguments': json.dumps({'path': 'synthetic.txt', 'api_key': 'synthetic-private-value'})}},
            {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'call-fixture',
             'output': 'Synthetic error: file does not exist', 'is_error': True}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
             'content': [{'type': 'output_text', 'text': 'The file was not found.'}]}}
        ]
        self.write(self.rows)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def write(self, rows):
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def op(self, function):
        with self.store.transaction():
            return function()

    def test_default_stays_text_only_and_discloses_incompleteness(self):
        batch = read_source(self.path, self.root)
        self.assertEqual(len(batch['messages']), 2)
        self.assertNotIn('events', batch)
        self.assertFalse(batch['coverage']['complete_trajectory'])
        self.assertEqual(batch['coverage']['mode'], 'text_only')
        self.assertNotIn('call-fixture', json.dumps(entries(batch)))

    def test_codex_order_ids_source_ranges_and_nested_secret_redaction(self):
        batch = read_source(self.path, self.root, include_tools=True)
        events = batch['events']
        self.assertEqual([item['kind'] for item in events], ['message', 'tool_call', 'tool_result', 'message'])
        self.assertEqual(events[1]['call_id'], events[2]['call_id'])
        self.assertTrue(events[2]['is_error'])
        self.assertIsNone(events[1]['is_error'])
        self.assertNotIn('synthetic-private-value', json.dumps(batch))
        self.assertIn('[REDACTED]', events[1]['text'])
        self.assertEqual(len({item['source_ref'] for item in events}), 4)
        self.assertTrue(all('/bytes/' in item['source_ref'] and '/events/' in item['source_ref'] for item in events))
        self.assertEqual([item['record_offset'] for item in events], sorted(item['record_offset'] for item in events))
        self.assertFalse(batch['coverage']['complete_trajectory'])

    def test_custom_tool_calls_and_missing_result_remain_unverified(self):
        self.write([self.rows[0], {'type': 'response_item', 'payload': {
            'type': 'custom_tool_call', 'name': 'apply_patch', 'call_id': 'missing-result', 'input': 'synthetic patch'}}])
        events = read_source(self.path, self.root, include_tools=True)['events']
        links = tool_links(events)
        self.assertEqual(links['by_call_id'][0]['results'], [])
        self.assertIsNone(events[0]['is_error'])
        self.assertNotIn('success', events[0])

    def test_custom_result_without_call_and_missing_native_ids_are_not_fabricated(self):
        self.write([self.rows[0], {'type': 'response_item', 'payload': {
            'type': 'custom_tool_call_output', 'call_id': 'orphan-result', 'output': 'logged output'}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'unknown-call', 'arguments': '{}'}}])
        batch = read_source(self.path, self.root, include_tools=True)
        self.assertEqual(batch['events'][0]['kind'], 'tool_result')
        self.assertEqual(batch['tool_links']['by_call_id'][0]['calls'], [])
        self.assertEqual(batch['tool_links']['without_call_id'], [batch['events'][1]['source_ref']])

    def test_claude_mixed_blocks_keep_order_and_skip_thinking_images_sidechains(self):
        meta = {'sessionId': 'synthetic-claude', 'cwd': str(self.root)}
        self.write([
            {'type': 'user', **meta, 'message': {'role': 'user', 'content': 'Inspect this'}},
            {'type': 'assistant', **meta, 'message': {'role': 'assistant', 'content': [
                {'type': 'text', 'text': 'Before call'},
                {'type': 'thinking', 'thinking': 'excluded-private-reasoning'},
                {'type': 'tool_use', 'id': 'tool-fixture', 'name': 'Read', 'input': {'nested': {'password': 'synthetic-secret'}}},
                {'type': 'text', 'text': 'After call'}]}},
            {'type': 'user', **meta, 'message': {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': 'tool-fixture', 'content': [
                    {'type': 'text', 'text': 'Actual logged output'},
                    {'type': 'image', 'data': 'excluded-image-body'}]}]}},
            {'type': 'assistant', **meta, 'isSidechain': True, 'message': {'role': 'assistant', 'content': 'excluded-sidechain'}}
        ])
        batch = read_source(self.path, self.root, agent='claude-code', include_tools=True)
        self.assertEqual([item['kind'] for item in batch['events']], ['message', 'message', 'tool_call', 'message', 'tool_result'])
        self.assertEqual(batch['events'][2]['call_id'], 'tool-fixture')
        self.assertIsNone(batch['events'][-1]['is_error'])
        serialized = json.dumps(batch)
        for excluded in ('excluded-private-reasoning', 'excluded-image-body', 'excluded-sidechain', 'synthetic-secret'):
            self.assertNotIn(excluded, serialized)
        self.assertGreaterEqual(batch['omitted_blocks'], 3)

    def test_cursor_compatible_tool_blocks_are_supported_without_claiming_unlogged_events(self):
        self.write([{'role': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': 'Inspecting'},
            {'type': 'tool_use', 'id': 'cursor-call', 'name': 'Read', 'input': {'path': 'synthetic.txt'}}]}},
            {'role': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'cursor-call', 'content': 'Logged output'}]}}])
        batch = read_source(self.path, self.root, agent='cursor', include_tools=True)
        self.assertEqual([item['kind'] for item in batch['events']], ['message', 'tool_call', 'tool_result'])
        self.assertFalse(batch['coverage']['complete_trajectory'])

    def test_tool_backfill_uses_independent_checkpoint_and_is_idempotent(self):
        first = self.op(lambda: ingest(self.store, self.path, self.root))
        self.assertEqual(first['messages'], 2)
        with_tools = self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        self.assertEqual(with_tools['tool_events'], 2)
        self.assertEqual(with_tools['messages'], 0)  # Original aggregate text is already stored.
        self.assertTrue(self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))['duplicate'])
        self.assertTrue(self.op(lambda: ingest(self.store, self.path, self.root))['duplicate'])
        mirror = self.root / 'mirror.jsonl'
        mirror.write_bytes(self.path.read_bytes())
        self.assertEqual(self.op(lambda: ingest(self.store, mirror, self.root, include_tools=True))['tool_events'], 0)

    def test_incremental_tool_only_append_and_partial_record(self):
        self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        row = json.dumps({'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'orphan', 'output': 'later result'}})
        with self.path.open('a') as output:
            output.write(row)
        self.assertTrue(self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))['duplicate'])
        with self.path.open('a') as output:
            output.write('\n')
        result = self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        self.assertEqual(result['tool_events'], 1)
        self.assertEqual(result['messages'], 0)

    def test_oversized_record_does_not_truncate_or_advance_checkpoint(self):
        with self.assertRaises(JudgmentError):
            read_source(self.path, self.root, limit=5, include_tools=True)
        self.assertFalse(any(e['kind'] == 'history_imported' for e in self.store.events()))

    def test_prefix_mutation_keeps_checkpoint_for_each_lane(self):
        self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        before = len(self.store.events())
        self.rows[2]['payload']['name'] = 'mutated_name'
        self.write(self.rows)
        with self.assertRaises(JudgmentError):
            self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        self.assertEqual(len(self.store.events()), before)

    def test_tool_only_batch_reaches_extractor_with_sources_and_stays_candidate(self):
        self.write([self.rows[0], self.rows[2], self.rows[3]])
        self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        batch = self.store.events()[-1]['data']['batch']
        candidate = {'name': 'Check output', 'statement': 'Do not claim success from a tool invocation alone.',
                     'rationale': 'A logged result reports an error.', 'situation': 'Synthetic missing file',
                     'polarity': 'avoid', 'source_refs': [batch['events'][1]['source_ref']], 'capture_trigger': 'agent_judgment'}
        with patch('judgment_layer.history.extract', return_value=[candidate]) as model:
            result = self.op(lambda: consolidate(self.store, 'coding', True))
            self.assertEqual(model.call_args.args[0], batch['events'])
        self.assertEqual(result['candidates'][0]['state'], 'proposed')
        self.assertEqual(self.store.record(result['candidates'][0]['id'])['provenance']['source_refs'], candidate['source_refs'])

    def test_cli_all_consolidation_processes_tool_only_batch(self):
        self.write([self.rows[0], self.rows[2], self.rows[3]])
        self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        args = parser().parse_args(['--workspace', str(self.store.root), 'consolidate',
                                    '--scope', 'coding', '--model-assessment', '--all'])
        with patch('judgment_layer.history.extract', return_value=[]) as model:
            result = run(args)
        self.assertEqual([e['kind'] for e in model.call_args.args[0]], ['tool_call', 'tool_result'])
        self.assertEqual(result['remaining_batches'], 0)

    def test_timeline_terminal_output_sanitizes_control_characters(self):
        from judgment_layer.presentation import render_text
        self.rows[2]['payload']['name'] = '\x1b[31mtool'
        self.rows[3]['payload']['output'] = '\x1b]0;untrusted title\x07'
        self.write(self.rows)
        args = parser().parse_args(['history', 'timeline', '--file', str(self.path),
                                    '--project', str(self.root), '--include-tools'])
        result = run(args)
        output = render_text('history', result)
        self.assertNotIn('\x1b', output)
        self.assertNotIn('\x07', output)

    def test_referenced_history_review_can_resolve_a_tool_source(self):
        self.op(lambda: ingest(self.store, self.path, self.root, include_tools=True))
        batch = self.store.events()[-1]['data']['batch']
        doc = json.loads((ROOT / 'examples/coding.json').read_text())
        doc['provenance']['source_refs'] = [batch['events'][2]['source_ref']]
        item = self.op(lambda: self.store.capture(doc))
        self.op(lambda: update_review_policy(self.store, {'evidence': 'referenced_history'}, True))
        with patch('judgment_layer.assessment.assess', return_value={'choice': 'unknown'}) as model:
            review_assist(self.store, item['id'])
        self.assertEqual(model.call_args.args[0]['source_excerpts'], [batch['events'][2]])

    def test_cli_timeline_requires_opt_in_and_does_not_import(self):
        argv = ['--workspace', str(self.store.root), 'history', 'timeline', '--file', str(self.path), '--project', str(self.root)]
        with self.assertRaises(JudgmentError):
            run(parser().parse_args(argv))
        result = run(parser().parse_args(argv + ['--include-tools']))
        self.assertEqual(len(result['events']), 4)
        self.assertFalse(any(e['kind'] == 'history_imported' for e in self.store.events()))

    def test_cli_timeline_byte_offset_and_import_checkpoint_ownership(self):
        offset = sum(len((json.dumps(row) + '\n').encode()) for row in self.rows[:2])
        args = ['history', 'timeline', '--file', str(self.path), '--project', str(self.root),
                '--include-tools', '--offset', str(offset)]
        result = run(parser().parse_args(args))
        self.assertEqual([e['kind'] for e in result['events']], ['tool_call', 'tool_result', 'message'])
        self.assertEqual(result['next_offset'], self.path.stat().st_size)
        args[1] = 'import'
        with self.assertRaises(JudgmentError):
            run(parser().parse_args(args))

    def test_project_preview_exposes_tool_content_choice_before_import(self):
        directory = self.root / 'sessions'
        directory.mkdir()
        (directory / 'fixture.jsonl').write_bytes(self.path.read_bytes())
        argv = ['--workspace', str(self.store.root), 'history', 'project', '--project', str(self.root), '--root', str(directory), '--include-tools']
        result = run(parser().parse_args(argv))
        self.assertEqual(result['coverage']['mode'], 'text_and_tools')
        self.assertFalse(result['imported'])
        imported = run(parser().parse_args(argv + ['--confirm']))
        self.assertEqual(imported['tool_events'], 2)
