"""Client for reviewed local software releases; no arbitrary shell commands or credentials."""
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from control.paths import child,reject_links
from control.recovery.gate import StopGate
from control.worker.process import OwnedProcess
from sdk.protocol import CoreError,canonical,read_json

def binding(root,ident='english-city'):
    path=child(root,'config/software.json')
    if not path.exists():raise CoreError('software_unavailable','Install the reviewed software release first')
    config=read_json(path)
    if not isinstance(config,dict) or type(config.get('schema')) is not int or config.get('schema')!=1 or ident not in config.get('software',{}):raise CoreError('software_unavailable','Software is not registered')
    item=config['software'][ident]
    if not isinstance(item,dict) or set(item)!={'enabled','release','build','revision'} or type(item['enabled']) is not bool or not isinstance(item['release'],str) or not isinstance(item['build'],str) or len(item['build'])!=64 or type(item['revision']) is not int:raise CoreError('software_integrity','Invalid software registration')
    if not item.get('enabled'):raise CoreError('software_disabled','Software disabled')
    folder=Path(item['release']);reject_links(folder)
    reject_links(folder/'software.json');manifest=read_json(folder/'software.json')
    if not isinstance(manifest,dict):raise CoreError('software_integrity','Invalid software manifest')
    if hashlib.sha256(canonical(manifest).encode()).hexdigest()!=item['build'] or manifest.get('id')!=ident or manifest.get('schema')!=1 or manifest.get('entry')!='engine.py' or set(manifest.get('files',{}))!={'engine.py'}:raise CoreError('software_integrity','Software descriptor changed')
    for name,sha in manifest['files'].items():
        p=folder/name;reject_links(p)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise CoreError('software_integrity','Software code changed')
    if {p.name for p in folder.iterdir()}!={'software.json','engine.py'}:raise CoreError('software_integrity','Unexpected release files')
    return {'id':ident,'build':item['build'],'version':manifest['version'],'revision':item['revision'],'release':str(folder)}

def invoke(root,operation,arguments,expected=None,checkpoint=lambda:None):
    StopGate(root).require_running();current=binding(root)
    if expected is not None and current!=expected:raise CoreError('software_stale','Software revision changed')
    payload=canonical({'schema':1,'operation':operation,'arguments':arguments}).encode()
    if len(payload)>65536:raise CoreError('software_input','Software input exceeds bound')
    base=child(root,'temp');base.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='software-',dir=base) as work:
        env={k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ};env.update(TEMP=work,TMP=work)
        with tempfile.TemporaryFile(dir=work) as out,tempfile.TemporaryFile(dir=work) as err:
            process=OwnedProcess([sys.executable,'-I','-B',str(Path(current['release'])/'engine.py')],stdout=out,stderr=err,env=env,cwd=work,input=payload,processes=1,cpu_seconds=5,memory_bytes=128*1024**2,checkpoint=checkpoint)
            try:
                deadline=time.monotonic()+8
                while process.poll() is None:
                    checkpoint();StopGate(root).require_running()
                    if time.monotonic()>deadline or out.tell()>65536 or err.tell()>8192:raise CoreError('software_timeout','Software exceeded bound')
                    time.sleep(.02)
                if process.returncode:raise CoreError('software_exit','Software process failed')
                out.seek(0);raw=out.read(65537)
            finally:process.close()
    if len(raw)>65536:raise CoreError('software_output','Software result exceeds bound')
    try:reply=json.loads(raw)
    except ValueError:raise CoreError('software_output','Invalid software response') from None
    if reply.get('ok') is not True or set(reply)!={'ok','result'}:raise CoreError('software_rejected','Software rejected request')
    if binding(root)!=current:raise CoreError('software_stale','Software changed during invocation')
    return reply['result']
