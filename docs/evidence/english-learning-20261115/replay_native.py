"""Recheck rollback with truly read-only observers; retain initial harness failure."""
from pathlib import Path
import hashlib,json,os,shutil,sqlite3,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent/'native';sys.path.insert(0,str(ROOT))
from control.controller_pin import read
from modules.release_recovery.application import Applications
from host.application_release import tracked_runtime

def main():
    report=json.loads((OUT/'result.json').read_text());assert not report['passed']
    shutil.copy2(OUT/'result.json',OUT/'result-initial.json')
    root=Path(report['root']);app=Applications(root);controller=Path(read(root)['controller']);port=report['port']
    candidate=next(s['result']['build'] for s in report['steps'] if s['name']=='candidate-build');fallback=json.loads((OUT.parent/'recovery-build.json').read_text())['build']
    manifest=json.loads((Path(app.approved(candidate)['path'])/'application.json').read_text())
    assert set(manifest['files'])==set(tracked_runtime(ROOT))
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    daily=Path('E:/Jarvis/runtime/user-data');daily_state=Applications(daily).state();daily_pin=read(daily)
    def run(name,action,*args):
        p=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port),*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
        (OUT/(name+'.txt')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,name
        report['steps'].append({'name':name,'result':json.loads(p.stdout)});print(name,flush=True)
    def observe():
        path=root/'state/english-learning.sqlite3';db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:
            value={table:db.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall() for table in ('settings','exercises','assessments','jobs')}
            assert value['exercises'][0][3]==1 and value['jobs'][0][4]=='INVALIDATED'
            assert not value['assessments'] and db.execute('PRAGMA user_version').fetchone()[0]==1
        finally:db.close()
        return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'records':value}
    before=observe();run('r2-start-full','start')
    try:
        run('r2-real-rollback','rollback');assert app.state()['active']['build']==fallback;assert observe()==before
        assert 'normal checkpoint allowed' in (OUT/'readonly-guard.txt').read_text()
        run('r2-readopt-full','adopt','--build',candidate,'--expected-epoch',app.state()['epoch']);assert observe()==before
        report['steps'].append({'name':'r2-readonly-byte-and-record-preservation','result':{'passed':True,'sha256':before['sha256'],'withdrawal_preserved':True,'test_only_fix':'Original final Store constructor issued PRAGMA user_version=1. Replaced observer with SQLite mode=ro; runtime bytes unchanged.'}})
    finally:run('r2-stop-fixture','stop')
    assert app.state()['phase']=='stopped' and Applications(daily).state()==daily_state and read(daily)==daily_pin
    report.update(passed=True,fixture_stopped=True,candidate_build=candidate,fallback_build=fallback,production_untouched=True)
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('Native replay passed',flush=True)
if __name__=='__main__':main()
