"""Data-only controller pointer rendering; parsing never executes a launcher."""
import ast
import json
from sdk.protocol import CoreError,canonical

MARKER='JARVIS_CONTROLLER_RECORD'


def legacy(build,port,expected):
    return '''"""Pinned Jarvis recovery-controller bootstrap (no user data migration)."""
from pathlib import Path
import hashlib,json,runpy,sys
base=Path(__file__).resolve().parent
root=base/'user-data'
controller=root/'deployment/controllers'/BUILD
inventory=(controller/'controller-files.json').read_bytes()
if hashlib.sha256(inventory).hexdigest()!=EXPECTED:raise RuntimeError('Recovery controller inventory changed')
for name,sha in json.loads(inventory).items():
    path=(controller/name).resolve()
    if not path.is_relative_to(controller.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise RuntimeError('Recovery controller code changed: '+name)
sys.path.insert(0,str(controller))
sys.argv=[str(controller/'apps/workbench/launch.py'),'--data-root',str(root),'--port',str(PORT),*sys.argv[1:]]
runpy.run_path(str(controller/'apps/workbench/launch.py'),run_name='__main__')
'''.replace('BUILD',repr(build)).replace('EXPECTED',repr(expected)).replace('PORT',str(port)).encode('utf-8')


def modern(record):
    return ('''"""Pinned controller bootstrap; business data are never restored here."""
from pathlib import Path
import hashlib,json,runpy,sys
JARVIS_CONTROLLER_RECORD = RECORD
record=json.loads(JARVIS_CONTROLLER_RECORD)
root=Path(__file__).resolve().parent/'user-data'
controller=Path(record['controller'])
if controller.parent.resolve()!=(root/'deployment/controllers').resolve():raise RuntimeError('Controller path changed')
if controller.is_symlink() or controller.is_junction():raise RuntimeError('Controller link refused')
inventory=(controller/'controller-files.json').read_bytes()
if hashlib.sha256(inventory).hexdigest()!=record['controller_inventory_sha256']:raise RuntimeError('Controller inventory changed')
files=json.loads(inventory)
actual=set()
for path in controller.rglob('*'):
    if path.is_symlink() or path.is_junction():raise RuntimeError('Controller link refused')
    if path.is_file():actual.add(path.relative_to(controller).as_posix())
if actual!=set(files)|{'controller-files.json'}:raise RuntimeError('Unexpected controller files')
for name,sha in files.items():
    path=(controller/name).resolve()
    if not path.is_relative_to(controller.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise RuntimeError('Controller code changed: '+name)
sys.path.insert(0,str(controller))
from control.controller_pin import verify
verify(root,record)
sys.argv=[str(controller/'apps/workbench/launch.py'),'--data-root',str(root),'--port',str(record['port']),*sys.argv[1:]]
runpy.run_path(str(controller/'apps/workbench/launch.py'),run_name='__main__')
'''.replace('RECORD\n',repr(canonical(record))+'\n')).encode('utf-8')


def embedded(raw):
    if len(raw)>131072:raise CoreError('controller_bootstrap','Launcher exceeds its bound')
    if MARKER.encode() not in raw:return None
    try:
        tree=ast.parse(raw.decode('utf-8'));values=[ast.literal_eval(node.value) for node in tree.body
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==MARKER for t in node.targets)]
        if len(values)!=1 or not isinstance(values[0],str):raise ValueError('Controller pointer')
        record=json.loads(values[0])
        if not isinstance(record,dict) or modern(record)!=raw:raise ValueError('Launcher template changed')
        return record
    except (ValueError,TypeError,SyntaxError,UnicodeError) as error:
        raise CoreError('controller_bootstrap','Cannot verify the controller launcher') from error
