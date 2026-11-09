"""Characterize two real old checkouts over disposable new state, then resume new.

Direct launches intentionally bypass adoption, to measure why a compatibility
gate is necessary. Nothing is adopted; no business backup is restored.
"""
import hashlib,json
from pathlib import Path
import socket,sqlite3,subprocess,sys,time,urllib.error,urllib.request,uuid,zipfile

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from adapters.application_host import WorkbenchProcess
from control.application_runtime import LocalApprovals,publish
from control.application_compatibility import require_compatible
from control.local_access import install_client
from control.recovery.gate import StopGate
from host.core import Core
from host import assistant,commitments
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments
from sdk.protocol import canonical


def signature(root):
    db=sqlite3.connect((root/'state/commitments.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        rows={table:db.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall()
              for table in ('commitments','history','operations','conversation_operations')}
        return hashlib.sha256(canonical(rows).encode()).hexdigest()
    finally:db.close()


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    report={'scope':'synthetic data, real old/native hosts; characterization bypasses adoption on purpose',
            'old_versions':[],'production_changed':False,'status':'running',
            'sources_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['control/application_compatibility.py','modules/release_recovery/application.py','adapters/application_host.py','modules/task_resource/commitment_intent.py','config/runtime-compatibility.json']}}
    save=lambda:(HERE/'rollback-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    refs=['efe50c7634a965d167e4ae197ed53dc35347d175','11a9e4b'];packages=[]
    for ref in refs:
        commit=subprocess.check_output(['git','rev-parse',ref],cwd=ROOT,text=True).strip()
        archive=work/(commit[:8]+'.zip')
        subprocess.run(['git','archive','--format=zip','--output',str(archive),commit,
            'sdk','control','adapters','modules','host','apps','config','contracts','seed','external','packaging','VERSION','evals/text-analyzer.json'],cwd=ROOT,check=True)
        destination=work/commit[:8];destination.mkdir()
        with zipfile.ZipFile(archive) as source:source.extractall(destination)
        packages.append((commit,destination))
    data=work/'data';core=Core.initialize(data);core.close();LocalApprovals(data).initialize()
    store=Dialogues(data)
    try:chat=store.create()
    finally:store.close()
    def chat_create(text,title):
        ident='rollback-'+uuid.uuid4().hex
        payload={'schema':'jarvis.assistant-turn.v1','reply':'candidate','action':{'kind':'commitment','goal':'','input_text':'','target':'',
            'commitment':{'operation':'create','title':title,'quote':text,'due_at':'','time_text':'','basis_turn':''}}}
        reply,action=assistant.parse(canonical(payload),assistant.context(data,chat));store=Dialogues(data)
        try:
            store.begin({'chat_id':chat,'request_id':ident,'text':text,'provider':'fixture','model':'fixture','reasoning':'default','assistant_mode':True},[])
            store.finish(ident,{'status':'SUCCEEDED','text':reply,'assistant_action':action})
        finally:store.close()
        return ident,assistant.commitment_from_turn(data,ident)['receipt']['current']
    turn,todo=chat_create('帮我记个待办：恢复后核对','恢复后核对')
    from datetime import datetime,timezone
    clock=datetime.fromtimestamp(time.time()+2,timezone.utc).isoformat(timespec='seconds')
    _,pending=chat_create(clock+'提醒我恢复后补投','恢复后补投')
    terminal=[]
    for action in ('cancel','complete'):
        body={'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,'title':action,'source':'synthetic user note','due_at':None}
        row=commitments.command(data,body)['current']
        terminal.append(commitments.command(data,{'action':action,'id':row['id'],'request_id':uuid.uuid4().hex,'revision':1})['current'])
    before=signature(data)
    with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
    driver=WorkbenchProcess(data,port,timeout=15);processes=[];epoch=0;selected=None
    def launch(code,healthy=True):
        global epoch,selected,token
        epoch+=1;selected={'build':str(epoch)*64,'epoch':epoch,'slot':'A'}
        publish(data,selected['build'],epoch,'starting')
        with (work/f'host-{epoch}.out').open('wb') as out,(work/f'host-{epoch}.err').open('wb') as err:
            process=subprocess.Popen([sys.executable,'-I','-B',str(code/'apps/workbench/server.py'),'--data-root',str(data),'--port',str(port),
                '--application-build',selected['build'],'--application-epoch',str(epoch)],cwd=code,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process);driver.processes[epoch]=process
        if healthy:driver.health(selected,epoch)
        else:
            end=time.monotonic()+15
            while True:
                try:driver.identity(selected,epoch);break
                except OSError:
                    if time.monotonic()>end:raise
                    time.sleep(.1)
        publish(data,selected['build'],epoch,'active')
        if healthy:driver.activate(selected,epoch)
        install_client(driver.origin,data)
        with urllib.request.urlopen(driver.origin+'/api/session') as response:token=json.load(response)['token']
    def request(path,body=None):
        req=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,
            headers={'Origin':driver.origin,'Content-Type':'application/json','X-Jarvis-Token':token})
        with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
    def stop():
        publish(data,selected['build'],epoch,'draining');driver.drain(selected,epoch);driver.stop(selected,epoch)
    save()
    try:
        for commit,code in packages:
            try:require_compatible(data,code)
            except Exception as error:preflight=getattr(error,'code',type(error).__name__)
            else:raise AssertionError('Incompatible old package was admitted')
            launch(code);chat_result=request('/api/chats/'+chat)
            try:request('/api/commitments');endpoint=200
            except urllib.error.HTTPError as error:endpoint=error.code
            try:request('/api/assistant/action',{'turn_id':turn});refusal=None
            except urllib.error.HTTPError as error:refusal=json.load(error).get('error')
            time.sleep(2.1)
            unchanged=signature(data)==before
            with Commitments(data) as db:unconsumed=db.read(pending['id'])['status']=='OPEN'
            stop()
            item={'commit':commit,'version':(code/'VERSION').read_text().strip(),'data_unchanged':unchanged,
                'controller_preflight':preflight,'commitment_endpoint_http':endpoint,'new_action_refusal':refusal,'new_receipt_projection':any('commitment_action' in t for t in chat_result['turns']),
                'due_processing_supported':not unconsumed,'feature_compatible':False}
            report['old_versions'].append(item);save();assert unchanged and unconsumed and endpoint==404 and refusal
            print(json.dumps({'old_commit':commit[:8],'preserved_data':unchanged,'reminders_supported':False}),flush=True)
        report['current_preflight']=require_compatible(data,ROOT)
        launch(ROOT);end=time.monotonic()+8
        while True:
            with Commitments(data) as db:row=db.read(pending['id'])
            if row['status']=='DUE':break
            if time.monotonic()>end:raise RuntimeError('New host did not catch up')
            time.sleep(.1)
        with Commitments(data) as db:
            assert all(db.read(r['id'])['status']==r['status'] for r in terminal)
            assert sum(e['event']=='due' for e in db.history(pending['id']))==1
        receipt=request('/api/chats/'+chat)['turns'][0]['commitment_action'];assert receipt['mode']=='APPLIED'
        stop();report['new_resume']={'pending_caught_up_once':True,'cancelled_and_done_preserved':True,'receipt_readable':True}
        new={'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,'title':'stop stays stopped','source':'synthetic user note','due_at':'2001-01-01T00:00:00Z'}
        with Commitments(data) as db:db.command(new)  # explicit disposable fixture setup, not a host command during maintenance
        StopGate(data).stop();generation=StopGate(data).token()
        launch(ROOT,healthy=False);time.sleep(2.1)
        try:driver.request(selected,epoch,'health');raise AssertionError('Stopped host reported healthy')
        except urllib.error.HTTPError:pass
        with Commitments(data) as db:assert db.read(new['id'])['status']=='OPEN'
        assert StopGate(data).token()==generation;stop()
        report.update(status='passed_characterization',stop_preserved=True,old_rollback_requires_gate=True);save()
    except BaseException as error:
        report.update(status='failed',error=getattr(error,'code',type(error).__name__));raise
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()
            process.wait(10)
        save()
    print(json.dumps({'status':report['status'],'old_feature_compatible':False,'new_resume':report['new_resume']}))
