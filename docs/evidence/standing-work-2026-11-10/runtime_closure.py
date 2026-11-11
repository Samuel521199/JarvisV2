"""Owned real Host/dispatcher restart; synthetic text goals, no cloud or mail."""
from pathlib import Path
import hashlib,http.cookiejar,json,shutil,socket,subprocess,sys,time,urllib.request,uuid
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from host.core import Core
from control.application_runtime import LocalApprovals,publish
from control.local_access import read_key
from adapters.application_host import WorkbenchProcess
from sdk.protocol import canonical
from test_development import specification,candidate
from test_preferences_dialogue import fixture
from test_standing_work import checks,config
from modules.dialogue.store import Dialogues


def host():
    import runpy
    sys.argv=[str(ROOT/'apps/workbench/server.py'),*sys.argv[2:]]
    runpy.run_path(str(ROOT/'apps/workbench/server.py'),run_name='__main__')


def run(work):
    work.mkdir(parents=True,exist_ok=False);root=work/'data';core=Core.initialize(root)
    core.preferences.install(fixture(),{});shutil.copytree(ROOT/'user-data/worker-runtime',root/'worker-runtime')
    spec=specification('standing-runtime');package=core.packages.stage(candidate('def run(text):\n    return text.upper()\n'),spec)
    assert core.packages.verify(package)['passed'];core.packages.activate(package,0);core.close()
    LocalApprovals(root).initialize();(root/'deployment').mkdir(exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    driver=WorkbenchProcess(root,port);selected={'build':'d'*64,'slot':'A','epoch':0};owned=[]
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    report={'passed':False,'scope':'actual Host/task dispatcher/LPAC text worker/restart; synthetic user data',
            'model_calls':0,'external_actions':0,'actual_desktop_clicks':False,'steps':[]}
    def save():(work/'result.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    def passed(name):report['steps'].append({'case':name,'passed':True});save();print(json.dumps({'passed':name}),flush=True)
    def request(path,body=None):
        headers={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None and path!='/api/local-access':
            with client.open(driver.origin+'/api/session',timeout=5) as r:headers['X-Jarvis-Token']=json.load(r)['token']
        q=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=headers)
        with client.open(q,timeout=15) as r:return json.load(r)
    def launch():
        selected['epoch']+=1;epoch=selected['epoch'];publish(root,selected['build'],epoch,'starting')
        with (work/f'host-{epoch}.log').open('wb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__).resolve()),'host','--data-root',str(root),'--port',str(port),'--application-build',selected['build'],'--application-epoch',str(epoch)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        owned.append(p);driver.processes[epoch]=p;driver.health(selected,epoch);publish(root,selected['build'],epoch,'active');driver.activate(selected,epoch)
        request('/api/local-access',{'key':read_key(root)})
    def stop():
        epoch=selected['epoch'];publish(root,selected['build'],epoch,'draining');driver.drain(selected,epoch);driver.stop(selected,epoch)
    try:
        launch();store=Dialogues(root)
        try:
            chat=store.create();turn='synthetic-'+uuid.uuid4().hex
            store.begin({'chat_id':chat,'request_id':turn,'text':'每天帮我把hello变为大写并保留结果','provider':'openai','model':'test-model','reasoning':'default','assistant_mode':True},[])
            store.finish(turn,{'status':'SUCCEEDED','text':'持续安排候选，尚未启用。','provider':'openai','model':'test-model','assistant_action':{'kind':'goal','goal':'把hello变为大写并保留结果','input_text':'hello','target':'','standing':{'quote':'每天帮我把hello变为大写并保留结果','interval_seconds':86400,'time_text':'每天'}}})
        finally:store.close()
        one=request('/api/assistant/action',{'turn_id':turn});goal=one['id'];detail=request('/api/goals',{'action':'detail','id':goal})
        proposal={'schema':'jarvis.goal-plan.v1','summary':'固定文字处理','input_text':'hello','steps':[{'title':'转换大写','capability':spec['capability'],'source':'input','expected':'HELLO'}],'questions':[]}
        request('/api/goals',{'action':'edit','id':goal,'revision':detail['plan']['revision'],'proposal':proposal})
        create={'action':'create','request_id':uuid.uuid4().hex,'title':'重启接续验收','plans':[{'goal_id':goal,'acceptance':checks('HELLO')}],'policy':config(time.time()+12,max_runs=1)}
        row=request('/api/standing-work',create);assert request('/api/standing-work',create)['id']==row['id']
        assert request('/api/snapshot')['tasks']==[];passed('source_conversation_to_editable_plan_and_inert_durable_mandate')
        request('/api/standing-work',{'action':'approve','id':row['id'],'revision':row['revision'],'request_id':uuid.uuid4().hex});stop();launch();passed('normal_drain_and_restart_preserve_authorized_schedule')
        end=time.monotonic()+40
        while True:
            data=request('/api/standing-work');current=next(r for r in data['items'] if r['id']==row['id'])
            assert request('/api/instance')
            if current['status']=='DONE':break
            if current['status']=='NEEDS_INPUT':raise AssertionError(current['error'])
            if time.monotonic()>end:raise TimeoutError('Dispatcher did not finish the standing plan')
            time.sleep(.4)
        run=current['runs'][0];assert run['status']=='VERIFIED' and len(run['goals'])==1;passed('actual_dispatcher_runs_frozen_plan_and_checks_declared_result')
        chat_view=request('/api/chats/'+chat);assert any(w['id']==row['id'] and w['notice']['status']=='VERIFIED' for t in chat_view['turns'] for w in (t.get('linked_goal') or {}).get('standing_work',[]))
        from host.session_workspace import command as session_command
        first=session_command(root,{'action':'sync','id':chat});second=session_command(root,{'action':'sync','id':chat})
        artifacts=[f for f in first['files'] if f['path'].startswith('artifacts/')]
        assert first['files']==second['files'] and len(artifacts)==1 and json.loads((Path(first['path'])/artifacts[0]['path']).read_text(encoding='utf-8'))['text']=='HELLO'
        passed('result_returns_to_original_conversation_and_session_artifact_without_duplicate_sync')
        end=time.monotonic()+8
        while True:
            item=next(i for i in request('/api/work-status')['items'] if i['id']==row['id'])
            if item['attention']['unread']:break
            if time.monotonic()>end:raise AssertionError('Deferred notification did not arrive')
            time.sleep(.25)
        request('/api/work-status',{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']});passed('one_shared_attention_receipt_not_a_second_execution')
        # Real HTTP feedback, still a synthetic operator confirmation.
        request('/api/standing-work',{'action':'feedback','id':row['id'],'revision':current['revision'],'request_id':uuid.uuid4().hex,'run_id':run['id'],'kind':'accept','note':'合成验收：仅在本次固定文字和工具版本下有效'})
        current=next(r for r in request('/api/standing-work')['items'] if r['id']==row['id']);assert current['runs'][0]['learning_candidate']['state']=='PENDING';passed('feedback_creates_source_bound_work_method_candidate_not_personal_fact')
        request('/api/standing-work',{'action':'feedback','id':row['id'],'revision':current['revision'],'request_id':uuid.uuid4().hex,'run_id':run['id'],'kind':'withdraw','note':'合成验收：撤回经验，后续需重新核对'})
        stop();launch();current=next(r for r in request('/api/standing-work')['items'] if r['id']==row['id']);assert current['status']=='PAUSED' and current['runs'][0]['learning_candidate']['state']=='WITHDRAWN'
        core=Core(root)
        try:
            assert len(core.db.all('SELECT * FROM tasks'))==1;assert not core.db.all('SELECT * FROM model_calls');assert not core.db.all('SELECT * FROM facts')
            assert core.db.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        finally:core.close()
        passed('withdrawal_and_restart_block_future_use_without_duplicate_effects')
        for path in ('/','/companion','/companion/native','/standing-work.js','/work-status.js','/assistant-actions.js'):
            with client.open(driver.origin+path,timeout=5) as r:assert r.status==200
        passed('workbench_and_companion_serve_same_standing_component_and_api');stop();report['passed']=True
    except BaseException as error:report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        for p in owned:
            if p.poll() is None:p.terminate()
            p.wait(15)
        report['owned_hosts_stopped']=all(p.poll() is not None for p in owned);save()

if __name__=='__main__':
    if sys.argv[1]=='host':host()
    else:run(Path(sys.argv[1]).resolve())
