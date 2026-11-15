"""Explicit daily upgrade; controller-owned transitions, private recovery and audit."""
from pathlib import Path
import collections,hashlib,http.cookiejar,importlib.util,json,os,shutil,sqlite3,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from tools import workstation as ws
from tools.recovery_snapshot import snapshot,restore
from control.controller_pin import read as controller_record
from control.recovery.gate import StopGate
from modules.release_recovery.application import Applications

DAILY=Path('E:/Jarvis/runtime/user-data');DEV=ROOT/'user-data'
PRIVATE=Path('E:/Jarvis/backups/daily-upgrade-20261115')
DISASTER=Path('D:/Jarvis-Recovery/jarvis/2026-11-15-upgrade-r1/snapshot')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def fingerprint(root):
    value={'files':{},'databases':{}}
    for name in ('config','private','sessions'):
        for p in (root/name).rglob('*'):
            if p.is_file() and not p.name.endswith(('.sqlite3','-wal','-shm','.lock')):
                value['files'][p.relative_to(root).as_posix()]=ws.sha(p)
    for directory in ('state','private'):
        for p in (root/directory).rglob('*.sqlite3'):
            tables={};db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
            try:
                assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                    rows=[]
                    for row in db.execute('SELECT * FROM "'+name.replace('"','""')+'"'):
                        raw=json.dumps([{'blob':hashlib.sha256(x).hexdigest()} if isinstance(x,bytes) else x for x in row],ensure_ascii=False,separators=(',',':')).encode()
                        rows.append(hashlib.sha256(raw).hexdigest())
                    tables[name]=dict(collections.Counter(rows))
            finally:db.close()
            value['databases'][p.relative_to(root).as_posix()]=tables
    return value

def retained(before,after):
    changed_files=[name for name,v in before['files'].items() if after['files'].get(name)!=v]
    missing=[];rows=0
    for name,tables in before['databases'].items():
        for table,counts in tables.items():
            rows+=sum(counts.values());now=after['databases'].get(name,{}).get(table,{})
            lost=sum((collections.Counter(counts)-collections.Counter(now)).values())
            if lost:missing.append({'database':name,'table':table,'missing_or_changed_rows':lost})
    return {'passed':not changed_files and not missing,'original_files':len(before['files']),'original_rows':rows,
            'original_databases':len(before['databases']),'changed_files':changed_files,'changed_tables':missing}

