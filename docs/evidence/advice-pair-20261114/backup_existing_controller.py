"""Back up the existing pinned controller and current qualification ledger only."""
from pathlib import Path
import sys,json,hashlib,shutil,sqlite3,zipfile
ROOT=Path('E:/Jarvis/dev');sys.path.insert(0,str(ROOT))
from control.controller_pin import read
from modules.release_recovery.application import Applications
from tools.workstation import state

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    daily=Path('E:/Jarvis/runtime/user-data');dest=Path('D:/Jarvis-Recovery/controllers/2026-11-14-r3').resolve()
    assert dest.is_relative_to(Path('D:/Jarvis-Recovery/controllers').resolve());dest.mkdir(exist_ok=False)
    record=read(daily);before=state(daily);assert record['controller_protocol']==2 and before['active']['version']=='0.1.8' and before['epoch']==10
    mappings=[(daily.parent/'JarvisLaunch.py','installation/JarvisLaunch.py'),(daily.parent/'StartJarvis.bat','installation/StartJarvis.bat'),
      (daily/'deployment/launcher.json','user-data/deployment/launcher.json'),(daily/'deployment/controller-protocol.json','user-data/deployment/controller-protocol.json'),
      (daily/'private/application-release.dpapi','user-data/private/application-release.dpapi'),(Path(record['recovery_archive']),'controller.zip'),(Path(record['launcher_backup'])/'event.json','activation.json')]
    files={}
    for source,name in mappings:
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert sha(source)==sha(target);files[name]={'sha256':sha(target),'bytes':target.stat().st_size}
    source=sqlite3.connect((daily/'deployment/control.sqlite3').as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(dest/'user-data/deployment/control.sqlite3')
    try:source.backup(target);assert target.execute('pragma integrity_check').fetchone()[0]=='ok'
    finally:source.close();target.close()
    database=dest/'user-data/deployment/control.sqlite3';files['user-data/deployment/control.sqlite3']={'sha256':sha(database),'bytes':database.stat().st_size}
    package=Path(Applications(daily).approved(record['runtime_source_build'],fresh=False)['path']);manifest=json.loads((package/'application.json').read_text())
    with zipfile.ZipFile(dest/'runtime-source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in ['application.json',*manifest['files']]:z.write(package/name,name)
    archive=dest/'runtime-source.zip';files['runtime-source.zip']={'sha256':sha(archive),'bytes':archive.stat().st_size}
    with zipfile.ZipFile(dest/'controller.zip') as z:
        index=z.read('controller-files.json');assert hashlib.sha256(index).hexdigest()==record['build'];members=json.loads(index)
        assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)|{'controller-files.json'}
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in members.items());zip_count=len(z.namelist())
    with zipfile.ZipFile(archive) as z:assert all(hashlib.sha256(z.read(name)).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    assert read(daily)==record and state(daily)==before
    report={'scope':'same installed controller, qualification/control increment after service resumed at epoch10; not full business backup; same Windows user DPAPI only','controller_build':record['build'],'controller_protocol':2,'generation':record['generation'],'runtime_source_build':record['runtime_source_build'],'application_state':before,
      'files':files,'indexed_controller_files':len(members),'controller_zip_members_including_index':zip_count,'sqlite_integrity_ok':True,'all_file_hashes_read_back':all(sha(dest/name)==meta['sha256'] for name,meta in files.items()),'source_state_unchanged':True,'passed':True}
    (dest/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out=ROOT/'docs/evidence/advice-pair-20261114/controller-disaster-copy.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'destination':str(dest),'files':len(files),'controller_files':len(members),'application_epoch':before['epoch']}))
if __name__=='__main__':main()
