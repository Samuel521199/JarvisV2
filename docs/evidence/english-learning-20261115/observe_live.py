"""Bounded foreground acceptance, no resident monitoring or scheduled task."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from tools.workstation import instance,state
from control.controller_pin import read
from host.application_release import tracked_runtime
import hashlib

def main():
    root=Path('E:/Jarvis/runtime/user-data');expected=state(root);pin=read(root);boot=instance(18282);assert boot
    result={'scope':'120 seconds foreground observation, including a separately recorded development restart; not continuous availability or automatic monitoring proof','samples':[],'passed':False}
    for i in range(25):
        current=instance(18282);result['samples'].append({'index':i,'time':time.time(),'online':bool(current),'same_boot':bool(current and current['boot_id']==boot['boot_id']),'same_build':bool(current and current['application_build']==expected['active']['build'])})
        (OUT/'live-observation.json').write_text(json.dumps(result,indent=2)+'\n')
        if i<24:time.sleep(5)
    assert all(r['online'] and r['same_boot'] and r['same_build'] for r in result['samples'])
    assert state(root)==expected and read(root)==pin
    from modules.release_recovery.application import Applications
    package=Path(Applications(root).approved(expected['active']['build'])['path']);manifest=json.loads((package/'application.json').read_text())
    assert set(manifest['files'])==set(tracked_runtime(ROOT)) and all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    result.update(passed=True,development_online=bool(instance(18283)),runtime_files_verified=len(manifest['files']),application=expected,boot_id=boot['boot_id'])
    (OUT/'live-observation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
if __name__=='__main__':main()
