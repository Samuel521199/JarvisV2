"""Explicit checked adoption; preserve business data, no fixture import or reset."""
from pathlib import Path
import hashlib,http.cookiejar,json,subprocess,sys,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'docs/evidence/native-mail-2026-11-09')]
from backup_daily import backup
from compare_daily import compare
from adapters.application_host import WorkbenchProcess
from control.local_access import read_key
from host.application_installation import install
from host.application_release import validator
from modules.preferences.store import Preferences
from modules.release_recovery.application import Applications
from sdk.protocol import canonical


def prepare(root,candidates,output):
    output.mkdir(parents=True,exist_ok=False);app=Applications(root)
    packages=json.loads((candidates/'result.json').read_text(encoding='utf-8'));report={}
    for version in ('0.1.6-rc.1','0.1.6'):
        record=app.stage(Path(packages[version]['archive']));checked=app.validate(record['build'],validator(root,reviewed_source=True))
        report[version]={'build':record['build'],'approved':bool(checked.get('approval')),'gate':checked['report']}
        (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if not checked.get('approval'):raise RuntimeError('Daily-root candidate check failed')
        print(json.dumps({'prepared':version,'build':record['build']}),flush=True)


def run(root,candidates,regression,controller,backup_folder,output):
    output.mkdir(parents=True,exist_ok=False)
    full=json.loads((regression/'result.json').read_text(encoding='utf-8'))
    lifecycle=json.loads((controller/'result.json').read_text(encoding='utf-8'))
    if not full['passed'] or full['tests']!=1572 or not lifecycle['passed']:
        raise RuntimeError('Final regression/lifecycle must pass first')
    packages=json.loads((candidates/'result.json').read_text(encoding='utf-8'))
    # The exact reviewed runtime must still match the source about to be adopted.
    with zipfile.ZipFile(packages['0.1.6']['archive']) as archive:
        manifest=json.loads(archive.read('application.json'))
        for name,meta in manifest['files'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=meta['sha256']:
                raise RuntimeError('Runtime changed after validation: '+name)
    app=Applications(root);driver=WorkbenchProcess(root,18282,timeout=45)
    report={'passed':False,'steps':[],'before':app.state()}
    def save():(output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(name):report['steps'].append({'case':name,'passed':True});save();print(json.dumps({'passed':name}),flush=True)
    def catalog():
        prefs=Preferences(root)
        try:
            value=prefs.read();cfg=value['catalog']
            return {'sha256':hashlib.sha256(canonical(value).encode()).hexdigest(),'connections':len(cfg['providers']),
                    'models':sum(len(row['models']) for row in cfg['providers'].values())}
        finally:prefs.close()
    before_catalog=catalog();save()
    try:
        for version in ('0.1.6-rc.1','0.1.6'):app.approved(packages[version]['build'])
        passed('both_candidates_pass_daily_root_bound_independent_gate')
        app.stop(driver);passed('normal_drain_and_stop_without_forced_termination')
        report['backup']=backup(root,backup_folder);save();passed('stopped_business_backup_and_sqlite_integrity')
        for version in ('0.1.6-rc.1','0.1.6'):
            ident=packages[version]['build'];state=app.adopt(ident,driver,expected_epoch=app.state()['epoch'])
            if state['active']['build']!=ident:raise RuntimeError('Adoption did not complete')
            install(root,root.parent,Path(app.record(ident)['path']),port=18282);passed('adopted_and_installed_'+version)
        launch=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(root.parent/'JarvisLaunch.py'),'--no-browser'],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (output/'launch.log').write_bytes(launch.stdout+b'\n'+launch.stderr)
        if launch.returncode:raise RuntimeError('Pinned root launcher failed')
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        q=urllib.request.Request(driver.origin+'/api/local-access',data=canonical({'key':read_key(root)}).encode(),headers={'Origin':driver.origin,'Content-Type':'application/json'})
        client.open(q,timeout=10).close();statuses={}
        for path in ('/','/companion','/companion/native','/settings','/api/instance','/api/standing-work','/api/work-status','/standing-work.js','/assistant-actions.js'):
            with client.open(driver.origin+path,timeout=20) as r:
                statuses[path]=r.status;raw=r.read()
                if path=='/api/instance':assert json.loads(raw)['application_build']==packages['0.1.6']['build']
                if path=='/api/standing-work':assert json.loads(raw)['items']==[]
        report['http']=statuses;passed('pinned_launcher_and_shared_endpoints_live_without_synthetic_business_records')
        report['preservation']=compare(root,backup_folder,expected_new_sessions=1)
        report['catalog']={**catalog(),'unchanged':catalog()==before_catalog}
        if not report['preservation']['passed'] or not report['catalog']['unchanged']:
            raise RuntimeError('Existing-data comparison failed; retain evidence and investigate')
        passed('existing_tables_settings_credentials_sessions_and_asset_metadata_preserved')
        report['after']=app.state();report['passed']=True;save()
    except BaseException as e:
        report['error']={'type':type(e).__name__,'message':str(e)};report['after']=app.state();save()
        # No data rollback, destructive cleanup, forced termination or blind retry.
        raise


if __name__=='__main__':run(*[Path(p).resolve() for p in sys.argv[1:]])
