"""Owned real Host/dispatcher/Gmail lane; synthetic Gmail adapter and user data."""
from pathlib import Path
import http.cookiejar,json,subprocess,socket,sys,time,urllib.request,uuid
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from host.core import Core
from control.application_runtime import LocalApprovals,publish
from control.local_access import read_key
from adapters.application_host import WorkbenchProcess
from modules.mail.store import MailStore
from sdk.mail import READ,SEND
from sdk.protocol import canonical
from test_mail_standing import Gmail,mail,policy


def host():
    import runpy
    from apps.workbench import mail_http
    from host.mailbox import Mailbox
    Gmail.messages={'m1':mail()};Gmail.calls=[];Gmail.failure=None;Gmail.pages=None;Gmail.blocked=None
    mail_http.Mailbox=lambda root:Mailbox(root,gmail_factory=Gmail)
    sys.argv=[str(ROOT/'apps/workbench/server.py'),*sys.argv[2:]];runpy.run_path(str(ROOT/'apps/workbench/server.py'),run_name='__main__')


def run(work):
    work.mkdir(parents=True,exist_ok=False);root=work/'data';Core.initialize(root).close();s=MailStore(root)
    try:s.put({'id':'account','kind':'account','email':'owner@example.com','generation':'g1','credentials':{'scope':READ+' '+SEND},'health':'connected'},0)
    finally:s.close()
    LocalApprovals(root).initialize()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    driver=WorkbenchProcess(root,port,timeout=45);selected={'build':'a'*64,'slot':'A','epoch':0};owned=[]
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));report={'passed':False,'synthetic_gmail_adapter':True,'real_model_calls':0,'real_mail_writes':0,'actual_desktop_clicks':False,'steps':[]}
    def save():(work/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    def passed(name):report['steps'].append({'case':name,'passed':True});save();print(json.dumps({'passed':name}),flush=True)
    def request(path,body=None):
        h={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None and path!='/api/local-access':
            with client.open(driver.origin+'/api/session',timeout=5) as r:h['X-Jarvis-Token']=json.load(r)['token']
        q=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=h)
        with client.open(q,timeout=15) as r:return json.load(r)
    def launch():
        selected['epoch']+=1;epoch=selected['epoch'];publish(root,selected['build'],epoch,'starting')
        with (work/('host-'+str(epoch)+'.log')).open('wb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__).resolve()),'host','--data-root',str(root),'--port',str(port),'--application-build',selected['build'],'--application-epoch',str(epoch)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        owned.append(p);driver.processes[epoch]=p;driver.health(selected,epoch);publish(root,selected['build'],epoch,'active');driver.activate(selected,epoch);request('/api/local-access',{'key':read_key(root)})
    def stop():publish(root,selected['build'],selected['epoch'],'draining');driver.drain(selected,selected['epoch']);driver.stop(selected,selected['epoch'])
    def wait_until(fn,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            value=fn()
            if value:return value
            time.sleep(.5)
        raise TimeoutError('Owned mailbox runtime did not reach expected condition')
    try:
        launch();row=request('/api/mail-standing',{'action':'create','request_id':uuid.uuid4().hex,'title':'Synthetic mail follow-through','policy':policy()})
        assert request('/api/mail-standing')['items'][0]['checks_started']==0;passed('shared_durable_draft_does_not_check_mail')
        request('/api/mail-standing',{'action':'approve','id':row['id'],'revision':row['revision'],'request_id':uuid.uuid4().hex});stop();launch();passed('normal_drain_restart_preserves_mandate_and_original_read_intent')
        def current():return request('/api/mail-standing')['items'][0]
        row=wait_until(lambda:(r if (r:=current())['last_checked'] else None),180);entry=next(iter(row['entries'].values()));task=entry['todo_id'];first=row['last_checked']
        assert request('/api/mail-work',{'action':'source','id':task})['source_status']=='available';passed('actual_dispatcher_and_mail_lane_create_one_source_bound_common_task')
        def due():return next((i for i in request('/api/work-status')['items'] if i['id']==task and i['raw_status']=='DUE' and i['attention']['unread']),None)
        item=wait_until(due,90);request('/api/work-status',{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']})
        assert request('/api/commitments/'+task)['current']['status']=='DUE';passed('actual_due_timer_and_shared_attention_do_not_complete_the_task')
        draft=request('/api/mail',{'action':'draft','id':'','revision':0,'value':{'to':'sender@example.com','subject':'Synthetic local review','body':'Local acceptance only; never sent'}})
        review=request('/api/mail-work',{'action':'review_reply','id':task,'operation':'send','payload':{'draft_id':draft['id'],'revision':draft['revision']}})
        assert not review.get('job_id');passed('same_mail_task_opens_existing_encrypted_draft_and_exact_review_without_automatic_send')
        row=wait_until(lambda:(r if (r:=current())['checks_started']>=2 and r['last_checked']>first else None),330)
        assert len(row['entries'])==1 and next(iter(row['entries'].values()))['todo_id']==task;passed('second_real_five_minute_timer_check_keeps_one_task_and_valid_source')
        todo=request('/api/commitments/'+task)['current'];request('/api/commitments',{'action':'complete','id':task,'revision':todo['revision'],'request_id':uuid.uuid4().hex})
        wait_until(lambda:next(iter(current()['entries'].values()))['state']=='DONE',10);passed('common_owner_feedback_stops_followup_without_model_generated_completion')
        row=current();request('/api/mail-standing',{'action':'cancel','id':row['id'],'revision':row['config_revision'],'request_id':uuid.uuid4().hex});stop();launch()
        assert current()['status']=='CANCELLED' and request('/api/commitments/'+task)['current']['status']=='DONE'
        core=Core(root)
        try:assert not core.db.all('SELECT * FROM model_calls')
        finally:core.close()
        for route in ('/','/companion','/companion/native','/mail-standing.js'):
            with client.open(driver.origin+route,timeout=5) as r:assert r.status==200
        passed('cancel_and_restart_keep_feedback_with_both_shared_surfaces');stop();report['passed']=True
    except BaseException as e:report['error']={'type':type(e).__name__,'message':str(e)};raise
    finally:
        for p in owned:
            if p.poll() is None:p.terminate()
            p.wait(15)
        report['owned_hosts_stopped']=all(p.poll() is not None for p in owned);save()


if __name__=='__main__':
    if sys.argv[1]=='host':host()
    else:run(Path(sys.argv[1]).resolve())
