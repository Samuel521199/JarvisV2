"""Owner-authorized local upgrade/rollback proof. No model or email calls.

Only the development fixture is created. Daily business rows are compared to
the stopped backup, never replaced. Auth cookies and private contents stay local.
"""
from datetime import datetime,timezone
import hashlib,http.client,http.cookiejar,json
from pathlib import Path
import subprocess,sys,threading,time,urllib.request

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'docs/evidence/assistant-release-2026-11-09'))
from backup_daily import table_hashes
from compare_daily import without_checked,browser_sessions
from control.local_access import read_key
from sdk.protocol import canonical
from tools.workstation import state,controller,release,start_daily,apply


def meta(port):
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        connection.request('GET','/api/instance');response=connection.getresponse()
        if response.status!=200:return None
        return json.loads(response.read(16384))
    except (OSError,ValueError):return None
    finally:connection.close()


if __name__=='__main__':
    daily=Path('D:/Jarvis-runtime/user-data');dev=ROOT/'user-data'
    target=dev/'state/workstation-acceptance.json'
    assert not target.exists(),'Keep the prior acceptance; do not blindly replay upgrades'
    report={'passed':False,'started_utc':datetime.now(timezone.utc).isoformat(),'steps':[],'paid_model_calls':0,'emails_sent':0}
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(name,**data):report['steps'].append({'case':name,'passed':True,**data});save();print(json.dumps({'passed':name}),flush=True)
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    origin='http://127.0.0.1:18282'
    def get(path):
        with client.open(origin+path,timeout=10) as response:return json.load(response)
    request=urllib.request.Request(origin+'/api/local-access',data=canonical({'key':read_key(daily)}).encode(),
        headers={'Origin':origin,'Content-Type':'application/json'})
    client.open(request,timeout=5).close();before_daily=meta(18282);before_dev=meta(18283)
    assert before_daily and before_dev and before_daily['root_digest']!=before_dev['root_digest']
    report['before']=state(daily);report['daily_boot_before']=before_daily['boot_id'];report['dev_boot_before']=before_dev['boot_id'];save()
    samples=[];stop=threading.Event()
    def sample():
        while not stop.is_set():
            samples.append({'at':time.monotonic(),'daily':bool(meta(18282)),'development':bool(meta(18283))});stop.wait(.25)
    watcher=threading.Thread(target=sample);watcher.start()
    try:
        # Creating and restarting only development must not restart daily.
        result=subprocess.run([sys.executable,'-X','utf8','-m','tools.workstation','restart-development'],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8',timeout=90)
        (HERE/'restart-development.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        assert result.returncode==0,result.stderr
        assert meta(18282)['boot_id']==before_daily['boot_id']
        before_dev=meta(18283);passed('development_restart_keeps_daily_boot_and_data_root')
        # A marker outside runtime source is explicitly development-only.
        marker=dev/'state/single-pc-fixture.txt';marker.write_text('Synthetic local development fixture, not a daily task.\n',encoding='utf-8')
        assert not (daily/'state/single-pc-fixture.txt').exists()
        passed('development_write_not_in_daily')
        receipt=apply(daily,dev);assert receipt['passed'];report['update']=receipt;save()
        assert meta(18283)['boot_id']==before_dev['boot_id']
        assert get('/api/chats') is not None  # same pre-upgrade cookie, no second unlock
        passed('prepared_upgrade_preserves_development_and_browser_session',version=receipt['after']['active']['version'])
        candidate=receipt['after']['active']['build'];baseline=receipt['before']['active']['build']
        restored=release(daily,'rollback');assert restored['active']['build']==baseline
        assert get('/api/commitments') is not None
        assert meta(18283)['boot_id']==before_dev['boot_id']
        passed('actual_recorded_baseline_rollback_with_same_cookie',epoch=restored['epoch'])
        upgraded=release(daily,'adopt','--build',candidate,'--expected-epoch',restored['epoch'])
        assert upgraded['active']['build']==candidate and upgraded['previous']['build']==baseline
        release(daily,'install-launcher');start_daily(daily)
        assert get('/api/chats') is not None and meta(18283)['boot_id']==before_dev['boot_id']
        passed('upgrade_again_and_pinned_launcher_reuses_service',epoch=upgraded['epoch'])
        # Compare semantic rows from the utility's stopped snapshot after all transitions.
        backup=Path(receipt['backup']['folder']);inventory=json.loads((backup/'inventory.json').read_text(encoding='utf-8'))
        changes=[];derived=[];tables=0
        for name in inventory['files']:
            if name.endswith('.sqlite3') and not name.startswith('deployment/'):
                before=table_hashes(backup/name);after=table_hashes(daily/name)
                for table,value in before.items():
                    tables+=1
                    if after.get(table)==value:continue
                    if table=='task_completion' and without_checked(backup/name)==without_checked(daily/name):derived.append(name+':'+table)
                    else:changes.append({'database':name,'table':table})
        private_changes=[];config_changes=[]
        for name,entry in inventory['files'].items():
            if (name.startswith(('config/','sessions/')) and not name.endswith('.sqlite3')) or (name.endswith('.dpapi') and name!='private/workbench-sessions.dpapi'):
                if hashlib.sha256((daily/name).read_bytes()).hexdigest()!=entry['sha256']:
                    (private_changes if name.endswith('.dpapi') else config_changes).append(name)
        session_result=browser_sessions(daily,backup,0)
        assert not changes and not private_changes and not config_changes and session_result['passed']
        report['preservation']={'existing_tables_checked':tables,'business_changes':changes,'derived_check_time_changes':derived,
            'dpapi_changes':private_changes,'config_session_changes':config_changes,'browser_sessions':session_result}
        passed('existing_business_settings_credentials_and_active_session_preserved')
        report['after']=state(daily);report['passed']=True
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        stop.set();watcher.join(timeout=5);report['samples']={'observations':len(samples),
            'development_unavailable_observations':sum(not s['development'] for s in samples),
            'daily_unavailable_observations':sum(not s['daily'] for s in samples),
            'scope':'includes intentional development restart and three daily version handoffs; not a long-term uptime metric'}
        report['completed_utc']=datetime.now(timezone.utc).isoformat();save()
        # Safe aggregate evidence only, no backups, secrets or business row hashes.
        public={key:value for key,value in report.items() if key not in {'update'}}
        if report.get('update'):public['update_summary']={'backup':report['update']['backup'],'passed':report['update']['passed']}
        (HERE/'acceptance.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'version':report['after']['active']['version'],'epoch':report['after']['epoch']}))
