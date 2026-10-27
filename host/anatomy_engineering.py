"""Bounded engineering DATA contract and rigid assembly transforms (mm/radians).

No model-generated code, paths, expressions or native-library objects accepted.
"""
import copy, json, math, re
from pathlib import Path
from sdk.protocol import CoreError

ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'modules/skills/anatomy'
CONTRACT=json.loads((HOME/'engineering-contract.json').read_text(encoding='utf-8'))

from modules.skills.anatomy.engineering_model import validate_engineering,assembly_poses,ports,rotation

def runtime_python():return ROOT/'.venv/anatomy'/('Scripts/python.exe' if __import__('os').name=='nt' else 'bin/python')
def readiness():
    import hashlib
    lock=ROOT/'user-data/optional/anatomy/prepared.json';ready=False
    try:ready=runtime_python().is_file() and json.loads(lock.read_text(encoding='utf-8'))['lock_sha256']==hashlib.sha256((HOME/'runtime-lock.json').read_bytes()).hexdigest()
    except (OSError,ValueError,KeyError):pass
    return {'schema':CONTRACT['schema'],'native_runtime':ready,'assembly':ready,'cad':ready,'combustion':ready,'limits':'Trusted optional native code, not an LPAC sandbox. Static interference and explicitly listed numerical models only.'}

