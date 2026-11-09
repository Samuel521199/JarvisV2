"""Real Host/dispatcher restart, synthetic Gmail adapter; zero external effects."""
from pathlib import Path
import copy,hashlib,http.cookiejar,json,socket,subprocess,sys,time,urllib.request,uuid
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from control.application_runtime import LocalApprovals,publish
from control.local_access import read_key
from adapters.application_host import WorkbenchProcess
from host.core import Core
from modules.mail.store import MailStore
from sdk.mail import READ,SEND
from sdk.protocol import canonical

MAIL={'id':'runtime-fixture-mail','thread_id':'runtime-fixture-thread','from':'Jarvis 本机验收 <sender@example.com>',
      'subject':'本机验收测试（不是真实邮件）','date':'synthetic','body':'本地闭环验收资料，不发送到任何真实邮箱。',
      'snippet':'本地闭环验收资料','labels':['INBOX','UNREAD']}

class FakeGmail:
    def __init__(self,credentials,guard):self.credentials=credentials;self.guard=guard
    def refresh(self):self.guard();return self.credentials
    def read(self,*_):self.guard();return copy.deepcopy(MAIL)
    def send(self,raw,draft):
        self.guard();path=Path(self.credentials['fixture_counter']);count=int(path.read_text()) if path.exists() else 0
        path.write_text(str(count+1));return {'id':'fixture-receipt','threadId':MAIL['thread_id']}

def host_main():
    from apps.workbench import mail_http
    from host.mailbox import Mailbox
    import runpy
    mail_http.Mailbox=lambda root:Mailbox(root,gmail_factory=FakeGmail)
    sys.argv=[str(ROOT/'apps/workbench/server.py'),*sys.argv[2:]]
    runpy.run_path(str(ROOT/'apps/workbench/server.py'),run_name='__main__')

def run(work):
    work.mkdir(parents=True,exist_ok=False);root=work/'user-data';Core.initialize(root).close();LocalApprovals(root).initialize();(root/'deployment').mkdir()
    store=MailStore(root)
    try:
        store.put({'id':'account','kind':'account','generation':'fixture-generation','email':'owner@example.com',
            'credentials':{'scope':READ+' '+SEND,'fixture_counter':str(work/'fake-send-count')},'health':'connected','checked_at':time.time()},0)
    finally:store.close()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    driver=WorkbenchProcess(root,port);processes=[];selected={'build':'c'*64,'slot':'A','epoch':0}
    report={'passed':False,'real_host_and_dispatcher':True,'gmail_adapter':'synthetic, never Google','model_calls':0,'real_mail_writes':0,'steps':[]}
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def save():(work/'result.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    def passed(name):report['steps'].append({'case':name,'passed':True});save();print(json.dumps({'passed':name}),flush=True)
    def request(path,body=None):
        headers={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None and path!='/api/local-access':
            with client.open(driver.origin+'/api/session',timeout=5) as response:headers['X-Jarvis-Token']=json.load(response)['token']
        req=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=headers)
        with client.open(req,timeout=10) as response:return json.load(response)
    def launch():
        selected['epoch']+=1;epoch=selected['epoch'];publish(root,selected['build'],epoch,'starting')
        with (work/f'host-{epoch}.log').open('wb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-I','-B',str(Path(__file__).resolve()),'host','--data-root',str(root),
                '--port',str(port),'--application-build',selected['build'],'--application-epoch',str(epoch)],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(p);driver.processes[epoch]=p;driver.health(selected,epoch);publish(root,selected['build'],epoch,'active');driver.activate(selected,epoch)
        request('/api/local-access',{'key':read_key(root)})
    def stop():
        epoch=selected['epoch'];publish(root,selected['build'],epoch,'draining');driver.drain(selected,epoch);driver.stop(selected,epoch)
    def wait_job(job):
        end=time.monotonic()+10
        while job['status'] in {'READY','RUNNING'} and time.monotonic()<end:
            time.sleep(.1);job=request('/api/mail',{'action':'detail','id':job['id']})
        assert job['status']=='SUCCEEDED',job;return job
    try:
        launch()
        mail=wait_job(request('/api/mail',{'action':'job','request_id':uuid.uuid4().hex,'operation':'read','payload':{'message_id':MAIL['id']}}))['result']
        body={'action':'create','account_generation':mail['account_generation'],'message_id':mail['id'],'source_digest':mail['source_digest'],
              'title':'合成验收：处理邮件','due_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()+2)),'request_id':uuid.uuid4().hex}
        row=request('/api/mail-work',body)['current'];ident=row['id'];passed('cached_read_to_one_shared_commitment')
        end=time.monotonic()+8
        while True:
            item=next(i for i in request('/api/work-status')['items'] if i['id']==ident)
            if item['raw_status']=='DUE':break
            if time.monotonic()>end:raise AssertionError('Real dispatcher failed to post due reminder')
            time.sleep(.15)
        assert item['attention']['unread'];request('/api/work-status',{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']})
        assert request('/api/commitments/'+ident)['current']['status']=='DUE';passed('actual_dispatcher_reminder_and_read_is_not_done')
        d=request('/api/mail',{'action':'draft','id':'','revision':0,'value':{'to':'sender@example.com','subject':'本机验收回复','body':'合成回复，不向 Google 提交。'}})
        assert not (work/'fake-send-count').exists();passed('encrypted_local_draft_has_no_remote_effect')
        review=request('/api/mail-work',{'action':'review_reply','id':ident,'operation':'send','payload':{'draft_id':d['id'],'revision':d['revision']}})
        approve={'action':'approve','review_id':review['id'],'request_id':uuid.uuid4().hex};job=wait_job(request('/api/mail',approve));request('/api/mail',approve)
        assert (work/'fake-send-count').read_text()=='1';assert request('/api/mail-work',{'action':'source','id':ident})['effects'][0]['status']=='SUCCEEDED'
        assert request('/api/commitments/'+ident)['current']['status']=='DUE';passed('exact_review_one_synthetic_effect_and_linked_receipt')
        request('/api/commitments',{'action':'complete','id':ident,'revision':1,'request_id':uuid.uuid4().hex})
        assert request('/api/mail-work',{'action':'inspect','account_generation':mail['account_generation'],'message_id':mail['id']})['items'][0]['status']=='DONE'
        passed('owner_feedback_updates_same_mail_and_work_record')
        stop();launch();assert request('/api/commitments/'+ident)['current']['status']=='DONE';assert (work/'fake-send-count').read_text()=='1'
        request('/api/mail',{'action':'disconnect'});source=request('/api/mail-work',{'action':'source','id':ident});assert source['message'] is None and source['source_status']=='disconnected'
        assert request('/api/mail-work',body)['current']['status']=='DONE';passed('restart_disconnect_and_replay_preserve_feedback_without_old_body')
        for path in ('/companion','/companion/native','/companion/native-robot','/mail-work.js','/mail-draft.js','/mail-review.js'):
            with client.open(driver.origin+path,timeout=5) as response:assert response.status==200
        passed('shared_routes_and_components_served');stop();report['passed']=True
    except BaseException as error:report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
            p.wait(10)
        report['all_owned_hosts_stopped']=all(p.poll() is not None for p in processes);save()

if __name__=='__main__':
    if sys.argv[1]=='host':host_main()
    else:run(Path(sys.argv[1]).resolve())
