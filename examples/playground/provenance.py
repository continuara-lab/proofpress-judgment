"""Proofpress capture API backed by our checked-in provenance source fork.

Upstream-compatible wire fields stay internal; judgment admission belongs to Proofpress.
"""
import asyncio
import hashlib
import json
from pathlib import Path

from trace_mcp.project_identity import canonical_project_key
from trace_mcp.storage.json_file import JsonFileStorage
from trace_mcp.tools.session_tools import create_session, end_session
from trace_mcp.tools.decision_tools import propose_decision
from trace_mcp.tools.logging_tools import log_annotation, log_tool_call, log_contribution
from trace_mcp.tools.export_tools import export_session
from trace_mcp.tools.query_tools import get_events

REVISION = 'd18a0bd1bf36eb625836fbbab78ae4bbd78c0db9'


class Provenance:
    def __init__(self, project):
        self.root = Path(project).resolve()
        self.storage = JsonFileStorage(str(self.root / '.provenance/sessions'))
        # Unique per selected sandbox, using TRACE's native canonical key logic.
        self.project = canonical_project_key('proofpress-playground-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:16])

    def start(self, description):
        session = asyncio.run(create_session(self.storage, {}, project=self.project,
            project_key=self.project, description=description,
            participants=[{'type':'human','id':'human:playground'},
                          {'type':'ai','id':'agent:codex-playground'},
                          {'type':'system','id':'system:playground'}]))
        return session.id

    def load(self, sid):
        session = asyncio.run(self.storage.get_session(sid))
        if session.metadata.project_key != self.project:
            raise ValueError('Provenance session belongs to another sandbox')
        return session

    def judgment(self, sid, text, rationale, human=False, snippet=None):
        return asyncio.run(propose_decision(self.storage, self.load(sid), description=text,
            rationale=rationale, proposed_by_type='human' if human else 'ai',
            proposed_by_id='human:playground' if human else 'agent:codex-playground',
            suggestion_type='proactive' if human else 'requested', conversation_snippet=snippet))

    def correction(self, sid, text, target=None):
        return asyncio.run(log_annotation(self.storage,self.load(sid),
            category='correction' if target else 'learning', content=text,
            actor_type='human', actor_id='human:playground',
            corrects_event_ids=[target] if target else [], conversation_snippet=text))

    def call(self, sid, surface, receipt, status='success', error=None):
        return asyncio.run(log_tool_call(self.storage,self.load(sid),server='codex-cli',
            tool_name='codex exec', input={'surface':surface,'context_receipt':receipt},
            output={'artifact_directory':str(self.root/'runs')},status=status,
            error_message=error,host='external',actor_type='system',actor_id='system:playground'))

    def contribution(self, sid, decision, artifact, snippet):
        return asyncio.run(log_contribution(self.storage,self.load(sid),
            description='Generated code draft; tests saved but not executed.',
            direction='human', execution='ai', artifact=str(artifact),
            related_decision_ids=[decision],actor_id='agent:codex-playground',
            conversation_snippet=snippet))

    def finish(self, sid, summary):
        result = asyncio.run(end_session(self.storage,{},session_id=sid,summary=summary))
        if result.startswith('Error:'): raise ValueError(result)
        session = self.load(sid)
        # Native export, a derived human view of the native JSON store.
        destination=self.root/'.provenance/exports'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/(sid+'.md')).write_text(export_session(session,format='markdown'))
        return result

    def export(self, sid):
        return json.loads(export_session(self.load(sid),format='json'))

    def inspect(self, sid=None):
        if sid: return self.export(sid)
        if not (self.root/'.provenance/sessions').exists(): return []
        summaries=asyncio.run(self.storage.list_sessions(limit=10000))
        return [self.export(s['id']) for s in reversed(summaries)]

    def last_ai_judgment(self):
        for session in reversed(self.inspect()):
            for event in reversed(get_events(self.load(session['id']),type_filter='decision')):
                if event['decision']['proposed_by']['type']=='ai':
                    return self.uri(session['id'],event['id'])
        return None

    @staticmethod
    def uri(sid, event):
        return 'trace://'+sid+'/event/'+event

# Compatibility for existing integrations; not a second product vocabulary.
Provenance.decision = Provenance.judgment
Provenance.last_ai_decision = Provenance.last_ai_judgment