def render_engineering(root,scene,source):
    import contextlib,ctypes,hashlib,os,shutil,subprocess,tempfile,time,uuid
    from control.paths import child
    from control.recovery.gate import StopGate
    if not readiness()['native_runtime']:raise CoreError('anatomy_native_missing','Prepare the pinned optional engineering runtime first')
    folder=child(root,'artifacts/anatomy');folder.mkdir(parents=True,exist_ok=True);ident=uuid.uuid4().hex
    final=folder/(ident+'-engineering')
    with tempfile.TemporaryDirectory(prefix='engineering-',dir=folder) as stage_name:
        stage=Path(stage_name).resolve()
        if folder.resolve() not in stage.parents:raise CoreError('unsafe_path','Invalid engineering work directory')
        stdout=stage/'worker.stdout';stderr=stage/'worker.stderr';job=None;native=None;resources_used={};started=time.monotonic()
        env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR'}};env.update(TEMP=str(stage),TMP=str(stage),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        with stdout.open('wb') as out,stderr.open('wb') as err:
            process=subprocess.Popen([str(runtime_python()),'-I','-B',str(ROOT/'apps/engineering/worker.py'),'--folder',str(stage)],stdin=subprocess.PIPE,stdout=out,stderr=err,env=env,cwd=stage,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                if os.name=='nt':
                    from control.worker import win32 as n
                    from ctypes import wintypes as w
                    native=n.bind();job=native['CreateJobObjectW'](None,None);limits=n.JobLimit();limits.basic.flags=0x2000|0x8|0x100|0x200|0x2;limits.basic.processes=2;limits.basic.cpu=30*10_000_000;limits.memory=limits.job_memory=1024*1024*1024
                    assign=n.api('kernel32','AssignProcessToJobObject',w.BOOL,w.HANDLE,w.HANDLE)
                    if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):raise CoreError('anatomy_engineering_limit','Native job limits unavailable')
                process.stdin.write(json.dumps(scene,ensure_ascii=False).encode());process.stdin.close();deadline=time.monotonic()+45
                while process.poll() is None:
                    StopGate(root).require_running()
                    if time.monotonic()>=deadline:raise CoreError('anatomy_timeout','Engineering task exceeded 45 seconds')
                    if sum(p.stat().st_size for p in stage.iterdir() if p.is_file())>64*1024*1024 or stdout.stat().st_size>1024*1024 or stderr.stat().st_size>1024*1024:raise CoreError('anatomy_engineering_limit','Engineering output quota exceeded')
                    time.sleep(.05)
                if process.returncode:
                    diagnostic=child(root,'diagnostics/anatomy');diagnostic.mkdir(parents=True,exist_ok=True)
                    peaks={}
                    if job:
                        measured=n.JobLimit()
                        if native['QueryInformationJobObject'](job,9,ctypes.byref(measured),ctypes.sizeof(measured),None):peaks={'peak_process_memory_bytes':measured.peak,'peak_job_memory_bytes':measured.job_peak}
                    (diagnostic/(ident+'-failure.json')).write_text(json.dumps({'id':ident,'exit_code':process.returncode,'resources':peaks,'elapsed_seconds':time.monotonic()-started,'stderr':stderr.read_text(encoding='utf-8',errors='replace')[-6000:],'stdout':stdout.read_text(encoding='utf-8',errors='replace')[-1800:],'successful_artifact':False},ensure_ascii=False,indent=2),encoding='utf-8')
                    raise CoreError('anatomy_engineering_build','Trusted geometry or numerical solver failed; no successful artifact was issued')
            finally:
                if process.poll() is None:process.kill()
                process.wait()
                if job:
                    measured=n.JobLimit()
                    if native['QueryInformationJobObject'](job,9,ctypes.byref(measured),ctypes.sizeof(measured),None):resources_used={'peak_process_memory_bytes':measured.peak,'peak_job_memory_bytes':measured.job_peak}
                    native['CloseHandle'](job)
        StopGate(root).require_running()
        data_path=stage/'result.json'
        if not data_path.is_file() or data_path.stat().st_size>8*1024*1024:raise CoreError('anatomy_engineering_limit','Engineering result size invalid')
        data=json.loads(data_path.read_text(encoding='utf-8'));downloads={}
        for name in ('assembly.step','assembly.stl','cad-package.zip','bom.csv','flange-profile.dxf','configuration.json','report.json'):
            p=stage/name
            if p.is_file():downloads[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'url':'/api/anatomy/exports/'+ident+'/'+name}
        import base64,gzip
        raw_total=sum(row['bytes'] for row in downloads.values())
        if raw_total>32*1024*1024:raise CoreError('anatomy_engineering_limit','Expanded portable download budget exceeded')
        payload={name:(stage/name).read_bytes() for name in downloads};encodings={}
        if raw_total>8*1024*1024:
            for name,raw in payload.items():
                compressed=gzip.compress(raw,mtime=0)
                if len(compressed)<len(raw):payload[name]=compressed;encodings[name]='gzip'
        if sum(len(raw) for raw in payload.values())>8*1024*1024:raise CoreError('anatomy_engineering_limit','Compressed portable download budget exceeded')
        envelope={'scene':scene,'result':data,'downloads':downloads,'embedded_encodings':encodings,'embedded_downloads':{name:base64.b64encode(raw).decode('ascii') for name,raw in payload.items()}}
        node=shutil.which('node')
        if not node:raise CoreError('anatomy_dependency','Node.js required')
        built=subprocess.run([node,str(HOME/'engineering-build.mjs')],input=json.dumps(envelope,ensure_ascii=False).encode(),capture_output=True,timeout=15,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if built.returncode or not 10000<len(built.stdout)<12*1024*1024:raise CoreError('anatomy_build','Engineering viewer did not produce bounded HTML')
        StopGate(root).require_running();output=folder/(ident+'.html');output.write_bytes(built.stdout)
        # Both resolved paths remain inside this artifact root; no user-selected moves.
        if folder.resolve() not in final.resolve().parents:raise CoreError('unsafe_path','Invalid engineering artifact directory')
        stage.rename(final)
        resources=['engineering-contract.json','engineering-presets.json','engineering-build.mjs','engineering.html','engineering-view.js','engineering-motion.mjs','engineering-gpu.mjs','engineering_physics.py','engineering_model.py','engineering_transmission.py','runtime-boundary.json','structure3d.mjs','runtime-lock.json']
        receipt={'id':ident,'skill':'gears','mechanism':'engineering','configuration':scene,'adapter_version':'5.2.0','source':source,'sha256':hashlib.sha256(built.stdout).hexdigest(),'bytes':len(built.stdout),'url':'/api/anatomy/artifacts/'+ident,'path':str(output),'model_calls':0,'downloads':downloads,'checks':{k:v for k,v in data['assembly'].items() if k not in ('fits',)},'renderer_sha256':{p:hashlib.sha256((HOME/p).read_bytes()).hexdigest() for p in resources},'host_validation_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['host/anatomy_engineering.py','adapters/engineering/worker.py','apps/engineering/worker.py','modules/skills/anatomy/engineering_model.py']},'runtime_lock_sha256':hashlib.sha256((HOME/'runtime-lock.json').read_bytes()).hexdigest(),'limits':data['limits']}
        extra=[data['assembly'].get('groups'),data['assembly'].get('operation')];extra.append((data['assembly'].get('groups') or {}).get('parallel_internal'))
        receipt['quality']={'status':'needs_revision' if data['assembly']['collisions'] or data['assembly']['insertion']['hits'] or any(x and x['hits'] for x in extra) or any(x['status']=='mismatch' for x in data['assembly']['fits']) else 'checked_scope_passed','unverified':['continuous_insertion_paths','full_motion_cycle_interference','manufacturing_tolerances','general_assembly_dynamics']}
        receipt['resources']={**resources_used,'elapsed_seconds':time.monotonic()-started,'wall_limit_seconds':45,'process_cpu_limit_seconds':30,'job_memory_limit_bytes':1024**3,'active_process_limit':2,'output_quota_bytes':64*1024**2,'portable_expanded_bytes':raw_total,'portable_embedded_bytes':sum(len(raw) for raw in payload.values()),'portable_encoding':encodings,'isolation':'Trusted fixed native factories; resource job only, not LPAC security isolation'}
        StopGate(root).require_running();output.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');return receipt

def exported(root,ident,name):
    import hashlib
    from control.paths import child
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident) or name not in ('assembly.step','assembly.stl','cad-package.zip','bom.csv','flange-profile.dxf','configuration.json','report.json'):raise CoreError('anatomy_missing','Unknown engineering export')
    folder=child(root,'artifacts/anatomy');receipt=json.loads((folder/(ident+'.json')).read_text(encoding='utf-8'));row=receipt.get('downloads',{}).get(name)
    if not row:raise CoreError('anatomy_missing','Unknown export')
    raw=(folder/(ident+'-engineering')/name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise CoreError('anatomy_changed','Export changed')
    return raw
