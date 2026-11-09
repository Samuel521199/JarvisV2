"""Disposable old pinned launcher -> current controller -> compatible recovery.

The two new packages share reviewed code and differ only in VERSION. This tests
installation/lifecycle compatibility, not independent business implementations.
No personal databases, model credentials or external services are used.
"""
from pathlib import Path
import hashlib
import http.cookiejar
import json
import shutil
import socket
import subprocess
import sys
import urllib.request
import uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from adapters.application_host import WorkbenchProcess
from control.local_access import read_key
from host.application_installation import install
from host.application_release import tracked_runtime,validator
from host.core import Core
from modules.release_recovery.application import Applications,build
from sdk.protocol import canonical


def run(work,old_controller,old_archive):
    work.mkdir(parents=True,exist_ok=False);root=work/'user-data';Core.initialize(root).close()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    app=Applications(root);driver=WorkbenchProcess(root,port,timeout=20)
    report={'passed':False,'scope':'disposable real controller installation and recovery; synthetic data only',
            'production_adopted':False,'same_code_baseline':True,'steps':[],'packages':{}}
    def save():(work/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(name,**details):
        report['steps'].append({'case':name,'passed':True,**details});save();print(json.dumps({'passed':name}),flush=True)
    def command(arguments,log):
        result=subprocess.run([sys.executable,'-I','-B',*map(str,arguments)],capture_output=True,timeout=180)
        (work/log).write_bytes(result.stdout+b'\n'+result.stderr)
        if result.returncode:raise RuntimeError('Command failed; inspect '+log)
        return result.stdout
    def old(action,**fields):
        arguments=[old_controller/'apps/development/releases.py',action,'--data-root',root,'--port',port]
        for name,value in fields.items():
            arguments+=['--'+name.replace('_','-')]
            if value is not True:arguments.append(value)
        return json.loads(command(arguments,'old-'+action+'.log'))
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def unlock():
        req=urllib.request.Request(driver.origin+'/api/local-access',data=canonical({'key':read_key(root)}).encode(),
            headers={'Origin':driver.origin,'Content-Type':'application/json'})
        client.open(req,timeout=5).close()
    def request(path,body=None):
        headers={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None:
            with client.open(driver.origin+'/api/session',timeout=5) as reply:headers['X-Jarvis-Token']=json.load(reply)['token']
        req=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=headers)
        with client.open(req,timeout=5) as reply:return json.load(reply)
    try:
        ident=old('stage',archive=old_archive)['build']
        old('validate',build=ident,reviewed_source=True);old('adopt',build=ident);old('install-launcher')
        before=hashlib.sha256((work/'JarvisLaunch.py').read_bytes()).hexdigest()
        app.stop(driver);command([work/'JarvisLaunch.py','--no-browser'],'old-bootstrap-start.log')
        state=app.state();driver.health(state['active'],state['epoch']);unlock()
        sentinel=root/'config/controller-upgrade-fixture.json';sentinel.write_text('{"synthetic":true}',encoding='utf-8')
        sentinel_hash=hashlib.sha256(sentinel.read_bytes()).hexdigest()
        passed('old_pinned_launcher_restart',version=state['active']['version'],bootstrap_sha256=before)
        names=tracked_runtime(ROOT)
        for label,version in [('baseline','0.1.4-rc.1'),('stable','0.1.4')]:
            source=work/('source-'+label);source.mkdir()
            for name in names:
                target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            (source/'VERSION').write_text(version+'\n',encoding='utf-8')
            archive=work/(version+'.zip');ident=build(source,names,archive,version);app.stage(archive)
            app.validate(ident,validator(root,reviewed_source=True));record=app.record(ident)
            check=record['approval']['receipt']['report'];assert check['passed']
            report['packages'][label]={'build':ident,'version':version,'validation':check}
            shutil.copyfile(root/'deployment/validation-logs'/check['test_log'],work/(label+'-validation.log'));save()
        baseline=report['packages']['baseline']['build'];stable=report['packages']['stable']['build']
        app.adopt(baseline,driver,expected_epoch=app.state()['epoch'])
        install(root,work,Path(app.record(baseline)['path']),port=port)
        after=hashlib.sha256((work/'JarvisLaunch.py').read_bytes()).hexdigest();assert before!=after
        unlock();item=request('/api/commitments',{'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,
            'title':'synthetic controller recovery reminder','source':'explicit synthetic owner instruction','due_at':None})['current']
        app.stop(driver);command([work/'JarvisLaunch.py','--no-browser'],'new-bootstrap-start.log')
        assert request('/api/commitments/'+item['id'])['current']['id']==item['id']
        passed('new_controller_installed_and_root_launcher_restarts_with_existing_data',bootstrap_sha256=after)
        app.adopt(stable,driver,expected_epoch=app.state()['epoch'])
        install(root,work,Path(app.record(stable)['path']),port=port)
        assert request('/api/commitments/'+item['id'])['current']['revision']==1
        passed('stable_adoption_preserves_record')
        state=app.rollback(driver);assert state['active']['build']==baseline
        assert request('/api/commitments/'+item['id'])['current']['revision']==1
        passed('compatible_baseline_rollback_preserves_record')
        state=app.adopt(stable,driver);assert state['active']['build']==stable
        install(root,work,Path(app.record(stable)['path']),port=port)
        app.stop(driver);command([work/'JarvisLaunch.py','--no-browser'],'stable-bootstrap-start.log')
        assert request('/api/commitments/'+item['id'])['current']['revision']==1
        assert hashlib.sha256(sentinel.read_bytes()).hexdigest()==sentinel_hash
        passed('stable_pinned_launcher_restart_and_config_unchanged',epoch=app.state()['epoch'])
        app.stop(driver);report['passed']=True
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        if app.state()['phase']=='active':
            try:app.stop(driver)
            except Exception as error:report['cleanup_error']=type(error).__name__
        report['final_phase']=app.state()['phase'];save()
    print(json.dumps({'passed':True,'steps':len(report['steps']),'port':port}),flush=True)


if __name__=='__main__':run(*map(lambda p:Path(p).resolve(),sys.argv[1:]))
