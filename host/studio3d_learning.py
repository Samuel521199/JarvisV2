"""One shared Host service for scoped experience and fixed Blender repairs."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from control.paths import child, data_root
from modules.context_knowledge.studio3d_experience import Studio3DExperience
from modules.skills.studio3d.learning_contract import validate, context, VERSION
from modules.skills.studio3d.assets import validate_glb
from sdk.protocol import CoreError

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('host/studio3d_learning.py', 'modules/context_knowledge/studio3d_experience.py',
           'modules/skills/studio3d/learning_contract.py', 'modules/skills/studio3d/experience-cards.json',
           'adapters/studio3d/learning_worker.py', 'apps/studio3d/learning_worker.py')
ADMISSION = threading.Lock()


def save(path, value):
    pending=path.with_suffix(path.suffix+'.tmp')
    pending.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    pending.replace(path)


def validate_export(path):
    node=shutil.which('node')
    if not node: raise CoreError('studio3d_build_failed','Node required for glTF validation')
    manifest=json.loads((ROOT/'external/gltf-validator/source.json').read_text(encoding='utf-8'))
    for name,row in manifest['files'].items():
        if hashlib.sha256((ROOT/'external/gltf-validator'/name).read_bytes()).hexdigest()!=row['sha256']:
            raise CoreError('studio3d_changed','Pinned validator changed')
    result=subprocess.run([node,'--max-old-space-size=256',str(ROOT/'adapters/studio3d/validate.cjs'),str(path)],
        capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or len(result.stdout)>200000: raise ValueError('glTF validation failed')
    report=json.loads(result.stdout)
    if report['issues']['numErrors'] or report['issues'].get('truncated'): raise ValueError('Export contains glTF errors')
    return report


def summary(root):
    from host.studio3d import enabled
    enabled(root); store = Studio3DExperience(root)
    try: return {**store.summary(), 'version':VERSION, 'tools':['remove_rejected','seat_attachment'], 'art_approval':False}
    finally: store.close()


def plan(root, contract):
    from host.studio3d import enabled
    enabled(root); v = validate(contract); store = Studio3DExperience(root)
    try: return {**store.retrieve(context(v)), 'contract':v, 'execution_requires_explicit_request':True}
    finally: store.close()


def feedback(root, body):
    from host.studio3d import enabled
    enabled(root)
    if not isinstance(body,dict) or set(body)!={'event_id','run_id','method_id','reason'}: raise ValueError('Invalid feedback fields')
    store = Studio3DExperience(root)
    try: return store.feedback(**body)
    finally: store.close()


def folder_for(root, ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident): raise ValueError('Invalid learning run ID')
    return child(data_root(root),'artifacts/studio3d-learning/'+ident)


def state(root, ident):
    folder = folder_for(root,ident)
    if (folder/'receipt.json').is_file(): return json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    if (folder/'status.json').is_file():
        value=json.loads((folder/'status.json').read_text(encoding='utf-8'))
        if value['status'] in ('QUEUED','RUNNING') and value.get('owner_pid')!=os.getpid():
            value.update(status='UNKNOWN',reason='Run belongs to a different process; no automatic replay')
        return value
    raise ValueError('Learning run not found')


def cancel(root, ident):
    folder = folder_for(root,ident); current = state(root,ident)
    if current['status'] in ('QUEUED','RUNNING'):
        (folder/'cancel').write_text('requested',encoding='ascii')
        return {'id':ident,'status':'CANCEL_REQUESTED'}
    return current


def _process(root, folder, executable, wall_seconds=300):
    from host.studio3d import enabled
    env = {k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')}
    config = folder/'config'; config.mkdir()
    env.update(TEMP=str(folder),TMP=str(folder),BLENDER_USER_CONFIG=str(config),BLENDER_USER_SCRIPTS=str(config),OMP_NUM_THREADS='4')
    native = job = None; began = time.monotonic()
    with (folder/'stdout.log').open('wb') as stdout, (folder/'stderr.log').open('wb') as stderr:
        process = subprocess.Popen([str(executable),'--background','--factory-startup','--disable-autoexec','--threads','4',
            '--python-exit-code','2','--python',str(ROOT/'apps/studio3d/learning_worker.py'),'--',str(folder)],
            cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import wintypes as w
                from control.worker import win32 as n
                native = n.bind(); job = native['CreateJobObjectW'](None,None)
                limits = n.JobLimit(); limits.basic.flags = 0x2000|0x8|0x100|0x200|0x2
                limits.basic.processes=2; limits.basic.cpu=1200*10_000_000; limits.memory=limits.job_memory=4*1024**3
                assign=n.api('kernel32','AssignProcessToJobObject',w.BOOL,w.HANDLE,w.HANDLE)
                if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):
                    raise CoreError('studio3d_limit','Resource Job unavailable')
            while process.poll() is None:
                enabled(root)
                if (folder/'cancel').exists(): raise CoreError('studio3d_cancelled','Learning run cancelled')
                if time.monotonic()-began > wall_seconds or sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) > 256*1024**2:
                    raise CoreError('studio3d_limit','Learning run exceeded resource budget')
                time.sleep(.15)
            if process.returncode: raise CoreError('studio3d_build_failed','Fixed learning worker failed; inspect retained logs')
        finally:
            if process.poll() is None: process.kill()
            process.wait()
            resource={'elapsed_seconds':time.monotonic()-began,'exit_code':process.returncode,'wall_limit_seconds':wall_seconds,'memory_limit_bytes':4*1024**3,'output_limit_bytes':256*1024**2}
            if job:
                measured=n.JobLimit()
                if native['QueryInformationJobObject'](job,9,ctypes.byref(measured),ctypes.sizeof(measured),None): resource['peak_memory_bytes']=measured.job_peak
                native['CloseHandle'](job)
            save(folder/'execution.json',resource)


def run(root, source, contract, *, repair=False, render=True, ident=None, reserved=False):
    """CLI and HTTP converge here. source is validated GLB bytes, never a path from a model."""
    from host.studio3d import enabled, LOCK, readiness
    root=data_root(root); enabled(root); contract=validate(contract)
    if type(repair) is not bool or type(render) is not bool: raise ValueError('Expected boolean execution flags')
    validate_glb(source)
    if not readiness(root)['ready']: raise CoreError('studio3d_not_prepared','Prepare installed Blender first')
    prepared=json.loads(child(root,'optional/studio3d/prepared.json').read_text(encoding='utf-8'))
    exe=Path(prepared['executable'])
    if hashlib.sha256(exe.read_bytes()).hexdigest()!=prepared['executable_sha256']: raise CoreError('studio3d_changed','Blender executable changed')
    ident=ident or uuid.uuid4().hex; folder=folder_for(root,ident)
    if not LOCK.acquire(blocking=False): raise CoreError('busy','Studio3D renderer busy')
    store=None; receipt=None
    try:
        if reserved:
            if state(root,ident)['status']!='QUEUED': raise ValueError('Run already started')
        else: folder.mkdir(parents=True,exist_ok=False)
        save(folder/'status.json',{'id':ident,'status':'RUNNING','owner_pid':os.getpid()})
        store=Studio3DExperience(root); retrieval=store.retrieve(context(contract))
        tools=sorted({t for m in retrieval['methods'] for t in m['tools']}) if repair else []
        source_hash=hashlib.sha256(source).hexdigest(); (folder/'source.glb').write_bytes(source)
        request={'contract':contract,'tools':tools,'render':render,'source_sha256':source_hash}
        save(folder/'request.json',request)
        receipt={'schema':'jarvis.studio3d.learning.receipt.v1','id':ident,'asset_id':contract['asset_id'],'status':'RUNNING',
            'version':VERSION,'source_sha256':source_hash,'contract_sha256':hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest(),
            'source_code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES},
            'retrieved_methods':[{'id':m['id'],'revision':m['revision']} for m in retrieval['methods']],
            'adoptions':[],'user_approval':False,'lod_authorized':False,'cross_asset_art_gain_verified':False,
            'cost':{'model_calls':0,'input_tokens':0,'output_tokens':0,'api_usd':0,'authoring_tokens':None,'authoring_usd':None,'compute_usd':None,'total_usd':None},
            'folder':str(folder)}
        tick=time.monotonic()
        try:
            _process(root,folder,exe)
            result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
            if result['source_sha256']!=source_hash: raise ValueError('Worker source mismatch')
            if result['candidate_sha256']:
                candidate=(folder/'candidate.glb').read_bytes(); validate_glb(candidate)
                if hashlib.sha256(candidate).hexdigest()!=result['candidate_sha256']: raise ValueError('Candidate changed')
                result['gltf_validation']=validate_export(folder/'candidate.glb')
            for action in result['actions']:
                if action['changed']:
                    method=next(m for m in retrieval['methods'] if action['tool'] in m['tools'])
                    receipt['adoptions'].append({'id':method['id'],'revision':method['revision'],'tool':action['tool']})
            receipt.update(status=result['status'],result=result)
            receipt['candidate_usable']=result['status'] in ('REPAIRED_DECLARED_CHECKS','PARTIAL_REPAIR')
            current={(m['id'],m['revision']) for m in store.retrieve(context(contract))['methods']}
            if any((m['id'],m['revision']) not in current for m in receipt['adoptions']):
                receipt.update(status='INVALIDATED_METHOD',candidate_usable=False)
            receipt['files']={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
                              for p in folder.iterdir() if p.is_file() and p.suffix in ('.glb','.blend','.png')}
            if (folder/'cancel').exists(): raise CoreError('studio3d_cancelled','Cancelled before adoption')
            if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>256*1024**2: raise CoreError('studio3d_limit','Final output quota exceeded')
        except BaseException as exc:
            receipt.update(status='FAILED',candidate_usable=False,error=str(exc))
            raise
        finally:
            receipt['cost']['wall_seconds']=time.monotonic()-tick
            save(folder/'receipt.json',receipt); store.record(receipt)
        return receipt
    finally:
        if store: store.close()
        LOCK.release()


def start(root, body):
    """HTTP accepts only an existing verified Jarvis job, no arbitrary path."""
    from host.studio3d import enabled, file, state as job_state
    enabled(root)
    if not isinstance(body,dict) or not {'id','source_job','contract'} <= set(body) or set(body)-{'id','source_job','contract','repair','render'}: raise ValueError('Unknown or missing learning request fields')
    contract=validate(body['contract'])
    repair=body.get('repair',False); render=body.get('render',True)
    if type(repair) is not bool or type(render) is not bool: raise ValueError('Expected execution flags')
    ident=body['id']; folder=folder_for(root,ident)
    signature=hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()
    with ADMISSION:
        if folder.exists():
            accepted=folder/'accepted.json'
            if not accepted.is_file() or json.loads(accepted.read_text(encoding='utf-8'))['signature']!=signature:
                raise CoreError('conflict','Learning request ID already has different inputs')
            return {**state(root,ident),'existing':True}
        from host.studio3d import LOCK
        if LOCK.locked(): raise CoreError('busy','Studio3D renderer busy')
        prior=job_state(root,body['source_job'])
        if prior['status']!='DELIVERED': raise ValueError('Use a delivered Studio3D job')
        source,_=file(root,body['source_job'],'model.glb')
        folder.mkdir(parents=True,exist_ok=False)
        save(folder/'accepted.json',{'signature':signature,'source_job':body['source_job']})
        save(folder/'status.json',{'id':ident,'status':'QUEUED','source_job':body['source_job'],'owner_pid':os.getpid()})
    def work():
        try: run(root,source,contract,repair=repair,render=render,ident=ident,reserved=True)
        except Exception as exc:
            if not (folder/'receipt.json').exists(): save(folder/'status.json',{'id':ident,'status':'FAILED','error':str(exc)})
    threading.Thread(target=work,daemon=True,name='studio3d-learning-'+ident[:8]).start()
    return {'id':ident,'status':'QUEUED'}
