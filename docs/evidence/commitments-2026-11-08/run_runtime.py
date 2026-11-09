"""Disposable real managed-host restart, offline catch-up and browser acceptance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from adapters.application_host import WorkbenchProcess
from control.application_runtime import LocalApprovals,publish
from control.local_access import install_client,read_key
from host.core import Core


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    data=work/'data';Core.initialize(data).close();LocalApprovals(data).initialize()
    with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
    driver=WorkbenchProcess(data,port,timeout=15);processes=[];selected=None
    report={'scope':'disposable managed hosts and synthetic user requests','passed':False,
            'sources_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [
                'modules/task_resource/commitments.py','host/commitments.py','host/task_scheduler.py',
                'modules/continuity/attention.py','apps/workbench/runtime_http.py','apps/workbench/server.py',
                'host/work_status.py','apps/workbench/work-client.js','apps/workbench/work-status.js',
                'apps/workbench/commitments.js','apps/workbench/commitment-time.js']}}
    def request(path,body=None):
        req=urllib.request.Request(driver.origin+path,data=json.dumps(body).encode() if body is not None else None,
            headers={'Origin':driver.origin,'Content-Type':'application/json','X-Jarvis-Token':token})
        with urllib.request.urlopen(req,timeout=5) as reply:return json.load(reply)
    def launch(epoch):
        global selected,token
        selected={'build':str(epoch)*64,'epoch':epoch,'slot':'A' if epoch==1 else 'B'}
        publish(data,selected['build'],epoch,'starting')
        with (work/f'host-{epoch}.out').open('wb') as out,(work/f'host-{epoch}.err').open('wb') as err:
            process=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'apps/workbench/server.py'),'--data-root',str(data),
                '--port',str(port),'--application-build',selected['build'],'--application-epoch',str(epoch)],stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process);driver.processes[epoch]=process;driver.health(selected,epoch)
        publish(data,selected['build'],epoch,'active');driver.activate(selected,epoch);install_client(driver.origin,data)
        with urllib.request.urlopen(driver.origin+'/api/session') as reply:token=json.load(reply)['token']
    def stop():
        publish(data,selected['build'],selected['epoch'],'draining');driver.drain(selected,selected['epoch']);driver.stop(selected,selected['epoch'])
    def mutation(action,row,**fields):return {'action':action,'id':row['id'],'request_id':uuid.uuid4().hex,'revision':row['revision'],**fields}
    def create(title,at):return {'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,'title':title,'source':'本人测试要求；不发送邮件或外部消息','due_at':datetime.fromtimestamp(at,timezone.utc).isoformat(timespec='seconds')}
    try:
        launch(1);started=time.time();a=create('改期旧版本不得触发',started+5);b=create('离线到期应补投',started+5)
        first=request('/api/commitments',a)['current'];request('/api/commitments',mutation('reschedule',first,due_at=datetime.fromtimestamp(started+600,timezone.utc).isoformat(timespec='seconds')))
        request('/api/commitments',b);stop()
        while time.time()<started+6:time.sleep(.1)
        launch(2);deadline=time.monotonic()+8
        while True:
            rows=request('/api/commitments')['items'];by_id={r['id']:r for r in rows}
            if by_id[b['id']]['raw_status']=='DUE':break
            if time.monotonic()>deadline:raise RuntimeError('Offline commitment not caught up')
            time.sleep(.1)
        assert by_id[a['id']]['raw_status']=='OPEN' and by_id[a['id']]['revision']==2
        current=by_id[b['id']];assert current['attention']['unread']
        request('/api/work-status',{'action':'viewed','key':current['attention']['key'],'version':current['attention']['version']})
        assert not next(r for r in request('/api/commitments')['items'] if r['id']==b['id'])['attention']['unread']
        cancelled=request('/api/commitments',mutation('cancel',current))['current']
        try:request('/api/commitments',mutation('reschedule',current,due_at=None))
        except urllib.error.HTTPError as error:assert error.code==409
        else:raise AssertionError('Stale schedule accepted')
        assert request('/api/commitments',b)['current']['status']=='CANCELLED'
        history=request('/api/commitments/'+b['id'])['history'];assert sum(e['event']=='due' for e in history)==1
        request('/api/commitments',mutation('complete',by_id[a['id']]))
        report['restart']={'passed':True,'old_schedule_not_posted':True,'offline_due_once':True,'read_receipt_persisted':True,'stale_write_rejected':True,'cancel_not_revived_by_replay':True}
        playwright=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
        browser_config=work/'browser-config.json';browser_config.write_text(json.dumps({'origin':driver.origin,'key':read_key(data),'screenshot':str(work/'work-view.png')}),encoding='utf-8')
        result=subprocess.run(['node',str(HERE/'browser.cjs'),playwright,str(browser_config)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        (HERE/'browser.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        assert result.returncode==0,'Browser acceptance failed; inspect browser.log'
        report['browser']=json.loads(result.stdout);report['work_root']=str(work);report['passed']=True
        stop()
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()
            process.wait(10)
        (HERE/'runtime-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
