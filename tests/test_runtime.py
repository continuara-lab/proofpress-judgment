import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from judgment_layer.model import JudgmentError
from judgment_layer.runtime import bind, gate, hook, screen
from judgment_layer.assessment import assess
from judgment_layer.store import Store, initialize
ROOT=Path(__file__).resolve().parents[1]

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        initialize(self.root/'store','human:synthetic-owner')
        self.s=Store(self.root/'store')
        self.doc=json.loads((ROOT/'examples/coding.json').read_text())
    def tearDown(self):self.s.close();self.temp.cleanup()
    def admit(self,doc=None):
        x=self.s.capture(doc or self.doc)
        self.s.owner_action(x['id'],1,x['digest'],'admit','Synthetic fixture',True)
        return x
    def binding(self,item,verifier='deny_generated_write'):
        return {'project_root':str(self.root),'scope':item['record']['applicability']['scope'],
                'judgment_id':item['id'],'version':item['version'],'digest':item['digest'],
                'verifier':verifier,'paths':['generated/*']}
    def event(self,path='generated/a.py',tool='Write'):
        return {'cwd':str(self.root),'tool_name':tool,'tool_input':{'file_path':str(self.root/path),'content':'fixture'}}
    def test_write_shell_and_withdrawal_fail_closed(self):
        x=self.admit();bind(self.s,self.binding(x),True)
        self.assertFalse(gate(self.s,self.event())['ok'])
        self.assertFalse(gate(self.s,self.event(tool='Bash'))['ok'])
        self.assertTrue(gate(self.s,self.event('src/a.py'))['ok'])
        self.s.owner_action(x['id'],1,x['digest'],'withdraw','Synthetic fixture',True)
        self.assertFalse(gate(self.s,self.event())['ok'])
    def test_unknown_facts_and_symlink_escape_block(self):
        x=self.admit();bind(self.s,self.binding(x),True)
        (self.root/'escape').symlink_to('/tmp',target_is_directory=True)
        self.assertFalse(gate(self.s,self.event('escape/a.py'))['ok'])
        doc=copy.deepcopy(self.doc);doc['applicability']['when']=[{'field':'unverifiable','equals':True}]
        y=self.admit(doc);bind(self.s,self.binding(y),True)
        self.assertFalse(gate(self.s,self.event())['ok'])
    def test_conflict_candidate_preserved_but_admission_paused(self):
        doc=copy.deepcopy(self.doc);doc['judgment']['assertion']={'key':'separator','value':'_'}
        self.admit(doc)
        doc['judgment']['assertion']['value']='-';x=self.s.capture(doc)
        self.assertEqual(x['state'],'proposed')
        with self.assertRaises(JudgmentError):self.s.owner_action(x['id'],1,x['digest'],'admit','Fixture',True)
    def test_semantic_unknown_blocks_candidate_and_current_gate(self):
        doc=copy.deepcopy(self.doc);doc['applicability']['when']=[]
        x=self.admit(doc);bind(self.s,self.binding(x,'semantic_output'),True)
        y=self.s.capture(doc)
        with patch('judgment_layer.runtime.assess',return_value={'choice':'unknown'}):
            self.assertFalse(screen(self.s,y)['ok'])
        with self.assertRaises(JudgmentError):self.s.owner_action(y['id'],1,y['digest'],'admit','Fixture',True)
        self.assertFalse(gate(self.s,self.event())['ok'])
    def test_semantic_pass_does_not_bypass_host_and_partial_edit_pauses(self):
        doc=copy.deepcopy(self.doc);doc['applicability']['when']=[]
        x=self.admit(doc);bind(self.s,self.binding(x,'semantic_output'),True)
        with patch('judgment_layer.runtime.assess',return_value={'choice':'pass'}):
            self.assertTrue(gate(self.s,self.event())['ok'])
            self.assertFalse(gate(self.s,self.event(tool='Edit'))['ok'])
        self.assertEqual(hook(self.root/'store',self.event(tool='Read')),{})
    def test_hook_cli_malformed_input_denies_even_missing_store(self):
        result=subprocess.run([sys.executable,'-m','judgment_layer.cli','--workspace',str(self.root/'absent'),'hook'],input='{',capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
    def test_provider_off_is_unknown_without_network(self):
        with patch.dict(os.environ,{},clear=True),patch('judgment_layer.assessment.build_opener') as network:
            self.assertEqual(assess({},'Question',{'pass':'pass','unknown':'unknown'})['choice'],'unknown')
            network.assert_not_called()
    def test_provider_request_shape_and_low_certainty(self):
        options={'pass':'Follows','violation':'Violates','unknown':'Unclear'}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps({'model':'fixture','answers':{'assessment':{'type':'choice','choice':'pass','confidence':.99,'probabilities':{'pass':.99,'violation':.005,'unknown':.005}}}}).encode()
        with patch.dict(os.environ,{'PROOFPRESS_SEMANTIC_PROVIDER':'typesafe','PROOFPRESS_SEMANTIC_MODEL':'fixture','TYPESAFE_API_KEY':'synthetic-test-key'},clear=True),patch('judgment_layer.assessment.build_opener') as network:
            network.return_value.open.return_value=Response()
            result=assess({'output':'fixture'},'Check',options)
            self.assertEqual(result['choice'],'pass')
            request=network.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(request.data)['questions']['assessment']['criteria'],options)
    def test_conflict_stales_old_receipt_and_clear_screen_cannot_admit(self):
        doc=copy.deepcopy(self.doc);doc['judgment']['assertion']={'key':'style','value':'a'}
        x=self.admit(doc)
        packet=self.s.context('coding/generated-files',{'generated_file':True},'agent:test','Fixture')
        doc['judgment']['assertion']['value']='b';y=self.s.capture(doc)
        self.assertEqual(self.s.context('coding/generated-files',{'generated_file':True},'agent:test','Fixture')['judgments'],[])
        self.assertFalse(self.s.check(packet['receipt']['receipt_id'],{'generated_file':True})['ok'])
        self.assertEqual(self.s.state(self.s.record(y['id'])),'proposed')

    def test_decision_model_cli_name_and_legacy_alias(self):
        from judgment_layer.cli import parser
        self.assertTrue(parser().parse_args(['capture','--from','fixture.json','--decision-model']).semantic)
        self.assertTrue(parser().parse_args(['capture','--from','fixture.json','--semantic']).semantic)
    def test_codex_patch_checks_every_target_and_move_destination(self):
        x=self.admit();bind(self.s,self.binding(x),True)
        def event(body):return {'cwd':str(self.root),'tool_name':'apply_patch','tool_input':{'command':'*** Begin Patch\n'+body+'\n*** End Patch'}}
        self.assertTrue(gate(self.s,event('*** Add File: src/a.py\n+fixture'))['ok'])
        self.assertFalse(gate(self.s,event('*** Add File: src/a.py\n+fixture\n*** Add File: generated/b.py\n+fixture'))['ok'])
        self.assertFalse(gate(self.s,event('*** Update File: src/a.py\n*** Move to: generated/a.py\n@@\n-fixture\n+other'))['ok'])
        self.assertFalse(gate(self.s,event('*** Delete File: generated/a.py'))['ok'])
        self.assertFalse(gate(self.s,{'cwd':str(self.root),'tool_name':'apply_patch','tool_input':{'command':'unparsed'}})['ok'])
    def test_condition_binding_passes_then_stales_after_withdrawal_and_revision(self):
        doc=copy.deepcopy(self.doc);doc['applicability']['when']=[]
        x=self.admit(doc);bind(self.s,self.binding(x,'require_conditions'),True)
        self.assertTrue(gate(self.s,self.event())['ok'])
        y=self.s.capture(doc,x['id'],'Synthetic revision',x['digest'])
        self.assertTrue(gate(self.s,self.event())['ok'])
        self.s.owner_action(y['id'],2,y['digest'],'admit','Synthetic fixture',True)
        self.assertIn('superseded',gate(self.s,self.event())['reason'])
        bind(self.s,{**self.binding(y,'require_conditions'),'version':2},True)
        self.assertTrue(gate(self.s,self.event())['ok'])
        self.s.owner_action(y['id'],2,y['digest'],'withdraw','Synthetic fixture',True)
        self.assertIn('withdrawn',gate(self.s,self.event())['reason'])
