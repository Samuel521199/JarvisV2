"""Explicit reviewed-source controller-only promotion after completed native checks.
This does not adopt an application, clear STOP, or restore a business database.
"""
from pathlib import Path
import hashlib,json,shutil,sqlite3,subprocess,sys,threading,time,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from control import controller_pin as pin
from modules.release_recovery.application import Applications
from tools.workstation import prepare,apply_controller


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def snapshot(root):
    result={'files':{},'databases':{}}
    for name in ['config','private']:
        for path in sorted((root/name).rglob('*')):
            if path.is_file() and not path.name.endswith(('.sqlite3','-wal','-shm')):result['files'][path.relative_to(root).as_posix()]=sha(path)
    for name in ['core','dialogue','commitments']:
        path=root/('state/'+name+'.sqlite3')
        if not path.exists():continue
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:
            tables={}
            for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
                rows=[]
                for row in db.execute('SELECT * FROM "'+table.replace('"','""')+'"'):
                    value=[{'blob_sha256':hashlib.sha256(v).hexdigest()} if isinstance(v,bytes) else v for v in row]
                    rows.append(json.dumps(value,ensure_ascii=False,separators=(',',':')))
                encoded='\n'.join(sorted(rows)).encode();tables[table]={'rows':len(rows),'sha256':hashlib.sha256(encoded).hexdigest()}
            result['databases'][name]=tables
        finally:db.close()
    return result


def main():
    output=Path(__file__).parent/(sys.argv[1] if len(sys.argv)>1 else 'production-r1');output.mkdir(exist_ok=False)
    native=json.loads((output.parent/'native-r4/result.json').read_text(encoding='utf-8'))
    assert native.get('passed') is True and native.get('fixture_stopped') is True
    assert native['source_commit']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    daily=Path('E:/Jarvis/runtime/user-data');dev=ROOT/'user-data';app=Applications(daily)
    oldstate=app.state();oldpin=pin.read(daily)
    def instance():
        with urllib.request.urlopen('http://127.0.0.1:18282/api/instance',timeout=5) as stream:return json.load(stream)
    before=instance();assert before['application_build']==oldstate['active']['build'] and before['application_epoch']==oldstate['epoch']
    original_ready=dev/'state/workstation-update.json';ready_sha=sha(original_ready) if original_ready.exists() else None
    report={'source_commit':native['source_commit'],'before_state':oldstate,'before_instance':before,'before_controller':oldpin,'application_adopted':False,'steps':[]}
    def save():(output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save();prepared=prepare(daily,dev,ROOT,controller_only=True);report['prepared']=prepared;save()
    pristine=snapshot(daily);(output/'business-before.json').write_text(json.dumps(pristine,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stop=threading.Event();samples=[]
    def observe():
        while not stop.is_set():
            try:samples.append({'ok':True,'boot_id':instance()['boot_id']})
            except Exception as error:samples.append({'ok':False,'error':type(error).__name__})
            stop.wait(.05)
    watcher=threading.Thread(target=observe);watcher.start()
    try:result=apply_controller(daily,dev,reviewed_source=True)
    finally:stop.set();watcher.join()
    report['promotion']=result;save()
    after=instance();record=pin.read(daily);after_data=snapshot(daily)
    (output/'business-after.json').write_text(json.dumps(after_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    checks={'controller_committed':result['committed'],'registration_complete':not result['registration_pending'],
        'application_state_unchanged':app.state()==oldstate,'boot_id_unchanged':before['boot_id']==after['boot_id'],
        'business_hashes_unchanged':pristine==after_data,'all_observations_same_boot':bool(samples) and all(v['ok'] and v['boot_id']==before['boot_id'] for v in samples),
        'application_ready_unchanged':ready_sha==(sha(original_ready) if original_ready.exists() else None)}
    checked=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(daily.parent/'JarvisLaunch.py'),'--check'],capture_output=True,text=True,encoding='utf-8',timeout=30)
    (output/'bootstrap-check.txt').write_text(checked.stdout+checked.stderr,encoding='utf-8');checks['fixed_bootstrap_check']=checked.returncode==0
    report.update(checks=checks,observations=len(samples),after_instance=after,after_controller=record);save()
    if not all(checks.values()):raise RuntimeError('Committed controller needs investigation; no automatic rollback was attempted')
    destination=Path('D:/Jarvis-Recovery/controllers/2026-11-14-r1');destination.mkdir(parents=True,exist_ok=False)
    mappings=[(daily.parent/'JarvisLaunch.py','installation/JarvisLaunch.py'),(daily.parent/'StartJarvis.bat','installation/StartJarvis.bat'),
        (daily/'deployment/launcher.json','user-data/deployment/launcher.json'),(daily/'deployment/controller-protocol.json','user-data/deployment/controller-protocol.json'),
        (daily/'private/application-release.dpapi','user-data/private/application-release.dpapi'),
        (Path(record['recovery_archive']),'controller.zip'),(Path(record['launcher_backup'])/'event.json','activation.json')]
    files={}
    for source,name in mappings:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        assert sha(source)==sha(target);files[name]={'sha256':sha(target),'bytes':target.stat().st_size}
    source_db=sqlite3.connect((daily/'deployment/control.sqlite3').as_uri()+'?mode=ro',uri=True);target_db=sqlite3.connect(destination/'user-data/deployment/control.sqlite3')
    try:
        source_db.backup(target_db);assert target_db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:source_db.close();target_db.close()
    database=destination/'user-data/deployment/control.sqlite3';files['user-data/deployment/control.sqlite3']={'sha256':sha(database),'bytes':database.stat().st_size}
    package=Path(app.approved(record['runtime_source_build'],fresh=False)['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
    archive=destination/'runtime-source.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as stream:
        for name in ['application.json',*manifest['files']]:stream.write(package/name,name)
    files['runtime-source.zip']={'sha256':sha(archive),'bytes':archive.stat().st_size}
    assert pin.sha(destination/'controller.zip')==record['recovery_sha256']
    with zipfile.ZipFile(destination/'controller.zip') as stream:
        index=stream.read('controller-files.json');assert hashlib.sha256(index).hexdigest()==record['build']
        members=json.loads(index)
        assert set(stream.namelist())==set(members)|{'controller-files.json'}
        assert all(hashlib.sha256(stream.read(name)).hexdigest()==value for name,value in members.items())
    with zipfile.ZipFile(archive) as stream:
        assert all(hashlib.sha256(stream.read(name)).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    backup={'schema':1,'scope':'controller and its source qualification only; not current business data backup; same Windows user DPAPI only',
        'root':str(daily),'controller_build':record['build'],'runtime_source_build':record['runtime_source_build'],'files':files,
        'archive_members_verified':len(members),'sqlite_integrity_ok':True,'passed':True}
    (destination/'verification.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'disaster-copy.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report['disaster_copy']=str(destination);report['passed']=True;save()
    print(json.dumps({'passed':True,'application_build':after['application_build'],'application_epoch':after['application_epoch'],
        'boot_id_unchanged':checks['boot_id_unchanged'],'business_hashes_unchanged':checks['business_hashes_unchanged'],
        'controller_build':record['build'],'observations':len(samples),'disaster_copy':str(destination)}),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        target=Path(__file__).parent/(sys.argv[1] if len(sys.argv)>1 else 'production-r1')/'failure.txt';target.parent.mkdir(exist_ok=True)
        target.write_text(traceback.format_exc(),encoding='utf-8');raise
