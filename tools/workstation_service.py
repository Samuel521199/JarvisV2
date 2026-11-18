"""Owner-enabled daily startup and reviewed-candidate updates, separate from development.

The installed copy runs against a hash-pinned existing controller and operator.
It never pulls Git, installs dependencies, approves source or restores old data.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import argparse
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

from control.application_runtime import LocalApprovals,coordination
from control.atomic import write_json
from control.local_access import read_key
from control.paths import reject_links
from control.recovery.gate import StopGate
from adapters.application_host import WorkbenchProcess
from modules.release_recovery.application import Applications,inspect_package
from control.application_compatibility import require_compatible
from sdk.protocol import canonical,CoreError,decode

SCHEMA=1
POLICY_SCHEMA=2
PASSIVE_SECONDS=3600
ACTIVE_SECONDS=30


def base(root):
    path=Path(root).resolve()/'deployment/automation';reject_links(path)
    return path


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):
    reject_links(path)
    if path.stat().st_size>4*1024**2:raise ValueError('Automation record exceeds limit')
    return json.loads(path.read_text(encoding='utf-8'))


def signed(root,path,value):
    write_json(path,{'value':value,'signature':LocalApprovals(root).sign(value)})


def verified(root,path):
    envelope=read(path)
    if set(envelope)!={'value','signature'}:raise ValueError('Invalid signed automation record')
    LocalApprovals(root).verify(envelope['value'],envelope['signature'])
    return envelope['value']


def policy(root):
    value=verified(root,base(root)/'policy.json')
    if (value.get('schema')!=POLICY_SCHEMA or value.get('daily_data')!=str(Path(root).resolve())
            or type(value.get('enabled')) is not bool or type(value.get('auto_updates')) is not bool
            or value.get('development_autostart') is not False
            or value.get('poll_seconds')!=PASSIVE_SECONDS or value.get('active_seconds')!=ACTIVE_SECONDS
            or value.get('offline_restart') is not False or value.get('source_notification') is not True
            or value.get('idle_seconds')!=60
            or value.get('observation_seconds')!=180 or value.get('restart_limit')!=3):
        raise ValueError('Unsupported automation policy; no action taken')
    development=Path(value['development_data']).resolve();backup=Path(value['backup_root']).resolve()
    for path in (development,backup):reject_links(path)
    daily=Path(root).resolve()
    if (daily==development or daily in development.parents or development in daily.parents
            or daily==backup or daily in backup.parents or backup in daily.parents):
        raise ValueError('Daily, development and backup directories must be separate')
    return value


def event_name(root):
    return 'Local\\JarvisDailyWake-'+hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:24]


class WakeSignal:
    """One auto-reset kernel event; hints wake existing management, never start it."""
    def __init__(self,root):
        if os.name!='nt':raise ValueError('Windows local notification only')
        import ctypes
        from ctypes import wintypes
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.CreateEventW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
        self.api.CreateEventW.restype=wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        self.api.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=self.api.CreateEventW(None,False,False,event_name(root))
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())

    def wait(self,seconds):
        result=self.api.WaitForSingleObject(self.handle,max(1,min(int(seconds*1000),3600000)))
        if result not in (0,258):raise OSError('Management notification wait failed')
        return result==0

    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None


def signal(root):
    if os.name!='nt':return False
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenEventW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR];api.OpenEventW.restype=wintypes.HANDLE
    api.SetEvent.argtypes=[wintypes.HANDLE];api.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=api.OpenEventW(2,False,event_name(root))
    if not handle:return False
    try:return bool(api.SetEvent(handle))
    finally:api.CloseHandle(handle)


def notify_completion(root):
    selected=policy(root)
    if not selected['enabled'] or not selected.get('completion',{}).get('enabled'):
        return {'notified':False,'reason':'disabled'}
    if StopGate(root).state()!='ready':return {'notified':False,'reason':'owner_stopped'}
    request={'schema':1,'id':uuid.uuid4().hex,'source':selected['completion']['source'],'created':time.time()}
    signed(root,base(root)/'notification.json',request)
    return {'notified':signal(root),'request':request['id'],'authority':'wake hint only; original review and checks still required'}


class Schedule:
    """Hourly fallback; only an in-flight operation has a short-lived timer."""
    def __init__(self,clock=time.time):
        self.clock=clock;self.passive_at=clock()+PASSIVE_SECONDS;self.source_at=None;self.last_notification=None

    def source_due(self,root):
        now=self.clock();due=False
        if now>=self.passive_at:self.passive_at=now+PASSIVE_SECONDS;due=True
        if self.source_at is not None and now>=self.source_at:self.source_at=None;due=True
        path=base(root)/'notification.json'
        if path.exists():
            value=verified(root,path);selected=policy(root)
            if (value.get('schema')!=1 or value.get('source')!=selected.get('completion',{}).get('source')
                    or not isinstance(value.get('id'),str) or len(value['id'])!=32
                    or type(value.get('created')) not in (int,float)):
                raise ValueError('Invalid local completion notification')
            if value['id']!=self.last_notification:
                self.last_notification=value['id']
                if -5<=now-value['created']<=86400:due=True
        return due

    def after_tick(self,engine,source_checked):
        if getattr(engine,'last_status',None) in {'offline_no_update_checks','manual_stop','owner_stopped','no_active_build','disabled'}:
            self.source_at=None;return
        completion=getattr(engine,'completion',None)
        if source_checked:
            self.source_at=None
            if engine.source_inspected and completion is not None:
                state=completion.state
                if state.get('status')=='waiting_for_quiet_snapshot':
                    self.source_at=state['stable_since']+120
                elif state.get('status')=='daily_check_limit':
                    retry_at=state.get('next_check_at')
                    if type(retry_at) in (int,float):self.source_at=retry_at

    def delay(self,engine):
        deadlines=[self.passive_at]
        if self.source_at is not None:deadlines.append(self.source_at)
        completion=getattr(engine,'completion',None)
        if engine.journal.get('phase')=='observing' or (completion is not None and completion.process is not None):
            deadlines.append(self.clock()+ACTIVE_SECONDS)
        elif getattr(engine,'last_status',None)=='waiting_for_idle' and engine.idle_since is not None:
            deadlines.append(max(self.clock()+1,engine.idle_since+60))
        return max(1,min(deadlines)-self.clock())


@contextmanager
def lease(root,name='service'):
    folder=base(root);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(name+'.lock');reject_links(path)
    stream=path.open('a+b');locked=False
    try:
        if not path.stat().st_size:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        locked=True;yield
    finally:
        if locked:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)
        stream.close()


def queue(root,development,prepared):
    """Called only after original reviewed-source preparation succeeds."""
    folder=base(root)
    if not (folder/'policy.json').exists():return {'queued':False,'reason':'not_enabled'}
    selected=policy(root)
    if not selected['enabled'] or not selected['auto_updates']:return {'queued':False,'reason':'disabled'}
    if str(Path(development).resolve())!=selected['development_data']:raise ValueError('Wrong development root')
    if prepared.get('daily_data')!=str(Path(root).resolve()):raise ValueError('Wrong prepared data root')
    app=Applications(root);state=app.state();record=app.approved(prepared['build'])
    _,manifest=inspect_package(Path(record['path']))
    files={name:meta['sha256'] for name,meta in manifest['files'].items()}
    if (prepared.get('files')!=files or state['epoch']!=prepared.get('expected_epoch')
            or state['phase']!='active' or record['report'].get('reviewed_source') is not True):
        raise ValueError('Preparation no longer binds the reviewed candidate and current baseline')
    now=time.time();ticket={'schema':SCHEMA,'id':uuid.uuid4().hex,'daily_data':str(Path(root).resolve()),
        'development_data':str(Path(development).resolve()),'prepared':prepared,
        'baseline':state['active'],'created':now,'expires':now+86400}
    with lease(root,'queue'):
        path=folder/'ticket.json'
        if path.exists():
            previous=verified(root,path)
            journal=read(folder/'journal.json') if (folder/'journal.json').exists() else {}
            if previous['id']==journal.get('ticket') and journal.get('phase') in {'applying','observing','rolling_back'}:
                raise ValueError('An automatic transition already owns the queue')
        signed(root,path,ticket)
    signal(root)
    return {'queued':True,'ticket':ticket['id'],'expires':ticket['expires']}


def parked_waits(root, items):
    """Prove only known persisted waits safe to leave to the next host."""
    mail = []
    for row in items:
        if row.get('source') == 'tasks' and (
                row.get('raw_status') == 'READY'
                or (row.get('raw_status') == 'WAITING'
                    and (row.get('recovery_wait') or {}).get('state') == 'WAITING'
                    and row['recovery_wait'].get('reason') == 'module_disabled')):
            continue
        if row.get('source') != 'mail' or row.get('operation') not in {'check','counts','list','sync','read'}:
            return False
        mail.append(row)
    if not mail:
        return True
    # Older active packages project mail waits without their exact status.
    # Re-read only these original records, without acquiring a mailbox writer.
    from control.credentials import crypt
    path = root/'private/mail.sqlite3'
    reject_links(path)
    try:
        db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=2)
        try:
            for row in mail:
                raw = db.execute("SELECT revision,payload FROM objects WHERE kind='job' AND id=?", (row['id'],)).fetchone()
                if raw is None:
                    return False
                job = decode(crypt(raw[1], decrypt=True))
                if (job.get('id') != row['id'] or job.get('kind') != 'job' or job.get('revision') != raw[0]
                        or job.get('operation') != row['operation'] or job.get('status') != 'WAITING_NETWORK'
                        or job.get('effect_started') is not False):
                    return False
            return True
        finally:
            db.close()
    except (CoreError, OSError, ValueError, sqlite3.Error):
        return False


def quiet_for_handoff(root, value):
    counts = value.get('counts', {})
    if (value.get('activity', {}).get('drained') is not True
            or not all(type(counts.get(k)) is int and counts[k] == 0 for k in ('running','queued','external','unknown'))
            or any(row.get('status') == 'unavailable' for row in value.get('sources', []))):
        return False
    waiting = [row for row in value.get('items', []) if row.get('state') == 'waiting']
    return type(counts.get('waiting')) is int and len(waiting) == counts['waiting'] and parked_waits(root, waiting)


class Engine:
    def __init__(self,root,operator,clock=time.time):
        self.root=Path(root).resolve();self.operator=operator;self.clock=clock
        self.folder=base(root);self.config=policy(root);self.app=Applications(self.root)
        self.port=operator.controller(self.root)[1];self.driver=WorkbenchProcess(self.root,self.port,timeout=15)
        self.started=False;self.idle_since=None;self.bad=0;self.error_count=0
        self.journal=read(self.folder/'journal.json') if (self.folder/'journal.json').exists() else {'phase':'idle','restarts':[]}
        self.completion=None
        if self.config.get('completion',{}).get('enabled'):
            module=load_completion()
            self.completion=module.Completion(self.root,self.config['completion'],self.config['development_data'],operator,clock)

    def save(self,**patch):
        if patch.get('failed_build'):
            rejected=set(self.journal.get('quarantined_builds',[]))
            if self.journal.get('failed_build'):rejected.add(self.journal['failed_build'])
            rejected.add(patch['failed_build']);patch['quarantined_builds']=sorted(rejected)
        self.journal.update(patch,updated=self.clock());write_json(self.folder/'journal.json',self.journal)

    def status(self,status,**extra):
        self.last_status=status
        completion=getattr(self,'completion',None)
        if completion is not None:extra['completion']={k:completion.state.get(k) for k in ('status','head','seen_head','error')}
        write_json(self.folder/'status.json',{'schema':SCHEMA,'pid':os.getpid(),'status':status,
            'time':self.clock(),'daily_data':str(self.root),'phase':self.journal.get('phase'),**extra})

    def idle(self):
        origin=f'http://127.0.0.1:{self.port}'
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        request=urllib.request.Request(origin+'/api/local-access',data=json.dumps({'key':read_key(self.root)}).encode(),
            headers={'Origin':origin,'Content-Type':'application/json'})
        with opener.open(request,timeout=3) as response:response.read(4096)
        with opener.open(origin+'/api/work-status',timeout=4) as response:value=json.load(response)
        return quiet_for_handoff(self.root, value)

    def restart(self):
        now=self.clock();attempts=[t for t in self.journal.get('restarts',[]) if now-t<3600]
        if len(attempts)>=self.config['restart_limit']:
            self.save(phase='attention',error='restart_limit');self.status('attention');return False
        self.save(restarts=attempts+[now]) # Reserve before attempting, even if it fails.
        self.operator.start_daily(self.root);self.bad=0
        return True

    def rollback(self,state,reason):
        current=self.app.state();target=self.journal.get('target');baseline=self.journal.get('baseline')
        if (not baseline or current!=state or not current.get('active')
                or current['active']['build']!=target or current.get('previous',{}).get('build')!=baseline['build']):
            self.save(phase='attention',error='rollback_baseline_changed');return
        approved=self.app.approved(baseline['build'],fresh=False)
        require_compatible(self.root,approved['path']);StopGate(self.root).require_running()
        self.save(phase='rolling_back',error=reason)
        result=self.app.adopt(baseline['build'],self.driver,rollback=True,expected_epoch=current['epoch'])
        if result['phase']!='active' or result['active']['build']!=baseline['build']:
            raise ValueError('Rollback was not confirmed')
        self.save(phase='quarantined',failed_build=target,rollback_epoch=result['epoch'],error=reason)

    def transition(self,ticket):
        prepared=ticket['prepared'];before=self.app.state()
        if (ticket['daily_data']!=str(self.root) or ticket['development_data']!=self.config['development_data']
                or self.clock()>ticket['expires'] or before['epoch']!=prepared['expected_epoch']
                or before['active']!=ticket['baseline']):raise ValueError('Expired or stale automatic ticket')
        self.operator.require_prepared(self.root,prepared)
        self.operator.preflight(self.root,prepared['build'])
        # Prove the baseline can still read the current data before any stop.
        baseline=self.app.approved(before['active']['build'],fresh=False)
        require_compatible(self.root,baseline['path'])
        backup_root=Path(self.config['backup_root']);reject_links(backup_root)
        backup_root.mkdir(parents=True,exist_ok=True)
        estimate=sum(p.stat().st_size for top in ('config','private','state','sessions') for p in (self.root/top).rglob('*') if p.is_file())
        if shutil.disk_usage(backup_root).free<estimate+512*1024**2:raise ValueError('Insufficient backup disk space')
        self.save(phase='applying',ticket=ticket['id'],target=prepared['build'],baseline=before['active'],
            started=self.clock(),error=None)
        try:
            result=self.operator.apply(self.root,Path(ticket['development_data']),prepared_record=prepared,backup_root=backup_root)
            after=self.app.state()
            if after['phase']=='active' and after['active']['build']==prepared['build']:
                self.save(phase='observing',adopted_epoch=after['epoch'],observe_until=self.clock()+self.config['observation_seconds'])
            elif after['phase']=='active' and after['active']['build']==before['active']['build']:
                self.save(phase='quarantined',failed_build=prepared['build'],error='candidate_not_adopted')
            else:raise ValueError('Unconfirmed adoption')
            return result
        except Exception as exc:
            current=self.app.state()
            if current.get('active',{}).get('build')==prepared['build'] and current['phase']=='active':
                self.rollback(current,type(exc).__name__)
            elif current['phase']=='active' and current.get('active',{}).get('build')==before['active']['build']:
                self.save(phase='quarantined',failed_build=prepared['build'],error=type(exc).__name__)
            else:self.save(phase='attention',error=type(exc).__name__)
            raise

    def logon_start(self):
        """The existing explicit login-start action, separate from supervision."""
        if not self.config['enabled'] or StopGate(self.root).state()!='ready':return
        current=self.app.state()
        if current['phase']=='active' and current['active'] and self.journal.get('phase') not in {'observing','applying','rolling_back','attention'}:
            if not self.driver.running(current['active'],current['epoch']):self.restart()

    def acknowledge_recovered_baseline(self,current):
        """Consume an interrupted ticket only after the controller restored its exact baseline."""
        baseline=self.journal.get('baseline')
        if (not baseline or current.get('phase')!='active' or current.get('error')!='interrupted_handoff'
                or current.get('pending') is not None or current.get('pending_epoch') is not None
                or current.get('epoch',0)<=baseline['epoch'] or not current.get('active')
                or current['active']['build']!=baseline['build']):
            return False
        path=self.folder/'ticket.json'
        if not path.exists():return False
        ticket=verified(self.root,path)
        if (ticket['id']!=self.journal.get('ticket') or ticket['baseline']!=baseline
                or ticket['prepared']['build']!=self.journal.get('target')):
            return False
        control=coordination(self.root)
        if (not control or control['phase']!='active' or control['build']!=baseline['build']
                or control['epoch']!=current['epoch'] or not self.driver.running(current['active'],current['epoch'])):
            return False
        self.save(phase='rejected',recovery_epoch=current['epoch'],original_error=self.journal.get('error'),
                  error='baseline_recovered')
        return True

    def tick(self,*,check_source=True):
        self.source_check_requested=check_source
        self.source_inspected=False
        self.config=policy(self.root)
        if not self.config['enabled']:self.close();self.status('disabled');return
        if StopGate(self.root).state()!='ready':self.close();self.status('owner_stopped');return
        completion=getattr(self,'completion',None)
        current=self.app.state();phase=self.journal.get('phase')
        if phase in {'applying','rolling_back'}:
            # Never replay an ambiguous local transition. Reconcile only its state.
            if current['phase']=='active' and current.get('active',{}).get('build')==self.journal.get('target') and phase=='applying':
                self.save(phase='observing',adopted_epoch=current['epoch'],observe_until=self.clock()+self.config['observation_seconds'])
            else:self.save(phase='attention',error='interrupted_transition');self.status('attention');return
        if self.journal.get('phase')=='attention' and not self.acknowledge_recovered_baseline(current):
            self.close();self.status('attention');return
        if current['phase'] not in {'active','stopped'}:self.close();self.status('maintenance_owned_elsewhere');return
        if not current['active']:self.close();self.status('no_active_build');return
        if current['phase']=='stopped':
            if completion is not None:completion.close()
            self.started=True;self.status('manual_stop');return
        try:healthy=self.driver.running(current['active'],current['epoch'])
        except CoreError as exc:
            self.bad+=1
            if self.journal.get('phase')=='observing':
                if self.bad>=3:self.rollback(current,exc.code)
                self.status('unhealthy',error=exc.code)
            else:
                if completion is not None:completion.close()
                self.status('offline_no_update_checks',error=exc.code)
            return
        except OSError:healthy=False
        if not healthy:
            self.bad+=1
            if self.journal.get('phase')=='observing':
                # A manager restart does not grant another start of the observed
                # candidate: it would advance its epoch and invalidate the bound
                # rollback. Count the original three failures, then roll back.
                self.started=True
                if self.bad>=3:self.rollback(current,'candidate_disappeared')
                self.status('unhealthy_observing');return
            if completion is not None:completion.close()
            self.status('offline_no_update_checks');return
        self.started=True;self.bad=0
        if completion is not None:
            try:completion.poll()
            except Exception as exc:completion.save(status='attention',error=type(exc).__name__)
        if self.journal.get('phase')=='observing':
            if current['active']['build']!=self.journal['target'] or current['epoch']!=self.journal['adopted_epoch']:
                self.save(phase='attention',error='observation_baseline_changed')
            elif self.clock()>=self.journal['observe_until']:self.save(phase='complete',error=None)
            self.status('observing');return
        if completion is not None and check_source:
            self.source_inspected=True
            try:completion.tick()
            except Exception as exc:completion.save(status='attention',error=type(exc).__name__)
        ticket_path=self.folder/'ticket.json'
        if not self.config['auto_updates'] or not ticket_path.exists():self.status('ready');return
        ticket=verified(self.root,ticket_path)
        rejected=set(self.journal.get('quarantined_builds',[]))|{self.journal.get('failed_build')}
        if ticket['id']==self.journal.get('ticket') or ticket['prepared']['build'] in rejected:
            self.status('ready_quarantined' if self.journal.get('failed_build') else 'ready');return
        if self.clock()>=ticket['expires']:
            self.save(ticket=ticket['id'],phase='rejected',error='ticket_expired');self.status('ready');return
        if ticket['prepared']['build']==current['active']['build']:
            self.save(ticket=ticket['id'],phase='complete');self.status('ready');return
        if ticket['baseline']!=current['active'] or ticket['prepared']['expected_epoch']!=current['epoch']:
            self.save(ticket=ticket['id'],phase='rejected',error='stale_baseline');self.status('ready');return
        commit=ticket['prepared'].get('completion_commit')
        if commit:
            if completion is None or completion.state.get('head')!=commit or completion.state.get('status')!='queued':
                self.status('waiting_for_independent_check_exit');return
            try:load_completion().require_snapshot(self.config['completion'],commit)
            except ValueError:
                self.idle_since=None;self.status('waiting_for_reviewed_snapshot');return
        if not self.idle():self.idle_since=None;self.status('waiting_for_idle');return
        if self.idle_since is None:self.idle_since=self.clock()
        if self.clock()-self.idle_since<self.config['idle_seconds']:self.status('waiting_for_idle');return
        self.idle_since=None
        try:self.transition(ticket)
        except Exception as exc:
            reason=exc.code if isinstance(exc,CoreError) else type(exc).__name__
            if self.journal.get('ticket')!=ticket['id']:
                self.save(ticket=ticket['id'],phase='rejected',error=reason)
            self.status('update_rejected',error=reason)

    def close(self):
        completion=getattr(self,'completion',None)
        if completion is not None:completion.close()


def install(root,development,backup_root,operator_path=None):
    from tools import workstation
    root=Path(root).resolve();development=Path(development).resolve();backup_root=Path(backup_root).resolve()
    a,b=workstation.roots(development)
    if root!=a or development!=b:raise ValueError('Use the existing separated daily/development roots')
    folder=base(root);folder.mkdir(parents=True,exist_ok=True)
    helper,port=workstation.controller(root);helper_inventory=helper/'controller-files.json'
    completion_module=load_completion()
    files={'service.py':Path(__file__).read_bytes(),'operator.py':Path(operator_path or workstation.__file__).read_bytes(),
        'completion.py':Path(completion_module.__file__).read_bytes()}
    index={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}
    inventory=canonical(index).encode();ident=hashlib.sha256(inventory).hexdigest();capsule=folder/'capsules'/ident
    capsule.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        target=capsule/name;reject_links(target)
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Existing service capsule changed')
        target.write_bytes(raw)
    (capsule/'files.json').write_bytes(inventory)
    completion=completion_module.settings(development.parent)
    if (folder/'policy.json').exists():
        prior=verified(root,folder/'policy.json').get('completion')
        if prior and prior.get('source')==str(development.parent):
            completion_module.validate(prior);completion=prior
    value={'schema':POLICY_SCHEMA,'enabled':True,'auto_updates':True,'daily_data':str(root),
        'development_data':str(development),'development_autostart':False,'backup_root':str(backup_root),
        'poll_seconds':PASSIVE_SECONDS,'active_seconds':ACTIVE_SECONDS,'offline_restart':False,'source_notification':True,
        'idle_seconds':60,'observation_seconds':180,'restart_limit':3,'completion':completion}
    signed(root,folder/'policy.json',value)
    from sdk.workstation_bootstrap import service_bootstrap
    bootstrap=service_bootstrap(ident,helper,digest(helper_inventory))
    target=root.parent/'JarvisService.py'
    if target.exists():shutil.copyfile(target,folder/('bootstrap-backup-'+uuid.uuid4().hex+'.py'))
    temporary=target.with_suffix('.pending');temporary.write_text(bootstrap,encoding='utf-8');temporary.replace(target)
    return {'schema':SCHEMA,'capsule':ident,'bootstrap':str(target),'helper':str(helper),'policy':value}


def register_startup(root):
    if os.name!='nt':raise ValueError('Windows logon startup only')
    import winreg
    root=Path(root).resolve();python=Path(sys.executable).with_name('pythonw.exe')
    if not python.is_file():raise ValueError('The reviewed interpreter lacks pythonw.exe')
    bootstrap=root.parent/'JarvisService.py'
    if not bootstrap.is_file():raise ValueError('Install and verify the pinned service first')
    name='JarvisDaily-'+hashlib.sha256(str(root).casefold().encode()).hexdigest()[:12]
    # A tiny current-user shim tolerates a late-mounted external drive. No
    # credentials/business files move to C; no administrator or saved password.
    local=Path(os.environ['LOCALAPPDATA'])/'Jarvis/startup'/name
    reject_links(local);local.mkdir(parents=True,exist_ok=True)
    shim=local/'start.py'
    payload='''"""Jarvis logon shim: bounded drive wait, pinned service, no UI."""
from pathlib import Path
import hashlib,runpy,sys,time
target=Path(TARGET)
log=Path(__file__).with_name('startup.log')
try:
 for attempt in range(180):
  if target.is_file():break
  time.sleep(5)
 else:raise RuntimeError('Daily drive unavailable after 15 minutes')
 if hashlib.sha256(target.read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Service bootstrap changed; register reviewed startup again')
 sys.argv=[str(target),'--logon-start']
 runpy.run_path(str(target),run_name='__main__')
except Exception as exc:
 if log.exists() and log.stat().st_size>262144:log.write_text('')
 with log.open('a',encoding='utf-8') as stream:stream.write(str(time.time())+' '+type(exc).__name__+'\\n')
'''.replace('TARGET',repr(str(bootstrap))).replace('EXPECTED',repr(digest(bootstrap)))
    if shim.exists():shutil.copyfile(shim,base(root)/('startup-shim-backup-'+uuid.uuid4().hex+'.py'))
    shim.write_text(payload,encoding='utf-8')
    command=subprocess.list2cmdline([str(python),'-X','utf8','-I','-B',str(shim)])
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run',0,winreg.KEY_READ|winreg.KEY_WRITE) as key:
        try:previous=winreg.QueryValueEx(key,name)[0]
        except FileNotFoundError:previous=None
        backup=base(root)/'startup-backup.json'
        if not backup.exists():write_json(backup,{'name':name,'previous':previous,'command':command})
        winreg.SetValueEx(key,name,0,winreg.REG_SZ,command)
        if winreg.QueryValueEx(key,name)[0]!=command:raise ValueError('Startup registration did not persist')
    result={'name':name,'command':command,'scope':'current-user-logon','elevation':False,'development_autostart':False,
        'shim':str(shim),'shim_sha256':digest(shim),'service_bootstrap_sha256':digest(bootstrap),'drive_wait_seconds':900}
    write_json(base(root)/'startup.json',result)
    return result


def unregister_startup(root):
    if os.name!='nt':raise ValueError('Windows logon startup only')
    import winreg
    receipt=read(base(root)/'startup.json');original=read(base(root)/'startup-backup.json')
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run',0,winreg.KEY_READ|winreg.KEY_WRITE) as key:
        try:current=winreg.QueryValueEx(key,receipt['name'])[0]
        except FileNotFoundError:return {'disabled':True}
        if current!=receipt['command']:raise ValueError('Startup value changed; preserve the owner edit')
        if original['previous'] is None:winreg.DeleteValue(key,receipt['name'])
        else:winreg.SetValueEx(key,receipt['name'],0,winreg.REG_SZ,original['previous'])
    return {'disabled':True,'daily_stopped':False}


def register_notification(root):
    """Register only this manager's local hook; never replace an owner hook."""
    selected=policy(root);source=Path(selected['completion']['source'])
    load_completion().repository(source)
    configured=subprocess.run(['git','-C',str(source),'config','--get','core.hooksPath'],
        capture_output=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if configured.returncode!=1:raise ValueError('Preserve the existing custom Git hooks configuration')
    hooks=source/'.git/hooks';reject_links(hooks)
    if not hooks.is_dir():raise ValueError('Local notification requires this installation own Git hooks directory')
    hook=hooks/'post-commit';reject_links(hook);receipt=base(root)/'notification-hook.json'
    if hook.exists():
        old=read(receipt) if receipt.exists() else {}
        if old.get('path')!=str(hook) or old.get('sha256')!=digest(hook):
            raise ValueError('Preserve the existing owner post-commit hook')
    python=Path(sys.executable).with_name('pythonw.exe')
    bootstrap=Path(root).resolve().parent/'JarvisService.py'
    if not python.is_file() or not bootstrap.is_file():raise ValueError('Install the reviewed service first')
    command=' '.join(shlex.quote(str(p).replace('\\','/')) for p in (python,'-X','utf8','-I','-B',bootstrap,'--notify-completion'))
    payload=('#!/bin/sh\n# JarvisDaily managed local completion hint; no update authority.\n'+command+' >/dev/null 2>&1\nexit 0\n').encode()
    if hook.exists():shutil.copy2(hook,base(root)/('notification-hook-backup-'+uuid.uuid4().hex+'.sh'))
    temporary=hook.with_suffix('.pending');temporary.write_bytes(payload);temporary.replace(hook)
    value={'schema':1,'path':str(hook),'sha256':digest(hook),'source':str(source),'mechanism':'post-commit to existing local event','passive_seconds':PASSIVE_SECONDS}
    write_json(receipt,value);return value


def load_operator(path):
    spec=importlib.util.spec_from_file_location('jarvis_pinned_operator',path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def load_completion():
    path=Path(__file__).with_name('completion.py')
    if not path.exists():
        from tools import workstation_completion
        return workstation_completion
    spec=importlib.util.spec_from_file_location('jarvis_workstation_completion',path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['install','register-startup','register-notification','disable-startup','run','status','pause','resume','notify'])
    parser.add_argument('--daily-data',type=Path,required=True);parser.add_argument('--development-data',type=Path)
    parser.add_argument('--backup-root',type=Path);parser.add_argument('--operator',type=Path);parser.add_argument('--once',action='store_true')
    parser.add_argument('--prepare-completion')
    parser.add_argument('--notify-completion',action='store_true');parser.add_argument('--logon-start',action='store_true')
    args=parser.parse_args();root=args.daily_data.resolve()
    if args.action=='install':
        if not args.development_data or not args.backup_root:parser.error('Installation needs existing development and backup roots')
        print(json.dumps(install(root,args.development_data,args.backup_root)));return
    if args.action=='register-startup':print(json.dumps(register_startup(root)));return
    if args.action=='register-notification':print(json.dumps(register_notification(root)));return
    if args.action=='disable-startup':print(json.dumps(unregister_startup(root)));return
    if args.action=='notify' or args.notify_completion:print(json.dumps(notify_completion(root)));return
    if args.action in {'pause','resume'}:
        value=policy(root)
        if args.action=='resume':
            receipt=read(base(root)/'startup.json');bootstrap=root.parent/'JarvisService.py'
            if digest(bootstrap)!=receipt['service_bootstrap_sha256']:raise ValueError('Register the reviewed startup bootstrap again')
        value['enabled']=args.action=='resume';signed(root,base(root)/'policy.json',value)
        signal(root)
        if args.action=='resume':
            log=base(root)/'management.log'
            with log.open('ab') as stream:
                subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-X','utf8','-I','-B',str(bootstrap)],
                    stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        print(json.dumps({'enabled':value['enabled'],'daily_stopped':False}));return
    if args.action=='status':
        print(json.dumps({'policy':policy(root),'status':read(base(root)/'status.json') if (base(root)/'status.json').exists() else None}));return
    if not args.operator:parser.error('Run through the pinned service bootstrap')
    if args.prepare_completion:
        selected=policy(root);config=selected.get('completion',{})
        if not selected['enabled'] or not config.get('enabled'):raise ValueError('Automatic completion checks are paused')
        StopGate(root).require_running()
        with lease(root,'completion'):
            print(json.dumps(load_completion().prepare_one(root,selected['development_data'],load_operator(args.operator),
                config,args.prepare_completion,queue)))
        return
    with lease(root):
        wake=WakeSignal(root);engine=Engine(root,load_operator(args.operator));schedule=Schedule()
        try:
            if args.logon_start:engine.logon_start()
            while True:
                source_checked=False
                try:
                    source_checked=schedule.source_due(root)
                    engine.tick(check_source=source_checked);engine.error_count=0
                except Exception as exc:
                    engine.error_count+=1;engine.status('attention',error=type(exc).__name__)
                    if engine.error_count>=3:return
                if args.once or not engine.config['enabled']:return
                schedule.after_tick(engine,source_checked)
                wake.wait(schedule.delay(engine))
        finally:engine.close();wake.close()


if __name__=='__main__':main()
