"""One bounded shared speech lane. It creates input receipts, never task permissions."""
import base64,json,re,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from control.application_runtime import require_accepting
from control.paths import child
from control.recovery.gate import RunLock,StopGate
from host import speech_sources
from host.speech_audio import read as read_audio,save as save_audio
from modules.speech.store import Store
from sdk.protocol import CoreError,digest


def writer(root):
    require_accepting(root)
    root=Path(root)
    if any(p.exists() for p in (root.parent/'JarvisLaunch.py',root/'deployment/launcher.json',root/'deployment/controller-protocol.json')):
        from control.controller_pin import read
        if read(root)['controller_protocol']<10:raise CoreError('controller_protocol','Shared speech needs a compatible controller before writing new data')


class Speech:
    def __init__(self,root,models,runner):
        writer(root);self.root=root;self.models=models;self.runner=runner;self.lock=threading.RLock();self.closing=threading.Event();self.futures={}
        self.lease=RunLock(root,'speech');self.lease.__enter__();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='shared-speech')
        try:
            with Store(root) as store:store.db.execute("UPDATE requests SET state='UNKNOWN',error='host_restarted' WHERE state IN ('QUEUED','RUNNING')")
        except BaseException:self.pool.shutdown(wait=False);self.lease.__exit__(None,None,None);raise

    def status(self):
        with self.lock,Store(self.root) as store:
            jobs=[]
            for r in store.db.execute('SELECT id FROM requests ORDER BY created DESC LIMIT 20'):
                row=store.get(r['id']);body=row['body'];result=row['result']
                try:
                    current=speech_sources.scope(self.root,body['scope']['purpose'],body['scope']['chat_id'],body['scope']['exercise_id'],pending=False)
                    if current!=body['scope'] and body['operation']=='transcribe':continue
                except (CoreError,OSError,ValueError):
                    jobs.append({'id':row['id'],'scope':body['scope'],'operation':body['operation'],'state':'WITHHELD','error':'speech_source_unavailable','result':None,'confirmed':bool(row['confirmation'])});continue
                jobs.append({'id':row['id'],'scope':body['scope'],'operation':body['operation'],'state':row['state'],'error':row['error'],'result':result,'confirmed':bool(row['confirmation'])})
            try:
                model=self.models.speech.pinned()
                from modules.local_models.runtime import status as runtime_status
                if not runtime_status(speech=True)['ready']:raise CoreError('model_runtime_missing','Pinned STT dependencies missing or changed')
                available=True;error=None
            except (CoreError,AttributeError) as exc:model=None;available=False;error=getattr(exc,'code','model_manager_unavailable')
            return {'schema':'jarvis.speech.v1','config':store.config(),'available':available,'model':model,'error':error,'jobs':jobs,'network':False,'scope':'Local STT/TTS; chat response generation follows its existing model route','automatic_transcription':True,'automatic_chat_submission':False}

    def _check(self,row):
        if self.closing.is_set():raise CoreError('speech_cancelled','Speech service is closing')
        StopGate(self.root).require_running();writer(self.root)
        with Store(self.root) as store:
            current=store.get(row['id']);cfg=store.config()
            if current['state'] not in ('QUEUED','RUNNING') or not cfg['enabled'] or cfg['revision']!=row['body']['policy_revision']:raise CoreError('speech_cancelled','Speech permission or request changed')
        body=row['body'];scope=body['scope']
        if body['operation'] in ('transcribe','warm'):
            if speech_sources.scope(self.root,scope['purpose'],scope['chat_id'],scope['exercise_id'])!=scope:raise CoreError('speech_stale','Speech source changed')
            if self.models.speech.pinned()!=body['model']:raise CoreError('speech_stale','STT selection changed')
        else:
            text,current=speech_sources.output_text(self.root,body['source'])
            if current!=scope or digest(text)!=body['text_digest']:raise CoreError('speech_stale','Spoken output source changed')

    def _run(self,ident):
        try:
            with Store(self.root) as store:
                if not store.db.execute("UPDATE requests SET state='RUNNING' WHERE id=? AND state='QUEUED'",(ident,)).rowcount:return
                row=store.get(ident)
            self._check(row);body=row['body'];check=lambda:self._check(row)
            if body['operation']=='warm':
                self.models.speech.start(self.models.item(body['model']['id']));result={'model':body['model'],'loaded':True,'network':False}
            elif body['operation']=='transcribe':
                raw,meta=read_audio(self.root,body['audio_id'])
                if meta['context']!=body['scope'] or meta['sha256']!=body['audio_sha256']:raise CoreError('speech_stale','Recording source changed')
                result=self.models.speech.transcribe(raw,body['language'],check,body['model'])
            else:
                from adapters.models.local_speech import synthesize
                text,_=speech_sources.output_text(self.root,body['source'])
                audio=synthesize(text,language='auto',checkpoint=check,work_dir=child(self.root,'temp'))
                saved=save_audio(self.root,'audio-'+digest('tts:'+ident)[:32],audio,body['scope'])
                result={'audio_id':saved['id'],'audio_sha256':saved['sha256'],'seconds':saved['seconds'],'provider':'windows_installed_voice','network':False,'text_digest':body['text_digest']}
            with self.lock:
                self._check(row)
                with Store(self.root) as store:store.finish(ident,result)
        except Exception as exc:
            with Store(self.root) as store:store.db.execute("UPDATE requests SET state='FAILED',error=? WHERE id=? AND state IN ('QUEUED','RUNNING')",(getattr(exc,'code',type(exc).__name__),ident))

    def command(self,value):
        schemas={'status':set(),'configure':{'enabled','revision'},'record':{'id','audio','purpose','chat_id','exercise_id'},'warm':{'id','purpose','chat_id','exercise_id'},'transcribe':{'id','audio_id','purpose','chat_id','exercise_id','language'},'cancel':{'id'},'withdraw':{'id'},'speak':{'id','purpose','chat_id','exercise_id','source_id'},'audio':{'id'},'submit':{'id','command'}}
        if not isinstance(value,dict) or value.get('action') not in schemas or set(value)!={'action',*schemas[value['action']]}:raise CoreError('speech_request','Unexpected shared speech fields')
        action=value['action']
        if action=='status':return self.status()
        StopGate(self.root).require_running();writer(self.root)
        if action=='submit':return self._submit(value)
        with self.lock,Store(self.root) as store:
            cfg=store.config()
            if action=='configure':
                if type(value['enabled']) is not bool or type(value['revision']) is not int or value['revision']!=cfg['revision']:raise CoreError('conflict','Speech settings changed')
                cfg={'enabled':value['enabled'],'revision':cfg['revision']+1};store.db.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(cfg),))
            elif action in ('cancel','withdraw'):
                row=store.get(value['id'])
                if action=='withdraw':store.db.execute("UPDATE requests SET state='WITHDRAWN' WHERE id=?",(row['id'],))
                else:store.db.execute("UPDATE requests SET state='CANCELLED' WHERE id=? AND state IN ('QUEUED','RUNNING')",(row['id'],))
            elif not cfg['enabled']:raise CoreError('speech_disabled','Shared speech is disabled')
            elif action=='record':
                context=speech_sources.scope(self.root,value['purpose'],value['chat_id'],value['exercise_id'])
                return {'recording':save_audio(self.root,value['id'],value['audio'],context)}
            elif action=='audio':
                row=store.get(value['id'])
                if row['state']!='SUCCEEDED' or row['body']['operation']!='speak':raise CoreError('speech_stale','Spoken output unavailable')
                text,current=speech_sources.output_text(self.root,row['body']['source'])
                if current!=row['body']['scope'] or digest(text)!=row['body']['text_digest']:raise CoreError('speech_stale','Spoken source changed')
                raw,meta=read_audio(self.root,row['result']['audio_id'])
                if meta['sha256']!=row['result']['audio_sha256']:raise CoreError('speech_stale','Spoken audio changed')
                return {'audio':base64.b64encode(raw).decode(),'recording':meta}
            elif action in ('transcribe','speak','warm'):
                ident=value['id']
                if not isinstance(ident,str) or not re.fullmatch(r'speech-[A-Za-z0-9_-]{1,80}',ident):raise CoreError('speech_request','Invalid speech request ID')
                if store.db.execute('SELECT 1 FROM requests WHERE id=?',(ident,)).fetchone():
                    row=store.get(ident)
                    if row['body']['api_digest']!=digest(value):raise CoreError('conflict','Speech request ID reused')
                else:
                    if store.db.execute("SELECT count(*) FROM requests WHERE state IN ('QUEUED','RUNNING')").fetchone()[0]>=8:raise CoreError('speech_busy','Speech queue is full')
                    if action=='warm':
                        scope=speech_sources.scope(self.root,value['purpose'],value['chat_id'],value['exercise_id']);extra={'model':self.models.speech.pinned()}
                    elif action=='transcribe':
                        if value['language'] not in ('auto','zh','en'):raise CoreError('speech_request','Invalid language hint')
                        scope=speech_sources.scope(self.root,value['purpose'],value['chat_id'],value['exercise_id']);raw,meta=read_audio(self.root,value['audio_id'])
                        if meta['context']!=scope:raise CoreError('speech_scope','Recording belongs to another context')
                        extra={'audio_id':meta['id'],'audio_sha256':meta['sha256'],'language':value['language'],'model':self.models.speech.pinned()}
                    else:
                        text,scope=speech_sources.output_text(self.root,value);extra={'source':value,'text_digest':digest(text)}
                    body={'operation':action,'api_digest':digest(value),'scope':scope,'policy_revision':cfg['revision'],**extra};store.add(ident,body)
                    self.futures={k:v for k,v in self.futures.items() if not v.done()};self.futures[ident]=self.pool.submit(self._run,ident)
        return self.status()

    def _submit(self,value):
        command=value['command']
        if not isinstance(command,dict):raise CoreError('speech_request','Expected the normal chat command')
        with self.lock:
            with Store(self.root) as store:
                if not store.config()['enabled']:raise CoreError('speech_disabled','Shared speech is disabled')
                row=store.get(value['id'])
            if row['body']['scope']['purpose']!='chat':raise CoreError('speech_scope','Learning input must use its learning entry')
            speech_sources.completed(self.root,row['id'],'chat',row['body']['scope']['chat_id'])
            ident='voice-'+row['id'];actual={**command,'request_id':ident,'chat_id':row['body']['scope']['chat_id']}
            if not isinstance(actual.get('text'),str) or not 1<=len(actual['text'].strip())<=3000:raise CoreError('speech_text','Confirm the recognized message before submitting')
            with Store(self.root) as store:store.confirm(row['id'],{'turn_id':ident,'command_digest':digest(actual),'confirmed_text':actual['text'],'raw_text':row['result']['text']})
        # No speech lock is held while entering the original dialogue queue.
        return {'submission':self.runner.submit(actual),'speech_id':row['id']}

    def close(self):
        self.closing.set();self.pool.shutdown(wait=True);self.lease.__exit__(None,None,None)


class Unavailable:
    def __init__(self,error):self.error=error
    def status(self):return {'schema':'jarvis.speech.v1','available':False,'error':self.error,'jobs':[],'config':{'enabled':False,'revision':0},'model':None}
    def command(self,value):
        if value=={'action':'status'}:return self.status()
        raise CoreError('speech_unavailable','Shared speech needs a compatible controller and model manager')
    def close(self):pass


def create(root,models,runner):
    try:return Speech(root,models,runner)
    except Exception as exc:return Unavailable(getattr(exc,'code',type(exc).__name__))
