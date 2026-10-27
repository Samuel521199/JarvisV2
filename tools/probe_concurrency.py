"""Bounded, offline HTTP response/dispatch experiment on disposable fixture data.

Run from the project root with python -m tools.probe_concurrency. No provider
credentials are read and no external model/network calls are made.
"""
import argparse
from contextlib import ExitStack
import hashlib
from http.server import ThreadingHTTPServer
import json
import math
import os
import platform
from pathlib import Path
import statistics
import tempfile
import threading
import time
import urllib.request
import uuid
from unittest.mock import patch

from adapters.models.native import NativeModel
from apps.workbench.server import Handler
from host.core import Core
from host.dialogue import DialogueHost
from host.task_scheduler import TaskRunner
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from modules.registry_composer.registry import Registry
from sdk.protocol import canonical


def configure(root):
    core = Core.initialize(root)
    try:
        core.grants.add({'schema':'jarvis.grant.v1','grant_id':'probe-local','principal_id':'owner.local','scope_id':'personal',
                         'capabilities':['text.analyze.v1','artifact.write.v1'],'max_cost_units':100000,'expires_at':time.time()+7200})
    finally: core.close()
    prefs = Preferences(root)
    try:
        prefs.install({'schema_version':1,'default_provider':'openai','automatic_fallback':False,
                       'fallback_order':['openai'],'max_output_tokens':512,'max_prompt_bytes':50000,
                       'providers':{'openai':{'adapter':'openai','label':'Offline test fixture','model':'fixture',
                                              'models':{'fixture':{'parameters':{},'reasoning_levels':[]}}}}},
                      {'model':'fixture','reasoning':'medium','enabled':False,'revision':1})
    finally: prefs.close()


def plan(key):
    return {'schema':'jarvis.task.v1','request_id':key,'principal_id':'owner.local','scope_id':'personal',
            'grant_id':'probe-local','goal':'Offline concurrency verification '+key,
            'steps':[{'step_id':'analyze','capability':'text.analyze.v1','arguments':{'text':key}},
                     {'step_id':'deliver','capability':'artifact.write.v1','arguments':{'name':'report.json'},'input_from':'analyze'}],
            'limits':{'max_steps':2,'max_attempts':1,'max_seconds':3600,'max_cost_units':2}}


def distribution(values):
    values=sorted(values)
    def q(frac): return round(values[max(0,math.ceil(len(values)*frac)-1)],3) if values else None
    return {'count':len(values),'p50':q(.5),'p95':q(.95),'p99':q(.99),'max':q(1)}


