"""Real pinned-controller upgrade and compatible recovery on disposable data."""
from pathlib import Path
import hashlib,http.cookiejar,json,shutil,socket,subprocess,sys,time,urllib.request,uuid,zipfile
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from host.core import Core
from host.application_release import validator
from host.application_installation import install
from adapters.application_host import WorkbenchProcess
from modules.release_recovery.application import Applications
from control.local_access import read_key
from sdk.protocol import CoreError,canonical
from test_development import specification,candidate
from test_preferences_dialogue import fixture
from test_standing_work import checks,config


def run(work,candidates,old_controller,old_package):
    work.mkdir(parents=True,exist_ok=False);root=work/'user-data';core=Core.initialize(root);core.preferences.install(fixture(),{})
    shutil.copytree(ROOT/'user-data/worker-runtime',root/'worker-runtime');spec=specification('standing-controller')
    ident=core.packages.stage(candidate('def run(text):\n    return text.upper()\n'),spec);assert core.packages.verify(ident)['passed'];core.packages.activate(ident,0);core.close()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    app=Applications(root);driver=WorkbenchProcess(root,port,timeout=30);report={'passed':False,'production_adopted':False,'same_code_compatible_baseline':True,'steps':[]}
    def save():(work/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(case):report['steps'].append({'case':case,'passed':True});save();print(json.dumps({'passed':case}),flush=True)
    def old(action,**fields):
        argv=[sys.executable,'-X','utf8','-I','-B',str(old_controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port)]
        for k,v in fields.items():
            argv+=['--'+k.replace('_','-')]
            if v is not True:argv.append(str(v))
        r=subprocess.run(argv,capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(work/('old-'+action+'.log')).write_bytes(r.stdout+b'\n'+r.stderr)
        assert r.returncode==0,'Old controller operation failed: '+action;return json.loads(r.stdout)
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,value=None):
        headers={'Origin':driver.origin,'Content-Type':'application/json'}
        if value is not None and path!='/api/local-access':
            with client.open(driver.origin+'/api/session',timeout=5) as r:headers['X-Jarvis-Token']=json.load(r)['token']
        q=urllib.request.Request(driver.origin+path,data=canonical(value).encode() if value is not None else None,headers=headers)
        with client.open(q,timeout=10) as r:return json.load(r)
    def unlock():request('/api/local-access',{'key':read_key(root)})
    try:
        archive=work/'old.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            manifest=json.loads((old_package/'application.json').read_text(encoding='utf-8'))
            for name in ['application.json',*manifest['files']]:z.write(old_package/name,name)
        legacy=old('stage',archive=archive)['build'];old('validate',build=legacy,reviewed_source=True);old('adopt',build=legacy);old('install-launcher')
        before_boot=hashlib.sha256((work/'JarvisLaunch.py').read_bytes()).hexdigest();unlock();assert request('/api/instance')['application_build']==legacy;passed('actual_v015_pinned_controller_and_host_running')
        packages=json.loads((candidates/'result.json').read_text(encoding='utf-8'));reviewed={}
        for version in ('0.1.6-rc.1','0.1.6'):
            build=app.stage(Path(packages[version]['archive']))['build'];checked=app.validate(build,validator(root,reviewed_source=True));assert checked.get('approval');reviewed[version]=build
        report['builds']=reviewed;save()
        baseline=reviewed['0.1.6-rc.1'];stable=reviewed['0.1.6']
        app.adopt(baseline,driver,expected_epoch=app.state()['epoch']);install(root,work,Path(app.record(baseline)['path']),port=port);unlock()
        assert hashlib.sha256((work/'JarvisLaunch.py').read_bytes()).hexdigest()!=before_boot;passed('new_compatible_controller_installed_after_normal_drain')
        goal=request('/api/goals',{'action':'create','request':{'request_id':uuid.uuid4().hex,'goal':'合成固定文字工作','input_text':'hello','provider':'openai','model':'test-model','reasoning':'default'}})['id']
        plan=request('/api/goals',{'action':'detail','id':goal})['plan'];proposal={'schema':'jarvis.goal-plan.v1','summary':'固定文字','input_text':'hello','steps':[{'title':'大写','capability':spec['capability'],'source':'input','expected':'HELLO'}],'questions':[]}
        request('/api/goals',{'action':'edit','id':goal,'revision':plan['revision'],'proposal':proposal})
        row=request('/api/standing-work',{'action':'create','request_id':uuid.uuid4().hex,'title':'兼容恢复验收','plans':[{'goal_id':goal,'acceptance':checks('HELLO')}],'policy':config(start_at='2099-01-01T09:00:00+08:00')})
        request('/api/standing-work',{'action':'approve','id':row['id'],'revision':row['revision'],'request_id':uuid.uuid4().hex})
        state=app.state()
        try:app.adopt(legacy,driver,expected_epoch=state['epoch'])
        except CoreError as e:assert e.code=='application_data_compatibility'
        else:raise AssertionError('Legacy host accepted live standing data')
        assert app.state()['epoch']==state['epoch'];assert request('/api/standing-work')['items'][0]['status']=='ACTIVE';passed('legacy_package_rejected_before_drain_without_discarding_mandate')
        app.adopt(stable,driver,expected_epoch=app.state()['epoch']);install(root,work,Path(app.record(stable)['path']),port=port)
        assert request('/api/standing-work')['items'][0]['id']==row['id'];passed('stable_adoption_preserves_live_authorization_and_schedule')
        app.rollback(driver);assert request('/api/standing-work')['items'][0]['status']=='ACTIVE';passed('compatible_rollback_retains_data_without_business_snapshot_restore')
        app.stop(driver);r=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(work/'JarvisLaunch.py'),'--no-browser'],capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));assert r.returncode==0;unlock();assert request('/api/standing-work')['items'][0]['id']==row['id'];passed('pinned_root_launcher_restarts_with_existing_standing_records')
        app.stop(driver);report['passed']=True
    except BaseException as e:report['error']={'type':type(e).__name__,'message':str(e)};raise
    finally:
        try:app.stop(driver)
        except CoreError:pass
        save()

if __name__=='__main__':run(*[Path(p).resolve() for p in sys.argv[1:]])
