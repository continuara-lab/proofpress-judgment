import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from judgment_layer.history import ingest, consolidate, preview
from judgment_layer.intake import onboard, policy, set_policy, observe, review_assist
from judgment_layer.model import JudgmentError, digest, validate
from judgment_layer.store import Store, initialize

ROOT=Path(__file__).resolve().parents[1]

class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        initialize(self.root/'store','human:synthetic');self.s=Store(self.root/'store')
        self.doc=json.loads((ROOT/'examples/coding.json').read_text())
        self.file=self.root/'session.jsonl'
        self.rows=[{'type':'session_meta','payload':{'id':'synthetic-session','cwd':str(self.root)}},
                   {'type':'response_item','timestamp':'2026-11-08T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Do not modify generated files. api_key=synthetic-private-token'}]}},
                   {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'I will change the source instead.'}]}}]
        self.file.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
    def tearDown(self):self.s.close();self.tmp.cleanup()
    def op(self,fn):
        with self.s.transaction():return fn()
    def test_onboarding_preview_and_manual_policy(self):
        project=self.root/'project';project.mkdir()
        result=onboard(project,'.judgment',['codex'],None,False)
        self.assertEqual(result['status'],'preview');self.assertFalse((project/'.judgment').exists())
        result=onboard(project,'.judgment',['codex'],'human:synthetic',True)
        self.assertFalse(result['hooks_installed']);self.assertEqual(result['capture_policy']['review'],'manual')
        bad=copy.deepcopy(policy(self.s));bad['review']='automatic'
        with self.assertRaises(JudgmentError):self.op(lambda:set_policy(self.s,bad,True))
        with self.assertRaises(JudgmentError):self.op(lambda:set_policy(self.s,policy(self.s),False))
    def test_new_ajf_and_legacy_immutable(self):
        old=copy.deepcopy(self.doc);old['ajf_version']='0.2-draft'
        first=self.op(lambda:self.s.capture(old))
        doc=copy.deepcopy(self.doc);doc['context']={'situation':'Generator overwrites edits','goal':'Durable change','constraints':['Local only']}
        doc['alternatives']=[{'option':'Patch generated file','reason_not_chosen':'Will be overwritten'}]
        doc['expected_outcome']={'description':'Change survives regeneration','verification':'Run generator'}
        doc['judgment']['polarity']='avoid'
        second=self.op(lambda:self.s.capture(doc,first['id'],'Synthetic new context',first['digest']))
        self.assertEqual(second['record']['ajf_version'],'0.3-draft')
        self.assertEqual(digest(self.s.record(first['id'],1)),first['digest'])
        doc['ajf_version']='0.2-draft'
        with self.assertRaises(JudgmentError):self.op(lambda:self.s.capture(doc))
    def test_observation_append_idempotency_and_digest(self):
        x=self.op(lambda:self.s.capture(self.doc));body=copy.deepcopy(x['record'])
        value={'judgment_id':x['id'],'version':1,'digest':x['digest'],'kind':'task','result':'failed',
               'summary':'Synthetic negative outcome','observer':'agent:test','observed_at':'2026-11-08T00:00:00Z',
               'evidence_refs':['synthetic://test'],'idempotency_key':'fixture-1'}
        self.op(lambda:observe(self.s,value));self.assertTrue(self.op(lambda:observe(self.s,value))['duplicate'])
        self.assertEqual(self.s.record(x['id'],1),body);self.assertEqual(self.s.state(body),'proposed')
        value['summary']='different'
        with self.assertRaises(JudgmentError):self.op(lambda:observe(self.s,value))
        value.pop('idempotency_key');value['digest']='bad'
        with self.assertRaises(JudgmentError):self.op(lambda:observe(self.s,value))
    def test_history_local_preview_redaction_and_idempotent_mirror(self):
        self.assertEqual(preview(self.file,self.root)['messages'],2)
        first=self.op(lambda:ingest(self.s,self.file,self.root));self.assertEqual(first['messages'],2)
        self.assertTrue(self.op(lambda:ingest(self.s,self.file,self.root))['duplicate'])
        self.assertNotIn('synthetic-private-token',json.dumps(self.s.events()))
        mirror=self.root/'mirror.jsonl';mirror.write_bytes(self.file.read_bytes())
        self.assertEqual(self.op(lambda:ingest(self.s,mirror,self.root))['messages'],0)
        self.assertEqual(self.s.db.execute('select count(*) from revisions').fetchone()[0],0)
    def test_project_history_preview_and_confirm_are_scoped_and_idempotent(self):
        from judgment_layer.cli import parser, run
        session_root = self.root/'sessions'; session_root.mkdir()
        (session_root/'one.jsonl').write_bytes(self.file.read_bytes())
        other = copy.deepcopy(self.rows); other[0]['payload']['cwd'] = str(self.root/'other')
        (session_root/'other.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in other))
        args = parser().parse_args(['--workspace', str(self.root/'store'), 'history', 'project', '--root', str(session_root), '--project', str(self.root)])
        result = run(args)
        self.assertEqual(result['sessions'], 1)
        self.assertFalse(any(e['kind']=='history_imported' for e in self.s.events()))
        args.confirm = True
        self.assertEqual(run(args)['messages'], 2)
        self.assertEqual(run(args)['messages'], 0)
        self.assertEqual(self.s.db.execute('select count(*) from revisions').fetchone()[0], 0)
    def test_partial_append_and_source_replacement(self):
        self.file.write_text(self.file.read_text()+'{"partial":')
        self.op(lambda:ingest(self.s,self.file,self.root))
        self.assertTrue(self.op(lambda:ingest(self.s,self.file,self.root))['duplicate'])
        raw=self.file.read_text().replace('Do not modify','Never modify')
        self.file.write_text(raw)
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,self.file,self.root))
    def test_project_mismatch_malformed_and_symlink_preserve_checkpoint(self):
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,self.file,self.root/'other'))
        link=self.root/'link.jsonl';link.symlink_to(self.file)
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,link,self.root))
        self.file.write_text(self.file.read_text()+'not-json\n')
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,self.file,self.root))
        self.assertFalse(any(e['kind']=='history_imported' for e in self.s.events()))
    def test_consolidation_opt_in_candidate_only_and_retry(self):
        self.op(lambda:ingest(self.s,self.file,self.root))
        self.assertEqual(self.op(lambda:consolidate(self.s,'coding'))['pending_batches'],1)
        source=self.s.events()[-1]['data']['batch']['messages'][0]['source_ref']
        candidate={'name':'avoid-hand-edits','statement':'Change source instead.','rationale':'Preserve generation.',
                   'situation':'Synthetic generator workflow','polarity':'avoid','source_refs':[source]}
        with patch('judgment_layer.history.extract',return_value=[candidate]):
            result=self.op(lambda:consolidate(self.s,'coding',True))
            self.assertEqual(result['candidates'][0]['state'],'proposed')
            self.assertEqual(self.op(lambda:consolidate(self.s,'coding',True))['candidates'],[])
        self.assertEqual(self.s.context('coding',{},'agent:test','fixture')['judgments'],[])
    def test_extraction_failure_rolls_back_and_unknown_refs_rejected(self):
        self.op(lambda:ingest(self.s,self.file,self.root))
        with patch('judgment_layer.history.extract',side_effect=JudgmentError('fixture')):
            with self.assertRaises(JudgmentError):self.op(lambda:consolidate(self.s,'coding',True))
        self.assertEqual(self.op(lambda:consolidate(self.s,'coding'))['pending_batches'],1)
    def test_assisted_review_never_approves(self):
        x=self.op(lambda:self.s.capture(self.doc))
        with patch('judgment_layer.assessment.assess',return_value={'choice':'supported'}):
            result=self.op(lambda:review_assist(self.s,x['id']))
        self.assertTrue(result['ok']);self.assertEqual(self.s.state(self.s.record(x['id'])),'proposed')
    def test_scope_change_record_rejected_and_mirror_collision_flagged(self):
        self.op(lambda:ingest(self.s,self.file,self.root))
        mirror=self.root/'mirror.jsonl'
        mirror.write_text(self.file.read_text().replace('Do not modify','Never modify!'))
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,mirror,self.root))
        # Identical reference range, different content must not silently deduplicate.
        other=self.root/'other.jsonl'
        other.write_text(self.file.read_text()+json.dumps({'type':'turn_context','payload':{'cwd':str(self.root/'other')}})+'\n')
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,other,self.root))
    def test_observation_receipt_must_contain_exact_version(self):
        x=self.op(lambda:self.s.capture(self.doc))
        packet=self.op(lambda:self.s.context('coding/generated-files',{'generated_file':True},'agent:test','fixture'))
        value={'judgment_id':x['id'],'version':1,'digest':x['digest'],'kind':'task','result':'unknown','summary':'Fixture',
               'observer':'agent:test','observed_at':'2026-11-08T00:00:00Z','evidence_refs':['synthetic://fixture'],
               'usage_receipt':packet['receipt']['receipt_id']}
        with self.assertRaises(JudgmentError):self.op(lambda:observe(self.s,value))
    def test_context_projection_keeps_new_fields(self):
        from judgment_layer.presentation import agent_projection
        doc=copy.deepcopy(self.doc);doc['context']={'situation':'Synthetic generator'}
        doc['expected_outcome']={'description':'Changes survive'}
        x=self.op(lambda:self.s.capture(doc))
        self.op(lambda:self.s.owner_action(x['id'],1,x['digest'],'admit','Synthetic fixture',True))
        packet=self.op(lambda:self.s.context('coding/generated-files',{'generated_file':True},'agent:test','fixture'))
        projected=agent_projection('context',packet)['judgments'][0]
        self.assertEqual(projected['context'],doc['context'])
        self.assertEqual(projected['expected_outcome'],doc['expected_outcome'])
    def test_metadata_scan_has_no_import_side_effect(self):
        from judgment_layer.history import scan
        result=scan(self.root,self.root)
        self.assertEqual(len(result['sessions']),1)
        self.assertNotIn('text',str(result))
        self.assertEqual(self.s.events(),[])
    def test_disabled_history_stops_import_and_model_processing(self):
        self.op(lambda:ingest(self.s,self.file,self.root))
        changed=copy.deepcopy(policy(self.s));changed['history']='none';changed['triggers']=[]
        self.op(lambda:set_policy(self.s,changed,True))
        with self.assertRaises(JudgmentError):self.op(lambda:ingest(self.s,self.file,self.root))
        with patch('judgment_layer.history.extract') as model:
            with self.assertRaises(JudgmentError):self.op(lambda:consolidate(self.s,'coding',True))
            model.assert_not_called()
    def test_scan_title_selection_is_stable_across_new_sessions(self):
        import sqlite3
        from judgment_layer.history import scan, resolve_selection
        sessions=self.root/'sessions';sessions.mkdir()
        source=sessions/'one.jsonl';source.write_bytes(self.file.read_bytes())
        with sqlite3.connect(self.root/'state_5.sqlite') as db:
            db.execute('create table threads(id text, title text, cwd text)')
            db.execute('insert into threads values(?,?,?)',('synthetic-session','Readable test title',str(self.root)))
        first=scan(sessions,self.root)['sessions'][0]
        self.assertEqual(first['title'],'Readable test title')
        another=sessions/'another.jsonl';another.write_bytes(source.read_bytes())
        self.assertEqual(resolve_selection(sessions,self.root,7,first['source_key']),str(source.resolve()))
        self.assertNotEqual(scan(sessions,self.root)['sessions'][0]['source_key'],scan(sessions,self.root)['sessions'][1]['source_key'])
    def test_scan_previews_are_optional_bounded_and_redacted(self):
        from judgment_layer.history import scan
        basic=scan(self.root,self.root)['sessions'][0]
        self.assertIsNone(basic['preview'])
        expanded=scan(self.root,self.root,previews=True)['sessions'][0]
        self.assertIn('Do not modify generated files',expanded['preview'])
        self.assertNotIn('synthetic-private-token',expanded['preview'])
        self.assertLessEqual(len(expanded['preview']),160)

    def test_claude_session_import_checks_project_and_ignores_nontext(self):
        from judgment_layer.history import scan, resolve_selection
        history = self.root / 'claude-projects'
        directory = history / 'project-slug'
        directory.mkdir(parents=True)
        path = directory / 'session.jsonl'
        meta = {'sessionId': 'claude-id', 'cwd': str(self.root)}
        records = [
            {'type': 'queue-operation', 'content': 'Ignore queue metadata'},
            {'type': 'user', **meta, 'message': {'role': 'user', 'content': 'Prefer public cache.'}},
            {'type': 'assistant', **meta, 'message': {'role': 'assistant', 'content': [
                {'type': 'thinking', 'thinking': 'Ignore hidden reasoning'},
                {'type': 'tool_use', 'input': {'text': 'Ignore tool input'}},
                {'type': 'text', 'text': 'I will recheck permissions.'},
            ]}},
            {'type': 'user', **meta, 'message': {'role': 'user', 'content': [
                {'type': 'tool_result', 'content': 'Ignore tool output'},
            ]}},
        ]
        path.write_text(''.join(json.dumps(row) + '\n' for row in records))
        sessions = scan(history, self.root, previews=True, agent='claude-code')['sessions']
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['preview'], 'Prefer public cache.')
        self.assertEqual(resolve_selection(history, self.root, 7, sessions[0]['source_key'], agent='claude-code'), str(path))
        self.assertEqual(scan(history, self.root / 'other', agent='claude-code')['sessions'], [])
        self.assertEqual(preview(path, self.root, agent='claude-code')['messages'], 2)
        self.assertEqual(self.s.events(), [])
        self.op(lambda: ingest(self.s, path, self.root, agent='claude-code'))
        batch = self.s.events()[-1]['data']['batch']
        self.assertEqual([m['text'] for m in batch['messages']], ['Prefer public cache.', 'I will recheck permissions.'])
        self.assertTrue(batch['messages'][0]['source_ref'].startswith('claude-code://claude-id/bytes/'))
        with path.open('a') as stream:
            stream.write(json.dumps({**records[1], 'cwd': str(self.root / 'other')}) + '\n')
        with self.assertRaises(JudgmentError):
            self.op(lambda: ingest(self.s, path, self.root, agent='claude-code'))
        self.assertEqual(self.s.events()[-1]['data']['batch']['offset'], batch['offset'])

    def test_cursor_project_import_resumes_with_native_transcripts(self):
        import re
        from judgment_layer.cli import parser, run

        history = self.root / 'cursor-projects'
        slug = re.sub(r'[^a-zA-Z0-9-]', '-', str(self.root).lstrip('/'))
        directory = history / slug / 'agent-transcripts' / 'cursor-id'
        directory.mkdir(parents=True)
        path = directory / 'cursor-id.jsonl'
        user = {'role': 'user', 'message': {'content': [{'type': 'text', 'text': 'Cache public results.'}]}}
        assistant = {'role': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Recheck private access.'}]}}
        partial = json.dumps(assistant)
        path.write_text(json.dumps(user) + '\n' + partial)
        args = ['--workspace', str(self.s.root), 'history', 'project', '--agent', 'cursor',
                '--project', str(self.root), '--root', str(history)]
        preview_result = run(parser().parse_args(args))
        self.assertEqual(preview_result['sessions'], 1)
        self.assertFalse(preview_result['imported'])
        self.assertEqual(self.s.events(), [])
        self.assertEqual(run(parser().parse_args(args + ['--confirm']))['pending_bytes'], len(partial))
        with path.open('a') as stream:
            stream.write('\n' + json.dumps({'type': 'turn_ended', 'status': 'completed'}) + '\n')
        self.assertEqual(run(parser().parse_args(args + ['--confirm']))['messages'], 1)
        self.assertEqual(run(parser().parse_args(args + ['--confirm']))['messages'], 0)
        imported = [event['data']['batch'] for event in self.s.events() if event['kind'] == 'history_imported']
        self.assertEqual([batch['agent'] for batch in imported], ['cursor', 'cursor'])
        self.assertTrue(imported[1]['messages'][0]['source_ref'].startswith('cursor://cursor-id/bytes/'))
        with self.assertRaises(JudgmentError):
            self.op(lambda: ingest(self.s, path, self.root / 'other', agent='cursor'))
