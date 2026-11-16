"""Build a reviewed first-party read-only compatibility backport from daily 0.1.12."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from modules.release_recovery.application import Applications,build

def main():
    work=Path('E:/Jarvis/validation/english-city-recovery-20261116');work.mkdir(exist_ok=False)
    source=work/'source';source.mkdir()
    app=Applications(Path('E:/Jarvis/runtime/user-data'));base=app.approved(app.state()['active']['build'])
    package=Path(base['path']);manifest=json.loads((package/'application.json').read_text())
    for name in manifest['files']:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(package/name,target)
    names=list(manifest['files'])
    changed=['control/application_compatibility.py','control/controller_pin.py','config/controller-compatibility.json','config/english-learning-compatibility.json','adapters/application_host.py','apps/workbench/supervisor.py']
    for name in changed:
        shutil.copy2(ROOT/name,source/name)
        if name not in names:names.append(name)
    guard='''"""Read-only recovery: never dispatch queued learning requests as ordinary chat."""
from pathlib import Path
import sqlite3
from sdk.protocol import CoreError

def binding(root,ident):return ident.startswith('english-')

def checkpoint(root,ident):
    if not ident.startswith('english-'):return
    path=Path(root)/'state/english-learning.sqlite3'
    if not path.exists():return
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if db.execute('PRAGMA user_version').fetchone()[0] not in (1,2,3):raise CoreError('english_readonly','Unknown learning schema')
        if db.execute('SELECT 1 FROM jobs WHERE id=?',(ident,)).fetchone():raise CoreError('english_readonly','Resume learning in the compatible full version')
    finally:db.close()
'''
    (source/'host/english_learning.py').write_text(guard,encoding='utf-8');names.append('host/english_learning.py')
    path=source/'host/dialogue.py';text=path.read_text(encoding='utf-8')
    anchor='                StopGate(self.root).require_running(); store.checkpoint(ident)'
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+'\n                from host.english_learning import checkpoint as learning_checkpoint\n                learning_checkpoint(self.root,ident)')
    path.write_text(text,encoding='utf-8')
    server=source/'apps/workbench/server.py';server_text=server.read_text(encoding='utf-8');server_text=server_text.replace("                from host.english_learning import command as learning_command","                raise CoreError('english_readonly','Resume learning in the full compatible version')\n                from host.english_learning import command as learning_command");server.write_text(server_text,encoding='utf-8')
    version='0.1.12-city-recovery.1';(source/'VERSION').write_text(version+'\n',encoding='utf-8')
    ident=build(source,names,work/'candidate.zip',version)
    result={'build':ident,'base_build':base['build'],'source':str(source),'archive':str(work/'candidate.zip'),'changed':changed+['host/english_learning.py','host/dialogue.py','VERSION'],'scope':'Read-only learning preservation; normal previous daily features, no learning API or automatic paid replay'}
    (Path(__file__).parent/'recovery-build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
