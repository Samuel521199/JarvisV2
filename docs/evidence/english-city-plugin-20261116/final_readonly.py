"""Read-only final installed software and unanswered actual learner question checks."""
from pathlib import Path
import hashlib,json,sys
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2];sys.path.insert(0,str(OUT))
from trial import Client
from adapters.software_client import binding
from tools.workstation import state,require_live_daily
from control.controller_pin import read
from modules.release_recovery.application import Applications

def main():
    root=Path('E:/Jarvis/runtime/user-data');c=Client(18282,root)
    final=json.loads((OUT/'source-format-adoption.json').read_text(encoding='utf-8'))
    v=c.call('/api/english-learning',{'action':'status'});first=json.loads((OUT/'daily-first-game.json').read_text(encoding='utf-8'));ex=next(e for e in v['exercises'] if e['id']==first['question']['id'])
    assert ex['assessment'] is None and ex['hints']==0 and not ex['exposed']
    s=state(root);pin=read(root);assert s==final['after_state'] and pin==final['controller']
    package=Path(Applications(root).approved(s['active']['build'],fresh=False)['path']);manifest=json.loads((package/'application.json').read_text())
    assert not any(n.startswith('software/') or n.endswith('/engine.py') for n in manifest['files'])
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==meta['sha256'] for n,meta in manifest['files'].items())
    assert v['games']['available'];bind=binding(root);assert not Path(bind['release']).is_relative_to(ROOT)
    observed=json.loads((OUT/'live-observation.json').read_text());assert observed['passed']
    boot=require_live_daily(root);assert boot['boot_id']==observed['boot_id']
    result={'passed':True,'application':s,'controller_protocol':pin['controller_protocol'],'controller_build':pin['build'],'external_software':bind,'runtime_files':len(manifest['files']),'game_engine_in_jarvis_package':False,'first_question_unanswered':True,'same_boot_after_observation':True,'model_calls':0,'scope':'Read-only final checks, no learner answer or additional cloud call'}
    (OUT/'final-readonly-status.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k in ('passed','first_question_unanswered','runtime_files','controller_protocol','same_boot_after_observation')}))

if __name__=='__main__':main()
