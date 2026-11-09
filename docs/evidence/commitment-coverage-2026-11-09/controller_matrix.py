"""Real controller + sealed packages + native Hosts, using disposable data only.

Faults are injected in the driver AFTER real health checks, not in product code.
Four package variants differ only in VERSION; they exercise lifecycle branches,
not four independent feature implementations. No production paths are adopted.
"""
from datetime import datetime,timezone
import base64,hashlib,http.cookiejar,json
from pathlib import Path
import secrets,shutil,socket,sys,time,urllib.error,urllib.request,uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from adapters.application_host import WorkbenchProcess
from control.application_compatibility import require_compatible
from control.atomic import write_json
from control.credentials import crypt
from control.local_access import read_key
from control.recovery.gate import StopGate
from host.application_release import validator
from host.core import Core
from host import assistant
from modules.dialogue.store import Dialogues
from modules.release_recovery.application import Applications,build,inspect_package
from modules.task_resource.commitments import Commitments
from sdk.protocol import canonical,CoreError


class InterruptedController(BaseException):pass


class Driver(WorkbenchProcess):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.events=[];self.health_fault=None;self.stop_fault=None
    def start(self,record,selected,epoch):
        super().start(record,selected,epoch);self.events.append(['start',selected['build'],epoch])
    def health(self,selected,epoch):
        super().health(selected,epoch)
        if self.health_fault:self.health_fault(selected,epoch)
    def stop(self,selected,epoch):
        if self.stop_fault:self.stop_fault(selected,epoch)
        super().stop(selected,epoch);self.events.append(['stop_confirmed',selected['build'],epoch])


