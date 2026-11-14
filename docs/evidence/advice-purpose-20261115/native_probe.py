"""Real-process controller-only promotion, incompatible rollback and signed recovery.
No production business data or model credentials are copied into the fixture.
"""
from pathlib import Path
import hashlib,http.cookiejar,json,os,socket,subprocess,sys,threading,time,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from control import controller_pin as pin
from control.local_access import read_key
from control.recovery.gate import StopGate
from host.application_controller import promote,recover,policy
from modules.release_recovery.application import Applications
from sdk.protocol import digest


def main():
    output=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve()
    output.mkdir(exist_ok=False);reuse='--reuse-stopped' in sys.argv
    work.mkdir(exist_ok=reuse)
    daily=Path('E:/Jarvis/runtime/user-data');original=pin.read(daily);frozen=Path(original['controller'])
    oldstate=Applications(daily).state();oldbuild=oldstate['active']['build']
    oldpackage=Path(Applications(daily).approved(oldbuild,fresh=False)['path'])
    root=work/'installation/user-data';root.mkdir(parents=True,exist_ok=reuse)
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    if reuse:
        saved=Applications(root).state();assert saved['phase']=='stopped' and saved['active']['build']==oldbuild
        previous=pin.read(root);assert previous['schema']==1 and previous['build']==oldbuild;port=previous['port']
    env=os.environ.copy();temp=work/'temp';temp.mkdir(exist_ok=reuse);env.update(TEMP=str(temp),TMP=str(temp))
    report={'scope':'isolated real native processes, legacy installation to protocol4; v3 format-only sentinel, no business task or model claim','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'production_adopted':False,'frozen_controller':original['build'],'port':port,'steps':[]}
    def save():(output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def step(name,value):report['steps'].append({'name':name,**value});save();print(json.dumps({'name':name,**value}),flush=True)
    def run(name,controller,action,*args,success=True):
        cmd=[sys.executable,'-X','utf8','-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port),*map(str,args)]
        begin=time.monotonic();p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=240)
        (output/(name+'.txt')).write_text(p.stdout+p.stderr,encoding='utf-8')
        try:value=json.loads(p.stdout)
        except ValueError:value=None
        step(name,{'exit_code':p.returncode,'seconds':round(time.monotonic()-begin,3),'result':value})
        if success and p.returncode:raise RuntimeError(name+' failed')
        return p,value
    if not reuse:
        code='import sys;sys.path.insert(0,'+repr(str(frozen))+');from host.core import Core;Core.initialize('+repr(str(root))+').close()'
        init=subprocess.run([sys.executable,'-I','-B','-c',code],env=env,capture_output=True,text=True,timeout=60)
        if init.returncode:raise RuntimeError(init.stderr)
        oldzip=work/'baseline.zip'
        manifest=json.loads((oldpackage/'application.json').read_text())
        with zipfile.ZipFile(oldzip,'x',zipfile.ZIP_DEFLATED) as archive:
            for name in ['application.json',*manifest['files']]:archive.write(oldpackage/name,name)
        run('baseline-stage',frozen,'stage','--archive',oldzip)
        run('baseline-independent-validation',frozen,'validate','--build',oldbuild,'--reviewed-source')
    else:
        assert Applications(root).approved(oldbuild)['approval']['receipt']['report']['passed']
        step('reuse-stopped-verified-baseline',{'passed':True,'prior_evidence':'native-r1; no repeat of unchanged baseline qualification'})
    live=False
    try:
        run('baseline-native-adopt',frozen,'adopt','--build',oldbuild);live=True
        run('baseline-install',frozen,'install-launcher')
        if '--reuse-qualified' not in sys.argv:
            archive=work/('candidate-'+output.name+'.zip')
            _,built=run('candidate-build',frozen,'build','--source',ROOT,'--archive',archive,'--version',(ROOT/'VERSION').read_text().strip())
            newbuild=built['build'];run('candidate-stage',frozen,'stage','--archive',archive)
            _,validated=run('candidate-independent-validation',frozen,'validate','--build',newbuild,'--reviewed-source')
            if not validated.get('approval'):raise RuntimeError('Independent qualification failed')
        else:
            prior=json.loads((output.parent/'native-r2/result.json').read_text(encoding='utf-8'))
            newbuild=next(row['result']['build'] for row in prior['steps'] if row['name']=='candidate-build')
            candidate=Applications(root).approved(newbuild);assert candidate['approval']['receipt']['report']['passed']
            from host.application_release import tracked_runtime
            manifest=json.loads((Path(candidate['path'])/'application.json').read_text(encoding='utf-8'))
            assert set(tracked_runtime(ROOT))==set(manifest['files'])
            assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
            step('reuse-qualified-unchanged-candidate',{'passed':True,'build':newbuild,'prior_evidence':'native-r2; 206 pass, 1 platform skip'})
        app=Applications(root);before=app.state();previous=pin.read(root);overlay,fingerprint=policy(root,previous)
        origin='http://127.0.0.1:'+str(port);opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        token=''
        def fetch(path,body=None):
            headers={'Origin':origin,'Content-Type':'application/json','X-Jarvis-Token':token}
            request=urllib.request.Request(origin+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
            with opener.open(request,timeout=5) as response:return json.loads(response.read(2000000))
        fetch('/api/local-access',{'key':read_key(root)});token=fetch('/api/session')['token'];identity=fetch('/api/instance')
        chat=fetch('/api/chats',{})['id'];fetch('/api/chats/'+chat)
        stop=threading.Event();samples=[]
        def observe():
            while not stop.is_set():
                try:samples.append({'ok':True,'boot_id':fetch('/api/instance')['boot_id']})
                except Exception as error:samples.append({'ok':False,'error':type(error).__name__})
                stop.wait(.05)
        observer=threading.Thread(target=observe);observer.start()
        try:promoted=promote(root,newbuild,expected_epoch=before['epoch'],expected_build=oldbuild,expected_controller=digest(previous),reviewed_source=True)
        finally:stop.set();observer.join()
        record=pin.read(root);after=fetch('/api/instance')
        assert app.state()==before and after['boot_id']==identity['boot_id']
        assert samples and all(s['ok'] and s['boot_id']==identity['boot_id'] for s in samples)
        assert fetch('/api/chats/'+chat)['id']==chat
        chat2=fetch('/api/chats',{})['id'];assert chat2!=chat
        assert all((Path(record['controller'])/name).read_bytes()==raw for name,raw in overlay.items())
        step('controller-only-native-continuity',{'passed':True,'application_epoch':before['epoch'],'application_build':oldbuild,'boot_id_unchanged':True,'authenticated_chat_write_before_after':True,'observations':len(samples),'request_failures':0,'frozen_policy_sha256':fingerprint,'controller_build':record['build'],'runtime_source_build':newbuild,'registration_pending':promoted['registration_pending']})
        upgraded=Path(record['controller'])
        run('new-controller-adopts-compatible-body',upgraded,'adopt','--build',newbuild,'--expected-epoch',before['epoch'])
        now=app.state();native=fetch('/api/instance');assert now['active']['build']==newbuild
        from host.core import Core
        from modules.context_knowledge.knowledge import Knowledge
        core=Core(root)
        try:
            from host.planning_advice import PlanningAdvice
            from modules.task_resource.plans import Plans
            from sdk.protocol import canonical
            assert PlanningAdvice.writer_version(root)==3
            with core.db.transaction() as tx:
                ident,_=Plans(core.db).create({'request_id':'native-v3-format-sentinel','goal':'Synthetic compact format compatibility sentinel'},[],[],tx)
                tx.execute('INSERT INTO goal_context VALUES(?,?,?,?,?)',(ident,'personal',1,canonical({'conditional_advice':{'version':3}}),'[]'))
        finally:core.close()
        failed,_=run('new-controller-refuses-incompatible-old-body',upgraded,'rollback',success=False)
        assert failed.returncode and 'application_data_compatibility' in failed.stderr
        assert app.state()==now and fetch('/api/instance')['boot_id']==native['boot_id']
        step('rollback-rejected-before-drain',{'passed':True,'application_epoch_unchanged':True,'boot_id_unchanged':True,'new_data_retained':True})
        gate=StopGate(root);gate.stop();stop_token=gate.token()
        target=upgraded/'host/application_release.py';target.write_bytes(target.read_bytes()+b'\n# injected fixture corruption\n')
        broken=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(root.parent/'JarvisLaunch.py'),'--check'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        (output/'tampered-bootstrap.txt').write_text(broken.stdout+broken.stderr,encoding='utf-8');assert broken.returncode
        recovered=recover(root,expected_controller=record['build'],expected_epoch=now['epoch'],expected_build=newbuild)
        fixed=pin.read(root);assert fixed['build']==record['build'] and fixed['controller']!=record['controller']
        assert gate.token()==stop_token and app.state()==now and fetch('/api/instance')['boot_id']==native['boot_id']
        checked=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(root.parent/'JarvisLaunch.py'),'--check'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        (output/'recovered-bootstrap.txt').write_text(checked.stdout+checked.stderr,encoding='utf-8');assert checked.returncode==0
        step('same-controller-native-recovery',{'passed':True,'controller_build':fixed['build'],'fresh_directory':True,'stop_preserved':True,'application_unchanged':True,'boot_id_unchanged':True,'registration_pending':recovered['registration_pending']})
        report['core_scenarios_passed']=True;save()
    finally:
        if live:
            current=pin.read(root);run('fixture-shutdown',Path(current['controller']),'stop')
            assert Applications(root).state()['phase']=='stopped'
            report['fixture_stopped']=True;save()
    assert Applications(daily).state()==oldstate and pin.read(daily)==original
    step('production-untouched',{'passed':True,'production_adopted':False})
    report['passed']=True;save()


if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        Path(sys.argv[1]).mkdir(parents=True,exist_ok=True)
        (Path(sys.argv[1])/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
