"""STT purpose selection and a separate CPU worker in the existing model manager."""
import base64,hashlib,time
from pathlib import Path
from control.recovery.gate import StopGate
from modules.local_models.assessments import context
from sdk.protocol import CoreError,PROJECT,digest


class SpeechModels:
    def __init__(self,manager,factory):
        self.manager=manager;self.factory=factory;self.worker=None;self.loaded=None;self.memory=None;self.busy=False
        with manager.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS purpose_models(kind TEXT PRIMARY KEY,selected TEXT,previous TEXT,revision INTEGER NOT NULL)')
            db.execute("INSERT OR IGNORE INTO purpose_models VALUES('stt',NULL,NULL,0)")
        from modules.local_models.runtime import status
        value=context(status(speech=True))
        value.update(backend='onnx-sensevoice-cpu',worker_sha256=hashlib.sha256((PROJECT/'adapters/models/local_speech_worker.py').read_bytes()+(PROJECT/'adapters/models/speech_features.py').read_bytes()).hexdigest())
        value['id']=digest({k:v for k,v in value.items() if k!='id'});self.context=value

    def state(self):
        with self.manager.db() as db:return dict(db.execute("SELECT * FROM purpose_models WHERE kind='stt'").fetchone())

    def stop(self):
        if self.worker:self.worker.close()
        self.worker=None;self.loaded=None;self.memory=None

    def _ensure(self,item):
        if item['kind']!='stt' or item['runtime']!='onnx-sensevoice-v1':raise CoreError('model_adapter_missing','Unsupported STT adapter')
        from modules.local_models.runtime import status
        if not status(speech=True)['ready']:raise CoreError('model_runtime_missing','Pinned STT dependencies are missing or changed')
        if not self.manager._verify(item):raise CoreError('model_integrity','Repair STT artifacts before starting')
        if self.loaded==item['id'] and self.worker and self.worker.process.poll() is None:return
        from adapters.desktop.resources import sample as resources
        memory=resources();available=(memory['memory_total']-memory['memory_used']) if memory['memory_total'] is not None else None
        if available is not None and available<max(1536*1024**2,sum(f['bytes'] for f in item['files'])*6):raise CoreError('model_memory','Insufficient free RAM for STT and foreground reserve')
        candidate=self.factory(self.manager.folder(item['id']))
        try:
            hello=candidate.wait(self.manager._check)
            if not hello.get('ready') or hello.get('kind')!='stt':raise CoreError('model_speech_contract','STT worker is not ready')
            self.manager._check()
            self.stop();self.worker=candidate;self.loaded=item['id'];self.memory=hello.get('memory')
            self.manager._observe(item,hello)
        except BaseException:candidate.close();raise

    def _enter(self):
        with self.manager.lock:
            if self.busy:raise CoreError('model_in_use','STT inference is in progress')
            self.busy=True

    def start(self,item):
        self._enter()
        try:self._ensure(item)
        finally:self.busy=False

    def select(self,item):
        from host.speech import writer
        writer(self.manager.root)
        self._enter()
        try:
            self._ensure(item);self.manager._check();StopGate(self.manager.root).require_running()
            with self.manager.db() as db:
                db.execute('PRAGMA user_version=3')
                db.execute("UPDATE purpose_models SET previous=selected,selected=?,revision=revision+1 WHERE kind='stt' AND (selected IS NULL OR selected!=?)",(item['id'],item['id']))
        finally:self.busy=False

    def pinned(self):
        value=self.state()
        if not value['selected']:raise CoreError('speech_model_missing','Choose an offline STT default in model management')
        item=self.manager.item(value['selected'])
        return {'id':item['id'],'revision':value['revision'],'fingerprint':digest(item),'kind':'stt','source_revision':item['revision']}

    def transcribe(self,raw,language,checkpoint,expected):
        with self.manager.lock:
            if self.busy:raise CoreError('speech_busy','An STT request is already running')
            if self.pinned()!=expected:raise CoreError('speech_stale','STT selection changed')
            item=self.manager.item(expected['id']);self.busy=True
        try:
            self._ensure(item)
            checkpoint();StopGate(self.manager.root).require_running()
            self.worker.sequence+=1;ident=self.worker.sequence
            from sdk.protocol import canonical
            self.worker.process.stdin.write(canonical({'id':ident,'audio':base64.b64encode(raw).decode(),'language':language})+'\n');self.worker.process.stdin.flush()
            result=self.worker.wait(checkpoint,expect=ident)
            checkpoint()
            if self.pinned()!=expected:raise CoreError('speech_stale','STT selection changed during inference')
            if result.get('audio_sha256')!=hashlib.sha256(raw).hexdigest() or not isinstance(result.get('text'),str) or len(result['text'])>3000 or result.get('network') is not False:raise CoreError('speech_contract','Unbound STT result')
            self.memory=result.get('memory');self.manager._observe(item,result)
            return {**result,'model':expected,'provider':'local-onnx-cpu'}
        except BaseException:
            self.stop();raise
        finally:self.busy=False
