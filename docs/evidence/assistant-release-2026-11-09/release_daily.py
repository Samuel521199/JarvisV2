"""Adopt the independently checked local candidates after full regression.

An explicit operator action, not an updater daemon. Existing business data is
backed up/compared, never replaced by a fixture or restored to an old snapshot.
"""
from pathlib import Path
import hashlib,http.cookiejar,json,subprocess,sys,urllib.request,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT),str(HERE)]
from backup_daily import backup
from compare_daily import compare
from adapters.application_host import WorkbenchProcess
from control.local_access import read_key
from host.application_installation import install
from host.application_release import tracked_runtime
from modules.preferences.store import Preferences
from modules.release_recovery.application import Applications
from sdk.protocol import canonical


def run(root,archives,backup_folder):
    result_path=ROOT/'user-data/daily-adoption-20261109.json'
    if result_path.exists():raise RuntimeError('Preserve the prior adoption record; do not repeat blindly')
    regression=json.loads((ROOT/'user-data/full-regression-r2/result.json').read_text(encoding='utf-8'))
    if not regression['passed'] or regression['tests']!=1531:raise RuntimeError('Full regression has not passed')
    candidates=json.loads((ROOT/'user-data/daily-candidates-20261109.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archives/'0.1.4.zip') as archive:manifest=json.loads(archive.read('application.json'))
    if set(manifest['files'])!=set(tracked_runtime(ROOT)):raise RuntimeError('Runtime inventory changed')
    for name,meta in manifest['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=meta['sha256']:raise RuntimeError('Runtime changed: '+name)
    app=Applications(root);driver=WorkbenchProcess(root,18282,timeout=45)
    report={'passed':False,'steps':[],'backup':None,'preservation':None}
    def save():result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(name):report['steps'].append({'case':name,'passed':True});save();print(json.dumps({'passed':name}),flush=True)
    def catalog():
        prefs=Preferences(root)
        try:
            value=prefs.read();cfg=value['catalog']
            return {'sha256':hashlib.sha256(canonical(value).encode()).hexdigest(),'connections':len(cfg['providers']),
                    'models':sum(len(row['models']) for row in cfg['providers'].values())}
        finally:prefs.close()
    before_catalog=catalog();report['before']=app.state();save()
    try:
        for value in candidates.values():app.approved(value['build'])
        app.stop(driver);passed('normal_drain_and_stop')
        report['backup']=backup(root,backup_folder);save();passed('stopped_backup_and_integrity')
        baseline=candidates['0.1.4-rc.1']['build'];stable=candidates['0.1.4']['build']
        state=app.adopt(baseline,driver,expected_epoch=app.state()['epoch'])
        if state['active']['build']!=baseline:raise RuntimeError('Baseline adoption did not complete')
        install(root,root.parent,Path(app.record(baseline)['path']),port=18282);passed('compatible_baseline_adopted_and_launcher_installed')
        state=app.adopt(stable,driver,expected_epoch=state['epoch'])
        if state['active']['build']!=stable or state['previous']['build']!=baseline:raise RuntimeError('Stable adoption did not complete')
        install(root,root.parent,Path(app.record(stable)['path']),port=18282);passed('stable_adopted_and_launcher_installed')
        launch=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(root.parent/'JarvisLaunch.py'),'--no-browser'],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (ROOT/'user-data/daily-launch-20261109.log').write_bytes(launch.stdout+b'\n'+launch.stderr)
        if launch.returncode:raise RuntimeError('Installed root launcher failed')
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        req=urllib.request.Request(driver.origin+'/api/local-access',data=canonical({'key':read_key(root)}).encode(),
            headers={'Origin':driver.origin,'Content-Type':'application/json'})
        client.open(req,timeout=5).close()
        statuses={}
        for path in ('/','/companion','/settings','/api/instance','/api/commitments','/api/work-status','/assistant-commitments.js','/commitments.js'):
            with client.open(driver.origin+path,timeout=20) as response:
                statuses[path]=response.status;response.read()
        report['http']=statuses;passed('installed_launcher_and_shared_http_endpoints')
        report['preservation']=compare(root,backup_folder,expected_new_sessions=1)
        report['catalog']={**catalog(),'unchanged':catalog()==before_catalog}
        if not report['preservation']['passed'] or not report['catalog']['unchanged']:raise RuntimeError('Data preservation check did not pass')
        passed('existing_business_settings_credentials_and_asset_metadata_preserved')
        report['after']=app.state();report['passed']=True;save()
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};report['after']=app.state();save();raise
    print(json.dumps({'passed':True,'version':report['after']['active']['version'],'epoch':report['after']['epoch']}),flush=True)


if __name__=='__main__':run(*map(lambda v:Path(v).resolve(),sys.argv[1:]))
