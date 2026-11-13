"""Disposable native-host proof plus focused and independent package checks.

No daily data, model calls or external actions; keep each run directory unique.
"""
import hashlib,json,socket,subprocess,sys,time,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from adapters.application_host import WorkbenchProcess
from host.core import Core
from host.application_release import tracked_runtime,validator
from modules.release_recovery.application import Applications,build
from sdk.protocol import CoreError


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    root=work/'data';Core.initialize(root).close();app=Applications(root)
    archive=work/'candidate.zip';ident=build(ROOT,tracked_runtime(ROOT),archive,(ROOT/'VERSION').read_text().strip())
    app.stage(archive);checked=app.validate(ident,validator(root,reviewed_source=True))
    proof=checked['approval']['receipt']['report'];assert proof['passed']
    report={'scope':'disposable new data and real managed Host; no daily adoption/model/email','passed':False,
        'build':ident,'independent_gate':proof,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ['tools/workstation.py','modules/release_recovery/application.py','host/application_release.py',
                         'tests/test_development_workstation.py','tests/test_application_release.py']}}
    with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
    driver=WorkbenchProcess(root,port,timeout=15)
    try:
        app.adopt(ident,driver);initial=app.state();before=driver.metadata()
        # Restart the same healthy package to produce a genuine newer epoch.
        app.stop(driver);app.start(driver);new=app.state();live=driver.metadata()
        assert new['epoch']>initial['epoch'] and live['boot_id']!=before['boot_id']
        try:app.stop(driver,expected_epoch=initial['epoch'],expected_build=ident)
        except CoreError as error:assert error.code=='application_epoch'
        else:raise AssertionError('Stale conditional stop was allowed')
        assert app.state()==new and driver.metadata()['boot_id']==live['boot_id']
        driver.health(new['active'],new['epoch'])
        report['native_stale_stop']={'rejected':True,'live_boot_unchanged':True,'control_state_unchanged':True}
        # Exercise the actual CLI flag path, not only the Python domain method.
        command=[sys.executable,'-X','utf8','-I','-B',str(ROOT/'apps/development/releases.py'),'stop',
            '--data-root',str(root),'--port',str(port),'--expected-epoch',str(initial['epoch']),'--build',ident]
        refused=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=20)
        assert refused.returncode and driver.metadata()['boot_id']==live['boot_id']
        command[command.index('--expected-epoch')+1]=str(new['epoch'])
        stopped=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=25)
        assert stopped.returncode==0,stopped.stderr
        assert app.state()['phase']=='stopped'
        report['native_cli']={'stale_rejected':True,'matching_stop_succeeded':True};report['passed']=True
    finally:
        if app.state()['phase']=='active':app.stop(driver)
        for process in driver.processes.values():process.wait(timeout=10)
        report['owned_processes_stopped']=all(process.poll() is not None for process in driver.processes.values())
        (HERE/'native-result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    script=('import unittest,sys,time,json;'
        's=unittest.TestSuite(unittest.TestLoader().discover("tests",pattern=p) for p in '
        +repr(['test_development_workstation.py','test_application_release.py','test_application_compatibility.py','test_application_runtime.py'])+' );'
        't=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(s);'
        'print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),seconds=round(time.monotonic()-t,3))));sys.exit(not r.wasSuccessful())')
    result=subprocess.run([sys.executable,'-X','utf8','-B','-c',script],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
    (HERE/'regression.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    summary=json.loads(result.stdout.strip().splitlines()[-1]);summary['passed']=result.returncode==0
    (HERE/'regression.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    assert not result.returncode
    print(json.dumps({'native_passed':report['passed'],'independent':proof['tests_summary'],'focused':summary}))
