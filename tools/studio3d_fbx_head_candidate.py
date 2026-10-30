"""Make one local experimental head/hair candidate from the owner's A-pose.

The diagnostic baseline is copied, never overwritten. This is a fixed worker,
not execution of model-generated code. Its result is not an approval.
"""
import argparse,hashlib,json,os,shutil,subprocess,time,uuid
from pathlib import Path
from control.recovery.gate import StopGate
from host.studio3d_learning import validate_export

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'user-data'
PROJECT=ROOT/'3DModels/SilverHairCharacter'
BASE=PROJECT/'user-fbx-a-pose-diagnostic/model-rigged-apose.blend'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision',choices=('v1','v2','v3','v4'),default='v1');args=parser.parse_args()
    out=PROJECT/('user-fbx-hair-face-candidate' if args.revision=='v1' else 'user-fbx-hair-face-candidate-'+args.revision)
    StopGate(DATA).require_running()
    if out.exists():raise ValueError('Candidate output exists; never overwrite it')
    if not BASE.is_file():raise ValueError('Expected owner-authorized baseline missing')
    original=sha(BASE);folder=DATA/'artifacts/studio3d-character'/uuid.uuid4().hex;folder.mkdir(parents=True)
    shutil.copyfile(BASE,folder/'source.blend')
    if sha(folder/'source.blend')!=original:raise ValueError('Source copy differs')
    prepared=json.loads((DATA/'optional/studio3d/prepared.json').read_text(encoding='utf8'));exe=Path(prepared['executable'])
    if sha(exe)!=prepared['executable_sha256']:raise ValueError('Prepared Blender changed')
    sources=['apps/studio3d/character_fbx_head_worker.py','modules/skills/studio3d/character_head.py',
             'modules/skills/studio3d/character_fbx_face.py','modules/skills/studio3d/character_contract.py',
             'modules/skills/studio3d/character_recipe.py','modules/skills/studio3d/character_surface.py',
             'modules/skills/studio3d/contract.py','adapters/studio3d/worker.py','control/studio3d_lane.py']
    hashes={p:sha(ROOT/p) for p in sources};save(folder/'request.json',{'source_sha256':original,'sources':hashes})
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')}
    config=folder/'config';config.mkdir();env.update(TEMP=str(folder),TMP=str(folder),BLENDER_USER_CONFIG=str(config),BLENDER_USER_SCRIPTS=str(config),OMP_NUM_THREADS='4')
    from control.worker import win32 as n
    import ctypes
    from ctypes import wintypes as w
    native=n.bind();job=native['CreateJobObjectW'](None,None);limits=n.JobLimit();limits.basic.flags=0x2000|0x8|0x100|0x200|0x2
    limits.basic.processes=2;limits.basic.cpu=1200*10_000_000;limits.memory=limits.job_memory=4*1024**3
    begin=time.monotonic()
    try:
        with (folder/'stdout.log').open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
            process=subprocess.Popen([str(exe),'--background','--factory-startup','--disable-autoexec','--threads','4',
                '--python-exit-code','2','--python',str(ROOT/sources[0]),'--',str(folder)],cwd=folder,env=env,
                stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                assign=n.api('kernel32','AssignProcessToJobObject',w.BOOL,w.HANDLE,w.HANDLE)
                if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):
                    raise RuntimeError('Worker resource Job unavailable')
                while process.poll() is None:
                    StopGate(DATA).require_running()
                    if time.monotonic()-begin>300:raise TimeoutError('Candidate total time limit')
                    if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('Candidate output limit')
                    time.sleep(.15)
                if process.returncode:raise RuntimeError('Worker failed; retained logs '+str(folder))
            finally:
                if process.poll() is None:process.kill()
                process.wait()
    finally:
        if job:native['CloseHandle'](job)
    if sha(BASE)!=original or any(sha(ROOT/p)!=h for p,h in hashes.items()):raise ValueError('Source changed during generation')
    report=json.loads((folder/'report.json').read_text(encoding='utf8'))
    if not report['roundtrip']['passed'] or report.get('atlas_loaded'):raise ValueError('Candidate verification failed')
    validation=validate_export(folder/'character-static-experimental.glb');save(folder/'format-validation.json',validation)
    out.mkdir()
    names=['character-rigged-experimental.blend','character-static-experimental.glb','view-front.png','view-rear.png','view-left.png','view-right.png','view-head.png','report.json','resource-lane.json','format-validation.json']
    for name in names:shutil.copyfile(folder/name,out/name)
    manifest={'source_baseline_sha256':original,'source_code_sha256':hashes,'files':{name:sha(out/name) for name in names},
              'source':'Existing user-provided FBX diagnostic; derivative, not image-to-3D learning',
              'user_approval':False,'user_atlas_loaded':False,'limited_visual_approximation':True,'artifact_run':folder.name}
    save(out/'manifest.json',manifest)
    print(json.dumps({'status':'CANDIDATE_READY','output':str(out),'run':str(folder)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