def fingerprint(root):
    with Commitments(root) as db:
        return hashlib.sha256(canonical({table:[dict(row) for row in db.db.execute('SELECT * FROM '+table+' ORDER BY 1')]
            for table in ('commitments','history','operations','conversation_operations')}).encode()).hexdigest()


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    complete='--complete' in sys.argv;final='--final' in sys.argv
    plan_name='plan-final.json' if complete else 'plan-r4.json' if final else 'plan-r3.json'
    plan=json.loads((HERE/plan_name).read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in plan['runtime_sha256'].items())
    report={'status':'running','production_adopted':False,'scope':'real lifecycle with synthetic data; driver faults after real health; four code-identical VERSION variants',
        'steps':[],'packages':{},'source_freeze':plan_name}
    result_path=HERE/('controller-complete-result.json' if complete else 'controller-final-result.json' if final else 'controller-result.json');assert not result_path.exists()
    def save():result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(name,**details):
        report['steps'].append({'case':name,'passed':True,**details});save();print(json.dumps({'passed':name}),flush=True)
    data=work/'data';Core.initialize(data).close();app=Applications(data)
    with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
    driver=Driver(data,port,timeout=15);drivers=[driver]
    packages={}
    for label in 'ABCD':
        source=work/('source-'+label);source.mkdir()
        for name in plan['runtime_sha256']:
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
        version='0.1.3-acceptance-'+label.lower();(source/'VERSION').write_text(version+'\n',encoding='utf-8')
        archive=work/(label+'.zip');ident=build(source,plan['runtime_sha256'],archive,version);app.stage(archive)
        print(json.dumps({'validating':label}),flush=True)
        approval=app.validate(ident,validator(data,reviewed_source=True));checked=approval['report'] if 'report' in approval else approval
        # validate returns the signed receipt wrapper; retain the actual report from the package record.
        record=app.record(ident);checked=record['approval']['receipt']['report']
        assert checked['passed']
        log=data/'deployment/validation-logs'/checked['test_log'];shutil.copyfile(log,HERE/(('controller-complete-' if complete else 'controller-final-' if final else 'controller-')+label+'-tests.log'))
        packages[label]=ident;report['packages'][label]={'build':ident,'version':version,'validation':checked,
            'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()};save()
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def unlock():
        request=urllib.request.Request(driver.origin+'/api/local-access',data=canonical({'key':read_key(data)}).encode(),
            headers={'Origin':driver.origin,'Content-Type':'application/json'})
        client.open(request,timeout=5).close()
    def request(path,body=None,opener=None):
        selected_client=opener or client;headers={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None:
            with selected_client.open(driver.origin+'/api/session',timeout=5) as response:headers['X-Jarvis-Token']=json.load(response)['token']
        req=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=headers)
        with selected_client.open(req,timeout=5) as response:return json.load(response)
    def create(title,due_at=None):
        return request('/api/commitments',{'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,
            'title':title,'source':'synthetic acceptance user','due_at':due_at})['current']
    def reject(call,code=None):
        try:call()
        except CoreError as error:
            if code:assert error.code==code,(error.code,code)
            return error.code
        raise AssertionError('Expected operation to be refused')
    def steady(expected):
        state=app.state();assert state['phase']=='active' and state['active']['build']==packages[expected]
        driver.health(state['active'],state['epoch']);assert driver.metadata()['application_epoch']==state['epoch']
        return state
    try:
        app.adopt(packages['A'],driver);steady('A');unlock();passed('initial_adoption')
        # Typed proposal is a fixed fixture; acceptance and its receipt use actual HTTP.
        chats=Dialogues(data)
        try:chat=chats.create()
        finally:chats.close()
        text='Please add a to-do item: check the sample cabinet.';turn='matrix-'+uuid.uuid4().hex
        envelope={'schema':'jarvis.assistant-turn.v1','reply':'candidate','action':{'kind':'commitment','goal':'','input_text':'','target':'',
            'commitment':{'operation':'create','title':'check the sample cabinet','quote':text,'due_at':'','time_text':'','basis_turn':''}}}
        reply,action=assistant.parse(canonical(envelope),assistant.context(data,chat));chats=Dialogues(data)
        try:
            chats.begin({'chat_id':chat,'request_id':turn,'text':text,'provider':'fixture','model':'fixture','reasoning':'default','assistant_mode':True},[])
            chats.finish(turn,{'status':'SUCCEEDED','text':reply,'assistant_action':action})
        finally:chats.close()
        receipt=request('/api/assistant/action',{'turn_id':turn});assert receipt['mode']=='APPLIED'
        for operation in ('cancel','complete'):
            item=create('terminal-'+operation)
            request('/api/commitments',{'action':operation,'id':item['id'],'request_id':uuid.uuid4().hex,'revision':1})
        edit=create('revision survives')
        request('/api/commitments',{'action':'reschedule','id':edit['id'],'request_id':uuid.uuid4().hex,'revision':1,'due_at':'2035-08-02T16:00:00Z'})
        overdue=create('offline catch-up',datetime.fromtimestamp(time.time()+3,timezone.utc).isoformat(timespec='seconds'))
        app.stop(driver);time.sleep(3.1)
        app.adopt(packages['B'],driver);steady('B')
        deadline=time.monotonic()+8
        while True:
            with Commitments(data) as db:row=db.read(overdue['id'])
            if row['status']=='DUE':break
            if time.monotonic()>deadline:raise AssertionError('No offline catch-up')
            time.sleep(.1)
        with Commitments(data) as db:assert sum(h['event']=='due' for h in db.history(overdue['id']))==1
        stable=fingerprint(data);assert request('/api/chats/'+chat)['turns'][0]['commitment_action']['mode']=='APPLIED'
        passed('adoption_with_offline_catchup_and_receipt',epoch=app.state()['epoch'])
        app.rollback(driver);steady('A');assert fingerprint(data)==stable
        passed('compatible_rollback_preserves_revisions_terminal_states_and_origins')
        # Controller dies after the real candidate is healthy, before adoption commit.
        def interrupt(selected,epoch):
            if selected['build']==packages['B']:raise InterruptedController()
        driver.health_fault=interrupt
        try:app.adopt(packages['B'],driver)
        except InterruptedController:pass
        else:raise AssertionError('Fault was not injected')
        assert app.state()['phase']=='starting';driver.health_fault=None
        driver=Driver(data,port,timeout=15);drivers.append(driver);app=Applications(data)
        app.recover(driver);steady('A');assert fingerprint(data)==stable
        passed('new_controller_and_driver_recover_live_pending_candidate',epoch=app.state()['epoch'])
        # Candidate B is still approved; interrupted_handoff did not label its code unhealthy.
        def fail_b(selected,epoch):
            if selected['build']==packages['B']:raise RuntimeError('injected unhealthy signal after real health')
        def unknown_exit(selected,epoch):
            if selected['build']==packages['B']:raise CoreError('injected_exit_unknown','Exit confirmation fault')
        driver.health_fault=fail_b;driver.stop_fault=unknown_exit
        reject(lambda:app.adopt(packages['B'],driver),'application_recovery_blocked')
        assert app.state()['phase']=='blocked' and driver.metadata()['application_build']==packages['B']
        starts=len([e for e in driver.events if e[0]=='start'])
        driver.health_fault=None;driver.stop_fault=None;app.recover(driver);steady('A')
        assert len([e for e in driver.events if e[0]=='start'])==starts+1 and fingerprint(data)==stable
        assert app.record(packages['B'])['approval'] is None
        passed('unconfirmed_exit_blocks_second_writer_then_recovers')
        def fail_c(selected,epoch):
            if selected['build']==packages['C']:raise RuntimeError('injected unhealthy signal after real health')
        driver.health_fault=fail_c;app.adopt(packages['C'],driver);driver.health_fault=None
        steady('A');assert fingerprint(data)==stable and app.record(packages['C'])['approval'] is None
        passed('failed_health_restores_baseline_at_new_epoch',epoch=app.state()['epoch'])
        # Rotate only this synthetic instance's local key while stopped. Old cookie must stay invalid.
        app.stop(driver)
        write_json(data/'private/workbench-access.dpapi',{'schema_version':1,'format':'windows-dpapi-current-user',
            'payload':base64.b64encode(crypt(canonical({'key':secrets.token_urlsafe(32)}).encode())).decode()})
        app.start(driver);steady('A')
        try:request('/api/commitments');raise AssertionError('Revoked session revived')
        except urllib.error.HTTPError as error:assert error.code==401
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));unlock()
        assert fingerprint(data)==stable
        passed('revoked_browser_session_not_revived_by_restart')
        legacy=Path('D:/jarvisTest/commitment-rollback-20261108-final/efe50c76')
        state=app.state();reject(lambda:require_compatible(data,legacy),'application_data_compatibility')
        assert app.state()==state;steady('A');passed('historical_compatibility_preflight_leaves_live_host_untouched')
        stopped_pending=None
        def stop_d(selected,epoch):
            global stopped_pending
            if selected['build']==packages['D']:
                with Commitments(data) as db:
                    stopped_pending=db.command({'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,
                        'title':'STOP fixture','source':'synthetic fixture during starting phase','due_at':'2001-01-01T00:00:00Z'})['current']
                StopGate(data).stop();raise RuntimeError('STOP while candidate health fails')
        driver.health_fault=stop_d;reject(lambda:app.adopt(packages['D'],driver),'stopped');driver.health_fault=None
        token=StopGate(data).token();starts=len([e for e in driver.events if e[0]=='start'])
        reject(lambda:Applications(data).recover(driver),'stopped')
        assert StopGate(data).token()==token and len([e for e in driver.events if e[0]=='start'])==starts
        with Commitments(data) as db:assert db.read(stopped_pending['id'])['status']=='OPEN'
        passed('STOP_during_failure_prevents_automatic_restore_and_due_processing')
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=type(error).__name__,detail=str(error));raise
    finally:
        processes={p.pid:p for d in drivers for p in d.processes.values()};forced=[]
        for process in processes.values():
            if process.poll() is None:forced.append(process.pid);process.terminate()
            process.wait(10)
        report.update(all_owned_processes_stopped=all(p.poll() is not None for p in processes.values()),cleanup_forced_owned_pids=forced,
            final_phase=app.state()['phase'],stop_generation_preserved=StopGate(data).state()=='stopped',
            driver_events=[e for d in drivers for e in d.events],completed_utc=datetime.now(timezone.utc).isoformat())
        save()
    print(json.dumps({'status':report['status'],'cases':len(report['steps'])}))
