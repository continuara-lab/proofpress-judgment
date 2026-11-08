import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from judgment_layer.cli import main
from judgment_layer.model import JudgmentError, canonical, digest
from judgment_layer.presentation import agent_projection, render_text
from judgment_layer.store import Store, initialize

ROOT=Path(__file__).resolve().parents[1]

class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'store'
        initialize(self.root,'human:synthetic-owner')
        self.doc=json.loads((ROOT/'examples/coding.json').read_text())
    def tearDown(self):self.temp.cleanup()
    def op(self, fn):
        s=Store(self.root)
        try:
            with s.transaction():return fn(s)
        finally:s.close()
    def test_compact_context_preserves_guidance_limits_and_receipt(self):
        item=self.op(lambda s:s.capture(self.doc))
        self.op(lambda s:s.owner_action(item['id'],1,item['digest'],'admit','Synthetic fixture',True))
        packet=self.op(lambda s:s.context('coding/generated-files',{'generated_file':True},'agent:test','Fixture'))
        compact=agent_projection('context',packet)
        self.assertEqual(compact['receipt_id'],packet['receipt']['receipt_id'])
        self.assertEqual(compact['judgments'][0]['judgment'],item['record']['judgment'])
        self.assertEqual(compact['judgments'][0]['applicability'],item['record']['applicability'])
        self.assertNotIn('provenance',compact['judgments'][0])
        self.assertLess(len(canonical(compact)),len(canonical(packet)))
        self.assertTrue(self.op(lambda s:s.check(compact['receipt_id'],{'generated_file':True}))['ok'])
        self.op(lambda s:s.owner_action(item['id'],1,item['digest'],'withdraw','Synthetic fixture',True))
        self.assertFalse(self.op(lambda s:s.check(compact['receipt_id'],{'generated_file':True}))['ok'])
    def test_text_default_and_explicit_json(self):
        item=self.op(lambda s:s.capture(self.doc))
        for fmt in ([],['--format','agent'],['--json']):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code=main(['--workspace',str(self.root),'show',item['id'],*fmt])
            self.assertEqual(code,0)
            if fmt:
                result=json.loads(out.getvalue())
                self.assertEqual(result['digest'],item['digest'])
                self.assertEqual('record' in result,fmt==['--json'])
            else:
                self.assertIn(item['record']['judgment']['statement'],out.getvalue())
                self.assertIn('Scope  coding/generated-files',out.getvalue())
                self.assertNotIn('"record":',out.getvalue())
    def test_legacy_schema_and_new_revision_do_not_rewrite_history(self):
        legacy=copy.deepcopy(self.doc)
        legacy['ajf_version']='0.1-draft'
        legacy['provenance']['decision_maker']=legacy['provenance'].pop('judged_by')
        old=self.op(lambda s:s.capture(legacy))
        new=self.op(lambda s:s.capture(self.doc,old['id'],'Synthetic revision',old['digest']))
        self.assertEqual(old['record']['ajf_version'],'0.1-draft')
        self.assertEqual(new['record']['ajf_version'],'0.2-draft')
        self.assertEqual(self.op(lambda s:s.record(old['id'],1)),old['record'])
        self.assertEqual(digest(old['record']),old['digest'])
        self.assertTrue(self.op(lambda s:s.audit())['ok'])
        wrong=copy.deepcopy(legacy);wrong['ajf_version']='0.2-draft'
        with self.assertRaises(JudgmentError):self.op(lambda s:s.capture(wrong))
