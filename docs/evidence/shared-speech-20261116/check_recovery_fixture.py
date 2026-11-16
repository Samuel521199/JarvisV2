from pathlib import Path
import sys,tempfile,json,hashlib,subprocess,copy
sys.path.insert(0,str(Path('tests').resolve()))
from test_shared_speech import SpeechFlow
from test_speech_models import FakeSpeech
from test_local_models import FakeWorker
from host.local_models import LocalModels
from modules.local_models.catalog import builtin
from control.application_compatibility import require_compatible
work=Path('E:/Jarvis/validation/shared-speech-bridge-fixture-20261116');work.mkdir(exist_ok=True);tempfile.tempdir=str(work)
case=SpeechFlow();case.setUp();case.test_asr_confirmed_learning_preserves_raw_and_withdraws_from_statistics();case.speech.close();case.host.close();case.chats.close();case.core.close();case.temp._finalizer.detach();root=case.root
m=LocalModels(root,worker_factory=FakeWorker);m.speech.factory=FakeSpeech
item=copy.deepcopy(next(x for x in builtin() if x['runtime']=='onnx-sensevoice-v1'));item['id']='fixture-speech';folder=m.folder(item['id']);folder.mkdir()
for f in item['files']:
 data=f['name'].encode();f.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());(folder/f['name']).write_bytes(data)
for command in ({'action':'register','manifest':item},{'action':'activate','id':item['id']}):
 m.command({**command,'revision':m.snapshot()['revision']});assert m.future.result(timeout=5)['status']=='succeeded'
m.close()
bridge=json.loads(Path('docs/evidence/shared-speech-20261116/recovery-build.json').read_text())['source'];assert require_compatible(root,bridge)['compatible']
# subprocess imports only the frozen bridge, not the development implementation.
script='''import sys,json,sqlite3;from pathlib import Path
sys.path.insert(0,sys.argv[1]);root=Path(sys.argv[2])
from host.local_models import LocalModels
from host.speech_sources import check_turn
from host.english_learning import checkpoint
from modules.english_learning.store import Store
from modules.speech.store import Store as SpeechStore
from sdk.protocol import CoreError
with SpeechStore(root) as s:assert s.get('speech-one')['state']=='WITHDRAWN'
s=Store(root);assert s.db.execute('PRAGMA user_version').fetchone()[0]==4;assert s.db.execute('SELECT count(*) FROM assessments').fetchone()[0]==1;s.close()
m=LocalModels(root);assert m.speech.state()['selected']=='fixture-speech';assert m.worker is None
m.command({'action':'start','id':'fixture-speech','revision':m.snapshot()['revision']});assert m.future.result(timeout=5)['error']=='speech_readonly';m.close()
for fn,args in ((check_turn,(root,'voice-speech-one',{})),(checkpoint,(root,'english-asr'))):
 try:fn(*args);raise AssertionError('pending business replay permitted')
 except CoreError as e:assert e.code.endswith('_readonly')
check_turn(root,'ordinary-chat',{});checkpoint(root,'ordinary-chat')
print(json.dumps({'passed':True,'speech_schema':1,'learning_schema':4,'model_schema':3,'withdrawal_preserved':True,'pending_paid_replay_blocked':True,'normal_chat_guard_passes':True}))
'''
result=subprocess.run([sys.executable,'-I','-B','-c',script,bridge,str(root)],capture_output=True,text=True,encoding='utf-8');assert result.returncode==0,result.stderr
record=json.loads(result.stdout);record.update(fixture=str(root),bridge=bridge)
Path('docs/evidence/shared-speech-20261116/recovery-fixture.json').write_text(json.dumps(record,indent=2)+'\n');print(result.stdout)
