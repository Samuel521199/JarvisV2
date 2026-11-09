"""At most twelve approved Google calls; record proposals, never apply them.

The existing frozen proxy holds credentials. Its startup is temporary if absent;
no workbench is started, production restarted, proxy adopted, or permission changed.
"""
from datetime import datetime
import hashlib,json
from pathlib import Path
import subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(HERE)]
from adapters.development_bridge import exchange
from control.development_profile import read
from control.network import NetworkGate
from control.recovery.gate import StopGate
from host.development_runtime import selected_proxy
from host import assistant
from modules.preferences.store import resolve
from sdk.protocol import CoreError,canonical
from evaluate import fixture,score,summary


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';profile=read(dev);production=Path(profile['production_data'])
    package,build=selected_proxy(production,False)
    data=json.loads((HERE/'cases.json').read_text(encoding='utf-8'));plan=json.loads((HERE/'plan.json').read_text())
    assert hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest()==plan['cases_sha256']
    reference=datetime.fromisoformat(data['reference_utc'].replace('Z','+00:00')).timestamp()
    result={'scope':'real model proposals through approved Google proxy; synthetic input only; no proposal execution',
            'calls_started':0,'rows':[],'outcomes':[],'proxy_build':build,'proxy_started_by_test':False,'status':'running'}
    def save(): (HERE/'live-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save();child=None;logs=[]
    try:
        StopGate(dev).require_running()
        if NetworkGate(dev).read()['blocked']:raise CoreError('network_disabled','Model network is paused')
        try:status=exchange(dev,'/status')
        except CoreError as error:
            if error.code!='development_bridge_unavailable':raise
            logs=[(work/'proxy.out').open('wb'),(work/'proxy.err').open('wb')]
            child=subprocess.Popen([sys.executable,'-I','-B',str(package/'apps/development/bridge.py'),
                '--production-data',str(production),'--port',profile['bridge_origin'].rsplit(':',1)[1]],
                cwd=package,stdin=subprocess.DEVNULL,stdout=logs[0],stderr=logs[1],creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+25
            while True:
                if child.poll() is not None:raise RuntimeError('Approved proxy exited; see retained local log')
                try:status=exchange(dev,'/status');break
                except CoreError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.2)
            result['proxy_started_by_test']=True
        assert status['build_id']==build,'Unexpected live proxy identity'
        remaining=max(0,status['daily_call_limit']-status['calls_in_24h'])
        catalog=exchange(dev,'/catalog')['catalog']
        provider=catalog['default_provider'];route=resolve(catalog,provider)
        assert provider in profile['allowed_providers'] and route['adapter'] in ('vertex','gemini')
        result.update(provider=provider,model=route['model'],adapter=route['adapter'],quota_remaining_before=remaining)
        print(json.dumps({'proxy_ready':True,'model':route['model'],'allowed_calls':min(12,remaining)}),flush=True)
        selected=[c for c in data['cases'] if c['id'] in data['live_ids']][:min(12,remaining)]
        for case in selected:
            root=work/case['id'];root.mkdir();chat,target=fixture(root,case,reference)
            instruction,items=assistant.instructions(root,chat,provider,False)
            messages=[{'role':'user','content':case['text']+'\n\n本次合成消息参考UTC时间：'+data['reference_utc']+'\n'+instruction}]
            request={'request_id':uuid.uuid4().hex,'provider':provider,'model':route['model'],
                     'reasoning':route['parameters'],'json_mode':True,'messages':messages}
            result['calls_started']+=1;save();started=time.monotonic()
            # No retry of UNKNOWN, no alternate credential/model and no tool path.
            output=exchange(dev,'/model',request)
            outcome={'id':case['id'],'status':output.get('status'),'code':output.get('code'),
                'text':output.get('text'),'usage':output.get('usage',{}),'seconds':round(time.monotonic()-started,3),
                'request_id':request['request_id'],'prompt_sha256':hashlib.sha256(canonical(messages).encode()).hexdigest()}
            result['outcomes'].append(outcome)
            (work/(case['id']+'-prompt.json')).write_text(canonical(messages),encoding='utf-8')
            try:envelope=json.loads(output.get('text','')) if output.get('status')=='SUCCEEDED' else {}
            except (TypeError,ValueError):envelope={}
            row=score(root,chat,case,envelope,reference);row['model_status']=output.get('status');result['rows'].append(row)
            save();print(json.dumps({'id':case['id'],'status':outcome['status'],'host_mode':row['mode']}),flush=True)
        result.update(status='completed',summary=summary(result['rows'],selected),
            usage_note='Provider-reported usage only. Actual currency charge has not been reconciled.',
            source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['host/assistant.py','host/assistant_commitments.py','modules/task_resource/commitment_intent.py']})
    except BaseException as error:
        result.update(status='failed',error=getattr(error,'code',type(error).__name__));raise
    finally:
        if child is not None:
            try:
                exchange(dev,'/shutdown',{});child.wait(timeout=15);result['owned_proxy_stopped']=child.poll() is not None
            except Exception:
                # This handle was created by this test; never terminate a shared
                # pre-existing proxy or daily workbench.
                if child.poll() is None:child.terminate();child.wait(10)
                result['owned_proxy_stopped']=True;result['proxy_stop_fallback']=True
        for stream in logs:stream.close()
        save()
    print(json.dumps({'status':result['status'],'calls':result['calls_started'],'summary':result.get('summary')}))
