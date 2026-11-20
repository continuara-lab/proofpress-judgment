"""Synthetic native-event contracts, including automatic retry and handoff."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from judgment_layer.behavior import AUTOMATIC
from judgment_layer.cursor import lifecycle_handle as cursor
from judgment_layer.hosts import doctor, install as action_install, uninstall
from judgment_layer.lifecycle import handle, install, manifest_path, remove
from judgment_layer.model import JudgmentError
from judgment_layer.store import Store, initialize
from judgment_layer.tasks import latest
from judgment_layer.workflows import attached, finish_files, plan, status

ROOT = Path(__file__).resolve().parents[1]


class NativeCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.ws = self.root / '.judgment'
        initialize(self.ws, 'human:synthetic-native-fixture')
        self.store = Store(self.ws)
        self.doc = json.loads((ROOT / 'examples/behavior-judgment.json').read_text())
        self.doc['applicability'].pop('task_criteria')
        self.doc['behavior']['hooks'] = [self.doc['behavior']['hooks'][2]]
        (self.root / 'api').mkdir()
        (self.root / 'api/schema.yaml').write_text('synthetic source')
        item = self.store.capture(self.doc)
        self.store.owner_action(item['id'], 1, item['digest'], 'admit', 'Synthetic fixture only', True)
        self.mock = patch('judgment_layer.behavior.assess', return_value={'choice': 'pass'})
        self.assess = self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.store.close()
        self.temp.cleanup()

    def codex(self, kind, turn='turn-one', **fields):
        return {'hook_event_name': kind, 'session_id': 'codex-fixture', 'turn_id': turn,
                'cwd': str(self.root), **fields}

    def cevent(self, kind, generation='generation-one', **fields):
        return {'hook_event_name': kind, 'conversation_id': 'cursor-fixture', 'generation_id': generation,
                'workspace_roots': [str(self.root)], **fields}

    def cursor_start(self, generation='generation-one', prompt='Synthetic API change'):
        self.assertEqual(cursor(self.ws, self.cevent('beforeSubmitPrompt', generation, prompt=prompt)), {'continue': True})
        return attached(self.store, {'host': 'cursor', 'session_id': 'cursor-fixture'})

    def cursor_response(self, generation='generation-one', text='Synthetic final response'):
        return cursor(self.ws, self.cevent('afterAgentResponse', generation, text=text))

    def cursor_stop(self, generation='generation-one', loop_count=0, **fields):
        return cursor(self.ws, self.cevent('stop', generation, status='completed', loop_count=loop_count, **fields))

    def test_codex_prompt_prepares_and_stop_automatically_reviews_real_response(self):
        response = handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', prompt='Synthetic task'), 'codex')
        packet = json.loads(response['hookSpecificOutput']['additionalContext'])['proofpress']
        self.assertFalse(packet['requires_plan'])
        event = self.codex('Stop', last_assistant_message='Actual native fixture response', stop_hook_active=False)
        self.assertEqual(handle(self.ws, AUTOMATIC, event, 'codex'), {})
        self.assertEqual(handle(self.ws, AUTOMATIC, event, 'codex'), {})
        self.assertEqual(self.assess.call_count, 1)
        self.assertEqual(self.assess.call_args.args[0]['artifacts']['@response'], 'Actual native fixture response')

    def test_codex_repair_continuation_keeps_same_task_and_bounded_retry(self):
        packet = handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', prompt='Synthetic task'), 'codex')
        task = json.loads(packet['hookSpecificOutput']['additionalContext'])['proofpress']['task_id']
        self.assess.return_value = {'choice': 'violation'}
        first = handle(self.ws, AUTOMATIC, self.codex('Stop', last_assistant_message='First response'), 'codex')
        self.assertEqual(first['decision'], 'block')
        self.assertTrue(first['reason'].startswith('proofpress resume task ' + task + '\n'))
        handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', 'turn-two', prompt=first['reason']), 'codex')
        self.assertEqual(len([e for e in self.store.events() if e['kind'] == 'task_prepared']), 1)
        second = handle(self.ws, AUTOMATIC, self.codex('Stop', 'turn-two', last_assistant_message='Second response'), 'codex')
        self.assertFalse(second['continue'])
        self.assertIn('systemMessage', second)
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')

    def test_codex_repair_can_pass_and_stale_turn_cannot_approve_new_task(self):
        handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', prompt='Synthetic task'), 'codex')
        self.assess.return_value = {'choice': 'violation'}
        retry = handle(self.ws, AUTOMATIC, self.codex('Stop', last_assistant_message='Wrong'), 'codex')
        handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', 'turn-two', prompt=retry['reason']), 'codex')
        self.assess.return_value = {'choice': 'pass'}
        self.assertEqual(handle(self.ws, AUTOMATIC, self.codex('Stop', 'turn-two', last_assistant_message='Fixed'), 'codex'), {})
        stale = handle(self.ws, AUTOMATIC, self.codex('Stop', last_assistant_message='Old'), 'codex')
        self.assertFalse(stale['continue'])

    def test_codex_unknown_pauses_with_warning_and_pretool_has_only_supported_fields(self):
        handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', prompt='Synthetic task'), 'codex')
        self.assess.return_value = {'choice': 'unknown'}
        result = handle(self.ws, AUTOMATIC, self.codex('Stop', last_assistant_message='Response'), 'codex')
        self.assertFalse(result['continue'])
        self.assertIn('systemMessage', result)
        denied = handle(self.ws, AUTOMATIC, self.codex('PreToolUse', tool_name='Bash', tool_input={'command': 'arbitrary'}), 'codex')
        self.assertEqual(set(denied), {'hookSpecificOutput'})
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_codex_missing_response_invalidates_earlier_completion_receipt(self):
        result = handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', prompt='Synthetic task'), 'codex')
        task = json.loads(result['hookSpecificOutput']['additionalContext'])['proofpress']['task_id']
        handle(self.ws, AUTOMATIC, self.codex('Stop', last_assistant_message='First response'), 'codex')
        self.assertEqual(status(self.store, task)['state'], 'ready')
        self.assertFalse(handle(self.ws, AUTOMATIC, self.codex('Stop'), 'codex')['continue'])
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')

    def test_project_subdirectory_events_work_but_foreign_projects_do_not(self):
        result = handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', cwd=str(self.root / 'api'), prompt='Task'), 'codex')
        self.assertIn('hookSpecificOutput', result)
        self.assertEqual(handle(self.ws, AUTOMATIC, self.codex('UserPromptSubmit', cwd=str(self.root.parent), prompt='Foreign'), 'codex')['decision'], 'block')
        self.assertEqual(cursor(self.ws, self.cevent('beforeSubmitPrompt', cwd=str(self.root / 'api'), prompt='Task')), {'continue': True})

    def test_cursor_context_is_automatically_delivered_before_first_tool(self):
        task = self.cursor_start()
        event = self.cevent('preToolUse', tool_name='Read', tool_input={'path': 'api/schema.yaml'})
        first = cursor(self.ws, event)
        self.assertEqual(first['permission'], 'deny')
        self.assertIn('proofpress', first['agent_message'])
        self.assertEqual(cursor(self.ws, event), {'permission': 'allow'})
        self.assertEqual(latest(self.store, task, 'cursor_context_delivered')['data']['task_id'], task)
        self.assess.assert_not_called()

    def test_cursor_auto_completion_reviews_captured_actual_response_and_files(self):
        task = self.cursor_start()
        self.assertEqual(self.cursor_response(text='Actual Cursor text'), {})
        self.assertEqual(self.cursor_stop(), {})
        self.assertEqual(self.cursor_stop(), {})
        self.assertEqual(self.assess.call_count, 1)
        self.assertEqual(self.assess.call_args.args[0]['artifacts']['@response'], 'Actual Cursor text')
        self.assertEqual(status(self.store, task)['state'], 'ready')

    def test_cursor_violation_auto_followup_keeps_task_then_repair_passes(self):
        task = self.cursor_start()
        self.cursor_response()
        self.assess.return_value = {'choice': 'violation'}
        first = self.cursor_stop()
        self.assertEqual(set(first), {'followup_message'})
        self.assertEqual(self.cursor_start('generation-two', first['followup_message']), task)
        self.cursor_response('generation-two', 'Actual corrected response')
        self.assess.return_value = {'choice': 'pass'}
        self.assertEqual(self.cursor_stop('generation-two', 1), {})
        self.assertEqual(status(self.store, task)['state'], 'ready')
        self.assertEqual(len([e for e in self.store.events() if e['kind'] == 'task_prepared']), 1)

    def test_cursor_repeated_violation_does_not_loop_or_approve(self):
        task = self.cursor_start()
        self.cursor_response()
        self.assess.return_value = {'choice': 'violation'}
        first = self.cursor_stop()
        self.cursor_start('generation-two', first['followup_message'])
        self.cursor_response('generation-two', 'Still wrong')
        self.assertEqual(self.cursor_stop('generation-two', 1), {})
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')
        self.assertIsNotNone(latest(self.store, task, 'task_host_paused'))

    def test_cursor_unknown_handoff_is_not_reevaluated_as_new_evidence(self):
        task = self.cursor_start()
        self.cursor_response()
        self.assess.return_value = {'choice': 'unknown'}
        first = self.cursor_stop()
        self.assertIn('Ask the user', first['followup_message'])
        self.cursor_start('generation-two', first['followup_message'])
        self.cursor_response('generation-two', 'Please review this uncertainty')
        self.assess.return_value = {'choice': 'pass'}
        self.assertEqual(self.cursor_stop('generation-two', 1), {})
        self.assertEqual(self.assess.call_count, 1)
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')

    def test_cursor_missing_response_or_wrong_generation_never_inherits_pass(self):
        task = self.cursor_start()
        self.cursor_response()
        self.cursor_stop()
        self.cursor_start('generation-two', 'proofpress resume task ' + task)
        result = self.cursor_stop('generation-two')
        self.assertIn('followup_message', result)
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')
        self.assertEqual(self.assess.call_count, 1)

    def test_cursor_aborted_and_error_status_do_not_trigger_review_or_retry(self):
        task = self.cursor_start()
        self.cursor_response()
        for native_status in ('aborted', 'error'):
            self.assertEqual(cursor(self.ws, self.cevent('stop', status=native_status, loop_count=0)), {})
        self.assertEqual(status(self.store, task)['state'], 'delivery_paused')
        self.assess.assert_not_called()

    def test_cursor_multiroot_invalid_response_cache_and_foreign_session_pause(self):
        self.assertFalse(cursor(self.ws, self.cevent('beforeSubmitPrompt', prompt='Task', workspace_roots=['/one', '/two']))['continue'])
        self.cursor_start()
        self.cursor_response()
        response = next((self.ws / 'host-responses').glob('*.json'))
        response.write_text(json.dumps('tampered response'))
        self.assertIn('followup_message', self.cursor_stop())
        self.assess.assert_not_called()

    def test_installers_preserve_user_hooks_upgrade_own_action_entry_and_doctor(self):
        for host, relative, event in (('codex', '.codex/hooks.json', 'Stop'), ('cursor', '.cursor/hooks.json', 'stop')):
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            user = {'hooks': [{'type': 'command', 'command': 'echo synthetic-user'}]} if host == 'codex' else {'command': 'echo synthetic-user'}
            path.write_text(json.dumps({'hooks': {event: [user]}}))
            action_install(self.store, self.root, host, True)
            install(self.store, AUTOMATIC, True, project=self.root, host=host)
            install(self.store, AUTOMATIC, True, project=self.root, host=host)
            settings = json.loads(path.read_text())
            self.assertIn(user, settings['hooks'][event])
            self.assertEqual(len(settings['hooks'][event]), 2)
            self.assertFalse((self.ws / ('host-' + host + '.json')).exists())
            if host == 'codex':
                self.assertNotIn('onFailure', settings['hooks']['PreToolUse'][0]['hooks'][0])
            else:
                self.assertEqual(settings['hooks']['stop'][-1]['loop_limit'], 1)
            self.assertTrue(any(h['host'] == host + ' lifecycle' for h in doctor(self.store, self.root)['hosts']))
            remove(self.store, AUTOMATIC, True, host)
            self.assertEqual(json.loads(path.read_text())['hooks'][event], [user])

    def test_uninstall_removes_all_native_hosts_and_preserves_store(self):
        for host in ('codex', 'cursor', 'claude-code'):
            install(self.store, AUTOMATIC, True, project=self.root, host=host)
        uninstall(self.store, self.root, True)
        for host in ('codex', 'cursor', 'claude-code'):
            self.assertFalse(manifest_path(self.store, host).exists())
        self.assertTrue((self.ws / 'store.sqlite3').exists())

    def test_cli_cursor_completion_has_native_output_and_invalid_env_fails_closed(self):
        bad_env = self.root / 'invalid.env'
        bad_env.write_text('UNSUPPORTED=synthetic')
        proc = subprocess.run([sys.executable, '-m', 'judgment_layer.cli', '--workspace', str(self.ws),
                               '--env-file', str(bad_env), 'behavior-hook', '--host', 'cursor'],
                              input=json.dumps(self.cevent('preToolUse', tool_name='Write', tool_input={'path': 'api/schema.yaml'})),
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['permission'], 'deny')

    def test_cli_native_flow_denies_actual_write_until_plan_for_both_hosts(self):
        doc = json.loads((ROOT / 'examples/behavior-judgment.json').read_text())
        doc['applicability'].pop('task_criteria')
        item = self.store.capture(doc)
        self.store.owner_action(item['id'], 1, item['digest'], 'admit', 'Synthetic fixture only', True)
        script = ('from unittest.mock import patch; from judgment_layer.cli import main; import sys; '
                  'p=patch("judgment_layer.behavior.assess",return_value={"choice":"pass"});p.start(); sys.exit(main())')

        def call(host, event=None, args=None):
            proc = subprocess.run([sys.executable, '-c', script, '--workspace', str(self.ws),
                                   *(args or ['behavior-hook', '--host', host])],
                                  input=json.dumps(event) if event else None, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

        for host in ('codex', 'cursor'):
            if host == 'codex':
                packet = call(host, self.codex('UserPromptSubmit', prompt='Synthetic schema change'))
                task = json.loads(packet['hookSpecificOutput']['additionalContext'])['proofpress']['task_id']
                action = self.codex('PreToolUse', tool_name='apply_patch', tool_input={
                    'command': '*** Begin Patch\n*** Update File: api/schema.yaml\n@@\n-synthetic source\n+synthetic actual output\n*** End Patch'})
                self.assertEqual(call(host, action)['hookSpecificOutput']['permissionDecision'], 'deny')
            else:
                call(host, self.cevent('beforeSubmitPrompt', prompt='Synthetic schema change'))
                task = attached(self.store, {'host': 'cursor', 'session_id': 'cursor-fixture'})
                action = self.cevent('preToolUse', tool_name='Write', tool_input={
                    'path': 'api/schema.yaml', 'content': 'synthetic actual output'})
                self.assertEqual(call(host, action)['permission'], 'deny')  # Context packet.
                self.assertEqual(call(host, action)['permission'], 'deny')  # Plan still missing.
            path = self.root / 'api/schema.yaml'
            self.assertEqual(path.read_text(), 'synthetic source')
            prepared = latest(self.store, task, 'task_prepared')
            from judgment_layer.workflows import plan_path
            draft = plan_path(self.store, task)
            draft.parent.mkdir(exist_ok=True)
            draft.write_text('Change source schema and regenerate the fixture client')
            call(host, args=['task-plan', '--task', task, '--context', prepared['event_id'], '--plan', str(draft), '--json'])
            allowed = call(host, action)
            self.assertEqual(allowed, {} if host == 'codex' else {'permission': 'allow'})
            path.write_text('synthetic actual output')  # Harness honors the native verdict before writing.
            if host == 'codex':
                self.assertEqual(call(host, self.codex('Stop', last_assistant_message='Synthetic completion')), {})
            else:
                call(host, self.cevent('afterAgentResponse', text='Synthetic completion'))
                self.assertEqual(call(host, self.cevent('stop', status='completed', loop_count=0)), {})
            self.assertEqual(status(self.store, task)['state'], 'ready')
            path.write_text('synthetic source')


if __name__ == '__main__':
    unittest.main()
