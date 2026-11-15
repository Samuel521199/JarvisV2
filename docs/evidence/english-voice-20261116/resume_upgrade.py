"""Resume after verifying exactly the existing completion observer timestamp delta."""
from deploy import *

def main():
    report=json.loads((OUT/'production.json').read_text());assert not report['passed']
    assert [r['name'] for r in report['steps']]==['live-baseline-confirmed','candidate-independent-qualified','fallback-independent-qualified']
    q=json.loads((OUT/'qualified.json').read_text());fallback=q['fallback_build'];before_state=report['before_state'];boot=report['before_instance']
    assert ws.state(DAILY)==before_state and ws.require_live_daily(DAILY)['boot_id']==boot['boot_id']
    assert read(DAILY)['controller_protocol']==8 and read(DAILY)['runtime_source_build']==q['candidate_build']
    shutil.copy2(OUT/'production.json',OUT/'production-initial.json')
    before=json.loads((PRIVATE/'before-controller.json').read_text());after=json.loads((PRIVATE/'after-controller.json').read_text())
    db=sqlite3.connect((DAILY/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
    archived=Path('D:/Jarvis-Recovery/controllers/2026-11-15-english-r2/user-data/state/core.sqlite3')
    old=sqlite3.connect(archived.as_uri()+'?mode=ro',uri=True)
    try:
        bodies=dict(db.execute('SELECT task_id,body FROM task_completion'));prior=dict(old.execute('SELECT task_id,body FROM task_completion'))
        assert bodies==prior
    finally:db.close();old.close()
    normalized=copy.deepcopy(after);normalized['databases']['state/core.sqlite3']['task_completion']=before['databases']['state/core.sqlite3']['task_completion']
    check=helpers.retained(before,normalized);assert check['passed'],check
    check.update(completion_bodies_verified_against='2026-11-15-english-r2 stopped snapshot companion increment',completion_body_count=len(bodies),derived_timestamp_only_rows=2,raw_initial_comparison=helpers.retained(before,after))
    def step(name,value):
        report['steps'].append({'name':name,'result':value});(OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(name,flush=True)
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
if __name__=='__main__':main()
