"""Session-local onboarding, explicit capture policy, and append-only observations."""
from pathlib import Path
import getpass

from .model import JudgmentError, canonical, digest, instant, now
from .setup import setup
from .store import Store

DEFAULT_POLICY={'version':1,'triggers':['human_judgment','human_correction','agent_judgment','task_end'],
                'extraction':'manual','history':'selected_only','review':'manual',
                'max_excerpt_chars':24000}


def policy(store):
    events=[e for e in store.events() if e['kind']=='capture_policy_set']
    return events[-1]['data']['policy'] if events else dict(DEFAULT_POLICY)


def set_policy(store, value, confirmed):
    if not confirmed:raise JudgmentError('Capture policy changes require human --confirm')
    if not isinstance(value,dict) or set(value)!=set(DEFAULT_POLICY) or value['version']!=1:
        raise JudgmentError('Unsupported capture policy shape')
    if not isinstance(value['triggers'],list) or any(x not in DEFAULT_POLICY['triggers'] for x in value['triggers']):
        raise JudgmentError('Unsupported capture trigger')
    if value['extraction'] not in {'manual','assisted'} or value['history'] not in {'selected_only','none'} or value['review']!='manual':
        raise JudgmentError('Only selected history and manual admission are supported')
    if type(value['max_excerpt_chars']) is not int or not 1000<=value['max_excerpt_chars']<=24000:
        raise JudgmentError('Excerpt limit must be between 1000 and 24000 characters')
    store.append('capture_policy_set',store.config['owner'],data={'policy':value})
    return {'ok':True,'capture_policy':value}


def onboard(project, workspace, agents, owner, confirmed, selection=None, upgrade=False):
    root=Path(project).resolve();path=Path(workspace)
    path=path if path.is_absolute() else root/path
    base=dict(DEFAULT_POLICY)
    if path.exists():
        existing=Store(path)
        try:
            with existing.transaction():base=policy(existing)
        finally:existing.close()
    value={**base,**(selection or {})}
    result=setup(root,workspace,agents,owner,dry_run=not confirmed,upgrade=upgrade)
    if confirmed:
        s=Store(path)
        try:
            with s.transaction():
                if selection is not None or not any(e['kind']=='capture_policy_set' for e in s.events()):set_policy(s,value,True)
                value=policy(s)
        finally:s.close()
    return {**result,'capture_policy':value,'status':'enabled' if confirmed else 'preview',
            'boundary':'Project skill and capture guidance only. No background listener, scheduler, automatic admission, or host hook is installed.'}


def observe(store, value):
    required={'judgment_id','version','digest','kind','result','summary','observer','observed_at','evidence_refs'}
    if not isinstance(value,dict) or not required<=value.keys() or set(value)-required-{'usage_receipt','idempotency_key'}:
        raise JudgmentError('Invalid outcome observation shape')
    if value['kind'] not in {'execution','task','long_term'} or value['result'] not in {'succeeded','failed','mixed','unknown'}:
        raise JudgmentError('Invalid outcome kind or result')
    for field in ['summary','observer','observed_at']:
        if not isinstance(value[field],str) or not value[field].strip():raise JudgmentError('Observation fields must be nonempty')
    instant(value['observed_at']);canonical(value)
    if type(value['version']) is not int:raise JudgmentError('Observation version must be an integer')
    refs=value['evidence_refs']
    if not isinstance(refs,list) or not refs or any(not isinstance(x,str) or not x.strip() for x in refs):
        raise JudgmentError('Observation requires evidence references')
    r=store.record(value['judgment_id'],value['version'])
    if digest(r)!=value['digest']:raise JudgmentError('Observation must bind an exact revision digest')
    if 'usage_receipt' in value:
        receipts=[e['data']['receipt'] for e in store.events() if e['kind']=='context_supplied' and e['data']['receipt']['receipt_id']==value['usage_receipt']]
        if not receipts or not any(x['id']==r['id'] and x['version']==r['version'] and x['digest']==value['digest'] for x in receipts[0]['items']):
            raise JudgmentError('Usage receipt does not include this exact revision')
    if 'idempotency_key' in value:
        if not isinstance(value['idempotency_key'],str) or not value['idempotency_key'].strip():raise JudgmentError('Invalid idempotency key')
        previous=[e for e in store.events() if e['kind']=='outcome_observed' and e['data']['observation'].get('idempotency_key')==value['idempotency_key']]
        if previous:
            if canonical(previous[0]['data']['observation'])!=canonical(value):raise JudgmentError('Observation key reused with changed content')
            return {'ok':True,'event_id':previous[0]['event_id'],'duplicate':True}
    event=store.append('outcome_observed',value['observer'],r,data={'observation':value})
    return {'ok':True,'event_id':event['event_id'],'boundary':'Sourced observation, not verified causality, approval, or proof of reliance.'}


def review_assist(store, jid):
    from .assessment import assess
    from .runtime import screen
    r=store.record(jid)
    deterministic=screen(store,store.describe(r))
    refs=set(r['provenance']['source_refs'])
    excerpts=[m for e in store.events() if e['kind']=='history_imported' for m in e['data']['batch']['messages'] if m['source_ref'] in refs]
    assessment=assess({'candidate':r,'source_excerpts':excerpts},
        'Assess whether the supplied evidence supports this candidate at its stated scope. If source evidence is absent or insufficient choose unknown. Do not infer human approval.',
        {'supported':'Evidence supports the bounded candidate.','revise':'Evidence contradicts the candidate or its scope is broader than supported.','unknown':'Evidence is absent or insufficient.'})
    result={'ok':deterministic['ok'] and assessment['choice']=='supported','id':r['id'],'version':r['version'],'digest':digest(r),
            'flags':deterministic['flags'],'assessment':assessment,'boundary':'Review assistance only. Manual admission remains required.'}
    store.append('review_assessed','agent:review-assistant',r,data={'result':result})
    return result
