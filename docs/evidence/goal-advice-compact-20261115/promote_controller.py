'''Explicit protocol-3 controller promotion; application and business state stay put.'''
from pathlib import Path
import hashlib,importlib.util,json,shutil,sqlite3,subprocess,sys,threading,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from control import controller_pin as pin
from modules.release_recovery.application import Applications
from tools.workstation import prepare,apply_controller
spec=importlib.util.spec_from_file_location('prior_controller_probe',ROOT/'docs/evidence/controller-promotion-20261114/promote_daily.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)

def main():
    output=Path(__file__).parent/'production-r1';output.mkdir(exist_ok=False)
    qualified=json.loads((output.parent/'independent-package/result.json').read_text(encoding='utf-8'));assert qualified['passed']
    from host.application_release import tracked_runtime
    package=Path(qualified['isolated_data'])/'deployment/packages'/qualified['build']
    manifest=json.loads((package/'application.json').read_text())
    assert set(tracked_runtime(ROOT))==set(manifest['files'])
    assert all(prior.sha(ROOT/name)==meta['sha256']==prior.sha(package/name) for name,meta in manifest['files'].items())
    native=json.loads((output.parent/'native-r1/result.json').read_text());assert native['passed'] and native['fixture_stopped']
    assert next(row['result']['build'] for row in native['steps'] if row['name']=='candidate-build')==qualified['build']
    checked=json.loads((output.parent/'actual-readers.json').read_text());assert checked['passed']
    assert json.loads((output.parent/'actual-old-controller-fence.json').read_text())['passed']
    disks=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',"@{primary=(Get-Partition -DriveLetter E).DiskNumber;backup=(Get-Partition -DriveLetter D).DiskNumber}|ConvertTo-Json -Compress"],text=True))
    assert disks['primary']!=disks['backup']
    private=Path('E:/Jarvis/backups/compact-controller-promotion-20261115-r1');private.mkdir(exist_ok=False)
    daily=Path('E:/Jarvis/runtime/user-data');dev=ROOT/'user-data';app=Applications(daily);oldstate=app.state();oldpin=pin.read(daily)
    def instance():
        with urllib.request.urlopen('http://127.0.0.1:18282/api/instance',timeout=5) as stream:return json.load(stream)
    before=instance();assert before['application_epoch']==oldstate['epoch'] and before['application_build']==oldstate['active']['build']
    ready=dev/'state/workstation-update.json';ready_sha=prior.sha(ready) if ready.exists() else None
    report={'scope':'controller only, protocol 2 to 3; no application adoption','before_state':oldstate,'before_controller':oldpin,'before_instance':before,'source_commit':qualified['source_commit'],'application_adopted':False}
    def save():(output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save();prepared=prepare(daily,dev,ROOT,controller_only=True);assert prepared['prepared_build']==qualified['build'];report['prepared']=prepared;save()
    pristine=prior.snapshot(daily);(private/'business-before.json').write_text(json.dumps(pristine,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stop=threading.Event();samples=[]
    def observe():
        while not stop.is_set():
            try:samples.append({'ok':True,'boot_id':instance()['boot_id']})
            except Exception as error:samples.append({'ok':False,'error':type(error).__name__})
            stop.wait(.05)
    watcher=threading.Thread(target=observe);watcher.start()
    try:promoted=apply_controller(daily,dev,reviewed_source=True)
    finally:stop.set();watcher.join()
    report['promotion']=promoted;save();record=pin.read(daily);after=instance();after_data=prior.snapshot(daily)
    (private/'business-after.json').write_text(json.dumps(after_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    checks={'committed':promoted['committed'],'registration_complete':not promoted['registration_pending'],
        'protocol_advanced':oldpin['controller_protocol']==2 and record['controller_protocol']==3,
        'floor_advanced':json.loads((daily/'deployment/controller-protocol.json').read_text(encoding='utf-8'))=={'schema':1,'minimum':3},
        'application_state_unchanged':app.state()==oldstate,'boot_id_unchanged':before['boot_id']==after['boot_id'],
        'business_hashes_unchanged':pristine==after_data,'observations_same_boot':bool(samples) and all(v['ok'] and v['boot_id']==before['boot_id'] for v in samples),
        'application_ready_unchanged':ready_sha==(prior.sha(ready) if ready.exists() else None)}
    launched=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(daily.parent/'JarvisLaunch.py'),'--check'],capture_output=True,text=True,encoding='utf-8',timeout=30)
    (output/'bootstrap-check.txt').write_text(launched.stdout+launched.stderr,encoding='utf-8');checks['bootstrap_check']=launched.returncode==0
    report.update(checks=checks,after_controller=record,after_instance=after,observations=len(samples));save()
    if not all(checks.values()):raise RuntimeError('Committed state requires investigation; never roll back automatically')
    destination=Path('D:/Jarvis-Recovery/controllers/2026-11-15-r1');destination.mkdir(parents=True,exist_ok=False)
    mappings=[(daily.parent/'JarvisLaunch.py','installation/JarvisLaunch.py'),(daily.parent/'StartJarvis.bat','installation/StartJarvis.bat'),
        (daily/'deployment/launcher.json','user-data/deployment/launcher.json'),(daily/'deployment/controller-protocol.json','user-data/deployment/controller-protocol.json'),
        (daily/'private/application-release.dpapi','user-data/private/application-release.dpapi'),(Path(record['recovery_archive']),'controller.zip'),
        (Path(record['launcher_backup'])/'event.json','activation.json')]
    files={}
    for source,name in mappings:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert prior.sha(source)==prior.sha(target)
        files[name]={'sha256':prior.sha(target),'bytes':target.stat().st_size}
    source_db=sqlite3.connect((daily/'deployment/control.sqlite3').as_uri()+'?mode=ro',uri=True);target_db=sqlite3.connect(destination/'user-data/deployment/control.sqlite3')
    try:source_db.backup(target_db);assert target_db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:source_db.close();target_db.close()
    database=destination/'user-data/deployment/control.sqlite3';files['user-data/deployment/control.sqlite3']={'sha256':prior.sha(database),'bytes':database.stat().st_size}
    package=Path(app.approved(record['runtime_source_build'],fresh=False)['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'));archive=destination/'runtime-source.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as stream:
        for name in ['application.json',*manifest['files']]:stream.write(package/name,name)
    files['runtime-source.zip']={'sha256':prior.sha(archive),'bytes':archive.stat().st_size}
    assert prior.sha(destination/'controller.zip')==record['recovery_sha256']
    with zipfile.ZipFile(destination/'controller.zip') as stream:
        index=stream.read('controller-files.json');assert hashlib.sha256(index).hexdigest()==record['build'];members=json.loads(index)
        assert set(stream.namelist())==set(members)|{'controller-files.json'}
        assert all(hashlib.sha256(stream.read(name)).hexdigest()==value for name,value in members.items())
    with zipfile.ZipFile(archive) as stream:assert all(hashlib.sha256(stream.read(name)).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    backup={'schema':1,'scope':'controller/qualification increment only; not full business backup; same Windows user DPAPI only',
        'root':str(daily),'controller_build':record['build'],'controller_protocol':3,'runtime_source_build':record['runtime_source_build'],
        'files':files,'archive_members_verified':len(members),'sqlite_integrity_ok':True,'passed':True}
    (destination/'verification.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'disaster-copy.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report.update(disaster_copy=str(destination),passed=True);save()
    print(json.dumps({'passed':True,'controller_build':record['build'],'controller_protocol':3,'generation':record['generation'],'application_epoch':after['application_epoch'],'application_unchanged':True,'business_hashes_unchanged':checks['business_hashes_unchanged'],'observations':len(samples),'disaster_copy':str(destination)}),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        out=Path(__file__).parent/'production-r1';out.mkdir(exist_ok=True);(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
