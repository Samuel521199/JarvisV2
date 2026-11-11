"""Real pinned-controller handoff and compatible recovery on disposable data."""
from pathlib import Path
import http.cookiejar,json,socket,subprocess,sys,urllib.request,uuid,zipfile
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from host.core import Core
from host.application_release import validator
from host.application_installation import install
from adapters.application_host import WorkbenchProcess
from modules.release_recovery.application import Applications
from modules.mail.store import MailStore
from control.network import NetworkGate
from control.local_access import read_key
from sdk.protocol import CoreError,canonical
from sdk.mail import READ
from test_mail_standing import policy


def run(work,candidates,old_controller,old_package):
    work.mkdir(parents=True,exist_ok=False);root=work/'user-data';Core.initialize(root).close()
    gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
    store=MailStore(root)
    try:store.put({'id':'account','kind':'account','generation':'fixture-generation','email':'owner@example.com','credentials':{'scope':READ},'health':'connected'},0)
    finally:store.close()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    app=Applications(root);driver=WorkbenchProcess(root,port,timeout=45);report={'passed':False,'synthetic_data':True,'network_blocked':True,'same_code_baseline':True,'steps':[]}
    def save():(work/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    def passed(case):report['steps'].append({'case':case,'passed':True});save();print(json.dumps({'passed':case}),flush=True)
    def old(action,**fields):
        argv=[sys.executable,'-X','utf8','-I','-B',str(old_controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port)]
        for k,v in fields.items():
            argv+=['--'+k.replace('_','-')]
            if v is not True:argv.append(str(v))
        r=subprocess.run(argv,capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));(work/('old-'+action+'.log')).write_bytes(r.stdout+b'\n'+r.stderr);assert r.returncode==0;return json.loads(r.stdout)
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,body=None):
        h={'Origin':driver.origin,'Content-Type':'application/json'}
        if body is not None and path!='/api/local-access':
            with client.open(driver.origin+'/api/session',timeout=5) as r:h['X-Jarvis-Token']=json.load(r)['token']
        q=urllib.request.Request(driver.origin+path,data=canonical(body).encode() if body is not None else None,headers=h)
        with client.open(q,timeout=10) as r:return json.load(r)
    def unlock():request('/api/local-access',{'key':read_key(root)})
    try:
        archive=work/'old.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            manifest=json.loads((old_package/'application.json').read_text(encoding='utf-8'))
            for name in ['application.json',*manifest['files']]:z.write(old_package/name,name)
        legacy=old('stage',archive=archive)['build'];old('validate',build=legacy,reviewed_source=True);old('adopt',build=legacy);old('install-launcher');unlock();assert request('/api/instance')['application_build']==legacy;passed('actual_v016_pinned_controller_and_host_running')
        packages=json.loads((candidates/'result.json').read_text(encoding='utf-8'));reviewed={}
        for version in ('0.1.7-rc.1','0.1.7'):
            ident=app.stage(Path(packages[version]['archive']))['build'];assert app.validate(ident,validator(root,reviewed_source=True)).get('approval');reviewed[version]=ident
        report['builds']=reviewed;baseline=reviewed['0.1.7-rc.1'];stable=reviewed['0.1.7']
        app.adopt(baseline,driver,expected_epoch=app.state()['epoch']);install(root,work,Path(app.record(baseline)['path']),port=port);unlock();passed('new_controller_installed_after_normal_drain')
        row=request('/api/mail-standing',{'action':'create','request_id':uuid.uuid4().hex,'title':'Encrypted compatible recovery','policy':policy()})
        request('/api/mail-standing',{'action':'approve','id':row['id'],'revision':row['revision'],'request_id':uuid.uuid4().hex});state=app.state()
        try:app.adopt(legacy,driver,expected_epoch=state['epoch'])
        except CoreError as e:assert e.code=='application_data_compatibility'
        else:raise AssertionError('Old package accepted encrypted mailbox mandate')
        assert app.state()['epoch']==state['epoch'];assert request('/api/mail-standing')['items'][0]['status']=='ACTIVE';passed('incompatible_legacy_refused_before_drain_and_mandate_retained')
        app.adopt(stable,driver,expected_epoch=state['epoch']);install(root,work,Path(app.record(stable)['path']),port=port);assert request('/api/mail-standing')['items'][0]['id']==row['id'];passed('stable_adoption_preserves_encrypted_mail_policy_and_original_account')
        app.rollback(driver);assert request('/api/mail-standing')['items'][0]['status']=='ACTIVE';passed('compatible_rollback_keeps_current_business_data')
        app.stop(driver);r=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(work/'JarvisLaunch.py'),'--no-browser'],capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));assert r.returncode==0;unlock();assert request('/api/mail-standing')['items'][0]['id']==row['id'];passed('pinned_root_launcher_restarts_existing_encrypted_mandate');app.stop(driver);report['passed']=True
    except BaseException as e:report['error']={'type':type(e).__name__,'message':str(e)};raise
    finally:
        try:app.stop(driver)
        except CoreError:pass
        save()


if __name__=='__main__':run(*[Path(p).resolve() for p in sys.argv[1:]])
