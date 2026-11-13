"""Read-only final reconciliation and repository gates; no upgrade/model calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,platform,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from control.credentials import load_envelope
from control.development_profile import read,client_secret
from host.development_runtime import selected_proxy
from host.application_release import tracked_runtime
from tools.workstation import state,controller,instance,preflight


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def command(item):
    name,args=item;r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (HERE/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    record={'exit_code':r.returncode,'log':name+'.log'}
    if name=='architecture':record['report']=json.loads(r.stdout)
    return name,record


if __name__=='__main__':
    daily=Path('D:/Jarvis-runtime/user-data');dev=ROOT/'user-data'
    final=state(daily);folder,port=controller(daily);profile=read(dev)
    package=daily/'deployment/packages'/final['active']['build']
    manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
    mismatch=[name for name,meta in manifest['files'].items() if sha(ROOT/name)!=meta['sha256'] or sha(package/name)!=meta['sha256']]
    accepted=json.loads((HERE/'acceptance.json').read_text(encoding='utf-8'))
    prepared=json.loads((dev/'state/workstation-update.json').read_text(encoding='utf-8'))
    proof=prepared['validation'];log=daily/'deployment/validation-logs'/proof['test_log']
    (HERE/'candidate-tests.log').write_bytes(log.read_bytes())
    proxy,proxy_build=selected_proxy(daily);bridge=exchange(dev,'/status');live=instance(port);dev_live=instance(18283)
    probes=[json.loads((HERE/name).read_text(encoding='utf-8').strip()) for name in ['live-development-probe.log','live-after-upgrade-probe.log']]
    checks={
        'daily_and_development_live':bool(live and dev_live),
        'daily_identity':live['application_build']==final['active']['build'] and live['application_epoch']==final['epoch']
            and live['root_digest']==hashlib.sha256(str(daily).casefold().encode()).hexdigest(),
        'development_identity':dev_live['root_digest']==hashlib.sha256(str(dev).casefold().encode()).hexdigest(),
        'v018_active_v017_baseline':final['phase']=='active' and final['active']['version']=='0.1.8' and final['epoch']==5
            and final['previous']['version']=='0.1.7',
        'both_versions_still_compatible':preflight(daily,final['active']['build'])['compatible'] and preflight(daily,final['previous']['build'])['compatible'],
        'profile_rebound_and_grant_preserved':Path(profile['production_data'])==daily and profile['external_actions'] is False
            and client_secret(dev)==load_envelope(daily/'private/development-bridge.dpapi'),
        'frozen_proxy_approved':bridge['build_id']==proxy_build and bridge['daily_call_limit']==64,
        'runtime_inventory_current':not mismatch and set(manifest['files'])==set(tracked_runtime(ROOT)),
        'controller_intact':folder.name==final['active']['build'],
        'independent_candidate_gate':proof['passed'] and proof['tests_summary']=='207 0 0 1' and sha(log)==proof['test_log_sha256'],
        'six_actual_acceptance_steps':accepted['passed'] and len(accepted['steps'])==6 and all(row['passed'] for row in accepted['steps']),
        'business_and_sessions_preserved':accepted['preservation']['existing_tables_checked']==92 and not accepted['preservation']['business_changes']
            and not accepted['preservation']['dpapi_changes'] and not accepted['preservation']['config_session_changes'] and accepted['preservation']['browser_sessions']['passed'],
        'two_live_model_calls':all(probe['live_chat']['status']=='SUCCEEDED' and probe['live_chat']['reply_matched'] and probe['stable_boot_unchanged'] for probe in probes)
            and probes[-1]['proxy']['calls_in_24h']==2,
        'no_model_credentials_or_mail_accounts_copied':all(probe['model_credentials_not_copied'] and probe['formal_mail_accounts_not_copied'] and probe['mail_actions_rejected'] for probe in probes),
    }
    _,navigation=command(('navigation',[sys.executable,'tools/sync_doc_navigation.py','--root','.']))
    with ThreadPoolExecutor(max_workers=3) as pool:
        gates=dict(pool.map(command,[('docs',[sys.executable,'tools/check_docs.py','--root','.']),
            ('architecture',[sys.executable,'tools/check_architecture.py']),('diff',['git','diff','--check'])]))
    gates['navigation']=navigation;checks.update({name+'_gate':record['exit_code']==0 for name,record in gates.items()})
    result={'status':'passed' if all(checks.values()) else 'failed','completed_utc':datetime.now(timezone.utc).isoformat(),
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'environment':{'platform':platform.platform(),'python':platform.python_version(),'source':str(ROOT)},
        'checks':checks,'gates':gates,'runtime_files':len(manifest['files']),'runtime_mismatches':mismatch,
        'candidate':{'build':prepared['build'],'validation':proof},'daily_after':final,
        'model':{'calls':2,'provider':'vertex','model':probes[-1]['live_chat']['model'],
            'provider_reported_total_tokens':sum(probe['live_chat']['usage']['total_tokens'] for probe in probes),
            'currency_cost_reconciled':False,'no_email_sent':True},
        'source_sha256':{name:sha(ROOT/name) for name in ['tools/workstation.py','host/development_runtime.py','tests/test_development_workstation.py',
            'tests/test_development_bridge.py','JarvisPC.bat','StartJarvisDaily.bat','StartJarvisDev.bat','UpdateJarvis.bat','RollbackJarvis.bat','VERSION']},
        'limitations':['Cloud Google model remains remote; no offline LLM was installed.',
            'The upgrade includes a brief managed handoff; no promise of zero interruption or arbitrary live-stack migration.',
            'Stopped backup excludes asset bodies, weights, optional environments and external projects.',
            '207 independent package tests plus 8 workstation and 19 bridge tests; not a fresh full-repository regression.',
            'No browser click or 3D-asset production retest, permanent monitoring, dependency installation, Git commit/push or automatic update task.',
            'Development/direct shell processes share the same OS account; directory/port separation is not an OS security boundary.'],
        'evidence_sha256':{path.name:sha(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name!='audit.json'}}
    (HERE/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'failed':[key for key,value in checks.items() if not value],'runtime_files':len(manifest['files'])}))
    raise SystemExit(result['status']!='passed')
