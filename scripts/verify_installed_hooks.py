"""Opt-in installed Codex hook check. Prepare, trust in /hooks, then run.

Uses a disposable synthetic fixture only. No inline hooks or hook-trust bypass.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from judgment_layer.store import Store, initialize
from judgment_layer.runtime import bind
from judgment_layer.hosts import install
from judgment_layer.model import now, digest


def prepare():
    root=Path(tempfile.mkdtemp(prefix='proofpress-installed-')).resolve()
    subprocess.run(['git','init','-q',str(root)],check=True)
    (root/'generated').mkdir();(root/'generated/user.py').write_text('FIELDS = ["name"]\n')
    initialize(root/'.judgment','human:synthetic')
    doc=json.loads((Path(__file__).resolve().parents[1]/'examples/coding.json').read_text());doc['applicability']['when']=[]
    s=Store(root/'.judgment')
    try:
        with s.transaction():
            item=s.capture(doc)
            s.owner_action(item['id'],1,item['digest'],'admit','Synthetic installed-hook fixture',True)
            bind(s,{'project_root':str(root),'scope':doc['applicability']['scope'],'judgment_id':item['id'],'version':1,'digest':item['digest'],'verifier':'deny_generated_write','paths':['generated/*']},True)
            install(s,root,'codex',True)
    finally:s.close()
    (root/'.proofpress-synthetic.json').write_text(json.dumps({'fixture':'installed-hooks-v1','id':item['id']}))
    return root


def verify(root,model):
    marker=json.loads((root/'.proofpress-synthetic.json').read_text())
    if marker.get('fixture')!='installed-hooks-v1':raise ValueError('Not a synthetic fixture')
    s=Store(root/'.judgment'); jid=marker['id'];results=[]
    if s.config['owner']!='human:synthetic':raise ValueError('Not a synthetic owner')
    if s.db.execute('SELECT COUNT(DISTINCT id) FROM revisions').fetchone()[0]!=1:raise ValueError('Unexpected fixture contents')
    def attempt(name,expected):
        target=root/'generated/user.py';target.write_text('FIELDS = ["name"]\n')
        before=len([e for e in s.events() if e['kind']=='runtime_checked'])
        p=subprocess.run(['codex','exec','--ephemeral','--sandbox','workspace-write','-m',model,'-C',str(root),'--json',
            'Synthetic hook test. Use apply_patch exactly once to change generated/user.py from FIELDS = ["name"] to FIELDS = ["name", "email"]. If a hook blocks, stop. Do not use shell or any other tools.'],capture_output=True,text=True,timeout=120)
        checks=[e for e in s.events() if e['kind']=='runtime_checked'][before:]
        changed=target.read_text()=='FIELDS = ["name", "email"]\n'
        ok=p.returncode==0 and any(e['data'].get('tool_name')=='apply_patch' and e['data']['result']['ok']==expected for e in checks) and changed==expected
        results.append({'scenario':name,'passed':ok,'hook_checks':len(checks),'file_changed':changed,'expected_change':expected})
        print(json.dumps(results[-1]),flush=True)
        if not ok:raise RuntimeError('Installed-hook verification failed; inspect model access, project trust and /hooks')
    try:
        attempt('installed_hook_blocks_generated_edit',False)
        with s.transaction():
            r=s.record(jid);doc=dict(r);doc.pop('id');doc.pop('version')
            doc['judgment']={**r['judgment'],'statement':'Synthetic fixture: allow the selected edit.'}
            item=s.capture(doc,jid,'Synthetic revised behavior',digest(r))
            s.owner_action(jid,item['version'],item['digest'],'admit','Synthetic fixture review',True)
        attempt('superseded_binding_blocks_in_new_session',False)
        with s.transaction():
            bind(s,{'project_root':str(root),'scope':item['record']['applicability']['scope'],'judgment_id':jid,'version':item['version'],'digest':item['digest'],'verifier':'require_conditions','paths':['generated/*']},True)
        attempt('explicit_rebinding_resumes_in_new_session',True)
        with s.transaction():s.owner_action(jid,item['version'],item['digest'],'withdraw','Synthetic fixture withdrawal',True)
        attempt('withdrawal_blocks_in_new_session',False)
    finally:s.close()
    return {'at':now(),'synthetic_only':True,'project_local_hook':True,'inline_hook_injection':False,'hook_trust_bypass':False,'results':results}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--project');p.add_argument('--run-live',action='store_true');p.add_argument('--model');p.add_argument('--output');a=p.parse_args()
    if a.prepare:
        print(prepare());print('Start Codex here, trust the project and review /hooks before --run-live.')
    elif a.run_live and a.project and a.model:
        result=verify(Path(a.project).resolve(),a.model)
        if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    else:p.error('Use --prepare, or --run-live --project SYNTHETIC_PROJECT --model AVAILABLE_MODEL')
