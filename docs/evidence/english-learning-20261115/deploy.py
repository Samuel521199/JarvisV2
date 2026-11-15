"""Authorized daily upgrade after independent and native compatibility checks."""
from pathlib import Path
import importlib.util,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from tools import workstation as ws
from tools.recovery_snapshot import snapshot,restore
from control.controller_pin import read
from control.recovery.gate import StopGate
spec=importlib.util.spec_from_file_location('prior_preservation',OUT.parent/'daily-upgrade-20261115/deploy.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
DAILY=Path('E:/Jarvis/runtime/user-data');DEV=ROOT/'user-data';PRIVATE=Path('E:/Jarvis/backups/english-learning-20261115')

def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    native=json.loads((OUT/'native/result.json').read_text());assert native['passed'] and native['fixture_stopped']
    resume='--resume-preparation' in sys.argv;resume_promoted='--resume-promoted' in sys.argv
    assert not (OUT/'production.json').exists() or resume or resume_promoted,'Inspect recorded state; never replay upgrade blindly'
    os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
    final=native['candidate_build'];fallback=native['fallback_build'];recovery=json.loads((OUT/'recovery-build.json').read_text())
    disks=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','Get-Partition -DriveLetter E,D | Select-Object DriveLetter,DiskNumber | ConvertTo-Json'],text=True));assert len({x['DiskNumber'] for x in disks})==2
    StopGate(DAILY).require_running();before_state=ws.state(DAILY);before_pin=read(DAILY);assert before_state['phase']=='active' and before_pin['controller_protocol']==(7 if resume_promoted else 6)
    report={'passed':False,'before_state':before_state,'before_controller':before_pin,'candidate_build':final,'fallback_build':fallback,'disk_partition_check':disks,'steps':[]}
    def step(name,value):report['steps'].append({'name':name,'result':value});save('production.json',report);print(name,flush=True)
    if resume_promoted:
        previous=json.loads((OUT/'production.json').read_text());assert previous['before_state']==before_state
        assert [s['name'] for s in previous['steps']]==['prepare-started','candidate-independent-qualified','fallback-independent-qualified']
        assert before_pin['runtime_source_build']==final and before_pin['policy_sha256']==previous['before_controller']['policy_sha256']
        assert (PRIVATE/'before-controller.json').exists() and not (PRIVATE/'before-application.json').exists()
        shutil.copy2(OUT/'production-failure.json',OUT/'production-failure-after-promotion.json');report=previous;before_pin=previous['before_controller']
        ws.require_prepared(DAILY,json.loads((DEV/'state/workstation-controller-update.json').read_text()))
        before=json.loads((PRIVATE/'before-controller.json').read_text())
        after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-controller.json',after);check=helpers.retained(before,after);assert check['passed'],check
        step('controller7-data-preserved-continuity-unverified',{'record':read(DAILY),'preservation':check,'policy_unchanged':True,'same_boot':None,'observed_daily_listener_absent':ws.instance(18282) is None,'cause':'Not established; original boot observation was not persisted. Do not claim continuous daily service.'})
    elif resume:
        previous=json.loads((OUT/'production.json').read_text());assert previous['before_state']==before_state and previous['before_controller']==before_pin
        assert [s['name'] for s in previous['steps']]==['prepare-started','candidate-independent-qualified'] and not PRIVATE.exists()
        shutil.copy2(OUT/'production.json',OUT/'production-initial.json');report=previous
        ws.require_prepared(DAILY,json.loads((DEV/'state/workstation-controller-update.json').read_text()))
    else:
        step('prepare-started',{'source_parent_commit':native['source_commit']})
        prepared=ws.prepare(DAILY,DEV,ROOT,controller_only=True);assert prepared['prepared_build']==final
        step('candidate-independent-qualified',prepared)
        staged=ws.release(DAILY,'stage','--archive',recovery['archive']);assert staged['build']==fallback
    if not resume_promoted:
        validated=ws.release(DAILY,'validate','--build',fallback,'--reviewed-source');assert validated.get('approval')
        step('fallback-independent-qualified',validated)
        PRIVATE.mkdir(parents=True,exist_ok=False)
        before=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'before-controller.json',before);boot=ws.instance(18282)
        promoted=ws.apply_controller(DAILY,DEV,reviewed_source=True);assert promoted['committed'] and not promoted['registration_pending']
        assert ws.state(DAILY)==before_state and ws.instance(18282)['boot_id']==boot['boot_id']
        after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-controller.json',after);check=helpers.retained(before,after);assert check['passed'],check
        assert read(DAILY)['policy_sha256']==before_pin['policy_sha256']
        step('controller7-no-restart-data-preserved',{'record':read(DAILY),'preservation':check,'same_boot':True,'policy_unchanged':True})
    ws.preflight(DAILY,final);ws.preflight(DAILY,fallback)
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build']);step('stopped-for-consistent-backup',ws.state(DAILY))
    try:
        before=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'before-application.json',before)
        launch=PRIVATE/'installation';launch.mkdir()
        for name in ('JarvisLaunch.py','StartJarvis.bat','StartJarvisCompanion.bat'):shutil.copy2(DAILY.parent/name,launch/name)
        destination=Path('D:/Jarvis-Recovery/jarvis/2026-11-15-english-r1/snapshot')
        step('stopped-full-independent-disk-backup',snapshot({'daily':DAILY,'installation':launch},destination,managed_root=DAILY))
        step('complete-inert-restore',restore(destination,Path('E:/Jarvis/validation/english-learning-restored-20261115')))
        adopted=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch']);assert adopted['active']['build']==fallback
        step('compatible-readonly-previous-adopted',adopted)
        adopted=ws.release(DAILY,'adopt','--build',final,'--expected-epoch',adopted['epoch']);assert adopted['active']['build']==final and adopted['previous']['build']==fallback
        step('full-learning-version-adopted',adopted);ws.release(DAILY,'install-launcher')
        after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-application.json',after);check=helpers.retained(before,after);step('original-data-retained',check);assert check['passed'],check
    except BaseException:
        current=ws.state(DAILY)
        if current['phase']=='stopped' and current['active']==before_state['active']:ws.start_daily(DAILY)
        raise
    fetch=helpers.client();smoke={}
    for path in ('/api/instance','/api/health','/api/goals','/api/tools','/api/developments','/api/chats','/api/network','/api/task-runner','/api/development-runner'):
        value=fetch(path);smoke[path]={'readable':True,'type':type(value).__name__}
    step('original-authenticated-entries-readable',smoke)
    initial=fetch('/api/english-learning',{'action':'status'});assert not initial['exercises'] and not initial['jobs']
    assert all(row['attempts']==0 for row in initial['progress']['domains'].values())
    enabled=fetch('/api/english-learning',{'action':'configure','enabled':True,'revision':initial['config']['revision']})
    step('personal-learning-enabled-no-synthetic-results',{'config':enabled['config'],'progress':enabled['progress'],'exercises':len(enabled['exercises'])})
    report.update(passed=True,after_state=ws.state(DAILY),after_controller=read(DAILY),after_instance=ws.instance(18282),actual_user_learning_gains_verified=False)
    save('production.json',report);print('daily upgrade complete',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        save('production-failure.json',{'error':traceback.format_exc(),'state':ws.state(DAILY)});raise
