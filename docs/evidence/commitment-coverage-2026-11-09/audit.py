"""Final local reconciliation; no model calls or runtime adoption."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,platform,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from sdk.application_policy import TESTS,TEST_SUPPORT

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def check_command(item):
    name,args=item;r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (HERE/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    result={'exit_code':r.returncode,'log':name+'.log'}
    if name=='architecture':result['report']=json.loads(r.stdout)
    return name,result

if __name__=='__main__':
    (HERE/'audit.json').write_text('{"status":"checking"}\n',encoding='utf-8')
    plan=read('plan-final.json');seal=read('holdout-final-audit.json');matrix=read('controller-complete-result.json')
    before=read('final-before.json');after=read('final-after.json');regression=read('regression-final.json')
    dev=read('dev-complete.json');intent=sha(ROOT/'modules/task_resource/commitment_intent.py')
    files_current=all(sha(ROOT/name)==digest for name,digest in plan['runtime_sha256'].items())
    tests_current=all(sha(ROOT/'tests'/name)==digest for name,digest in plan['tests_sha256'].items())
    sets=['holdout.json','holdout-r2.json','holdout-r3.json','holdout-final.json'];all_texts=[]
    for name in sets:all_texts.extend(case['text'] for case in read(name)['cases'])
    policy=hashlib.sha256((ROOT/'tools/check_architecture.py').read_bytes()+(ROOT/'tools/architecture-baseline.json').read_bytes()
        +b''.join((ROOT/'tests'/name).read_bytes() for name in TESTS+TEST_SUPPORT)).hexdigest()
    builds={};package_checks=[]
    work=Path('D:/jarvisTest/commitment-controller-20261109-complete')
    for label,entry in matrix['packages'].items():
        folder=work/'data/deployment/packages'/entry['build'];manifest=json.loads((folder/'application.json').read_text(encoding='utf-8'))
        mismatches=[name for name,meta in manifest['files'].items() if sha(folder/name)!=meta['sha256']
            or name!='VERSION' and meta['sha256']!=plan['runtime_sha256'][name]]
        passed=(not mismatches and entry['validation']['passed'] and entry['validation']['policy_sha256']==policy
            and sha(HERE/('controller-complete-'+label+'-tests.log'))==entry['validation']['test_log_sha256'])
        package_checks.append(passed);builds[label]={'build':entry['build'],'matches_final_source_except_VERSION':not mismatches,
            'tests_summary':entry['validation']['tests_summary'],'test_log_intact':passed}
    attempts=[read(name) for name in ['generator-result.json','generator-result-r2.json','generator-result-fresh.json','generator-result-third.json','generator-result-final.json']]
    usage={}
    for attempt in attempts:
        for key,value in attempt.get('usage',{}).items():
            if type(value) is int:usage[key]=usage.get(key,0)+value
    checks={
        'frozen_runtime_current':files_current,'frozen_tests_current':tests_current,
        'holdout_seal_intact':sha(HERE/'holdout-final.json')==seal['sha256']==before['cases_sha256']==after['cases_sha256'],
        'no_duplicate_text_across_160_new_cases':len(set(all_texts))==len(all_texts)==160,
        'final_eval_source_current':intent==after['source_sha256']==dev['source_sha256'],
        'no_shadow_proposal_writes':before['seed_state_unchanged'] and after['seed_state_unchanged'] and dev['seed_state_unchanged'],
        'final_utility_gate':after['summary']['coverage']>=plan['gates']['holdout_clear_coverage_min'],
        'final_safety_gate':after['summary']['unsafe_auto']==after['summary']['wrong_auto_content']==0,
        'original_supported_preserved':dev['groups']['supported']['correct_auto']==10,
        'controller_nine_cases':matrix['status']=='passed' and len(matrix['steps'])==9 and all(step['passed'] for step in matrix['steps']),
        'controller_packages_intact':len(package_checks)==4 and all(package_checks),
        'controller_no_forced_cleanup':matrix['all_owned_processes_stopped'] and not matrix['cleanup_forced_owned_pids'],
        'stop_lock_preserved':matrix['stop_generation_preserved'],
        'generator_call_limits':sum(attempt['calls_started'] for attempt in attempts)==5 and sum(attempt['status']=='SUCCEEDED' for attempt in attempts)==4,
        'owned_proxies_stopped':all(attempt.get('owned_proxy_stopped') for attempt in attempts),
        'related_tests':regression['failures']==regression['errors']==regression['skipped']==0,
    }
    _,navigation=check_command(('navigation',[sys.executable,'tools/sync_doc_navigation.py','--root','.']))
    with ThreadPoolExecutor(max_workers=3) as pool:
        gates=dict(pool.map(check_command,[('docs',[sys.executable,'tools/check_docs.py','--root','.']),
            ('architecture',[sys.executable,'tools/check_architecture.py']),('diff',['git','diff','--check'])]))
    gates['navigation']=navigation;checks.update({name+'_gate':entry['exit_code']==0 for name,entry in gates.items()})
    result={'status':'passed' if all(checks.values()) else 'failed','completed_utc':datetime.now(timezone.utc).isoformat(),
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'environment':{'platform':platform.platform(),'python':platform.python_version(),'workspace':str(ROOT)},
        'checks':checks,'gates':gates,'packages':builds,'results':{'baseline':before['summary'],'final_holdout':after['summary'],'development':dev['summary']},
        'generation_calls':5,'generation_successes':4,'provider_reported_usage_totals':usage,
        'limitations':['Model-authored synthetic wording with operator label review, not third-party blind or real-user validation.',
            'First three holdouts are now development data; their repair scores are not unseen results.',
            'Final source was amended for a known development-set pronoun regression before the final holdout was read/scored; both freezes retained.',
            'Forced-candidate admission is not end-to-end model action-selection quality.',
            'Four runtime variants differ only in VERSION. Faults were injected after actual health, not naturally occurring crashes.',
            'No production adoption, browser visual re-test, external notification or full data-migration matrix in this round; monetary cost unreconciled.'],
        'evidence_sha256':{path.name:sha(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name!='audit.json'}}
    (HERE/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'failed_checks':[name for name,value in checks.items() if not value]},ensure_ascii=False))
    raise SystemExit(result['status']!='passed')
