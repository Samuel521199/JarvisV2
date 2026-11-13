"""Explicit single-PC operator commands; no updater daemon or dependency install.

Daily lifecycle and candidate validation run from the pinned daily controller,
not from candidate-supplied tests. Development credentials remain proxy-only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import uuid
import zipfile

from control.atomic import write_json
from control.credentials import load_envelope
from control.development_profile import read,client_secret
from control.paths import data_root,reject_links
from control.recovery.gate import RunLock
from host.application_release import tracked_runtime
from sdk.protocol import CoreError
from sdk.protocol import canonical

SOURCE=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def state(root):
    db=sqlite3.connect((root/'deployment/control.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:return json.loads(db.execute('SELECT body FROM status WHERE id=1').fetchone()[0])
    finally:db.close()


def roots(development):
    development=data_root(development);profile=read(development)
    if not profile or not profile.get('production_data'):raise ValueError('Configure the development profile first')
    daily=data_root(profile['production_data'])
    if development==daily or development in daily.parents or daily in development.parents:
        raise ValueError('Daily and development data must stay in separate trees')
    if not (daily.parent/'JarvisLaunch.py').is_file():raise ValueError('A managed daily installation is required')
    return daily,development


def controller(root):
    """Verify every installed controller byte before executing its entry point."""
    meta=json.loads((root/'deployment/launcher.json').read_text(encoding='utf-8'))
    folder=Path(meta['controller']).resolve();reject_links(folder)
    if folder.parent!=root/'deployment/controllers':raise ValueError('Controller is outside the installation')
    index=folder/'controller-files.json'
    if sha(index)!=meta['controller_inventory_sha256']:raise ValueError('Controller inventory changed')
    for name,digest in json.loads(index.read_text(encoding='utf-8')).items():
        path=(folder/name).resolve();reject_links(path)
        if not path.is_relative_to(folder) or sha(path)!=digest:raise ValueError('Installed controller changed')
    return folder,int(meta['port'])


def release(root,action,*options):
    folder,port=controller(root)
    result=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(folder/'apps/development/releases.py'),action,
        '--data-root',str(root),'--port',str(port),*map(str,options)],capture_output=True,text=True,encoding='utf-8',
        timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Daily controller refused '+action+'; '+result.stderr[-1200:])
    return json.loads(result.stdout)


def start_daily(root):
    controller(root)
    result=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(root.parent/'JarvisLaunch.py'),'--no-browser'],
        capture_output=True,text=True,encoding='utf-8',timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Daily startup refused; '+result.stderr[-1200:])
    return {'running':True,'state':state(root)}


def instance(port):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        conn.request('GET','/api/instance');response=conn.getresponse()
        return json.loads(response.read(16384)) if response.status==200 else None
    except (OSError,ValueError):return None
    finally:conn.close()


def repair_link(daily,development):
    """Rebind an existing identical grant; never silently create/expand a grant."""
    daily=data_root(daily);development=data_root(development);profile=read(development)
    if daily==development or daily in development.parents or development in daily.parents:
        raise ValueError('Daily and development data must stay separate')
    grant=load_envelope(daily/'private/development-bridge.dpapi')
    if not profile or grant!=client_secret(development) or profile['client_id']!=grant['client_id']:
        raise ValueError('Existing grants do not match; no credentials or policy were changed')
    if profile['allowed_providers']!=grant['allowed_providers']:raise ValueError('Sharing policy differs')
    controller(daily)
    bridge_port=int(profile['bridge_origin'].rsplit(':',1)[1])
    conn=http.client.HTTPConnection('127.0.0.1',bridge_port,timeout=1)
    try:
        conn.connect();raise ValueError('Stop the existing development proxy before changing the link')
    except OSError:pass
    finally:conn.close()
    backups=development/'state/workstation-link-backups';backups.mkdir(exist_ok=True)
    original=development/'config/development.json';shutil.copyfile(original,backups/(uuid.uuid4().hex+'.json'))
    profile['production_data']=str(daily);write_json(original,profile)
    return {'daily_data':str(daily),'development_data':str(development),'grant_preserved':True,'external_actions':False}


def backup(root,destination):
    """Consistent small-data snapshot after stop; never automatically restored."""
    destination=destination.resolve();reject_links(destination)
    if destination==root or root in destination.parents:raise ValueError('Backup must be outside daily user-data')
    with RunLock(root,'application-release'),RunLock(root,'workbench-host'):
        if state(root)['phase']!='stopped':raise ValueError('Stop the managed Host before backup')
        destination.mkdir(parents=True,exist_ok=False);files={};databases=0
        sources=[]
        for folder in ('config','private','sessions','state'):
            sources.extend(p for p in (root/folder).rglob('*') if p.is_file())
        sources.extend(p for p in [root/'deployment/control.sqlite3',root/'deployment/launcher.json'] if p.exists())
        for source in sources:
            name=source.relative_to(root).as_posix()
            if source.suffix=='.lock' or name.endswith(('-wal','-shm')):continue
            reject_links(source);target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
            if source.suffix=='.sqlite3':
                original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);copy=sqlite3.connect(target)
                try:
                    original.backup(copy)
                    if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup integrity failed')
                finally:copy.close();original.close()
                databases+=1
            else:shutil.copy2(source,target)
            files[name]={'sha256':sha(target),'bytes':target.stat().st_size}
        write_json(destination/'inventory.json',{'schema':1,'root':str(root),'files':files,
            'scope':'stopped config/private/sessions/state plus deployment journal; no asset bodies, model weights or external project folders; not an automatic rollback source'})
        return {'folder':str(destination),'files':len(files),'sqlite_integrity_ok':databases}


def prepare(root,development,source):
    source=source.resolve();names=tracked_runtime(source)
    # Never silently ship only the tracked half of a newly added runtime feature.
    untracked=subprocess.check_output(['git','-C',str(source),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
    from modules.release_recovery.application import TOPS
    if any(name and name.split('/')[0] in TOPS for name in untracked):
        raise ValueError('Review/register new runtime files before packaging; untracked runtime files were not silently omitted')
    frozen={name:sha(source/name) for name in names}
    expected=state(root)['epoch'];archive=development/'state/workstation-releases'/(uuid.uuid4().hex+'.zip')
    archive.parent.mkdir(exist_ok=True)
    built=release(root,'build','--source',source,'--archive',archive,'--version',(source/'VERSION').read_text().strip())
    ident=built['build']
    with zipfile.ZipFile(archive) as stream:manifest=json.loads(stream.read('application.json'))
    if hashlib.sha256(canonical(manifest).encode()).hexdigest()!=ident:
        raise ValueError('Built manifest does not match the candidate identity')
    candidate_files={name:meta['sha256'] for name,meta in manifest['files'].items()}
    if candidate_files!=frozen:raise ValueError('Source changed during candidate build; prepare again')
    release(root,'stage','--archive',archive)
    checked=release(root,'validate','--build',ident,'--reviewed-source')
    if not checked.get('approval'):raise ValueError('Candidate validation failed; daily Host was not stopped')
    if set(tracked_runtime(source))!=set(candidate_files) or any(sha(source/name)!=digest for name,digest in candidate_files.items()):
        raise ValueError('Source changed during candidate validation; prepare again')
    record={'schema':1,'daily_data':str(root),'source':str(source),'build':ident,'expected_epoch':expected,
        'created_utc':datetime.now(timezone.utc).isoformat(),'files':candidate_files,
        'validation':checked['approval']['receipt']['report']}
    write_json(development/'state/workstation-update.json',record)
    return {'prepared_build':ident,'expected_epoch':expected,'validation':record['validation'],'daily_restarted':False}


def require_prepared(root,record):
    if record.get('daily_data')!=str(root):raise ValueError('Prepared candidate belongs to another installation')
    if state(root)['epoch']!=record['expected_epoch']:raise ValueError('Daily baseline changed; prepare again')
    source=Path(record['source'])
    if set(tracked_runtime(source))!=set(record['files']) or any(sha(source/name)!=digest for name,digest in record['files'].items()):
        raise ValueError('Source changed after validation; prepare again')


def preflight(root,ident):
    # Read the existing signed controller receipt and target data requirements;
    # do not import or execute candidate code to decide its own admission.
    from modules.release_recovery.application import Applications
    from control.application_compatibility import require_compatible
    record=Applications(root).approved(ident)
    return require_compatible(root,record['path'])


def conditional_stop(root,expected_epoch,expected_build):
    # The reviewed operator's transition uses the same persistent journal/OS
    # lock as every installed controller, including older versions. Candidate
    # validation and adoption still use the independently pinned controller.
    from modules.release_recovery.application import Applications
    from adapters.application_host import WorkbenchProcess
    _,port=controller(root)
    return Applications(root).stop(WorkbenchProcess(root,port),expected_epoch=expected_epoch,expected_build=expected_build)


def apply(root,development):
    record=json.loads((development/'state/workstation-update.json').read_text(encoding='utf-8'));require_prepared(root,record)
    before=state(root)
    if before['active'] and before['active']['build']==record['build']:
        return {'unchanged':True,'state':before}
    checked=release(root,'status')
    if checked['phase']!='active':raise ValueError('Start daily normally before applying an update')
    if checked['epoch']!=record['expected_epoch'] or checked['active']!=before['active']:
        raise ValueError('Daily baseline changed; prepare again')
    # Reject stale approval and incompatible data BEFORE the maintenance window.
    preflight(root,record['build'])
    conditional_stop(root,record['expected_epoch'],before['active']['build'])
    receipt={'schema':1,'before':before,'build':record['build'],'backup':None,'after':None,'passed':False}
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    try:
        receipt['backup']=backup(root,root.parent/'backups'/name)
        adopted=release(root,'adopt','--build',record['build'],'--expected-epoch',record['expected_epoch'])
        if adopted['phase']!='active' or adopted['active']['build']!=record['build']:
            raise ValueError('Candidate was not adopted; inspect controller recovery result')
        release(root,'install-launcher');start_daily(root)
        receipt.update(after=state(root),passed=True)
        return receipt
    except BaseException:
        # Only an untouched stopped baseline may be restarted here. In-flight,
        # blocked and STOP states remain owned by the existing recovery controls.
        current=state(root)
        if current['phase']=='stopped' and current['active']==before['active']:start_daily(root)
        raise
    finally:
        receipt['after']=state(root);write_json(development/'state/workstation-last-update.json',receipt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','repair-link','start-daily','start-development','restart-development','stop-development','prepare-update','apply-update','rollback'])
    parser.add_argument('--development-data',type=Path,default=SOURCE/'user-data')
    parser.add_argument('--daily-data',type=Path);parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--open-browser',action='store_true')
    parser.add_argument('--reviewed-source',action='store_true');args=parser.parse_args()
    if args.action=='repair-link':
        if not args.daily_data:parser.error('repair-link requires --daily-data')
        result=repair_link(args.daily_data,args.development_data)
    else:
        daily,dev=roots(args.development_data)
        if args.action=='status':
            _,port=controller(daily);live=instance(port);expected=hashlib.sha256(str(daily).casefold().encode()).hexdigest()
            dev_live=instance(18283);dev_expected=hashlib.sha256(str(dev).casefold().encode()).hexdigest()
            result={'daily_data':str(daily),'development_data':str(dev),'daily_state':state(daily),
                'daily_online':bool(live and live.get('root_digest')==expected),'development_online':bool(dev_live and dev_live.get('root_digest')==dev_expected)}
        elif args.action=='start-daily':result=start_daily(daily)
        elif args.action in {'start-development','restart-development','stop-development'}:
            from host.development_runtime import start,stop
            if args.action in {'restart-development','stop-development'}:stop(dev,18283)
            result=start(dev,daily,18283) if args.action!='stop-development' else {'development_stopped':True}
        elif args.action=='prepare-update':
            if not args.reviewed_source:parser.error('prepare-update requires --reviewed-source after review')
            result=prepare(daily,dev,args.source)
        elif args.action=='apply-update':result=apply(daily,dev)
        else:
            # rollback uses current data and compatibility checks; no business restore.
            before=state(daily)
            if not before['previous']:raise ValueError('No previous adopted package is recorded')
            result=release(daily,'rollback')
            if result['active']['build']!=before['previous']['build']:raise ValueError('Rollback failed')
        if args.open_browser and args.action=='start-daily':
            import webbrowser
            from apps.workbench.launch import access_url
            _,port=controller(daily)
            webbrowser.open(access_url('http://127.0.0.1:'+str(port)+'/',daily))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
