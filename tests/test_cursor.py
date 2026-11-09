"""Cursor-native synthetic owner fixtures; no real user records or model calls."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from judgment_layer.cursor import handle, normalize
from judgment_layer.hosts import install, remove, doctor, uninstall, registration
from judgment_layer.runtime import bind
from judgment_layer.store import Store, initialize
from judgment_layer.model import JudgmentError

ROOT=Path(__file__).resolve().parents[1]

class CursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.ws=self.root/'.judgment'
        initialize(self.ws,'human:synthetic');self.s=Store(self.ws)
        doc=json.loads((ROOT/'examples/coding.json').read_text());doc['applicability']['when']=[]
        with self.s.transaction():
            self.item=self.s.capture(doc)
            self.s.owner_action(self.item['id'],1,self.item['digest'],'admit','Synthetic fixture',True)
            self.binding={'project_root':str(self.root),'scope':doc['applicability']['scope'],'judgment_id':self.item['id'],'version':1,'digest':self.item['digest'],'verifier':'deny_generated_write','paths':['generated/*']}
            bind(self.s,self.binding,True)
    def tearDown(self):self.s.close();self.tmp.cleanup()
    def event(self,tool='Write',args=None):
        return {'hook_event_name':'preToolUse','tool_name':tool,'tool_input':args if args is not None else {'path':'generated/user.py','contents':'FIELDS = ["name", "email"]\n'},'cwd':str(self.root),'conversation_id':'synthetic-cursor'}
    def test_native_write_and_shell_block_and_read_preserves_normal_permissions(self):
        self.assertEqual(handle(self.ws,self.event())['permission'],'deny')
        self.assertEqual(handle(self.ws,self.event('Shell',{'command':'echo dangerous'}))['permission'],'deny')
        self.assertEqual(handle(self.ws,self.event('Read',{'path':'generated/user.py'}))['permission'],'allow')
        events=[e for e in self.s.events() if e['kind']=='runtime_checked']
        self.assertEqual(len(events),3)
        self.assertEqual(events[0]['data']['session_id'],'synthetic-cursor')
    def test_ambiguous_or_invalid_events_block(self):
        for value in (None,{},self.event(args={'path':'generated/a','file_path':'generated/b'}),self.event(args={'path':'generated/a','contents':'a','content':'b'})):
            self.assertEqual(handle(self.ws,value)['permission'],'deny')
    def test_symlink_escape_and_partial_edits_block(self):
        outside=Path(self.tmp.name).parent/'synthetic-outside'
        (self.root/'generated').symlink_to(outside,target_is_directory=True)
        self.assertEqual(handle(self.ws,self.event())['permission'],'deny')
        (self.root/'generated').unlink()
        b={**self.binding,'verifier':'decision_model_output'}
        with self.s.transaction():bind(self.s,b,True)
        self.assertEqual(handle(self.ws,self.event('StrReplace',{'path':'generated/user.py','old_string':'a','new_string':'b'}))['permission'],'deny')
    def test_revision_does_not_upgrade_binding_and_withdrawal_stops_reuse(self):
        doc=copy.deepcopy(self.item['record']);doc.pop('id');doc.pop('version');doc['judgment']['statement']='Synthetic allow selected write'
        with self.s.transaction():
            revised=self.s.capture(doc,self.item['id'],'Synthetic revision',self.item['digest'])
            self.s.owner_action(revised['id'],2,revised['digest'],'admit','Synthetic review',True)
        self.assertEqual(handle(self.ws,self.event())['permission'],'deny')
        with self.s.transaction():bind(self.s,{**self.binding,'version':2,'digest':revised['digest'],'verifier':'require_conditions'},True)
        self.assertEqual(handle(self.ws,self.event())['permission'],'allow')
        with self.s.transaction():self.s.owner_action(revised['id'],2,revised['digest'],'withdraw','Synthetic withdrawal',True)
        self.assertEqual(handle(self.ws,self.event())['permission'],'deny')
    def test_installation_preserves_cursor_events_and_other_pretool_hooks(self):
        path=self.root/'.cursor/hooks.json';path.parent.mkdir()
        other={'command':'echo user-policy'}
        original={'version':1,'hooks':{'preToolUse':[other],'stop':[{'command':'echo stop'}]}}
        path.write_text(json.dumps(original))
        with self.s.transaction():install(self.s,self.root,'cursor',False)
        self.assertEqual(json.loads(path.read_text()),original)
        with self.s.transaction():
            install(self.s,self.root,'cursor',True);install(self.s,self.root,'cursor',True)
            result=doctor(self.s,self.root)
        data=json.loads(path.read_text());self.assertEqual(len(data['hooks']['preToolUse']),2)
        self.assertTrue(data['hooks']['preToolUse'][1]['failClosed'])
        self.assertTrue(result['hosts'][0]['configured'])
        with self.s.transaction():uninstall(self.s,self.root,True)
        self.assertEqual(json.loads(path.read_text()),original)
    def test_missing_executable_returns_native_deny(self):
        with patch('judgment_layer.hosts.sys.executable','/synthetic/missing/python'):
            _,entry=registration(self.root,self.ws,'cursor')
        p=subprocess.run(entry['command'],shell=True,capture_output=True,text=True)
        self.assertEqual(json.loads(p.stdout)['permission'],'deny')
