"""Synthetic owner, provider and native-host fixtures. No real account actions."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from judgment_layer.lifecycle import handle, install, remove
from judgment_layer.model import JudgmentError, digest
from judgment_layer.runtime import gate, hook
from judgment_layer.store import Store, initialize
from judgment_layer.tasks import check_release, latest
from judgment_layer.workflows import (attach, configure, exception, export, finish_files,
                                     plan, plan_path, prepare, snapshot, status)

ROOT = Path(__file__).resolve().parents[1]


class EnforcementWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.ws = self.root / '.judgment'
        initialize(self.ws, 'human:synthetic-workflow-owner')
        self.store = Store(self.ws)
        self.doc = json.loads((ROOT / 'examples/coding.json').read_text())
        self.doc['applicability']['when'] = []
        self.scope = self.doc['applicability']['scope']
        self.item = self.admit(self.doc)
        self.policy = {'id': 'coding', 'project_root': str(self.root),
                       'mandatory_scopes': [self.scope], 'scope_criteria': {}, 'facts': {},
                       'paths': ['src/*'], 'artifacts': ['src/result.py'], 'allow_exceptions': True}
        configure(self.store, self.policy, True)
        (self.root / 'src').mkdir()
        (self.root / 'src/result.py').write_text('complete synthetic result')
        self.model = patch('judgment_layer.workflows.assess', return_value={'choice': 'pass'})
        self.assess = self.model.start()
        self.finish_model = patch('judgment_layer.tasks.assess', return_value={'choice': 'pass'})
        self.review = self.finish_model.start()

    def tearDown(self):
        self.model.stop()
        self.finish_model.stop()
        self.store.close()
        self.temp.cleanup()

    def admit(self, doc):
        item = self.store.capture(doc)
        self.store.owner_action(item['id'], item['version'], item['digest'],
                                'admit', 'Synthetic fixture only', True)
        return item

    def prepare(self):
        return prepare(self.store, 'task-fixture', 'coding', 'Regenerate the synthetic client.')

    def plan(self):
        context = self.prepare()
        self.assertTrue(context['ok'])
        return plan(self.store, 'task-fixture', context['context_id'], 'Change schema and regenerate.')

    def event(self, tool='Write', path='src/result.py'):
        return {'cwd': str(self.root), 'tool_name': tool, 'host': 'codex', 'session_id': 'session-fixture',
                'tool_input': {'file_path': str(self.root / path), 'content': 'updated'}}

    def native(self, kind, **fields):
        return {'cwd': str(self.root), 'session_id': 'native-fixture',
                'hook_event_name': kind, **fields}

    def native_plan(self):
        response = handle(self.ws, 'coding', self.native('UserPromptSubmit', prompt='Regenerate client'))
        packet = json.loads(response['hookSpecificOutput']['additionalContext'])['proofpress']
        self.assertTrue(packet['ok'])
        plan(self.store, packet['task_id'], packet['context_id'], 'Change source schema and regenerate')
        return packet

    def test_context_is_supplied_before_planning_and_no_model_on_required_scope(self):
        packet = self.prepare()
        self.assertTrue(packet['ok'])
        self.assertEqual(packet['judgments'][0]['id'], self.item['id'])
        self.assess.assert_not_called()
        self.assertIsNone(latest(self.store, 'task-fixture', 'task_started'))
        self.assertTrue(plan(self.store, 'task-fixture', packet['context_id'], 'Concrete plan')['ok'])
        self.assertEqual(self.assess.call_count, 1)
        model_state = self.assess.call_args.args[0]
        self.assertEqual(model_state['judgments'][0]['id'], self.item['id'])

    def test_jev_selects_multiple_scopes_but_cannot_drop_mandatory(self):
        other = copy.deepcopy(self.doc)
        other['applicability']['scope'] = 'coding/state'
        self.admit(other)
        policy = {**self.policy, 'scope_criteria': {self.scope: 'Mandatory cannot be excluded', 'coding/state': 'State changes'}}
        configure(self.store, policy, True)
        self.assess.return_value = {'choice': 'applicable'}
        packet = self.prepare()
        self.assertTrue(packet['ok'])
        self.assertEqual(set(packet['scopes']), {self.scope, 'coding/state'})
        self.assertEqual(self.assess.call_count, 1)
        self.assess.return_value = {'choice': 'pass'}
        self.assertTrue(plan(self.store, 'task-fixture', packet['context_id'], 'Concrete plan')['ok'])
        self.assertEqual(len(self.assess.call_args.args[0]['judgments']), 2)

    def test_unknown_scope_pauses_instead_of_dropping_it(self):
        configure(self.store, {**self.policy, 'scope_criteria': {'coding/state': 'State changes'}}, True)
        self.assess.return_value = {'choice': 'unknown', 'reason': 'low_certainty'}
        packet = self.prepare()
        self.assertFalse(packet['ok'])
        self.assertIn('scope_uncertain:coding/state', packet['reasons'])
        self.assertFalse(plan(self.store, 'task-fixture', packet['context_id'], 'Fixture plan')['ok'])
        self.assertEqual(self.assess.call_count, 1)

    def test_missing_facts_cannot_silently_exclude_admitted_judgment(self):
        conditional = copy.deepcopy(self.doc)
        conditional['applicability']['when'] = [{'field': 'multi_instance', 'equals': True}]
        self.admit(conditional)
        packet = self.prepare()
        self.assertFalse(packet['ok'])
        self.assertIn('missing_fact:multi_instance', packet['reasons'])

    def test_stale_context_and_wrong_context_token_do_not_start_plan(self):
        packet = self.prepare()
        with self.assertRaises(JudgmentError):
            plan(self.store, 'task-fixture', 'invented-context', 'Fixture plan')
        self.prepare()
        with self.assertRaises(JudgmentError):
            plan(self.store, 'task-fixture', packet['context_id'], 'Fixture plan')

    def test_host_session_bridge_blocks_execution_then_allows_repairs(self):
        packet = self.prepare()
        attach(self.store, 'task-fixture', 'codex', 'session-fixture')
        denied = hook(self.ws, self.event(), managed=True)
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(hook(self.ws, self.event('Write', str(plan_path(self.store, 'task-fixture'))), managed=True), {})
        plan(self.store, 'task-fixture', packet['context_id'], 'Concrete plan')
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.review.return_value = {'choice': 'violation'}
        self.assertFalse(finish_files(self.store, 'task-fixture')[0]['ok'])
        self.assertEqual(status(self.store, 'task-fixture')['state'], 'delivery_paused')
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.assertFalse(export(self.store, 'task-fixture')['ok'])

    def test_unknown_routes_and_out_of_scope_writes_pause(self):
        self.plan()
        attach(self.store, 'task-fixture', 'codex', 'session-fixture')
        for event in (self.event(path='other.py'), self.event(tool='Bash'), self.event(tool='mcp__unknown')):
            self.assertIn('hookSpecificOutput', hook(self.ws, event, managed=True))

    def test_control_channel_cannot_run_owner_commands_or_shell_expansion(self):
        packet = self.prepare()
        attach(self.store, 'task-fixture', 'codex', 'session-fixture')
        safe = f'proofpress --workspace {self.ws} task-status --task task-fixture'
        event = {**self.event('Bash'), 'tool_input': {'command': safe}}
        self.assertEqual(hook(self.ws, event, managed=True), {})
        for command in (safe + '; echo unsafe', safe + ' $(echo unsafe)',
                        f'proofpress --workspace {self.ws} pause --confirm',
                        f'proofpress --workspace {self.ws} task-status --task wrong-task'):
            self.assertIn('hookSpecificOutput', hook(self.ws, {**event, 'tool_input': {'command': command}}, managed=True))

    def test_patch_checks_all_paths_and_allows_only_plan_before_start(self):
        self.prepare()
        attach(self.store, 'task-fixture', 'codex', 'session-fixture')
        patch_event = {**self.event('apply_patch'), 'tool_input': {'command':
                       '*** Begin Patch\n*** Add File: src/new.py\n+fixture\n*** End Patch'}}
        self.assertIn('hookSpecificOutput', hook(self.ws, patch_event, managed=True))
        self.plan()
        self.assertEqual(hook(self.ws, patch_event, managed=True), {})

    def test_exact_file_export_and_changes_require_recheck(self):
        self.plan()
        self.assertFalse(export(self.store, 'task-fixture')['ok'])
        self.assertFalse((self.ws / 'deliveries').exists())
        self.assertTrue(finish_files(self.store, 'task-fixture')[0]['ok'])
        result = export(self.store, 'task-fixture')
        self.assertTrue(result['ok'])
        bundle = json.loads(Path(result['path']).read_text())
        self.assertEqual(bundle['artifacts'], snapshot(self.store, 'task-fixture'))
        (self.root / 'src/result.py').write_text('changed without hook')
        self.assertFalse(export(self.store, 'task-fixture')['ok'])

    def test_snapshot_includes_new_files_and_deletions_in_covered_scope(self):
        old = self.root / 'src/old.py'
        old.write_text('old fixture')
        self.plan()
        old.unlink()
        (self.root / 'src/new.py').write_text('new fixture')
        outputs = snapshot(self.store, 'task-fixture')
        self.assertEqual(outputs['src/new.py'], 'new fixture')
        self.assertIn('@deleted/src/old.py', outputs)
        finish_files(self.store, 'task-fixture')
        self.assertIn('src/new.py', self.review.call_args.args[0]['artifacts'])

    def test_unknown_review_status_and_human_exception_are_distinct(self):
        self.plan()
        self.review.return_value = {'choice': 'unknown', 'reason': 'low_certainty'}
        result, outputs = finish_files(self.store, 'task-fixture')
        self.assertEqual(json.loads(Path(result['review_path']).read_text()), outputs)
        paused = status(self.store, 'task-fixture')
        self.assertEqual(paused['assessment'], 'unknown')
        self.assertEqual(paused['paused_boundary'], 'delivery')
        exception(self.store, 'task-fixture', outputs, 'Synthetic bounded approval', True)
        self.assertEqual(status(self.store, 'task-fixture')['state'], 'ready')

    def test_parent_symlink_cannot_send_workspace_content_to_provider(self):
        self.plan()
        (self.root / 'src/result.py').unlink()
        (self.root / 'src').rmdir()
        (self.root / 'src').symlink_to(self.ws, target_is_directory=True)
        with self.assertRaises(JudgmentError):
            finish_files(self.store, 'task-fixture')
        self.review.assert_not_called()

    def test_cli_native_bridge_denies_actual_write_until_plan_then_checks_stop(self):
        # Entire host protocol through CLI subprocesses. The test harness, not
        # an actual host, honors the returned decision before its filesystem write.
        script = ('from unittest.mock import patch; from judgment_layer.cli import main; '
                  'import sys; '
                  'p=patch("judgment_layer.workflows.assess",return_value={"choice":"pass"});p.start(); '
                  'q=patch("judgment_layer.tasks.assess",return_value={"choice":"pass"});q.start(); '
                  'sys.exit(main())')

        def call(args, event=None):
            proc = subprocess.run([sys.executable, '-c', script, '--workspace', str(self.ws), *args],
                                  input=json.dumps(event) if event else None, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

        args = ['workflow-hook', '--workflow', 'coding']
        prompt = call(args, self.native('UserPromptSubmit', prompt='Regenerate client'))
        packet = json.loads(prompt['hookSpecificOutput']['additionalContext'])['proofpress']
        path = self.root / 'src/result.py'
        write = self.native('PreToolUse', tool_name='Write', tool_input={'file_path': str(path), 'content': 'new source'})
        verdict = call(args, write)
        self.assertEqual(verdict['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(path.read_text(), 'complete synthetic result')
        draft = Path(packet['plan_path'])
        draft.parent.mkdir(exist_ok=True)
        draft.write_text('Change source schema then regenerate')
        call(['task-plan', '--task', packet['task_id'], '--context', packet['context_id'], '--plan', str(draft), '--json'])
        self.assertEqual(call(args, write), {})
        path.write_text('new source')
        self.assertEqual(call(args, self.native('Stop', last_assistant_message='Completed fixture', stop_hook_active=False)), {})

    def test_doctor_and_uninstall_include_lifecycle_hooks(self):
        from judgment_layer.hosts import doctor, uninstall
        install(self.store, 'coding', True)
        info = doctor(self.store, self.root)
        self.assertTrue(any(h['host'] == 'claude-code lifecycle' and h['configured'] for h in info['hosts']))
        uninstall(self.store, self.root, True)
        self.assertFalse((self.ws / 'workflow-host-claude.json').exists())

    def test_human_exception_is_exact_and_cannot_override_withdrawal(self):
        self.plan()
        self.review.return_value = {'choice': 'unknown'}
        finish_files(self.store, 'task-fixture')
        outputs = snapshot(self.store, 'task-fixture')
        exception(self.store, 'task-fixture', outputs, 'Synthetic review exception', False)
        self.assertFalse(export(self.store, 'task-fixture')['ok'])
        exception(self.store, 'task-fixture', outputs, 'Synthetic review exception', True)
        self.assertTrue(export(self.store, 'task-fixture')['ok'])
        self.store.owner_action(self.item['id'], 1, self.item['digest'],
                                'withdraw', 'Synthetic fixture only', True)
        self.assertFalse(export(self.store, 'task-fixture')['ok'])
        with self.assertRaises(JudgmentError):
            exception(self.store, 'task-fixture', outputs, 'Cannot override stale context', True)

    def test_workflow_change_invalidates_execution(self):
        self.plan()
        attach(self.store, 'task-fixture', 'codex', 'session-fixture')
        configure(self.store, {**self.policy, 'facts': {'changed': True}}, True)
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event(), managed=True))

    def test_missing_artifact_symlink_and_glob_cannot_hide_coverage(self):
        with self.assertRaises(JudgmentError):
            configure(self.store, {**self.policy, 'artifacts': ['src/*.py']}, True)
        self.plan()
        path = self.root / 'src/result.py'
        path.unlink()
        with self.assertRaises(JudgmentError):
            finish_files(self.store, 'task-fixture')
        path.symlink_to(ROOT / 'README.md')
        with self.assertRaises(JudgmentError):
            snapshot(self.store, 'task-fixture')

    def test_native_prompt_injection_gate_and_stop_review(self):
        packet = self.native_plan()
        write = self.native('PreToolUse', tool_name='Write',
                            tool_input={'file_path': str(self.root / 'src/result.py'), 'content': 'fixture'})
        self.assertEqual(handle(self.ws, 'coding', write), {})
        stop = self.native('Stop', last_assistant_message='Actual synthetic final response', stop_hook_active=False)
        self.assertEqual(handle(self.ws, 'coding', stop), {})
        self.assertEqual(handle(self.ws, 'coding', stop), {})
        self.assertEqual(self.review.call_count, 1)
        self.assertEqual(self.assess.call_count, 1)
        self.assertIn('@response', self.review.call_args.args[0]['artifacts'])

    def test_native_unknown_returns_control_and_violation_allows_one_repair_turn(self):
        self.native_plan()
        self.review.return_value = {'choice': 'unknown'}
        stop = self.native('Stop', last_assistant_message='Fixture response', stop_hook_active=False)
        result = handle(self.ws, 'coding', stop)
        self.assertFalse(result['continue'])
        self.assertIn('delivery paused', result['stopReason'])
        handle(self.ws, 'coding', stop)
        self.assertEqual(self.review.call_count, 1)
        self.review.return_value = {'choice': 'violation'}
        stop['last_assistant_message'] = 'Changed fixture response'
        self.assertEqual(handle(self.ws, 'coding', stop)['decision'], 'block')
        self.assertFalse(handle(self.ws, 'coding', {**stop, 'stop_hook_active': True})['continue'])

    def test_explicit_resume_keeps_session_task_and_refuses_another_task(self):
        packet = self.native_plan()
        before = len([e for e in self.store.events() if e['kind'] == 'task_prepared'])
        resumed = handle(self.ws, 'coding', self.native('UserPromptSubmit',
                         prompt='proofpress resume task ' + packet['task_id']))
        context = json.loads(resumed['hookSpecificOutput']['additionalContext'])
        self.assertEqual(context['proofpress_resume']['task_id'], packet['task_id'])
        self.assertEqual(len([e for e in self.store.events() if e['kind'] == 'task_prepared']), before)
        wrong = handle(self.ws, 'coding', self.native('UserPromptSubmit', prompt='proofpress resume task another'))
        self.assertEqual(wrong['decision'], 'block')

    def test_native_missing_context_never_allows_pretool(self):
        result = handle(self.ws, 'coding', self.native('PreToolUse', tool_name='Write', tool_input={}))
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_invalid_provider_env_still_denies_native_tool(self):
        env = self.root / 'invalid.env'
        env.write_text('UNSUPPORTED_KEY=fixture')
        result = subprocess.run([sys.executable, '-m', 'judgment_layer.cli', '--workspace', str(self.ws),
                                 '--env-file', str(env), 'workflow-hook', '--workflow', 'coding'],
                                input=json.dumps(self.native('PreToolUse', tool_name='Write', tool_input={})),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_lifecycle_installer_preserves_user_hooks_and_removes_only_own(self):
        path = self.root / '.claude/settings.local.json'
        path.parent.mkdir()
        user = {'hooks': [{'type': 'command', 'command': 'echo user'}]}
        path.write_text(json.dumps({'hooks': {'Stop': [user]}}))
        install(self.store, 'coding', False)
        self.assertEqual(json.loads(path.read_text())['hooks']['Stop'], [user])
        install(self.store, 'coding', True)
        install(self.store, 'coding', True)
        value = json.loads(path.read_text())
        self.assertEqual(len(value['hooks']['Stop']), 2)
        self.assertEqual(value['hooks']['PreToolUse'][0]['hooks'][0]['onFailure'], 'block')
        remove(self.store, 'coding', True)
        self.assertEqual(json.loads(path.read_text())['hooks']['Stop'], [user])

    def test_cli_status_distinguishes_boundary_and_next_actions(self):
        self.prepare()
        result = subprocess.run([sys.executable, '-m', 'judgment_layer.cli', '--workspace',
                                 str(self.ws), 'task-status', '--task', 'task-fixture'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('planning', result.stdout.lower())
        self.assertIn('task-plan', result.stdout)
