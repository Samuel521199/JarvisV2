"""Online recovery increment for the real daily tasks; never restores live data."""
from pathlib import Path
import json,shutil,sqlite3,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from control.controller_pin import read,sha
from tools.workstation import state
OUT=Path(__file__).parent

def main():
    root=Path('E:/Jarvis/runtime/user-data');before=state(root);pin=read(root)
    dest=Path('D:/Jarvis-Recovery/controllers/2026-11-15-r4');dest.mkdir(parents=True,exist_ok=False)
    sources=set()
    for name in ('state','private','config','packages'):
        sources.update(p for p in (root/name).rglob('*') if p.is_file() and not p.name.endswith(('-wal','-shm','.lock')))
    sources.add(root/'deployment/control.sqlite3')
    sources.add(root/'development/bridge.sqlite3')
    sources.add(root/'deployment/launcher.json');sources.add(root/'deployment/controller-protocol.json')
    for label in ('english','materials'):
        result=json.loads((OUT/(label+'-task-result.json')).read_text())
        sources.update(p for p in (root/'artifacts'/result['task_id']).rglob('*') if p.is_file())
    db=sqlite3.connect((root/'state/workspace.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        for label in ('english','materials'):
            chat=json.loads((OUT/(label+'-dialogue-start.json')).read_text())['chat_id']
            row=db.execute('SELECT path FROM session_folders WHERE chat_id=?',(chat,)).fetchone()
            folder=Path(row[0]).resolve();assert folder.is_relative_to(root.resolve())
            sources.update(p for p in folder.rglob('*') if p.is_file())
    finally:db.close()
    files={};databases=0
    for source in sorted(sources):
        if not source.exists():continue
        name='user-data/'+source.relative_to(root).as_posix();target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix=='.sqlite3':
            live=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);copy=sqlite3.connect(target)
            try:live.backup(copy);assert copy.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            finally:copy.close();live.close()
            databases+=1
        else:
            original=sha(source);shutil.copy2(source,target);assert original==sha(target)==sha(source)
        files[name]={'bytes':target.stat().st_size,'sha256':sha(target)}
    assert state(root)==before and read(root)==pin
    assert all(sha(dest/name)==value['sha256'] for name,value in files.items())
    value={'passed':True,'destination':str(dest),'files':files,'sqlite_integrity_ok':databases,'application':before,'controller_protocol':pin['controller_protocol'],
        'scope':'Per-database consistent online increment plus packages and selected task/chat artifacts; not an atomic full snapshot. Requires prior full snapshot and r3 controller recovery material. Reconcile newer authority before restoring; same-Windows-user DPAPI only. No restored task started.'}
    for path in (dest/'verification.json',OUT/'recovery-increment.json'):path.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'files':len(files),'sqlite':databases,'destination':str(dest)}))

if __name__=='__main__':main()
