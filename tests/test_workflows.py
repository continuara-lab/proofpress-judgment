"""Synthetic owner fixtures for installation, atomic review and lifecycle recovery."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from judgment_layer.store import Store, initialize
from judgment_layer.hosts import install, remove, bindings, doctor, uninstall
from judgment_layer.runtime import hook
from judgment_layer.interactive import interactive_review
from judgment_layer.cli import parser, run
from judgment_layer.setup import setup
from judgment_layer.intake import DEFAULT_POLICY, set_policy
from judgment_layer.history import consolidate, ingest
from judgment_layer.model import JudgmentError

ROOT=Path(__file__).resolve().parents[1]

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name).resolve()
        self.ws=self.root/'.judgment'; initialize(self.ws,'human:synthetic'); self.s=Store(self.ws)
        self.doc=json.loads((ROOT/'examples/coding.json').read_text())
        self.doc['applicability']['when']=[]
        with self.s.transaction(): self.item=self.s.capture(self.doc)
    def tearDown(self): self.s.close(); self.tmp.cleanup()
    def tx(self, f):
        with self.s.transaction(): return f()
    def enforce(self):
        return {'project_root':str(self.root),'paths':['generated/*'],'verifier':'deny_generated_write'}
    def review(self, enforcement=None, answer='a'):
        with patch('builtins.print'):
            return interactive_review(self.ws,self.item['id'],enforcement,input_fn=lambda _:answer)
    def test_review_binds_atomically_and_invalid_enforcement_rolls_back(self):
        bad={**self.enforce(),'paths':['../escape']}
        with self.assertRaises(JudgmentError): self.review(bad)
        self.assertEqual(self.s.state(self.s.record(self.item['id'])),'proposed')
        self.review(self.enforce())
        self.assertEqual(len(bindings(self.s)),1)
        self.assertEqual(self.s.state(self.s.record(self.item['id'])),'admitted')
    def test_review_cancel_never_admits(self):
        self.review(self.enforce(),'c')
        self.assertFalse(bindings(self.s))
        self.assertEqual(self.s.state(self.s.record(self.item['id'])),'proposed')
    def test_host_install_preserves_other_hooks_is_idempotent_and_removable(self):
        path=self.root/'.codex/hooks.json'; path.parent.mkdir()
        user={'matcher':'Bash','hooks':[{'type':'command','command':'echo user'}]}
        path.write_text(json.dumps({'hooks':{'PreToolUse':[user]},'description':'keep me'}))
        self.tx(lambda:install(self.s,self.root,'codex',False))
        self.assertEqual(len(json.loads(path.read_text())['hooks']['PreToolUse']),1)
        self.tx(lambda:install(self.s,self.root,'codex',True))
        self.tx(lambda:install(self.s,self.root,'codex',True))
        self.assertEqual(len(json.loads(path.read_text())['hooks']['PreToolUse']),2)
        self.tx(lambda:remove(self.s,'codex',True))
        self.assertEqual(json.loads(path.read_text())['hooks']['PreToolUse'],[user])
    def test_host_symlink_refused(self):
        (self.root/'.codex').symlink_to(self.ws,target_is_directory=True)
        with self.assertRaises(JudgmentError):self.tx(lambda:install(self.s,self.root,'codex',True))
    def test_managed_hook_pause_withdraw_and_explicit_unbind(self):
        self.review(self.enforce())
        event={'tool_name':'Write','cwd':str(self.root),'tool_input':{'file_path':str(self.root/'generated/user.py'),'content':'bad'}}
        def blocked(): return hook(self.ws,event,managed=True).get('hookSpecificOutput',{}).get('permissionDecision')=='deny'
        self.assertTrue(blocked())
        run(parser().parse_args(['--workspace',str(self.ws),'pause','--confirm']))
        self.assertFalse(blocked())
        run(parser().parse_args(['--workspace',str(self.ws),'resume','--confirm']))
        self.assertTrue(blocked())
        self.tx(lambda:self.s.owner_action(self.item['id'],1,self.item['digest'],'withdraw','Synthetic fixture',True))
        self.assertTrue(blocked())
        run(parser().parse_args(['--workspace',str(self.ws),'unbind',self.item['id'],'--confirm']))
        self.assertFalse(blocked())
    def test_no_binding_does_not_block_normal_work_and_doctor_does_not_infer_trust(self):
        self.assertEqual(hook(self.ws,{'tool_name':'Bash','tool_input':{'command':'true'}},managed=True),{})
        self.tx(lambda:install(self.s,self.root,'codex',True))
        result=self.tx(lambda:doctor(self.s,self.root))
        self.assertTrue(result['hosts'][0]['configured'])
        self.assertIn('does not',result['hosts'][0]['trust'])
        self.assertIsNotNone(result['last_check'])
    def test_skill_upgrade_backs_up_edits_and_uninstall_preserves_modified_files(self):
        setup(self.root,self.ws,['codex'],'human:synthetic')
        path=self.root/'.agents/skills/proofpress/SKILL.md'
        path.write_text('synthetic old guidance')
        with self.assertRaises(JudgmentError):setup(self.root,self.ws,['codex'],'human:synthetic')
        setup(self.root,self.ws,['codex'],'human:synthetic',upgrade=True)
        self.assertTrue(any(p.read_text()=='synthetic old guidance' for p in (self.ws/'skill-backups').rglob('SKILL.md')))
        path.write_text('synthetic human edit')
        self.tx(lambda:uninstall(self.s,self.root,True))
        self.assertEqual(path.read_text(),'synthetic human edit')
        self.assertTrue((self.ws/'store.sqlite3').is_file())
    def test_editor_creates_candidate_and_stale_editor_cannot_overwrite(self):
        from judgment_layer.interactive import revise_in_editor
        changed=copy.deepcopy(self.item['record']); changed.pop('id');changed.pop('version')
        changed['judgment']['statement']='Synthetic revised guidance'
        with patch('judgment_layer.interactive.edit_document',return_value=changed):
            result=revise_in_editor(self.ws,self.item['id'])
        self.assertEqual(result['version'],2);self.assertEqual(result['state'],'proposed')
        self.assertEqual(self.s.record(self.item['id'],1)['judgment']['statement'],self.doc['judgment']['statement'])
        def concurrent_edit(base):
            self.tx(lambda:self.s.capture(changed,self.item['id'],'Concurrent synthetic edit',result['digest']))
            return changed
        with patch('judgment_layer.interactive.edit_document',side_effect=concurrent_edit):
            with self.assertRaises(JudgmentError):revise_in_editor(self.ws,self.item['id'])
        self.assertEqual(self.s.record(self.item['id'])['version'],3)
    def test_pending_revision_withdraws_admitted_revision_and_keeps_protection(self):
        from judgment_layer.interactive import withdraw_interactive
        self.review(self.enforce())
        doc=copy.deepcopy(self.doc);doc['judgment']['statement']='Synthetic pending revision'
        self.tx(lambda:self.s.capture(doc,self.item['id'],'Synthetic edit',self.item['digest']))
        answers=iter(['y','Synthetic retirement'])
        with patch('builtins.print'):withdraw_interactive(self.ws,self.item['id'],input_fn=lambda _:next(answers))
        self.assertEqual(self.s.state(self.s.record(self.item['id'],1)),'withdrawn')
        self.assertEqual(self.s.state(self.s.record(self.item['id'],2)),'proposed')
        self.assertEqual(len(bindings(self.s)),1)
    def test_editor_form_preserves_provenance(self):
        from judgment_layer.interactive import edit_document
        import subprocess
        def editor(argv):
            path=Path(argv[-1]);text=path.read_text()
            text=text.replace('statement = '+json.dumps(self.doc['judgment']['statement']), 'statement = "Synthetic editor change"')
            path.write_text(text)
            return subprocess.CompletedProcess(argv,0)
        with patch('judgment_layer.interactive.subprocess.run',side_effect=editor):
            doc=edit_document(self.item['record'])
        self.assertEqual(doc['judgment']['statement'],'Synthetic editor change')
        self.assertEqual(doc['provenance'],self.item['record']['provenance'])
        self.assertNotIn('id',doc)
    def test_policy_disabled_triggers_filter_model_candidates(self):
        session=self.root/'session.jsonl'
        session.write_text(json.dumps({'type':'session_meta','payload':{'id':'synthetic','cwd':str(self.root)}})+'\n'+json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Synthetic guidance'}]}})+'\n')
        self.tx(lambda:ingest(self.s,session,self.root))
        p=copy.deepcopy(DEFAULT_POLICY);p['triggers']=['human_judgment']
        self.tx(lambda:set_policy(self.s,p,True))
        source=next(e for e in self.s.events() if e['kind']=='history_imported')['data']['batch']['messages'][0]['source_ref']
        c={'name':'synthetic','statement':'Unsupported agent choice','rationale':'Synthetic','situation':'Fixture','polarity':'avoid','source_refs':[source],'capture_trigger':'agent_judgment'}
        with patch('judgment_layer.history.extract',return_value=[c]):
            self.assertEqual(self.tx(lambda:consolidate(self.s,'coding',True))['candidates'],[])
