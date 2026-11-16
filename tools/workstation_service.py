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
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

from control.application_runtime import LocalApprovals
from control.atomic import write_json
from control.local_access import read_key
from control.paths import reject_links
from control.recovery.gate import StopGate
from adapters.application_host import WorkbenchProcess
from modules.release_recovery.application import Applications,inspect_package
from control.application_compatibility import require_compatible
from sdk.protocol import canonical,CoreError

SCHEMA=1


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
    if (value.get('schema')!=SCHEMA or value.get('daily_data')!=str(Path(root).resolve())
            or type(value.get('enabled')) is not bool or type(value.get('auto_updates')) is not bool
            or value.get('development_autostart') is not False
            or value.get('poll_seconds')!=30 or value.get('idle_seconds')!=60
            or value.get('observation_seconds')!=180 or value.get('restart_limit')!=3):
        raise ValueError('Unsupported automation policy; no action taken')
    development=Path(value['development_data']).resolve();backup=Path(value['backup_root']).resolve()
    for path in (development,backup):reject_links(path)
    daily=Path(root).resolve()
    if (daily==development or daily in development.parents or development in daily.parents
            or daily==backup or daily in backup.parents or backup in daily.parents):
        raise ValueError('Daily, development and backup directories must be separate')
    return value


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
    return {'queued':True,'ticket':ticket['id'],'expires':ticket['expires']}


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
        # Unknown runtime participants and queued/new foreground work fail closed.
        return (value.get('activity',{}).get('drained') is True
            and not any(value.get('counts',{}).get(k,0) for k in ('running','queued','waiting')))

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

    def tick(self):
        self.config=policy(self.root)
        if not self.config['enabled']:self.close();self.status('disabled');return
        if StopGate(self.root).state()!='ready':self.close();self.status('owner_stopped');return
        completion=getattr(self,'completion',None)
        if completion is not None:
            try:completion.poll()
            except Exception as exc:completion.save(status='attention',error=type(exc).__name__)
        current=self.app.state();phase=self.journal.get('phase')
        if phase in {'applying','rolling_back'}:
            # Never replay an ambiguous local transition. Reconcile only its state.
            if current['phase']=='active' and current.get('active',{}).get('build')==self.journal.get('target') and phase=='applying':
                self.save(phase='observing',adopted_epoch=current['epoch'],observe_until=self.clock()+self.config['observation_seconds'])
            else:self.save(phase='attention',error='interrupted_transition');self.status('attention');return
        if self.journal.get('phase')=='attention':self.status('attention');return
        if current['phase'] not in {'active','stopped'}:self.status('maintenance_owned_elsewhere');return
        if not current['active']:self.status('no_active_build');return
        if current['phase']=='stopped':
            self.started=True;self.status('manual_stop');return
        try:healthy=self.driver.running(current['active'],current['epoch'])
        except CoreError as exc:
            self.bad+=1;self.status('unhealthy',error=exc.code)
            if self.journal.get('phase')=='observing' and self.bad>=3:self.rollback(current,exc.code)
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
            elif (not self.started or current['phase']=='active') and self.bad>= (1 if not self.started else 3):
                self.restart();self.started=True
            self.status('restarting' if self.bad==0 else 'offline');return
        self.started=True;self.bad=0
        if self.journal.get('phase')=='observing':
            if current['active']['build']!=self.journal['target'] or current['epoch']!=self.journal['adopted_epoch']:
                self.save(phase='attention',error='observation_baseline_changed')
            elif self.clock()>=self.journal['observe_until']:self.save(phase='complete',error=None)
            self.status('observing');return
        if completion is not None:
            try:completion.tick()
            except Exception as exc:completion.save(status='attention',error=type(exc).__name__)
        ticket_path=self.folder/'ticket.json'
        if not self.config['auto_updates'] or not ticket_path.exists():self.status('ready');return
        ticket=verified(self.root,ticket_path)
        commit=ticket['prepared'].get('completion_commit')
        if commit and (completion is None or completion.state.get('head')!=commit or completion.state.get('status')!='queued'):
            self.status('waiting_for_independent_check_exit');return
        rejected=set(self.journal.get('quarantined_builds',[]))|{self.journal.get('failed_build')}
        if ticket['id']==self.journal.get('ticket') or ticket['prepared']['build'] in rejected:
            self.status('ready_quarantined' if self.journal.get('failed_build') else 'ready');return
        if ticket['prepared']['build']==current['active']['build']:
            self.save(ticket=ticket['id'],phase='complete');self.status('ready');return
        if not self.idle():self.idle_since=None;self.status('waiting_for_idle');return
        if self.idle_since is None:self.idle_since=self.clock()
        if self.clock()-self.idle_since<self.config['idle_seconds']:self.status('waiting_for_idle');return
        try:self.transition(ticket)
        except Exception as exc:
            if self.journal.get('ticket')!=ticket['id']:
                self.save(ticket=ticket['id'],phase='rejected',error=type(exc).__name__)
            self.status('update_rejected',error=type(exc).__name__)

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
        prior=policy(root).get('completion')
        if prior and prior.get('source')==str(development.parent):
            completion_module.validate(prior);completion=prior
    value={'schema':SCHEMA,'enabled':True,'auto_updates':True,'daily_data':str(root),
        'development_data':str(development),'development_autostart':False,'backup_root':str(backup_root),
        'poll_seconds':30,'idle_seconds':60,'observation_seconds':180,'restart_limit':3,'completion':completion}
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
 sys.argv=[str(target)]
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['install','register-startup','disable-startup','run','status','pause','resume'])
    parser.add_argument('--daily-data',type=Path,required=True);parser.add_argument('--development-data',type=Path)
    parser.add_argument('--backup-root',type=Path);parser.add_argument('--operator',type=Path);parser.add_argument('--once',action='store_true')
    parser.add_argument('--prepare-completion')
    args=parser.parse_args();root=args.daily_data.resolve()
    if args.action=='install':
        if not args.development_data or not args.backup_root:parser.error('Installation needs existing development and backup roots')
        print(json.dumps(install(root,args.development_data,args.backup_root)));return
    if args.action=='register-startup':print(json.dumps(register_startup(root)));return
    if args.action=='disable-startup':print(json.dumps(unregister_startup(root)));return
    if args.action in {'pause','resume'}:
        value=policy(root)
        if args.action=='resume':
            receipt=read(base(root)/'startup.json');bootstrap=root.parent/'JarvisService.py'
            if digest(bootstrap)!=receipt['service_bootstrap_sha256']:raise ValueError('Register the reviewed startup bootstrap again')
        value['enabled']=args.action=='resume';signed(root,base(root)/'policy.json',value)
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
        engine=Engine(root,load_operator(args.operator))
        try:
            while True:
                try:engine.tick();engine.error_count=0
                except Exception as exc:
                    engine.error_count+=1;engine.status('attention',error=type(exc).__name__)
                    if engine.error_count>=3:return
                if args.once or not engine.config['enabled']:return
                time.sleep(engine.config['poll_seconds'])
        finally:engine.close()


if __name__=='__main__':main()
