"""Deploy the Jarvis bridge and a separately owned, separately backed-up software release."""
from pathlib import Path
import copy,importlib.util,json,os,shutil,sqlite3,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from tools import workstation as ws
from tools.install_english_city import install
from tools.recovery_snapshot import snapshot,restore
from control.controller_pin import read
from modules.release_recovery.application import Applications
spec=importlib.util.spec_from_file_location('preservation',OUT.parent/'daily-upgrade-20261115/deploy.py');helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
DAILY=Path('E:/Jarvis/runtime/user-data');DEV=ROOT/'user-data';PRIVATE=Path('E:/Jarvis/backups/english-city-plugin-20261116')
SOFTWARE=Path('E:/Jarvis/software/english-city');SOURCE=SOFTWARE/'source'

def completions():
    db=sqlite3.connect((DAILY/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:return {r[0]:r for r in db.execute('SELECT task_id,body,checked FROM task_completion')}
    finally:db.close()

def preserve(before,after,old,new):
    assert old.keys()<=new.keys()
    assert all(row[:2]==new[k][:2] and new[k][2]>=row[2] for k,row in old.items()),'Only checked timestamps may change without a business review'
    normalized=copy.deepcopy(after);normalized['databases']['state/core.sqlite3']['task_completion']=before['databases']['state/core.sqlite3']['task_completion']
    value=helpers.retained(before,normalized)
    value['derived_timestamp_changes']=[{'task_id':k,'before':r[2],'after':new[k][2]} for k,r in old.items() if r!=new[k]]
    return value

def main():
    q=json.loads((OUT/'qualified.json').read_text());assert q['passed'] and q['fixture_stopped']
    assert not (OUT/'production.json').exists(),'Inspect recorded phase; never replay adoption blindly'
    assert SOURCE.exists() and not SOURCE.is_relative_to(ROOT) and not (ROOT/'software/english_city/engine.py').exists()
    os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
    before_state=ws.state(DAILY);before_pin=read(DAILY);boot=ws.require_live_daily(DAILY);assert before_pin['controller_protocol']==8
    report={'passed':False,'before_state':before_state,'before_controller':before_pin,'before_instance':boot,'steps':[]}
    def step(name,value):
        report['steps'].append({'name':name,'result':value});(OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(name,flush=True)
    step('live-baseline-confirmed',boot)
    prepared=ws.prepare(DAILY,DEV,ROOT,controller_only=True);assert prepared['prepared_build']==q['candidate_build'];step('bridge-independently-qualified',prepared)
    fallback=q['fallback_build'];archive=json.loads((OUT/'recovery-build.json').read_text())['archive']
    assert ws.release(DAILY,'stage','--archive',archive)['build']==fallback
    accepted=ws.release(DAILY,'validate','--build',fallback,'--reviewed-source');assert accepted['approval'];step('readonly-fallback-independently-qualified',accepted)
    # Separate release installation; no source or game engine is copied into Jarvis.
    installed=install(SOURCE,SOFTWARE,DAILY);assert not Path(installed['release']).is_relative_to(ROOT)
    package=Path(Applications(DAILY).approved(q['candidate_build'])['path']);manifest=json.loads((package/'application.json').read_text())
    assert not any(name.startswith('software/') or name.endswith('/engine.py') for name in manifest['files'])
    step('independent-software-installed-outside-project',installed)
    PRIVATE.mkdir(parents=True,exist_ok=False);before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-controller.json',before)
    assert ws.require_live_daily(DAILY)['boot_id']==boot['boot_id']
    promoted=ws.apply_controller(DAILY,DEV,reviewed_source=True);assert promoted['committed'] and not promoted['registration_pending']
    assert ws.state(DAILY)==before_state and ws.require_live_daily(DAILY)['boot_id']==boot['boot_id']
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-controller.json',after);check=preserve(before,after,old,completions());assert check['passed'],check
    assert read(DAILY)['policy_sha256']==before_pin['policy_sha256'];step('controller9-fixed-policy-same-boot-data-preserved',check)
    ws.preflight(DAILY,q['candidate_build']);ws.preflight(DAILY,fallback)
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build']);step('stopped-for-consistent-backup',ws.state(DAILY))
    before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-application.json',before)
    launch=PRIVATE/'installation';launch.mkdir()
    for name in ('JarvisLaunch.py','StartJarvis.bat','StartJarvisCompanion.bat'):shutil.copy2(DAILY.parent/name,launch/name)
    target=Path('D:/Jarvis-Recovery/jarvis/2026-11-16-city-r1/snapshot')
    step('full-backup-including-independent-software',snapshot({'daily':DAILY,'installation':launch,'english-city':SOFTWARE},target,managed_root=DAILY))
    step('full-inert-restore-verified',restore(target,Path('E:/Jarvis/validation/english-city-restored-20261116')))
    try:
        adopted=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch']);step('compatible-readonly-previous-adopted',adopted)
        adopted=ws.release(DAILY,'adopt','--build',q['candidate_build'],'--expected-epoch',adopted['epoch']);step('bridge-adopted',adopted);ws.release(DAILY,'install-launcher')
    except BaseException:
        current=ws.state(DAILY)
        if current['phase']=='stopped' and current['active']==before_state['active']:ws.start_daily(DAILY)
        raise
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-application.json',after);check=preserve(before,after,old,completions());step('original-business-data-preserved',check);assert check['passed'],check
    fetch=helpers.client();smoke={}
    for path in ('/api/instance','/api/health','/api/goals','/api/tools','/api/developments','/api/chats','/api/network','/api/task-runner','/api/development-runner'):
        fetch(path);smoke[path]=True
    step('original-entries-readable',smoke)
    state=fetch('/api/english-learning',{'action':'status'});assert state['games']['available'] and not state['games']['sessions'] and not state['games']['vocabulary_observations']
    step('independent-plugin-ready-no-synthetic-progress',{'software':state['games']['software'],'written_progress':state['progress'],'oral_progress':state['oral_progress'],'previous_exercises':len(state['exercises'])})
    report.update(passed=True,after_state=ws.state(DAILY),after_controller=read(DAILY),after_instance=ws.require_live_daily(DAILY),independent_software=installed,software_source=str(SOURCE),bridge_runtime_files=len(manifest['files']))
    step('complete',{'passed':True})
if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        (OUT/'production-failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
