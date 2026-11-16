"""Prepare a reviewable code-only bridge; never adopt or restore user state."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from modules.release_recovery.application import Applications,build

OVERLAY=[
 'sdk/protocol.py','control/application_compatibility.py','control/controller_pin.py','config/controller-compatibility.json',
 'config/english-learning-compatibility.json','config/speech-compatibility.json','config/local-models-compatibility.json',
 'host/learning_sources.py','host/speech_receipts.py','host/local_models.py','host/speech_models.py','host/speech.py','host/speech_audio.py','host/speech_sources.py',
 'modules/local_models/assessments.json','modules/local_models/catalog.py','modules/local_models/catalog.json','modules/local_models/runtime.py',
 'modules/local_models/speech-runtime.json','modules/local_models/speech-evaluations.json',
 'adapters/models/audio_pcm.py','adapters/models/local_speech_worker.py','adapters/models/speech_features.py',
 'modules/english_learning/store.py','modules/speech/__init__.py','modules/speech/store.py',
 'host/dialogue.py','adapters/application_host.py','apps/workbench/supervisor.py']

def prepare(work,base):
 work=Path(work);work.mkdir(exist_ok=False);source=work/'source';source.mkdir()
 package=Path(base['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'));names=list(manifest['files'])
 for name in names:
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(package/name,target)
 for name in OVERLAY:
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
  if name not in names:names.append(name)
 guard='''"""Compatible recovery: keep history, reject pending learning before provider use."""
from sdk.protocol import CoreError
def binding(root,ident):return {'body':{}} if ident.startswith('english-') else None
def checkpoint(root,ident):
 if ident.startswith('english-'):raise CoreError('english_readonly','Resume learning in the compatible full version')
def context(*args):raise CoreError('english_readonly','Recovery does not evaluate learning')
def materialize(*args):raise CoreError('english_readonly','Recovery does not evaluate learning')
def completed(*args):pass
'''
 (source/'host/english_learning.py').write_text(guard,encoding='utf-8')
 if 'host/english_learning.py' not in names:names.append('host/english_learning.py')
 p=source/'host/speech_sources.py';s=p.read_text(encoding='utf-8');mark="    if not isinstance(ident,str) or not ident.startswith('voice-speech-'):return"
 assert s.count(mark)==1;s=s.replace(mark,mark+"\n    raise CoreError('speech_readonly','Resume confirmed speech input in the compatible full version')",1);p.write_text(s,encoding='utf-8')
 p=source/'host/local_models.py';s=p.read_text(encoding='utf-8');mark="            self._check()\n            if action=='register':"
 assert s.count(mark)==1;s=s.replace(mark,"            self._check()\n            if action.startswith('speech_') or ident and self.item(ident)['kind']=='stt':raise CoreError('speech_readonly','Recovery preserves speech selection without starting or changing it')\n            if action=='register':",1);p.write_text(s,encoding='utf-8')
 p=source/'apps/workbench/server.py';s=p.read_text(encoding='utf-8');mark="                from host.english_learning import command as learning_command"
 assert s.count(mark)==1;s=s.replace(mark,"                raise CoreError('english_readonly','Resume learning in the compatible full version')\n"+mark,1);p.write_text(s,encoding='utf-8')
 from tools.sync_studio3d_programs import sync
 import contextlib,io
 with contextlib.redirect_stdout(io.StringIO()):sync(source)
 version='0.1.13-speech-recovery.1';(source/'VERSION').write_text(version+'\n',encoding='utf-8');ident=build(source,names,work/'candidate.zip',version)
 return {'build':ident,'base_build':base['build'],'source':str(source),'archive':str(work/'candidate.zip'),'changed':OVERLAY+['host/english_learning.py','apps/workbench/server.py','modules/skills/studio3d/worker-programs.json','VERSION'],
 'scope':'Code-only bridge; original embedding/chat remain usable; speech model pins retained; learning/speech input are read-only; pending paid learning/voice requests do not replay; no user database restore'}

if __name__=='__main__':
 app=Applications(Path('E:/Jarvis/runtime/user-data'));base=app.approved(app.state()['active']['build'])
 result=prepare(Path(sys.argv[1]),base);(Path(__file__).parent/'recovery-build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
