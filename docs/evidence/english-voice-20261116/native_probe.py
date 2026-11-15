"""Native daily/controller compatibility rehearsal, isolated from business data."""
from pathlib import Path
import hashlib,json,os,socket,sqlite3,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent/'native';sys.path.insert(0,str(ROOT))
from control import controller_pin as pin
from host.application_controller import promote,policy
from modules.release_recovery.application import Applications
from modules.english_learning.store import Store
from sdk.protocol import digest
from tools.workstation import instance

def main():
    OUT.mkdir(exist_ok=False);work=Path('E:/Jarvis/validation/english-voice-native-20261116');work.mkdir(exist_ok=False)
    root=work/'installation/user-data';root.mkdir(parents=True)
    daily=Path('E:/Jarvis/runtime/user-data');oldpin=pin.read(daily);oldstate=Applications(daily).state();frozen=Path(oldpin['controller']);oldbuild=oldstate['active']['build']
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=os.environ.copy();temp=work/'temp';temp.mkdir();env.update(TEMP=str(temp),TMP=str(temp))
    report={'passed':False,'root':str(root),'port':port,'production_adopted':False,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'steps':[]}
    def step(name,value):
        report['steps'].append({'name':name,'result':value});(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(name,flush=True)
    def run(name,controller,action,*args,success=True):
        cmd=[sys.executable,'-X','utf8','-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port),*map(str,args)]
        p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=240)
        (OUT/(name+'.txt')).write_text(p.stdout+p.stderr,encoding='utf-8')
        try:value=json.loads(p.stdout)
        except ValueError:value={'exit_code':p.returncode}
        step(name,value)
        if success and p.returncode:raise RuntimeError(name+' failed')
        return p,value
    code='import sys;sys.path.insert(0,'+repr(str(frozen))+');from host.core import Core;Core.initialize('+repr(str(root))+').close()'
    subprocess.run([sys.executable,'-I','-B','-c',code],env=env,check=True,capture_output=True)
    package=Path(Applications(daily).approved(oldbuild)['path']);manifest=json.loads((package/'application.json').read_text())
    with zipfile.ZipFile(work/'baseline.zip','x',zipfile.ZIP_DEFLATED) as stream:
        for name in ['application.json',*manifest['files']]:stream.write(package/name,name)
    run('baseline-stage',frozen,'stage','--archive',work/'baseline.zip')
    run('baseline-validation',frozen,'validate','--build',oldbuild,'--reviewed-source')
    _,candidate=run('candidate-build',frozen,'build','--source',ROOT,'--archive',work/'candidate.zip','--version','0.1.12');newbuild=candidate['build']
    run('candidate-stage',frozen,'stage','--archive',work/'candidate.zip')
    _,qualified=run('candidate-validation',frozen,'validate','--build',newbuild,'--reviewed-source');assert qualified.get('approval')
    fallback=json.loads((OUT.parent/'recovery-build.json').read_text())
    run('fallback-stage',frozen,'stage','--archive',fallback['archive'])
    _,qualified=run('fallback-validation',frozen,'validate','--build',fallback['build'],'--reviewed-source');assert qualified.get('approval')
    app=Applications(root);live=False
    try:
        run('baseline-adopt',frozen,'adopt','--build',oldbuild);live=True
        run('baseline-install',frozen,'install-launcher');before=app.state();boot=instance(port);old=pin.read(root);_,fingerprint=policy(root,old)
        promoted=promote(root,newbuild,expected_epoch=before['epoch'],expected_build=oldbuild,expected_controller=digest(old),reviewed_source=True)
        assert app.state()==before and instance(port)['boot_id']==boot['boot_id']
        current=pin.read(root);assert current['controller_protocol']==8 and current['policy_sha256']==fingerprint
        step('controller8-same-boot-fixed-policy',{'passed':True,'policy_sha256':fingerprint,'registration_pending':promoted['registration_pending']})
        controller=Path(current['controller'])
        run('fallback-adopt',controller,'adopt','--build',fallback['build'],'--expected-epoch',app.state()['epoch'])
        run('candidate-adopt',controller,'adopt','--build',newbuild,'--expected-epoch',app.state()['epoch'])
        store=Store(root)
        try:
            store.db.execute("INSERT INTO exercises VALUES(?,?,?,?,?,?)",('english-withdrawn-sentinel','unlinked',json.dumps({'prompt':'synthetic withdrawn fixture'}),1,0,0))
            store.db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",('english-readonly-sentinel','unlinked','question','{}','INVALIDATED',None,None))
        finally:store.close()
        path=root/'state/english-learning.sqlite3';prior=hashlib.sha256(path.read_bytes()).hexdigest();before=app.state();boot=instance(port)
        p,_=run('incompatible-original-refused',controller,'adopt','--build',oldbuild,success=False)
        assert p.returncode and 'application_data_compatibility' in p.stderr
        assert app.state()==before and instance(port)['boot_id']==boot['boot_id']
        step('refused-before-drain',{'passed':True,'same_boot':True,'same_epoch':True})
        run('compatible-code-only-rollback',controller,'rollback')
        assert app.state()['active']['build']==fallback['build'] and hashlib.sha256(path.read_bytes()).hexdigest()==prior
        fallback_source=Path(app.approved(fallback['build'])['path'])
        code='''import sys
sys.path.insert(0,sys.argv[1])
from host.english_learning import checkpoint
from sdk.protocol import CoreError
checkpoint(sys.argv[2],'normal-chat')
try:checkpoint(sys.argv[2],'english-readonly-sentinel')
except CoreError as exc:assert exc.code=='english_readonly'
else:raise AssertionError('Queued learning was not refused')
print('normal checkpoint allowed; stored learning refused before model dispatch')
'''
        p=subprocess.run([sys.executable,'-I','-B','-c',code,str(fallback_source),str(root)],capture_output=True,text=True,timeout=30)
        (OUT/'readonly-guard.txt').write_text(p.stdout+p.stderr);assert p.returncode==0
        assert hashlib.sha256(path.read_bytes()).hexdigest()==prior
        run('return-to-full-learning',controller,'adopt','--build',newbuild,'--expected-epoch',app.state()['epoch'])
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:assert db.execute('SELECT withdrawn FROM exercises WHERE id=?',('english-withdrawn-sentinel',)).fetchone()[0]==1
        finally:db.close()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==prior
        step('records-and-withdrawal-preserved-across-real-rollback',{'passed':True,'learning_store_sha256':prior,'guard_no_model_dispatch':True})
    finally:
        if live:
            run('fixture-stop',Path(pin.read(root)['controller']),'stop');assert app.state()['phase']=='stopped'
            report['fixture_stopped']=True
    assert Applications(daily).state()==oldstate and pin.read(daily)==oldpin
    report.update(passed=True,candidate_build=newbuild,fallback_build=fallback['build'],production_untouched=True)
    step('complete',{'passed':True})
if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        OUT.mkdir(exist_ok=True);(OUT/'failure.txt').write_text(traceback.format_exc());raise
