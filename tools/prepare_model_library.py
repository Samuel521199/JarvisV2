"""Run the fixed preview/extraction worker with finite resources and provenance."""
import ctypes,hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT)]
from host.studio3d_learning import save
from control.worker import win32 as n

def main():
 folder=ROOT/'user-data/artifacts/model-library-prep'/uuid.uuid4().hex;folder.mkdir(parents=True)
 tank=ROOT/'3DModels/PanzerII-reference-assembly/revision-r3';receipt=json.loads((tank/'metadata/native-receipt.json').read_text());current=json.loads((ROOT/'3DModels/PaK38/metadata/current-model.json').read_text())['working_candidate']
 req={'sources':[{'id':'tank','path':str(tank/'assembled.blend'),'sha256':receipt['outputs']['assembled.blend']['sha256']},{'id':'pak','path':str(ROOT/'3DModels/PaK38'/current['blend']),'sha256':current['blend_sha256']}]}
 # Some asset versions use the model path key instead of the short alias.
 for row in req['sources']:
  if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Exact current source required')
 save(folder/'request.json',req);save(ROOT/'user-data/model-library-preparation.json',{'folder':str(folder),'status':'RUNNING','owner_pid':os.getpid()});prepared=json.loads((ROOT/'user-data/optional/studio3d/prepared.json').read_text());exe=Path(prepared['executable'])
 if hashlib.sha256(exe.read_bytes()).hexdigest()!=prepared['executable_sha256']:raise ValueError('Blender changed')
 worker=ROOT/'tools/model_library_prepare_worker.py';bootstrap=folder/'bootstrap.py';bootstrap.write_text("import sys\nfrom pathlib import Path\nsys.path[:0]=["+repr(str(ROOT))+ "]\nfrom tools.model_library_prepare_worker import main\nfrom control.studio3d_lane import render_lane\nfolder=Path(sys.argv[-1])\nwith render_lane(folder):main(folder)\n",encoding='utf-8')
 status={'status':'RUNNING','started_at':time.time(),'wall_limit_seconds':600,'memory_bytes':16*1024**3,'worker_sha256':hashlib.sha256(worker.read_bytes()).hexdigest(),'request':req,'api_usd':0,'local_compute_usd':None};save(folder/'status.json',status);process=None;job=None;native=None
 try:
  with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
   process=subprocess.Popen([str(exe),'--background','--factory-startup','--disable-autoexec','--threads','4','--python-exit-code','2','--python',str(bootstrap),'--',str(folder)],cwd=folder,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if os.name=='nt':
    native=n.bind();job=native['CreateJobObjectW'](None,None);limits=n.JobLimit();limits.basic.flags=0x2000|0x8|0x100|0x200;limits.basic.processes=2;limits.memory=limits.job_memory=16*1024**3
    assign=ctypes.windll.kernel32.AssignProcessToJobObject;assign.argtypes=[ctypes.c_void_p,ctypes.c_void_p];assign.restype=ctypes.c_int
    if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):raise RuntimeError('Resource guard unavailable')
   while process.poll() is None:
    if time.time()-status['started_at']>600:raise TimeoutError('Preview preparation exceeded600 seconds')
    time.sleep(.3)
   if process.returncode or not (folder/'report.json').exists():raise RuntimeError('Preview worker failed; retained evidence: '+str(folder))
  status['status']='SUCCEEDED'
 except BaseException as exc:status.update(status='FAILED',error=str(exc));raise
 finally:
  if process and process.poll() is None:process.kill();process.wait()
  if job:native['CloseHandle'](job)
  status['elapsed_seconds']=time.time()-status['started_at'];save(folder/'status.json',status);save(ROOT/'user-data/model-library-preparation.json',{'folder':str(folder),'status':status['status']})
 print(str(folder))
if __name__=='__main__':main()