class Fixture:
    def __init__(self, root, port=0):
        self.root=root;configure(root);self.load=threading.Event();self.stop=threading.Event()
        self.execution_lock=threading.Lock();self.active_steps=0;self.max_overlap=0;self.completed=0
        self.hold_background=threading.Event();self.stack=ExitStack()
        self.stack.enter_context(patch.object(NativeModel,'available',return_value=True))
        self.stack.enter_context(patch.object(NativeModel,'complete',self.complete))
        original=Registry.execute
        def work(reg,root,tid,aid,cap,args,impl,checkpoint=lambda:None):
            if cap=='text.analyze.v1' and args['text'].startswith('load-'):
                with self.execution_lock:
                    self.active_steps+=1;self.max_overlap=max(self.max_overlap,self.active_steps)
                try:
                    deadline=time.monotonic()+.35
                    while time.monotonic()<deadline:
                        checkpoint();hashlib.sha256(b'bounded background fixture'*2048).digest();time.sleep(.005)
                finally:
                    with self.execution_lock:self.active_steps-=1;self.completed+=1
            return original(reg,root,tid,aid,cap,args,impl,checkpoint)
        self.stack.enter_context(patch.object(Registry,'execute',work))
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler);self.server.data_root=root
        self.server.nonce='offline-probe-nonce';self.server.boot_id=uuid.uuid4().hex
        self.dialogues=DialogueHost(root);self.server.dialogues=self.dialogues
        self.runner=TaskRunner(root,foreground_pending=lambda:any(r["lane"]=="foreground" for r in self.dialogues.state()["queued"]));self.server.task_runner=self.runner
        self.http=threading.Thread(target=self.server.serve_forever,daemon=True);self.http.start()
        self.feeder=threading.Thread(target=self.feed,daemon=True);self.feeder.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        store=Dialogues(root)
        try:self.chat=store.create();self.background_chat=store.create()
        finally:store.close()

    def complete(self,messages,checkpoint,**kwargs):
        if messages[-1]['content'].startswith('background fixture'):
            while not self.hold_background.is_set():checkpoint();time.sleep(.01)
        else:
            end=time.monotonic()+(4 if messages[-1]['content'].startswith('UI slow') else .2)
            while time.monotonic()<end:checkpoint();time.sleep(.005)
        checkpoint()
        return {'status':'SUCCEEDED','text':'A substantive, fixed-size offline response. No model fees.','usage':{}}

    def call(self,path,value=None):
        headers={'Origin':self.base,'X-Jarvis-Nonce':self.server.nonce,'Content-Type':'application/json'}
        # Header spelling follows the actual Host nonce contract.
        headers['X-Jarvis-Token']=self.server.nonce
        request=urllib.request.Request(self.base+path,data=canonical(value).encode() if value is not None else None,headers=headers)
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)

    def command(self,ident,text='foreground fixture',chat=None):
        return {'chat_id':chat or self.chat,'request_id':ident,'text':text,'provider':'openai','model':'fixture',
                'reasoning':'default','skill':'none','memory_enabled':False}

    def response(self):
        key='front-'+uuid.uuid4().hex;start=time.monotonic()
        self.call('/api/chat/send',self.command(key));accepted=(time.monotonic()-start)*1000
        store=Dialogues(self.root)
        try:
            while time.monotonic()-start<10:
                row=store.turn(key)
                if row['status'] not in {'READY','RUNNING'}:
                    if row['status']!='SUCCEEDED':raise RuntimeError('Fixture reply failed: '+str(row['error']))
                    if row['reply'] != 'A substantive, fixed-size offline response. No model fees.': raise RuntimeError('Fixture response content changed')
                    return {'input_ms':accepted,'reply_ms':(time.monotonic()-start)*1000,'dispatch_ms':self.dialogues.state()['dispatch_delay_ms'][-1]}
                time.sleep(.005)
        finally:store.close()
        raise TimeoutError('No fixture reply within ten seconds')

    def feed(self):
        core=Core(self.root)
        try:
            while not self.stop.is_set():
                if self.load.is_set() and not self.runner.state()['active'] and not self.runner.state()['queued']:
                    for _ in range(2):core.tasks.submit(plan('load-'+uuid.uuid4().hex))
                    self.runner.start({'max_tasks':2})
                self.stop.wait(.025)
        finally:core.close()

    def set_load(self,on):
        if on:
            self.hold_background.clear()
            self.dialogues.submit_background(self.command('back-'+uuid.uuid4().hex,'background fixture',self.background_chat))
            self.load.set();end=time.monotonic()+5
            while self.active_steps<2 and time.monotonic()<end:time.sleep(.01)
            if self.active_steps<2:raise RuntimeError('Could not sustain two background tasks; inspect resource pressure')
        else:
            self.load.clear();self.hold_background.set();end=time.monotonic()+5
            while (self.runner.state()['active'] or self.runner.state()['queued'] or self.dialogues.state()['running']) and time.monotonic()<end:time.sleep(.01)

    def close(self):
        self.stop.set();self.load.clear();self.hold_background.set();self.feeder.join(5)
        self.server.shutdown();self.server.server_close();self.http.join(5)
        self.dialogues.close();self.runner.close()
        if hasattr(self.server,'family'):self.server.family.close()
        self.stack.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pairs',type=int,default=200);parser.add_argument('--seconds',type=int,default=1800)
    parser.add_argument('--output',type=Path,default=Path('docs/evidence/concurrency-1.0.0/performance.json'))
    parser.add_argument('--serve',action='store_true');parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args()
    if not 1<=args.pairs<=1000 or not 0<=args.seconds<=3600:parser.error('Bounded probe parameters required')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-concurrency-probe-') as temp:
        fixture=Fixture(Path(temp),args.port)
        print(json.dumps({'url':fixture.base,'fixture_only':True,'paid_calls':0}),flush=True)
        try:
            if args.serve:
                fixture.submit_for_ui = fixture.runner.start
                core=Core(fixture.root)
                try:
                    for name in ['ui-queued-example','ui-priority-example']:core.tasks.submit(plan(name))
                finally:core.close()
                while True:time.sleep(1)
            for _ in range(10):fixture.response()
            idle=[];loaded=[];raw=[];began=time.monotonic()
            for index in range(args.pairs):
                baseline=fixture.response();fixture.set_load(True);busy=fixture.response();fixture.set_load(False)
                idle.append(baseline);loaded.append(busy);raw.append({'pair':index+1,'idle':baseline,'loaded':busy})
                if (index+1)%25==0:print(json.dumps({'pairs':index+1,'of':args.pairs}),flush=True)
            before=fixture.completed;soak=[];peaks={'threads':0,'system_memory_used':0,'cpu_percent':0};fixture.set_load(True);start=time.monotonic();next_report=start+60
            while time.monotonic()-start<args.seconds:
                soak.append(fixture.response())
                metrics=fixture.runner.state()['resources']
                peaks['threads']=max(peaks['threads'],threading.active_count());peaks['system_memory_used']=max(peaks['system_memory_used'],metrics.get('memory_used') or 0);peaks['cpu_percent']=max(peaks['cpu_percent'],metrics.get('cpu_percent') or 0)
                if time.monotonic()>=next_report:
                    print(json.dumps({'soak_seconds':round(time.monotonic()-start),'replies':len(soak),'background_completed':fixture.completed-before}),flush=True);next_report+=60
                time.sleep(.1)
            elapsed=time.monotonic()-start;fixture.set_load(False)
            stats={name:{k:distribution([v[k] for v in rows]) for k in ('input_ms','reply_ms','dispatch_ms')} for name,rows in [('idle',idle),('loaded',loaded),('soak',soak)]}
            base=stats['idle']['reply_ms']['p95'];busy=stats['loaded']['reply_ms']['p95']
            checks={'two_background_executions_overlap':fixture.max_overlap>=2,
                    'loaded_input_p95_le_200ms':stats['loaded']['input_ms']['p95']<=200,
                    'loaded_input_p99_le_500ms':stats['loaded']['input_ms']['p99']<=500,
                    'reply_p95_increase_le_10_percent':busy<=base*1.1,
                    'reply_p95_increase_le_100ms':busy-base<=100,
                    'foreground_dispatch_p95_le_100ms':stats['loaded']['dispatch_ms']['p95']<=100,
                    'foreground_dispatch_p99_le_250ms':stats['loaded']['dispatch_ms']['p99']<=250,
                    'soak_30_minutes':elapsed>=1800,'background_progress':fixture.completed>before}
            result={'date':'2026-10-26','version':'bounded-concurrency-1.0.0','scope':'real Host HTTP/SQLite/dispatch with deterministic model and bounded synthetic CPU/I/O tools',
                    'environment':{'platform':platform.platform(),'python':platform.python_version(),'logical_cpus':os.cpu_count(),'system_memory_total':fixture.runner.state()['resources'].get('memory_total')},'peaks':peaks,
                    'paid_model_calls':0,'model_delay_seconds':.2,'pairs':args.pairs,'soak_seconds':elapsed,
                    'checks':checks,'statistics_ms':stats,'max_execution_overlap':fixture.max_overlap,
                    'background_completed':fixture.completed,'soak_background_completed':fixture.completed-before,
                    'elapsed_seconds':time.monotonic()-began,'raw_pairs':raw,'soak_samples':soak,
                    'not_verified':['real cloud limits and latency','GPU-heavy rendering','8 GiB device','thermal/battery limits','arbitrary external tools','full V-DLG-01..14']}
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
            print(json.dumps({'checks':checks,'statistics_ms':stats},ensure_ascii=False),flush=True)
        finally:fixture.close()


if __name__=='__main__':main()
