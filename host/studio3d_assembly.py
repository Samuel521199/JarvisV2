"""Local-only high-poly intake, using Jarvis skill state and the shared render lane."""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import time
import uuid
from pathlib import Path
from host.studio3d import ROOT, enabled
from modules.skills.studio3d.assets import validate_glb
from modules.skills.studio3d.assembly_contract import VERSION, LIMITS, validate


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def intake(path):
    path=Path(path)
    if path.suffix.lower()!='.glb' or not path.is_file() or path.stat().st_size>LIMITS['part_bytes']:raise ValueError('Bounded GLB required')
    raw=path.read_bytes();validate_glb(raw);size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size])
    mesh_triangles=[sum(doc['accessors'][p['indices']]['count']//3 if 'indices' in p else doc['accessors'][p['attributes']['POSITION']]['count']//3 for p in m['primitives']) for m in doc['meshes']]
    # glTF may instance the same mesh in many nodes. Budget visible instances,
    # conservatively including nodes outside the selected scene, not definitions.
    indices=[n['mesh'] for n in doc.get('nodes',[]) if 'mesh' in n]
    if any(type(i) is not int or not 0<=i<len(mesh_triangles) for i in indices):raise ValueError('Invalid mesh instance')
    triangles=sum(mesh_triangles[i] for i in indices) if indices else sum(mesh_triangles)
    if any(p.get('mode',4)!=4 for m in doc['meshes'] for p in m['primitives']):raise ValueError('Triangle meshes required')
    if triangles>LIMITS['triangles']:raise ValueError('Triangle budget')
    return raw,{'path':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'triangles':triangles,'materials':len(doc.get('materials',[])),'textures':len(doc.get('images',[])),'generator':doc['asset'].get('generator')}


def run(root,contract,sources,reference=None):
    root=Path(root).resolve();enabled(root);config=validate(contract)
    required={p['source'] for p in config['parts']}
    if set(sources)!=required:raise ValueError('Exact named local source mapping required')
    prepared=json.loads((root/'optional/studio3d/prepared.json').read_text(encoding='utf-8'));exe=Path(prepared['executable'])
    if hashlib.sha256(exe.read_bytes()).hexdigest()!=prepared['executable_sha256']:raise ValueError('Blender executable changed')
    ident=uuid.uuid4().hex;folder=root/'artifacts/studio3d-assembly'/ident;folder.mkdir(parents=True)
    rows={}
    for name,path in sources.items():
        raw,row=intake(path);rows[name]=row;(folder/(name+'.glb')).write_bytes(raw)
    triangles=sum(rows[p['source']]['triangles'] for p in config['parts'])
    if triangles>LIMITS['triangles']:raise ValueError('Combined triangle budget')
    reference_row=None
    if reference:
        p=Path(reference)
        if p.suffix.lower()!='.png' or p.stat().st_size>20*1024**2:raise ValueError('Reference PNG required')
        from PIL import Image
        with Image.open(p) as im:
            if im.format!='PNG' or im.width*im.height>20000000:raise ValueError('Reference image budget')
            im.verify()
        shutil.copyfile(p,folder/'reference.png');reference_row={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    save(folder/'request.json',{'contract':config,'sources':rows,'reference':reference_row})
    source_paths=['modules/skills/studio3d/assembly_contract.py','host/studio3d_assembly.py','adapters/studio3d/assembly_worker.py','apps/studio3d/assembly_worker.py','control/studio3d_lane.py']
    receipt={'schema':'jarvis.studio3d.assembly.receipt.v1','id':ident,'version':VERSION,'status':'RUNNING','folder':str(folder),'sources':rows,'contract':config,'reference':reference_row,'limits':LIMITS,'source_code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},'model_calls':0,'api_usd':0,'authoring_cost':None,'mechanical_certified':False,'AAA_certified':False}
    save(folder/'receipt.json',receipt);print(json.dumps({'id':ident,'folder':str(folder),'status':'RUNNING'}),flush=True)
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')}
    (folder/'config').mkdir();env.update(TEMP=str(folder),TMP=str(folder),BLENDER_USER_CONFIG=str(folder/'config'),BLENDER_USER_SCRIPTS=str(folder/'config'),OMP_NUM_THREADS='4')
    started=time.monotonic();job=None;native=None;process=None
    try:
        with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
            process=subprocess.Popen([str(exe),'--background','--factory-startup','--disable-autoexec','--threads','4','--python-exit-code','2','--python',str(ROOT/'apps/studio3d/assembly_worker.py'),'--',str(folder)],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if os.name=='nt':
                import ctypes
                from ctypes import wintypes as w
                from control.worker import win32 as n
                native=n.bind();job=native['CreateJobObjectW'](None,None);limits=n.JobLimit()
                limits.basic.flags=0x2000|0x8|0x100|0x200;limits.basic.processes=2;limits.memory=limits.job_memory=LIMITS['memory_bytes']
                assign=n.api('kernel32','AssignProcessToJobObject',w.BOOL,w.HANDLE,w.HANDLE)
                if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):raise RuntimeError('Resource Job unavailable')
            while process.poll() is None:
                enabled(root)
                if any(p.exists() for p in [folder/'cancel',root/'state/STOP',root/'state/LATCH']):raise RuntimeError('Assembly cancelled')
                if time.monotonic()-started>LIMITS['wall_seconds'] or sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>LIMITS['output_bytes']:raise RuntimeError('Assembly resource budget')
                time.sleep(.5)
            if process.returncode:raise RuntimeError('Blender assembly failed; inspect retained logs')
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        receipt.update(status='BUILT_AWAITING_VISUAL_REVIEW',report=report,source_unchanged=all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in rows.values()))
        if not receipt['source_unchanged']:raise RuntimeError('Source changed during assembly')
        receipt['outputs']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.iterdir() if p.name not in {x+'.glb' for x in rows} and p.suffix in ('.blend','.glb','.png','.json') and p.name not in ('receipt.json','request.json')}
    except BaseException as e:
        receipt.update(status='FAILED',error=str(e));raise
    finally:
        if process is not None and process.poll() is None:process.kill()
        if process is not None:process.wait()
        if job:
            measured=n.JobLimit()
            if native['QueryInformationJobObject'](job,9,ctypes.byref(measured),ctypes.sizeof(measured),None):receipt['peak_memory_bytes']=measured.job_peak
            native['CloseHandle'](job)
        receipt['elapsed_seconds']=time.monotonic()-started;save(folder/'receipt.json',receipt)
    return receipt
