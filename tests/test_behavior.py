"""Synthetic owner fixtures; host protocols are not live-host verification."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from judgment_layer.behavior import AUTOMATIC, connect, inventory, prepare
from judgment_layer.interactive import review_preview
from judgment_layer.lifecycle import handle, install
from judgment_layer.model import JudgmentError, digest
from judgment_layer.runtime import hook
from judgment_layer.store import Store, initialize
from judgment_layer.workflows import attach, export, finish_files, plan, snapshot, status

ROOT = Path(__file__).resolve().parents[1]


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.ws = self.root / '.judgment'
        initialize(self.ws, 'human:synthetic-behavior-owner')
        self.store = Store(self.ws)
        self.doc = json.loads((ROOT / 'examples/behavior-judgment.json').read_text())
        self.doc['applicability'].pop('task_criteria')
        (self.root / 'api').mkdir()
        (self.root / 'api/schema.yaml').write_text('synthetic schema')
        (self.root / 'src/generated').mkdir(parents=True)
        (self.root / 'src/generated/client.py').write_text('synthetic client')
        self.mock = patch('judgment_layer.behavior.assess', return_value={'choice': 'pass'})
        self.assess = self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.store.close()
        self.temp.cleanup()

    def admit(self, doc=None):
        item = self.store.capture(doc or self.doc)
        self.store.owner_action(item['id'], item['version'], item['digest'], 'admit',
                                'Synthetic review fixture only', True)
        return item

    def event(self, path='api/schema.yaml', tool='Write'):
        return {'host': 'codex', 'session_id': 'synthetic-session', 'cwd': str(self.root),
                'tool_name': tool, 'tool_input': {'file_path': str(self.root / path), 'content': 'fixture'}}

    def start(self):
        packet = prepare(self.store, 'synthetic-task', 'Add a schema field')
        attach(self.store, 'synthetic-task', 'codex', 'synthetic-session')
        self.assertTrue(plan(self.store, 'synthetic-task', packet['context_id'], 'Modify schema then regenerate')['ok'])
        return packet

    def native(self, kind, **fields):
        return {'hook_event_name': kind, 'cwd': str(self.root), 'session_id': 'native-synthetic', **fields}

    def test_one_review_activates_embedded_behavior_without_binding_or_workflow(self):
        pending = self.store.capture(self.doc)
        self.assertEqual(inventory(self.store), [])
        self.assertEqual(hook(self.ws, self.event('src/generated/client.py'), managed=True), {})
        self.store.owner_action(pending['id'], 1, pending['digest'], 'admit', 'Synthetic fixture', True)
        packet = self.start()
        self.assertEqual(packet['judgments'][0]['id'], pending['id'])
        self.assertNotIn('workflow_configured', {e['kind'] for e in self.store.events()})
        self.assertNotIn('runtime_bound', {e['kind'] for e in self.store.events()})
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event('src/generated/client.py'), managed=True))

    def test_plan_and_delivery_are_two_aggregate_calls_actions_do_not_call_model(self):
        self.admit()
        self.start()
        self.assertEqual(self.assess.call_count, 1)
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.assertEqual(hook(self.ws, self.event(tool='Read'), managed=True), {})
        self.assertEqual(self.assess.call_count, 1)
        self.assertTrue(finish_files(self.store, 'synthetic-task')[0]['ok'])
        self.assertEqual(self.assess.call_count, 2)
        checks = self.assess.call_args.args[0]['checks']
        self.assertIn('supporting generation evidence', checks[0]['criteria'])
        self.assertTrue(export(self.store, 'synthetic-task')['ok'])

    def test_multiple_scopes_share_stage_calls_and_all_declared_criteria_are_supplied(self):
        first = self.admit()
        doc = copy.deepcopy(self.doc)
        doc['applicability']['scope'] = 'coding/another-scope'
        second = self.admit(doc)
        packet = self.start()
        self.assertEqual(len(packet['scopes']), 2)
        self.assertEqual(self.assess.call_count, 1)
        self.assertEqual({c['judgment_id'] for c in self.assess.call_args.args[0]['checks']},
                         {first['id'], second['id']})
        finish_files(self.store, 'synthetic-task')
        self.assertEqual(self.assess.call_count, 2)

    def test_no_declared_delivery_check_is_labeled_not_requested(self):
        from judgment_layer.presentation import render_text
        doc = copy.deepcopy(self.doc)
        doc['behavior']['hooks'] = [doc['behavior']['hooks'][1]]
        self.admit(doc)
        prepare(self.store, 'synthetic-task', 'Fixture task')
        finish_files(self.store, 'synthetic-task')
        result = status(self.store, 'synthetic-task')
        self.assertEqual(result['delivery_coverage'], 'not_requested')
        self.assertIn('No delivery check requested', render_text('task-status', result))
        self.assess.assert_not_called()

    def test_symlink_action_and_newly_created_then_deleted_artifact_pause(self):
        self.admit()
        self.start()
        alias = self.root / 'src/generated/alias.py'
        alias.symlink_to(self.root / 'api/schema.yaml')
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event('src/generated/alias.py'), managed=True))
        alias.unlink()
        new = self.root / 'api/new.yaml'
        new.write_text('synthetic addition')
        finish_files(self.store, 'synthetic-task')
        new.unlink()
        self.assertEqual(status(self.store, 'synthetic-task')['state'], 'delivery_paused')
        self.assertFalse(export(self.store, 'synthetic-task')['ok'])

    def test_semantic_task_nonmatch_does_not_disable_direct_action_rule(self):
        doc = copy.deepcopy(self.doc)
        doc['applicability']['task_criteria'] = 'API changes'
        self.admit(doc)
        self.assess.return_value = {'choice': 'not_applicable'}
        packet = prepare(self.store, 'synthetic-task', 'Unrelated documentation task')
        self.assertFalse(packet['requires_plan'])
        self.assertEqual(packet['judgments'], [])
        attach(self.store, 'synthetic-task', 'codex', 'synthetic-session')
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event('src/generated/client.py'), managed=True))
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})

    def test_task_match_unknown_pauses_and_cannot_become_empty_pass(self):
        doc = copy.deepcopy(self.doc)
        doc['applicability']['task_criteria'] = 'API changes'
        self.admit(doc)
        self.assess.return_value = {'choice': 'unknown'}
        packet = prepare(self.store, 'synthetic-task', 'Ambiguous task')
        self.assertFalse(packet['ok'])
        self.assertTrue(packet['reasons'][0].startswith('task_match_uncertain:'))
        self.assertFalse(plan(self.store, 'synthetic-task', packet['context_id'], 'Plan')['ok'])
        self.assertEqual(self.assess.call_count, 1)

    def test_missing_fact_pauses_without_invention_and_trusted_connection_supplies_it(self):
        doc = copy.deepcopy(self.doc)
        doc['applicability']['when'] = [{'field': 'generated', 'equals': True}]
        self.admit(doc)
        packet = prepare(self.store, 'synthetic-task', 'API change')
        self.assertFalse(packet['ok'])
        connect(self.store, self.root, {'generated': True}, True)
        self.assertTrue(prepare(self.store, 'synthetic-task', 'API change')['ok'])
        self.assess.assert_not_called()

    def test_action_only_needs_no_task_or_plan_and_checks_conditions(self):
        doc = copy.deepcopy(self.doc)
        doc['behavior']['hooks'] = [doc['behavior']['hooks'][1]]
        doc['behavior'].pop('artifacts')
        self.admit(doc)
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event('src/generated/client.py'), managed=True))
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.assess.assert_not_called()

    def test_unattached_session_cannot_skip_required_plan(self):
        self.admit()
        result = hook(self.ws, self.event(), managed=True)
        self.assertIn('Prepare and attach', result['hookSpecificOutput']['permissionDecisionReason'])

    def test_optional_hooks_do_not_introduce_unrequested_model_checks(self):
        doc = copy.deepcopy(self.doc)
        doc['behavior']['hooks'] = [doc['behavior']['hooks'][1]]
        self.admit(doc)
        packet = prepare(self.store, 'synthetic-task', 'Synthetic change')
        self.assertFalse(packet['requires_plan'])
        self.assertTrue(finish_files(self.store, 'synthetic-task')[0]['ok'])
        self.assess.assert_not_called()

    def test_new_revision_requires_review_and_invalidates_prior_run_only_on_admission(self):
        item = self.admit()
        self.start()
        doc = copy.deepcopy(self.doc)
        doc['behavior']['hooks'][0]['verifier']['criteria'] = 'Narrowed synthetic check'
        pending = self.store.capture(doc, item['id'], 'Synthetic revision', item['digest'])
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.store.owner_action(pending['id'], 2, pending['digest'], 'admit', 'Synthetic review', True)
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event(), managed=True))

    def test_withdrawal_invalidates_existing_run_and_does_not_resurrect_old_revision(self):
        item = self.admit()
        self.start()
        finish_files(self.store, 'synthetic-task')
        self.store.owner_action(item['id'], 1, item['digest'], 'withdraw', 'Synthetic withdrawal', True)
        self.assertFalse(export(self.store, 'synthetic-task')['ok'])
        self.assertEqual(inventory(self.store), [])

    def test_changed_facts_and_new_judgment_invalidate_run(self):
        self.admit()
        self.start()
        connect(self.store, self.root, {'extra_fact': True}, True)
        self.assertIn('hookSpecificOutput', hook(self.ws, self.event(), managed=True))

    def test_exact_artifacts_new_files_and_deletions_cannot_keep_old_approval(self):
        self.admit()
        self.start()
        (self.root / 'src/generated/client.py').unlink()
        (self.root / 'src/generated/new.py').write_text('new fixture')
        outputs = snapshot(self.store, 'synthetic-task')
        self.assertIn('@deleted/src/generated/client.py', outputs)
        self.assertIn('src/generated/new.py', outputs)
        finish_files(self.store, 'synthetic-task')
        (self.root / 'api/schema.yaml').write_text('modified after review')
        self.assertFalse(export(self.store, 'synthetic-task')['ok'])
        self.assertEqual(status(self.store, 'synthetic-task')['state'], 'delivery_paused')

    def test_delivery_violation_allows_repairs_but_not_export(self):
        self.admit()
        self.start()
        self.assess.return_value = {'choice': 'violation'}
        self.assertFalse(finish_files(self.store, 'synthetic-task')[0]['ok'])
        self.assertEqual(hook(self.ws, self.event(), managed=True), {})
        self.assertFalse(export(self.store, 'synthetic-task')['ok'])

    def test_patch_move_checks_both_paths_without_model(self):
        self.admit()
        self.start()
        event = self.event(tool='apply_patch')
        event['tool_input'] = {'command': '*** Begin Patch\n*** Update File: api/schema.yaml\n*** Move to: src/generated/escape.py\n@@\n-old\n+new\n*** End Patch'}
        self.assertIn('hookSpecificOutput', hook(self.ws, event, managed=True))
        self.assertEqual(self.assess.call_count, 1)

    def test_unsupported_commands_and_private_or_oversize_artifacts_pause(self):
        self.admit()
        self.start()
        event = {**self.event(tool='Bash'), 'tool_input': {'command': 'python arbitrary.py'}}
        self.assertIn('hookSpecificOutput', hook(self.ws, event, managed=True))
        (self.root / 'api/schema.yaml').write_text('x' * 64001)
        with self.assertRaises(JudgmentError):
            finish_files(self.store, 'synthetic-task')

    def test_schema_rejects_old_version_unknown_verifier_and_unsafe_paths(self):
        mutations = [lambda d: d.update(ajf_version='0.3-draft'),
                     lambda d: d['behavior']['hooks'][0]['verifier'].update(type='command'),
                     lambda d: d['behavior'].pop('artifacts'),
                     lambda d: d['behavior']['hooks'][1]['match'].update(paths=['../escape']),
                     lambda d: d['behavior']['hooks'][1]['match'].update(paths=['.env'])]
        for mutate in mutations:
            doc = copy.deepcopy(self.doc)
            mutate(doc)
            with self.assertRaises(JudgmentError):
                self.store.capture(doc)

    def test_review_preview_contains_task_match_criteria_hooks_and_failure_policy(self):
        doc = copy.deepcopy(self.doc)
        doc['applicability']['task_criteria'] = 'API changes'
        item = self.store.capture(doc)
        preview = review_preview(item, None)
        for text in ('API changes', 'before_execution', 'deny_action', 'before_delivery', 'Unknown: pause'):
            self.assertIn(text, preview)

    def test_default_native_bridge_uses_judgment_context_and_bounds_repair_loop(self):
        self.admit()
        response = handle(self.ws, AUTOMATIC, self.native('UserPromptSubmit', prompt='API change'))
        packet = json.loads(response['hookSpecificOutput']['additionalContext'])['proofpress']
        plan(self.store, packet['task_id'], packet['context_id'], 'Modify schema and regenerate')
        stop = self.native('Stop', last_assistant_message='Synthetic final response')
        self.assess.return_value = {'choice': 'violation'}
        self.assertEqual(handle(self.ws, AUTOMATIC, stop)['decision'], 'block')
        calls = self.assess.call_count
        self.assertFalse(handle(self.ws, AUTOMATIC, {**stop, 'stop_hook_active': True})['continue'])
        self.assertEqual(self.assess.call_count, calls)

    def test_cli_install_preview_and_confirm_need_no_workflow(self):
        args = [sys.executable, '-m', 'judgment_layer.cli', '--workspace', str(self.ws),
                'enforce', 'install', '--project', str(self.root), '--json']
        preview = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse((self.root / '.claude/settings.local.json').exists())
        self.assertNotIn('behavior_connected', {e['kind'] for e in self.store.events()})
        installed = subprocess.run([*args, '--confirm'], capture_output=True, text=True)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        settings = json.loads((self.root / '.claude/settings.local.json').read_text())
        self.assertIn('behavior-hook', settings['hooks']['Stop'][0]['hooks'][0]['command'])
        self.assertNotIn('workflow_configured', {e['kind'] for e in self.store.events()})

    def test_native_protocol_cli_blocks_real_write_then_reviews_actual_files(self):
        self.admit()
        script = ('from unittest.mock import patch; from judgment_layer.cli import main; import sys; '
                  'p=patch("judgment_layer.behavior.assess",return_value={"choice":"pass"});p.start(); sys.exit(main())')

        def call(args, event=None):
            proc = subprocess.run([sys.executable, '-c', script, '--workspace', str(self.ws), *args],
                                  input=json.dumps(event) if event else None, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)

        response = call(['behavior-hook'], self.native('UserPromptSubmit', prompt='API change'))
        packet = json.loads(response['hookSpecificOutput']['additionalContext'])['proofpress']
        event = self.native('PreToolUse', tool_name='Write', tool_input=self.event()['tool_input'])
        self.assertEqual(call(['behavior-hook'], event)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual((self.root / 'api/schema.yaml').read_text(), 'synthetic schema')
        draft = Path(packet['plan_path'])
        draft.parent.mkdir(exist_ok=True)
        draft.write_text('Modify source schema then regenerate')
        call(['task-plan', '--task', packet['task_id'], '--context', packet['context_id'], '--plan', str(draft), '--json'])
        self.assertEqual(call(['behavior-hook'], event), {})
        (self.root / 'api/schema.yaml').write_text('actual fixture output')
        self.assertEqual(call(['behavior-hook'], self.native('Stop', last_assistant_message='Synthetic completion')), {})


if __name__ == '__main__':
    unittest.main()
