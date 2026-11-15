"""Post-upgrade online recovery increment; never restores a live database."""
from pathlib import Path
import hashlib,json,shutil,sqlite3,sys,zipfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from control.controller_pin import read,sha
from tools.workstation import state

def main():
    root=Path('E:/Jarvis/runtime/user-data');before=state(root);pin=read(root)
    dest=Path('D:/Jarvis-Recovery/controllers/2026-11-15-r3');dest.mkdir(parents=True,exist_ok=False)
    mappings=[(root.parent/'JarvisLaunch.py','installation/JarvisLaunch.py'),(root.parent/'StartJarvis.bat','installation/StartJarvis.bat'),
        (root/'deployment/launcher.json','user-data/deployment/launcher.json'),(root/'deployment/controller-protocol.json','user-data/deployment/controller-protocol.json'),
        (root/'private/application-release.dpapi','user-data/private/application-release.dpapi'),(Path(pin['recovery_archive']),'controller.zip'),
        (Path(pin['launcher_backup'])/'event.json','activation.json')]
    files={}
    for source,name in mappings:
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert sha(source)==sha(target)
        files[name]={'bytes':target.stat().st_size,'sha256':sha(target)}
    paths=[root/'deployment/control.sqlite3',*sorted((root/'state').rglob('*.sqlite3')),*sorted((root/'private').rglob('*.sqlite3'))]
    bridge=root/'development/bridge.sqlite3'
    if bridge.exists():paths.append(bridge)
    for source in paths:
        name='user-data/'+source.relative_to(root).as_posix();target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);copy=sqlite3.connect(target)
        try:db.backup(copy);assert copy.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        finally:copy.close();db.close()
        files[name]={'bytes':target.stat().st_size,'sha256':sha(target)}
    assert sha(dest/'controller.zip')==pin['recovery_sha256']
    with zipfile.ZipFile(dest/'controller.zip') as stream:
        index=stream.read('controller-files.json');assert hashlib.sha256(index).hexdigest()==pin['build'];members=json.loads(index)
        assert set(stream.namelist())==set(members)|{'controller-files.json'}
        assert all(hashlib.sha256(stream.read(name)).hexdigest()==value for name,value in members.items())
    assert state(root)==before and read(root)==pin
    result={'passed':True,'destination':str(dest),'application':before,'controller_build':pin['build'],'controller_protocol':pin['controller_protocol'],
        'files':files,'sqlite_integrity_ok':len(paths),'archive_members_verified':len(members),
        'scope':'Online per-database consistent recovery increment, not an atomic cross-database snapshot or anti-rollback proof. Pair with stopped full snapshot; reconcile newer authority before restore. Same Windows user DPAPI only; no restored work started.'}
    (dest/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (OUT/'recovery-increment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'files':len(files),'sqlite_integrity_ok':len(paths),'destination':str(dest)}))

if __name__=='__main__':main()