def client():
    from control.local_access import read_key
    origin='http://127.0.0.1:18282';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));token=''
    def fetch(path,body=None):
        req=urllib.request.Request(origin+path,data=None if body is None else json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json','X-Jarvis-Token':token})
        with opener.open(req,timeout=15) as stream:return json.loads(stream.read(8000000))
    fetch('/api/local-access',{'key':read_key(DAILY)});token=fetch('/api/session')['token']
    return fetch

def main():
    os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
    native=json.loads((OUT/'native-r1/result.json').read_text(encoding='utf-8'))
    assert native['passed'] and native['fixture_stopped']
    final=next(s['result']['build'] for s in native['steps'] if s['name']=='candidate-build')
    fallback=json.loads((OUT/'baseline-qualified/result.json').read_text())['build']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==native['source_commit']
    assert not (OUT/'production.json').exists(),'Resume by inspecting recorded phase; never replay this script blindly'
    disks=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','Get-Partition -DriveLetter E,D | Select-Object DriveLetter,DiskNumber | ConvertTo-Json'],text=True))
    assert len({x['DiskNumber'] for x in disks})==2
    StopGate(DAILY).require_running();before_state=ws.state(DAILY);before_pin=controller_record(DAILY)
    assert before_state['phase']=='active' and ws.instance(18282)
    report={'before_state':before_state,'before_controller':before_pin,'final_build':final,'fallback_build':fallback,'disk_partition_check':disks,'steps':[],'passed':False}
    def step(name,body):
        report['steps'].append({'name':name,'result':body});write(OUT/'production.json',report);print(json.dumps({'stage':name}),flush=True)
    step('preparation_started',{'source_commit':native['source_commit']})
    prepared=ws.prepare(DAILY,DEV,ROOT,controller_only=True);assert prepared['prepared_build']==final
    step('final_qualified_by_daily_controller',prepared)
    staged=ws.release(DAILY,'stage','--archive','E:/Jarvis/validation/daily-upgrade-baseline-20261115/candidate.zip');assert staged['build']==fallback
    validated=ws.release(DAILY,'validate','--build',fallback,'--reviewed-source');assert validated.get('approval')
    step('fallback_qualified_by_daily_controller',validated)
    before=fingerprint(DAILY);write(PRIVATE/'before-controller.json',before);identity=ws.instance(18282)
    promoted=ws.apply_controller(DAILY,DEV,reviewed_source=True)
    assert promoted['committed'] and not promoted['registration_pending']
    assert ws.state(DAILY)==before_state and ws.instance(18282)['boot_id']==identity['boot_id']
    after=fingerprint(DAILY);write(PRIVATE/'after-controller.json',after)
    check=retained(before,after);assert check['passed'],check
    step('controller_promoted_without_business_changes',{'record':controller_record(DAILY),'preservation':check,'same_boot':True})
    ws.preflight(DAILY,final);ws.preflight(DAILY,fallback)
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build'])
    step('old_host_stopped_for_consistent_backup',ws.state(DAILY))
    try:
        before=fingerprint(DAILY);write(PRIVATE/'before-application.json',before)
        launch=PRIVATE/'installation';launch.mkdir(parents=True,exist_ok=False)
        for name in ('JarvisLaunch.py','StartJarvis.bat','StartJarvisCompanion.bat'):
            shutil.copy2(DAILY.parent/name,launch/name)
        backed=snapshot({'daily':DAILY,'installation':launch},DISASTER,managed_root=DAILY)
        step('independent_disk_snapshot',backed)
        restored=restore(DISASTER,Path('E:/Jarvis/validation/daily-upgrade-restored-20261115'))
        step('restored_all_snapshot_files_without_starting_work',restored)
        adopted=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch'])
        assert adopted['active']['build']==fallback
        step('compatible_fallback_adopted',adopted)
        final_state=ws.release(DAILY,'adopt','--build',final,'--expected-epoch',adopted['epoch'])
        assert final_state['active']['build']==final and final_state['previous']['build']==fallback
        step('final_adopted_with_compatible_previous',final_state)
        ws.release(DAILY,'install-launcher')
        after=fingerprint(DAILY);write(PRIVATE/'after-application.json',after)
        check=retained(before,after);step('business_preservation',check)
        assert check['passed'],check
    except BaseException:
        current=ws.state(DAILY)
        if current['phase']=='stopped' and current['active']==before_state['active']:ws.start_daily(DAILY)
        raise
    fetch=client();smoke={}
    for path in ('/api/instance','/api/health','/api/goals','/api/tools','/api/developments','/api/chats','/api/network','/api/task-runner','/api/development-runner'):
        try:
            value=fetch(path);smoke[path]={'readable':True,'type':type(value).__name__}
        except Exception as error:smoke[path]={'readable':False,'error':str(error)}
    step('authenticated_daily_reads',smoke);assert all(x['readable'] for x in smoke.values())
    from host.core import Core
    from modules.context_knowledge.lesson_trials import LessonTrials
    core=Core(DAILY)
    try:policy=LessonTrials(core.db).policy()
    finally:core.close()
    enabled=fetch('/api/operations',{'action':'lesson_validation_configure','enabled':True,'max_trials_24h':4,'revision':policy['revision']})
    step('existing_bounded_local_verification_enabled',{'before':policy,'after':enabled,'new_schedule':False,'cloud_calls':0,'auto_repair_still_requires_single_task_authorization':True})
    report.update(passed=True,after_state=ws.state(DAILY),after_instance=ws.instance(18282),after_controller=controller_record(DAILY),long_term_effect_verified=False)
    write(OUT/'production.json',report);print(json.dumps({'passed':True,'version':report['after_state']['active']['version'],'epoch':report['after_state']['epoch']}),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        write(OUT/'production-failure.json',{'error':traceback.format_exc(),'state':ws.state(DAILY)})
        raise
