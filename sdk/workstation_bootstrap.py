"""Pure bootstrap template for the hash-pinned workstation management capsule."""


def service_bootstrap(capsule,helper,helper_sha):
    return '''"""Pinned daily automation; no development startup or model calls."""
from pathlib import Path
import hashlib,json,runpy,sys
root=Path(__file__).resolve().parent/'user-data'
capsule=root/'deployment/automation/capsules'/CAPSULE
raw=(capsule/'files.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!=CAPSULE:raise RuntimeError('Service inventory changed')
for name,sha in json.loads(raw).items():
 p=(capsule/name).resolve()
 if not p.is_relative_to(capsule.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise RuntimeError('Service changed')
helper=Path(HELPER)
raw=(helper/'controller-files.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!=HELPER_SHA:raise RuntimeError('Service helper inventory changed')
for name,sha in json.loads(raw).items():
 p=(helper/name).resolve()
 if not p.is_relative_to(helper.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise RuntimeError('Service helper changed')
if {p.relative_to(helper).as_posix() for p in helper.rglob('*') if p.is_file()}!=set(json.loads(raw))|{'controller-files.json'}:raise RuntimeError('Unregistered helper file')
sys.path.insert(0,str(helper))
sys.argv=[str(capsule/'service.py'),'run','--daily-data',str(root),'--operator',str(capsule/'operator.py'),*sys.argv[1:]]
runpy.run_path(str(capsule/'service.py'),run_name='__main__')
'''.replace('CAPSULE',repr(capsule)).replace('HELPER_SHA',repr(helper_sha)).replace('HELPER',repr(str(helper)))
