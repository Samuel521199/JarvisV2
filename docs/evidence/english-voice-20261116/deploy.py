"""Daily upgrade with measured continuity, stopped backup and explicit data deltas."""
from pathlib import Path
import collections,copy,hashlib,importlib.util,json,os,shutil,sqlite3,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from tools import workstation as ws
from tools.recovery_snapshot import snapshot,restore
from control.controller_pin import read
spec=importlib.util.spec_from_file_location('preservation',OUT.parent/'daily-upgrade-20261115/deploy.py');helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
DAILY=Path('E:/Jarvis/runtime/user-data');DEV=ROOT/'user-data';PRIVATE=Path('E:/Jarvis/backups/english-voice-20261116')

def main():
    q=json.loads((OUT/'qualified.json').read_text());assert q['passed'] and q['fixture_stopped']
    assert not (OUT/'production.json').exists(),'Inspect recorded phase; never replay upgrade blindly'
    os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
    before_state=ws.state(DAILY);before_pin=read(DAILY);boot=ws.require_live_daily(DAILY);assert before_pin['controller_protocol']==7
    report={'passed':False,'before_state':before_state,'before_controller':before_pin,'before_instance':boot,'steps':[]}
    def step(name,value):
        report['steps'].append({'name':name,'result':value});(OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(name,flush=True)
    step('live-baseline-confirmed',boot)
    prepared=ws.prepare(DAILY,DEV,ROOT,controller_only=True);assert prepared['prepared_build']==q['candidate_build'];step('candidate-independent-qualified',prepared)
    fallback=q['fallback_build'];archive=json.loads((OUT/'recovery-build.json').read_text())['archive']
    assert ws.release(DAILY,'stage','--archive',archive)['build']==fallback
    qualified=ws.release(DAILY,'validate','--build',fallback,'--reviewed-source');assert qualified['approval'];step('fallback-independent-qualified',qualified)
    PRIVATE.mkdir(parents=True,exist_ok=False);before=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'before-controller.json',before)
    assert ws.require_live_daily(DAILY)['boot_id']==boot['boot_id']
    promoted=ws.apply_controller(DAILY,DEV,reviewed_source=True);assert promoted['committed'] and not promoted['registration_pending']
    assert ws.state(DAILY)==before_state and ws.require_live_daily(DAILY)['boot_id']==boot['boot_id']
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-controller.json',after);check=helpers.retained(before,after);assert check['passed'],check
    assert read(DAILY)['policy_sha256']==before_pin['policy_sha256']
    step('controller8-same-boot-fixed-policy-data-preserved',check)
    ws.preflight(DAILY,q['candidate_build']);ws.preflight(DAILY,fallback)
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build']);step('stopped',ws.state(DAILY))
    before=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'before-application.json',before)
    launch=PRIVATE/'installation';launch.mkdir()
    for name in ('JarvisLaunch.py','StartJarvis.bat','StartJarvisCompanion.bat'):shutil.copy2(DAILY.parent/name,launch/name)
    snapshot_path=Path('D:/Jarvis-Recovery/jarvis/2026-11-16-voice-r1/snapshot')
    step('full-independent-backup',snapshot({'daily':DAILY,'installation':launch},snapshot_path,managed_root=DAILY))
    step('inert-restore-verified',restore(snapshot_path,Path('E:/Jarvis/validation/english-voice-restored-20261116')))
    adopted=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch']);step('readonly-fallback-adopted',adopted)
    adopted=ws.release(DAILY,'adopt','--build',q['candidate_build'],'--expected-epoch',adopted['epoch']);step('voice-runtime-adopted',adopted)
    ws.release(DAILY,'install-launcher')
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-application.json',after)
    # Compare every original value; only the existing observer's derived timestamp can advance.
    def completion(root):
        db=sqlite3.connect((root/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:return {r[0]:r for r in db.execute('SELECT task_id,body,checked FROM task_completion')}
        finally:db.close()
    old=completion(snapshot_path/'daily');now=completion(DAILY);assert old.keys()==now.keys()
    deltas=[]
    for ident,row in old.items():
        assert row[:2]==now[ident][:2] and now[ident][2]>=row[2]
        if row!=now[ident]:deltas.append({'task_id':ident,'field':'checked','before':row[2],'after':now[ident][2]})
    normalized=copy.deepcopy(after)
    normalized['databases']['state/core.sqlite3']['task_completion']=dict(collections.Counter(hashlib.sha256(json.dumps(list(r),ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for r in old.values()))
    check=helpers.retained(before,normalized);assert check['passed'],check;check['derived_timestamp_changes']=deltas;step('business-preservation',check)
    fetch=helpers.client();smoke={}
    for path in ('/api/instance','/api/health','/api/goals','/api/tools','/api/developments','/api/chats','/api/network','/api/task-runner','/api/development-runner'):
        fetch(path);smoke[path]=True
    step('original-entries-readable',smoke)
    learning=fetch('/api/english-learning',{'action':'status'});assert all(x['attempts']==0 for x in learning['oral_progress']['domains'].values())
    step('learning-source-preserved-no-synthetic-oral-results',{'config':learning['config'],'written_progress':learning['progress'],'oral_progress':learning['oral_progress'],'exercises':len(learning['exercises'])})
    report.update(passed=True,after_state=ws.state(DAILY),after_controller=read(DAILY),after_instance=ws.require_live_daily(DAILY),automatic_stt_implemented=False,pronunciation_assessment_implemented=False)
    step('complete',{'passed':True})
if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        (OUT/'production-failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
