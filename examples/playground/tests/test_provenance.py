import asyncio
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import trace_mcp
from trace_mcp.tools.decision_tools import resolve_decision
from trace_mcp.tools.session_tools import append_event
from trace_mcp.schema import Actor, TraceEvent, AnnotationData
from trace_mcp.validate import load_schema
from jsonschema import validate
import playground as app
from provenance import Provenance


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=app.PROJECT
        app.PROJECT=Path(self.tmp.name)/'sandbox'
        app.install()
        self.history=Provenance(app.PROJECT)
    def tearDown(self):
        app.PROJECT=self.previous
        self.tmp.cleanup()
    def test_runtime_comes_from_local_source_fork(self):
        self.assertTrue(Path(inspect.getfile(trace_mcp)).resolve().is_relative_to(app.ROOT/'vendor/provenance-core/src'))
    def seed_choice(self):
        sid=self.history.start('Synthetic coding task')
        eid=self.history.decision(sid,'Use hyphens','Synthetic reported rationale')
        self.history.finish(sid,'Synthetic task completed; no human acceptance claimed')
        return sid,eid
    def test_native_capture_correction_import_and_export(self):
        sid,eid=self.seed_choice()
        item=app.capture('Synthetic correction: use underscores for internal URLs.')
        self.assertEqual(item['state'],'proposed')
        source=item['record']['extensions']['trace']
        self.assertEqual(source['historical_disposition'],'proposed')
        document=self.history.export(source['session_id'])
        validate(document,load_schema())
        annotations=[e for e in document['events'] if e['type']=='annotation']
        self.assertEqual(annotations[0]['annotation']['corrects_event_ids'],[self.history.uri(sid,eid)])
        self.assertEqual(annotations[0]['actor']['type'],'human')
        self.assertTrue((app.PROJECT/'.provenance/exports'/(document['id']+'.md')).exists())
        with app.store() as s:
            self.assertEqual(s.context(app.SCOPE,{'surface':'internal'},'agent:fixture','Fixture')['judgments'],[])
        # Synthetic owner gesture in temporary fixture only.
        app.review({**item,'action':'admit','reason':'Synthetic owner fixture'})
        revised=app.capture('Synthetic revised correction: preserve Chinese too.',True)
        newer=self.history.export(revised['record']['extensions']['trace']['session_id'])
        correction=next(e for e in newer['events'] if e['type']=='annotation')
        self.assertEqual(correction['annotation']['corrects_event_ids'],[self.history.uri(source['session_id'],source['event_id'])])
        with app.store() as s:
            self.assertEqual(s.context(app.SCOPE,{'surface':'internal'},'agent:fixture','Fixture')['judgments'][0]['version'],1)
    def test_completed_capture_cannot_be_appended(self):
        sid,_=self.seed_choice()
        with self.assertRaises(ValueError):self.history.decision(sid,'late edit','not allowed')
    def test_historical_acceptance_does_not_admit_judgment(self):
        item=app.capture('Synthetic human guidance')
        source=item['record']['extensions']['trace']
        asyncio.run(resolve_decision(self.history.storage,self.history.load(source['session_id']),
            event_id=source['event_id'],disposition='accepted',resolved_by_type='human',
            resolved_by_id='human:synthetic-independent-reviewer'))
        with app.store() as s:
            self.assertEqual(s.state(s.record(item['id'])),'proposed')
            self.assertEqual(s.context(app.SCOPE,{'surface':'internal'},'agent:fixture','Fixture')['judgments'],[])

    def test_failed_agent_run_retains_completed_error_session(self):
        with patch('playground.subprocess.Popen',side_effect=FileNotFoundError('synthetic unavailable agent')):
            result=app.run_agent()
        self.assertEqual(result['status'],'failed')
        session=self.history.export(result['capture_session'])
        validate(session,load_schema())
        self.assertEqual(session['status'],'completed')
        calls=[e for e in session['events'] if e['type']=='tool_call']
        self.assertEqual(calls[0]['tool_call']['status'],'error')
        self.assertFalse(any(e['type']=='decision' for e in session['events']))

    def test_import_failure_keeps_source_without_admission(self):
        with patch('judgment_layer.store.Store.capture',side_effect=RuntimeError('synthetic import failure')):
            with self.assertRaises(RuntimeError):app.capture('Synthetic source record retained despite failed import')
        self.assertEqual(len(self.history.inspect()),1)
        self.assertEqual(app.state()['records'],[])

    def test_stale_receipt_prevents_draft_files_from_being_released(self):
        item=app.capture('Synthetic guidance')
        app.review({**item,'action':'admit','reason':'Synthetic fixture'})
        class Process:
            returncode=0
            def __init__(self,args,**kwargs):self.output=Path(args[args.index('--output-last-message')+1])
            def communicate(self,*args,**kwargs):
                self.output.write_text(json.dumps({'code':'fixture','tests':'fixture','choice':'fixture','rationale':'fixture'}))
        with patch('playground.subprocess.Popen',Process),patch('judgment_layer.store.Store.check',return_value={'ok':False,'reasons':['withdrawn']}):
            result=app.run_agent()
        self.assertEqual(result['status'],'failed')
        self.assertIsNone(result['output'])
        self.assertFalse((app.PROJECT/'runs'/result['id']/'solution.py').exists())
