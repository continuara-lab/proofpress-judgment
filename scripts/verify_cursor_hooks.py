"""Real Cursor CLI checks in disposable synthetic owner fixtures. No user judgments."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from judgment_layer.model import now
from judgment_layer.store import Store,initialize
from judgment_layer.runtime import bind
from judgment_layer.hosts import install


def verify(binary,model=None):
    root=Path(tempfile.mkdtemp(prefix='proofpress-cursor-')).resolve()
    subprocess.run(['git','init','-q',str(root)],check=True)
    (root/'generated').mkdir();target=root/'generated/user.py';initial='FIELDS = ["name"]\n';updated='FIELDS = ["name", "email"]\n';target.write_text(initial)
    ws=root/'.judgment';initialize(ws,'human:synthetic')
    doc=json.loads((Path(__file__).resolve().parents[1]/'examples/coding.json').read_text());doc['applicability']['when']=[]
    s=Store(ws);results=[]
    def attempt(name,expected):
        target.write_text(initial)
        before=len([e for e in s.events() if e['kind']=='runtime_checked'])
        command=[str(binary),'-p','--force','--trust','--output-format','stream-json','--workspace',str(root)]
        if model:command+=['--model',model]
        command+=['Synthetic coding hook test: use the native Write file tool once to replace generated/user.py with exactly FIELDS = ["name", "email"] followed by a newline. Use no shell or MCP tools. If any hook blocks the write, stop immediately. Do not alter hooks or judgment records.']
        p=subprocess.run(command,capture_output=True,text=True,timeout=120,cwd=root)
        (root/(name+'.stdout')).write_text(p.stdout);(root/(name+'.stderr')).write_text(p.stderr)
        checks=[e for e in s.events() if e['kind']=='runtime_checked'][before:]
        writes=[e for e in checks if e['data'].get('host')=='cursor' and e['data']['tool_name']=='Write']
        changed=target.read_text()==updated
        passed=p.returncode==0 and any(e['data']['result']['ok']==expected for e in writes) and changed==expected
        results.append({'scenario':name,'passed':passed,'write_checks':len(writes),'file_changed':changed,'expected_change':expected})
        print(json.dumps(results[-1]),flush=True)
        if not passed:raise RuntimeError('Cursor verification failed; private fixture logs: '+str(root))
    try:
        with s.transaction():
            item=s.capture(doc);s.owner_action(item['id'],1,item['digest'],'admit','Synthetic fixture',True)
            binding={'project_root':str(root),'scope':doc['applicability']['scope'],'judgment_id':item['id'],'version':1,'digest':item['digest'],'verifier':'deny_generated_write','paths':['generated/*']}
            bind(s,binding,True);install(s,root,'cursor',True)
        attempt('generated_write_blocked',False)
        with s.transaction():
            doc['judgment']['statement']='Synthetic fixture: permit the selected edit.'
            revised=s.capture(doc,item['id'],'Synthetic revision',item['digest'])
            s.owner_action(item['id'],2,revised['digest'],'admit','Synthetic review',True)
        attempt('old_binding_stale_after_revision',False)
        with s.transaction():bind(s,{**binding,'version':2,'digest':revised['digest'],'verifier':'require_conditions'},True)
        attempt('rebound_revision_allows_real_write',True)
        with s.transaction():s.owner_action(item['id'],2,revised['digest'],'withdraw','Synthetic retirement',True)
        attempt('withdrawn_revision_blocks_write',False)
        return {'at':now(),'synthetic_only':True,'host':'cursor-cli','version':subprocess.check_output([str(binary),'--version'],text=True).strip(),'flags':['--print','--force','--trust (synthetic workspace only)'],'project_local_preToolUse':True,'results':results}
    finally:s.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-live',action='store_true');p.add_argument('--binary',default=str(Path.home()/'.local/bin/cursor-agent'));p.add_argument('--model');p.add_argument('--output');a=p.parse_args()
    if not a.run_live:p.error('--run-live is required; this runs real model calls in a synthetic project')
    result=verify(Path(a.binary).expanduser(),a.model)
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
