"""One bounded local model lane per Host, independent of cloud chat and tasks."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from control.paths import child, data_root
from control.network import NetworkGate
from control.recovery.gate import StopGate, RunLock
from sdk.protocol import CoreError, PROJECT, canonical, digest
from modules.local_models.catalog import builtin, validate, space
from modules.local_models.runtime import status as runtime_status
from modules.local_models.assessments import identity, context, profiles, assess, merge_sample
from modules.local_models.benchmark import run as run_benchmark
from sdk.protocol import read_json
from adapters.desktop.resources import sample as resources
from adapters.models.local_download import fetch, valid

MANAGERS={}
TIMEOUT_RESTART=3  # consecutive local timeouts before the worker is treated as hung


class Worker:
    def __init__(self, folder):
        env={k:v for k,v in os.environ.items() if k in ('SystemRoot','WINDIR','PATH','TEMP','TMP')}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
        self.process=subprocess.Popen([sys.executable,'-I','-B',str(PROJECT/'adapters/models/local_embedding_worker.py'),str(folder)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.queue=queue.Queue(maxsize=8)
        self.sequence=0
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                if len(line)>512000:break
                value=json.loads(line)
                while True:
                    try:self.queue.put_nowait(value);break
                    except queue.Full:
                        # Unclaimed replies of timed-out requests must not stop the reader.
                        try:self.queue.get_nowait()
                        except queue.Empty:pass
        except Exception:pass
        finally:
            try:self.queue.put({'error':'worker_exited'},timeout=1)
            except queue.Full:pass

    def wait(self, check, timeout=45, expect=None):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            check()
            try:
                value=self.queue.get(timeout=.1)
                if value.get('error')=='worker_exited':raise CoreError('local_inference','worker_exited')
                # A late answer to an earlier, timed-out request is discarded, never mis-assigned.
                if expect is not None and value.get('id')!=expect:continue
                if value.get('error'):raise CoreError('local_inference',value['error'])
                return value
            except queue.Empty:pass
        raise CoreError('local_timeout','Local worker timed out')

    def request(self,texts,role,check):
        self.sequence+=1;ident=self.sequence
        self.process.stdin.write(canonical({'id':ident,'texts':texts,'role':role})+'\n');self.process.stdin.flush()
        return self.wait(check,expect=ident)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        self.reader.join(timeout=2)
        for stream in (self.process.stdin,self.process.stdout):stream.close()


class LocalModels:
    api_version='jarvis.local-models.v1'

    def __init__(self, root, *, worker_factory=Worker):
        self.root=data_root(root);self.base=child(self.root,'local-models');self.base.mkdir(exist_ok=True)
        self.path=child(self.root,'config/local-models.sqlite3')
        self.lease=RunLock(self.root,'local-models');self.lease.__enter__()
        self.lock=threading.RLock();self.cancel=threading.Event();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='local-models')
        self.future=None;self.worker=None;self.loaded=None;self.telemetry=None;self.worker_factory=worker_factory;self.closed=False
        self.recall_future=None
        # Passage vectors of short facts, keyed by (model, text). Ranking 64 facts on every
        # turn otherwise re-encodes all of them inside a 2 s foreground budget.
        from collections import OrderedDict
        self.passage_cache=OrderedDict();self.passage_cache_limit=4096
        self.timeouts=0  # consecutive local timeouts; a hung worker is restarted after TIMEOUT_RESTART
        try:
            self.measurement_context=context(runtime_status());self.profiles=profiles()
            self.descriptor=read_json(PROJECT/'modules/local_models/descriptor.json')
            with self.db() as db:
                if db.execute('PRAGMA user_version').fetchone()[0] not in (0,1,2):raise CoreError('model_state_version','A newer model state requires its compatible manager')
                db.execute('CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY, manifest TEXT NOT NULL, state TEXT NOT NULL, error TEXT, checked REAL)')
                db.execute('CREATE TABLE IF NOT EXISTS manager(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER,selected TEXT,previous TEXT,job TEXT)')
                db.execute('INSERT OR IGNORE INTO manager VALUES(1,0,NULL,NULL,NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,created REAL,action TEXT,model TEXT,result TEXT)')
                db.execute('CREATE TABLE IF NOT EXISTS observations(model TEXT, fingerprint TEXT, context TEXT, data TEXT NOT NULL, PRIMARY KEY(model,fingerprint,context))')
                for item in builtin():db.execute("INSERT OR IGNORE INTO models VALUES(?,?,'catalog',NULL,NULL)",(item['id'],canonical(item)))
                db.execute("UPDATE models SET state='interrupted',error='host_restarted' WHERE state IN ('downloading','checking','starting','repairing')")
                old=db.execute('SELECT job FROM manager WHERE id=1').fetchone()[0]
                if old and json.loads(old).get('status')=='running':db.execute('UPDATE manager SET job=? WHERE id=1',(canonical({'status':'interrupted','error':'host_restarted'}),))
                db.execute('PRAGMA user_version=2')
        except BaseException:
            self.pool.shutdown(wait=False);self.lease.__exit__(None,None,None)
            raise
        MANAGERS[str(self.root)]=self
        self.guard_stop=threading.Event()
        self.guard=threading.Thread(target=self._guard,daemon=True,name='local-model-guard');self.guard.start()

    def _guard(self):
        while not self.guard_stop.wait(1):
            if StopGate(self.root).state()!='ready':
                self.cancel.set()
                with self.lock:self._stop()

    def db(self):
        # sqlite context commits but does not close; keep an explicit closing wrapper.
        from contextlib import contextmanager
        @contextmanager
        def connection():
            db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
            try:
                with db:yield db
            finally:db.close()
        return connection()

    def item(self,ident):
        with self.db() as db:row=db.execute('SELECT manifest FROM models WHERE id=?',(ident,)).fetchone()
        if not row:raise CoreError('model_missing','Unknown model')
        return validate(json.loads(row[0]))

    def folder(self,ident):return child(self.base,ident)

    def _state(self,ident,state,error=None):
        with self.db() as db:db.execute('UPDATE models SET state=?,error=?,checked=? WHERE id=?',(state,error,time.time(),ident))

    def _check(self, network=False):
        if self.cancel.is_set() or self.closed:raise CoreError('model_cancelled','Operation cancelled')
        StopGate(self.root).require_running()
        if network:NetworkGate(self.root).require_online()

    def _observe(self,item,result=None,*,verified=False,benchmark=None):
        """Persist only measured metadata, scoped by immutable model and execution context."""
        fingerprint=identity(item)
        with self.db() as db:
            if verified:
                size=sum(child(self.folder(item['id']),f['name']).stat().st_size for f in item['files'])
                db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?)',
                    (item['id'],fingerprint,'artifact',canonical({'verified_disk_bytes':size,'updated_at':time.time()})))
            if result is not None or benchmark is not None:
                key=self.measurement_context['id']
                row=db.execute('SELECT data FROM observations WHERE model=? AND fingerprint=? AND context=?',(item['id'],fingerprint,key)).fetchone()
                value=json.loads(row[0]) if row else {}
                if result is not None:value=merge_sample(value,result.get('memory'),result.get('workload'))
                if benchmark is not None:value['benchmark']=benchmark
                if value:
                    value['context']=self.measurement_context
                    db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?)',(item['id'],fingerprint,key,canonical(value)))

    def snapshot(self):
        with self.lock:
            if self.worker and self.worker.process.poll() is not None:
                ident=self.loaded;self._stop();self._state(ident,'failed','worker_exited')
            if self.worker and StopGate(self.root).state()!='ready':self._stop()
            with self.db() as db:
                meta=dict(db.execute('SELECT * FROM manager WHERE id=1').fetchone())
                rows=[dict(x) for x in db.execute('SELECT * FROM models ORDER BY id')]
                events=[dict(x) for x in db.execute('SELECT * FROM events ORDER BY seq DESC LIMIT 20')]
                observations={}
                for record in db.execute('SELECT * FROM observations'):
                    observations.setdefault((record['model'],record['fingerprint']),{})[record['context']]=json.loads(record['data'])
            runtime=runtime_status()
            for row in rows:
                item=json.loads(row.pop('manifest'));folder=self.folder(item['id']);size=0;partial=0
                for f in item['files']:
                    p=child(folder,f['name'])
                    if p.is_file():size+=p.stat().st_size
                    p=child(folder,f['name']+'.part')
                    if p.is_file():partial+=p.stat().st_size
                row.update(item,disk_bytes=size,partial_bytes=partial,download_bytes=sum(f['bytes'] for f in item['files']),
                    loaded=item['id']==self.loaded,selected=item['id']==meta['selected'],vector_space=space(item) if item['kind']=='embedding' else None,
                    adapter_ready=runtime['ready'] and item['runtime']=='onnx-e5-v1',memory=self.telemetry if item['id']==self.loaded else {'rss_bytes':0,'gpu_bytes':0})
                row['assessment']=assess(item,observations.get((item['id'],identity(item)),{}),self.measurement_context,self.profiles)
            return {'schema':self.api_version,'revision':meta['revision'],'observed_at':time.time(),'selected':meta['selected'],'previous':meta['previous'],
                'job':json.loads(meta['job']) if meta['job'] else None,'models':rows,'events':events,
                'runtime':runtime,'manager':{**self.descriptor,
                'supported_runtime':['onnx-e5-v1'],'replaceable':True,'replacement_state':'requires_candidate_tests_and_host_restart',
                'startup':'no_models_autoloaded','weights_location':'user-data/local-models','gpu_backend':'CPU only'}}

    def command(self,body):
        actions={'download','repair','verify','start','standby','uninstall','activate','rollback','unselect','embed','benchmark','register','cancel','retire_previous'}
        if not isinstance(body,dict) or body.get('action') not in actions:raise CoreError('model_command','Invalid operation')
        action=body['action'];expected={'action','revision'}
        if action in {'download','repair','verify','start','standby','uninstall','activate','benchmark'}:expected.add('id')
        if action=='register':expected.add('manifest')
        if action=='embed':expected.update({'texts','role'})
        if set(body)!=expected or type(body['revision']) is not int:raise CoreError('model_command','Unexpected operation fields')
        with self.lock:
            if self.closed:raise CoreError('model_closed','Manager closed')
            if action=='cancel':self.cancel.set();return {'status':'cancelling'}
            if (self.future and not self.future.done()) or (self.recall_future and not self.recall_future.done()):raise CoreError('model_busy','Local model operation in progress')
            StopGate(self.root).require_running()
            if action=='register':validate(body['manifest'])
            if 'id' in body:
                if not isinstance(body['id'],str):raise CoreError('model_command','Invalid model ID')
                self.item(body['id'])
            if action=='embed' and (body['role'] not in ('query','passage') or not isinstance(body['texts'],list) or not 1<=len(body['texts'])<=8 or any(not isinstance(x,str) or not x.strip() or len(x)>8000 for x in body['texts'])):
                raise CoreError('model_input','Expected one to eight bounded texts')
            with self.db() as db:
                if db.execute('UPDATE manager SET revision=revision+1 WHERE id=1 AND revision=?',(body['revision'],)).rowcount!=1:raise CoreError('conflict','Model state changed')
            self.cancel.clear();job={'id':uuid.uuid4().hex,'action':action,'model':body.get('id'),'status':'running','started':time.time(),'downloaded_bytes':0}
            self._job(job);self.future=self.pool.submit(self._run,body,job)
            return job

    def _job(self,value):
        with self.db() as db:db.execute('UPDATE manager SET job=? WHERE id=1',(canonical(value),))

    def _verify(self,item):
        return bool(item['files']) and all(valid(child(self.folder(item['id']),f['name']),f,self._check) for f in item['files'])

    def _timed_out(self):
        self.timeouts+=1
        if self.timeouts>=TIMEOUT_RESTART:
            self.timeouts=0;return True
        return False

    def _stop(self):
        if self.worker:self.worker.close()
        self.worker=None;self.loaded=None;self.telemetry=None

    def _start(self,item):
        if item['runtime']!='onnx-e5-v1':raise CoreError('model_adapter_missing','Runtime adapter not installed')
        if not runtime_status()['ready']:raise CoreError('model_runtime_missing','Pinned optional dependencies are missing or changed')
        if not self._verify(item):raise CoreError('model_integrity','Repair artifacts before starting')
        self._observe(item,verified=True)
        if self.loaded==item['id']:return
        memory=resources()
        available=(memory['memory_total']-memory['memory_used']) if memory['memory_total'] is not None else None
        # A conservative admission floor, not a guaranteed bound on ORT allocation.
        required=max(768*1024**2,sum(f['bytes'] for f in item['files'])*3)
        if available is not None and available<required:raise CoreError('model_memory','Insufficient free RAM for candidate and foreground reserve')
        # Current worker remains usable until candidate health and dimensions are verified.
        candidate=self.worker_factory(self.folder(item['id']))
        try:
            hello=candidate.wait(self._check)
            if not hello.get('ready') or hello.get('dimension')!=item['dimension']:raise CoreError('model_dimension','Worker contract mismatch')
            probe=candidate.request(['你好 hello'],'query',self._check)
            self._validate_vectors(item,probe,1)
            self._observe(item,probe)
            with self.lock:
                self._check();self._stop();self.worker=candidate;self.loaded=item['id'];self.telemetry=probe.get('memory')
        except BaseException:candidate.close();raise

    @staticmethod
    def _validate_vectors(item,result,count):
        import math
        vectors=result.get('vectors')
        if (result.get('dimension')!=item['dimension'] or not isinstance(vectors,list) or len(vectors)!=count
            or any(not isinstance(v,list) or len(v)!=item['dimension'] or any(type(x) not in (float,int) or not math.isfinite(x) for x in v) or not .98<=sum(x*x for x in v)<=1.02 for v in vectors)):
            raise CoreError('model_dimension','Invalid embedding result')

    def _run(self,body,job):
        action=body['action'];ident=body.get('id');result={}
        try:
            self._check()
            if action=='register':
                item=validate(body['manifest']);ident=item['id']
                with self.db() as db:
                    row=db.execute('SELECT manifest FROM models WHERE id=?',(ident,)).fetchone()
                    if row and row[0]!=canonical(item):raise CoreError('model_immutable','Use a new ID for another model revision')
                    db.execute("INSERT OR IGNORE INTO models VALUES(?,?,'catalog',NULL,NULL)",(ident,canonical(item)))
            elif action in ('download','repair'):
                item=self.item(ident)
                if not item['files']:raise CoreError('model_recipe_missing','A pinned artifact recipe is required')
                if self.loaded==ident:raise CoreError('model_in_use','Standby before repairing a loaded model')
                self._check(True);self._state(ident,'downloading')
                remaining=sum(f['bytes'] for f in item['files']);folder=self.folder(ident);folder.mkdir(exist_ok=True)
                if shutil.disk_usage(folder).free<remaining+64*1024**2:raise CoreError('model_disk','Insufficient temporary disk capacity')
                completed=0
                for f in item['files']:
                    path=child(folder,f['name'])
                    if not valid(path,f,self._check):
                        def progress(n):job['downloaded_bytes']=completed+n;self._job(job)
                        fetch(item['source']+'/resolve/'+item['revision']+'/'+f['path'],path,f,lambda:self._check(True),progress)
                    completed+=f['bytes']
                self._observe(item,verified=True)
                self._state(ident,'ready');result={'verified_bytes':completed}
            elif action=='verify':
                self._state(ident,'checking')
                ok=self._verify(self.item(ident));self._state(ident,'ready' if ok else 'damaged')
                if not ok:raise CoreError('model_integrity','Missing or damaged assets')
                self._observe(self.item(ident),verified=True)
            elif action in ('start','activate','rollback'):
                if action=='rollback':
                    with self.db() as db:ident=db.execute('SELECT previous FROM manager WHERE id=1').fetchone()[0]
                    if not ident:raise CoreError('model_previous_missing','No previous model')
                self._start(self.item(ident));self._state(ident,'ready')
                if action!='start':
                    self._check()
                    with self.db() as db:db.execute('UPDATE manager SET previous=selected,selected=? WHERE id=1 AND (selected IS NULL OR selected!=?)',(ident,ident))
                result={'loaded':ident,'space':space(self.item(ident)),'index_migration':'new_space_required'}
            elif action=='standby':
                with self.lock:
                    if self.loaded==ident:self._stop()
                result={'loaded':False,'files_preserved':True}
            elif action=='unselect':
                with self.lock:self._stop()
                with self.db() as db:db.execute('UPDATE manager SET previous=selected,selected=NULL WHERE id=1')
            elif action=='retire_previous':
                with self.db() as db:db.execute('UPDATE manager SET previous=NULL WHERE id=1')
            elif action=='uninstall':
                with self.db() as db:meta=db.execute('SELECT selected,previous FROM manager WHERE id=1').fetchone()
                if self.loaded==ident or ident in tuple(meta):raise CoreError('model_in_use','Selected, loaded or recovery model is retained')
                item=self.item(ident);folder=self.folder(ident)
                for f in item['files']:
                    path=child(folder,f['name']);part=child(folder,f['name']+'.part');self._check();path.unlink(missing_ok=True);part.unlink(missing_ok=True)
                if folder.is_dir() and not any(folder.iterdir()):folder.rmdir()
                self._state(ident,'catalog')
            elif action=='embed':
                if not self.worker:raise CoreError('model_not_loaded','Start an embedding model first')
                item=self.item(self.loaded)
                try:result=self.worker.request(body['texts'],body['role'],self._check);self._validate_vectors(item,result,len(body['texts']))
                except BaseException:
                    with self.lock:self._stop()
                    raise
                self.telemetry=result.get('memory');result.update(vector_space=space(item),model=item['id'])
                self._observe(item,result)
            elif action=='benchmark':
                item=self.item(ident)
                # A benchmark must not evict another active model or change defaults.
                if self.loaded and self.loaded!=ident:raise CoreError('model_in_use','Standby the other model before benchmarking')
                was_loaded=self.loaded==ident
                try:
                    self._start(item)
                    self._state(ident,'ready')
                    def request(texts,role):
                        value=self.worker.request(texts,role,self._check)
                        self._validate_vectors(item,value,len(texts));self.telemetry=value.get('memory');self._observe(item,value)
                        return value
                    result=run_benchmark(request,self._check)
                    self._observe(item,benchmark=result)
                except BaseException:
                    with self.lock:self._stop()
                    raise
                finally:
                    if not was_loaded:
                        with self.lock:self._stop()
            job.update(status='succeeded',result=result)
        except Exception as exc:
            code=exc.code if isinstance(exc,CoreError) else type(exc).__name__
            if ident and action in ('download','repair','verify'):self._state(ident,'interrupted' if code=='model_cancelled' else 'failed',code)
            job.update(status='cancelled' if code=='model_cancelled' else 'failed',error=code)
        finally:
            # Persist metadata only; embeddings and input text stay in transient job result.
            job['finished']=time.time();saved={k:v for k,v in job.items() if k!='result'}
            if 'result' in job:saved['result']={k:v for k,v in job['result'].items() if k!='vectors'}
            self._job(saved)
            with self.db() as db:db.execute('INSERT INTO events(created,action,model,result) VALUES(?,?,?,?)',(time.time(),action,ident,job['status']+':'+job.get('error','')))
        return job

    def result(self):
        with self.lock:
            if self.future and self.future.done():return self.future.result()
        return None

    def rank_memory(self, rows, query, wait_seconds=.35):
        """Use the selected, already-running encoder. Never start/download or queue chat behind it."""
        if not self.lock.acquire(blocking=False):return {'status':'busy'}
        try:
            if self.closed or not self.worker:return {'status':'not_loaded'}
            if (self.future and not self.future.done()) or (self.recall_future and not self.recall_future.done()):return {'status':'busy'}
            with self.db() as db:selected=db.execute('SELECT selected FROM manager WHERE id=1').fetchone()[0]
            if selected!=self.loaded:return {'status':'not_selected'}
            if len(query)>160:return {'status':'long_query'}
            # Long facts retain full keyword recall; do not silently embed only a prefix.
            candidates=[r for r in rows if len(r['key']+' '+r['value'])<=160][:64]
            if not candidates:return {'status':'no_short_candidates'}
            self.recall_future=self.pool.submit(self._rank_memory,candidates,query)
            future=self.recall_future
        except (CoreError,OSError,sqlite3.Error,RuntimeError):return {'status':'unavailable'}
        finally:self.lock.release()
        try:return future.result(timeout=wait_seconds)
        except TimeoutError:return {'status':'timeout'}

    def knowledge_encoder(self):
        with self.lock:
            if not self.worker or self.closed:raise CoreError('model_not_loaded','Start the selected local embedding model first')
            with self.db() as db:selected=db.execute('SELECT selected FROM manager WHERE id=1').fetchone()[0]
            if selected!=self.loaded:raise CoreError('model_not_selected','Activate the local embedding model first')
            item=self.item(self.loaded)
            return {'model':item['id'],'space':space(item),'dimension':item['dimension']}

    def encode_knowledge(self,texts,role,expected_space,checkpoint=lambda:None,wait_seconds=3):
        if not self.lock.acquire(blocking=False):raise CoreError('model_busy','Local worker busy')
        try:
            info=self.knowledge_encoder()
            if info['space']!=expected_space:raise CoreError('model_space_changed','Embedding selection changed')
            if (self.future and not self.future.done()) or (self.recall_future and not self.recall_future.done()):
                raise CoreError('model_busy','Local worker busy')
            limit=160 if role=='query' else 512
            if role not in {'query','passage'} or not 1<=len(texts)<=4 or any(not isinstance(t,str) or not t.strip() or len(t)>limit for t in texts):
                raise CoreError('model_input','Expected up to four short texts')
            self.recall_future=self.pool.submit(self._encode_knowledge,texts,role,checkpoint)
            future=self.recall_future
        finally:self.lock.release()
        try:return future.result(timeout=wait_seconds)
        except TimeoutError:raise CoreError('local_timeout','Foreground encoding budget exceeded') from None

    def _encode_knowledge(self,texts,role,checkpoint):
        deadline=time.monotonic()+2
        try:
            item=self.item(self.loaded)
            def check():
                self._check();checkpoint()
                if time.monotonic()>deadline:raise CoreError('local_timeout','Embedding deadline')
            check();value=self.worker.request(texts,role,check)
            self._validate_vectors(item,value,len(texts));self.telemetry=value.get('memory')
            self.timeouts=0
            return value['vectors']
        except CoreError as exc:
            # A slow answer is discarded by request ID; keep the model loaded for the next turn
            # unless the worker keeps timing out (then it is probably hung).
            if exc.code!='local_timeout' or self._timed_out():
                with self.lock:self._stop()
            raise
        except BaseException:
            with self.lock:self._stop()
            raise

    def _rank_memory(self, rows, query):
        deadline=time.monotonic()+2
        try:
            item=self.item(self.loaded);worker=self.worker
            def check():
                self._check()
                if time.monotonic()>deadline:raise CoreError('local_timeout','Memory encoding deadline')
            def encode(texts,role):
                value=worker.request(texts,role,check);self._validate_vectors(item,value,len(texts))
                self.telemetry=value.get('memory');return value['vectors']
            q=encode([query],'query')[0]
            texts=[r['key']+' '+r['value'] for r in rows]
            # Collect this call's vectors locally: inserting new entries may evict older hits.
            local={}
            for text in dict.fromkeys(texts):
                key=(item['id'],text)
                if key in self.passage_cache:
                    self.passage_cache.move_to_end(key);local[text]=self.passage_cache[key]
            missing=[t for t in dict.fromkeys(texts) if t not in local]
            for start in range(0,len(missing),4):
                batch=missing[start:start+4]
                for text,vector in zip(batch,encode(batch,'passage')):
                    local[text]=vector;self.passage_cache[(item['id'],text)]=vector
                    while len(self.passage_cache)>self.passage_cache_limit:self.passage_cache.popitem(last=False)
            vectors=[local[text] for text in texts]
            self.timeouts=0
            return {'status':'ready','model':item['id'],'space':space(item),'count':len(rows),'encoded':len(missing),
                    'scores':{r['id']:sum(a*b for a,b in zip(q,v)) for r,v in zip(rows,vectors)}}
        except CoreError as exc:
            if exc.code=='local_timeout':
                # Late replies are discarded by request ID, so the model stays loaded
                # unless repeated timeouts suggest the worker is hung.
                if self._timed_out():
                    with self.lock:self._stop()
                return {'status':'timeout'}
            with self.lock:self._stop()
            return {'status':'worker_failed'}
        except Exception:
            with self.lock:self._stop()
            return {'status':'worker_failed'}

    def close(self):
        self.closed=True;self.cancel.set();self.pool.shutdown(wait=True)
        self.guard_stop.set();self.guard.join(timeout=3)
        with self.lock:self._stop()
        MANAGERS.pop(str(self.root),None)
        self.lease.__exit__(None,None,None)


def describe(root):
    manager=MANAGERS.get(str(data_root(root)))
    if not manager:return {'manager':'not_running','local_inference':'unavailable'}
    s=manager.snapshot()
    return {'manager':s['manager'],'selected':s['selected'],'models':[{'id':m['id'],'kind':m['kind'],'state':m['state'],'loaded':m['loaded'],'dimension':m['dimension'],'languages':m['languages'],'adapter_ready':m['adapter_ready'],
        'resource_forecast':m['assessment']['expected'],'calibrated':m['assessment']['calibrated'],'scores':m['assessment']['scores'],
        'score_scope':'Small synthetic retrieval regression and declared language coverage, not factual verification or universal accuracy'} for m in s['models']]}


class UnavailableModels:
    """A failed optional manager must not prevent the workbench from starting."""
    def __init__(self, code):self.code=code
    def snapshot(self):
        return {'schema':LocalModels.api_version,'revision':0,'selected':None,'previous':None,
                'job':None,'models':[],'events':[],'observed_at':time.time(),
                'runtime':{'ready':False},'manager':{'version':'1.1.0','status':'unavailable','error':self.code,
                'recovery':'Inspect local-model state and descriptors; preserve artifacts; restart Host after repair'}}
    def command(self,body):raise CoreError('model_manager_unavailable','Local model manager needs repair')
    def result(self):return None
    def close(self):pass


def create_manager(root):
    try:return LocalModels(root)
    except Exception as exc:return UnavailableModels(exc.code if isinstance(exc,CoreError) else type(exc).__name__)
