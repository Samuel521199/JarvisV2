"""Detect explicit developer completion; fixed checks run off the daily lane.

A quiet editor or passing tests is not source review. Only the configured local
branch's clean committed snapshot with the developer's review trailer qualifies.
No fetch, pull, checkout, source edits, model calls or dependency installation.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from control.atomic import write_json
from control.paths import reject_links
from control.worker.process import OwnedProcess
from modules.release_recovery.application import inspect_package, TOPS, RUNTIME_DATA

TRAILER='Jarvis-Reviewed: complete'
QUIET_SECONDS=120
MAX_CHECKS=4
WALL_SECONDS=600


def git(source,*arguments):
    env=dict(os.environ,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_NO_REPLACE_OBJECTS='1',GIT_OPTIONAL_LOCKS='0')
    result=subprocess.run(['git','-c','core.fsmonitor=false','-c','core.untrackedCache=false','-c','core.hooksPath='+os.devnull,
        '-C',str(source),*arguments],capture_output=True,env=env,timeout=10,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Completion Git inspection failed')
    if len(result.stdout)>4*1024**2:raise ValueError('Completion Git output exceeds limit')
    return result.stdout


def repository(source):
    source=Path(source).resolve();reject_links(source)
    top=Path(git(source,'rev-parse','--show-toplevel').decode().strip()).resolve()
    if top!=source:raise ValueError('Completion source must be the repository root')
    head=git(source,'rev-parse','HEAD').decode().strip()
    if not re.fullmatch('[a-f0-9]{40,64}',head):raise ValueError('Invalid completion commit')
    branch=git(source,'symbolic-ref','--quiet','--short','HEAD').decode().strip()
    message=git(source,'show','-s','--format=%B',head).decode('utf-8')
    trailers=git(source,'show','-s','--format=%(trailers:only,unfold)',head).decode('utf-8').splitlines()
    lock=Path(git(source,'rev-parse','--git-path','index.lock').decode().strip())
    if not lock.is_absolute():lock=source/lock
    return {'source':str(source),'head':head,'branch':branch,
        'clean':not lock.exists() and not git(source,'status','--porcelain=v1','-z','--untracked-files=normal','--ignore-submodules=none'),
        'reviewed':trailers.count(TRAILER)==1 and not re.match(r'\s*(?:wip|draft)\b',message,re.I)}


def settings(source):
    state=repository(source)
    return {'schema':1,'enabled':True,'source':state['source'],'branch':state['branch'],
        'baseline_head':state['head'],'required_trailer':TRAILER,'quiet_seconds':QUIET_SECONDS,
        'max_checks_per_24h':MAX_CHECKS,'worker_wall_seconds':WALL_SECONDS}


def validate(config):
    if (not isinstance(config,dict) or config.get('schema')!=1 or type(config.get('enabled')) is not bool
            or config.get('required_trailer')!=TRAILER or config.get('quiet_seconds')!=QUIET_SECONDS
            or config.get('max_checks_per_24h')!=MAX_CHECKS or config.get('worker_wall_seconds')!=WALL_SECONDS
            or not isinstance(config.get('branch'),str) or not config['branch']
            or not re.fullmatch('[a-f0-9]{40,64}',config.get('baseline_head',''))):
        raise ValueError('Unsupported completion policy')
    path=Path(config['source']);reject_links(path)
    if not path.is_absolute():raise ValueError('Completion source must be absolute')


def require_snapshot(config,expected_head):
    validate(config);state=repository(config['source'])
    if not state['clean'] or not state['reviewed'] or state['branch']!=config['branch'] or state['head']!=expected_head:
        raise ValueError('Completion snapshot changed or lacks developer review')
    return state


def prepare_one(root,development,operator,config,expected_head,queue_callback):
    """The developer attests review; fixed controller independently verifies code."""
    require_snapshot(config,expected_head)
    def guarded_queue(daily,development,prepared):
        require_snapshot(config,expected_head)
        return queue_callback(daily,development,{**prepared,'completion_commit':expected_head})
    result=operator.prepare(root,Path(development),Path(config['source']),queue_callback=guarded_queue)
    return {'head':expected_head,'review_basis':'explicit developer Git trailer; not inferred from passing tests',
        'preparation':result}


class Completion:
    def __init__(self,root,config,development,operator,clock=time.time):
        validate(config);self.root=Path(root).resolve();self.config=config;self.development=Path(development).resolve()
        if Path(config['source']).resolve()!=self.development.parent:raise ValueError('Completion source differs from development installation')
        self.operator=operator;self.clock=clock;self.folder=self.root/'deployment/automation'
        self.path=self.folder/'completion-state.json'
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {'schema':1,'attempts':[]}
        self.process=None;self.handles=[]
        if self.state.get('status')=='checking':self.save(status='interrupted',error='previous_check_result_unknown')

    def save(self,**patch):
        self.state.update(patch,updated=self.clock());write_json(self.path,self.state)

    def resources_changed(self):
        current=self.operator.state(self.root);active=current.get('active')
        if not active:return True
        _,manifest=inspect_package(self.root/'deployment/packages'/active['build'])
        # Older pinned controllers enumerate through a console-creating Git
        # wrapper. Use our hidden reader and the same authoritative package
        # policy so completion checks do not reopen a window after a commit.
        names=[name for name in git(self.config['source'],'ls-files','-z').decode().split('\0') if name and (
            name.split('/')[0] in TOPS or name in {'VERSION','tools/architecture-baseline.json',*RUNTIME_DATA})
            and not name.endswith(('.pyc','.blend','.glb','.fbx'))]
        return set(names)!=set(manifest['files']) or any(
            self.operator.sha(Path(self.config['source'])/name)!=manifest['files'][name]['sha256'] for name in names)

    def spawn(self,head):
        job=self.folder/'completion-jobs'/(head[:12]+'-'+uuid.uuid4().hex[:8]);job.mkdir(parents=True)
        self.handles=[(job/'stdout.log').open('wb'),(job/'stderr.log').open('wb')]
        self.save(status='checking',head=head,job=str(job),started=self.clock(),
            attempts=self.state.get('attempts',[])+[{'head':head,'time':self.clock(),'checked':True}])
        try:
            self.process=OwnedProcess([sys.executable,'-X','utf8','-I','-B',str(self.root.parent/'JarvisService.py'),
                '--prepare-completion',head],stdout=self.handles[0],stderr=self.handles[1],env=dict(os.environ),cwd=job,
                processes=64,cpu_seconds=600,memory_bytes=2*1024**3)
        except Exception:
            self.save(status='failed',error='check_worker_start_failed');self.close_handles();raise

    def close_handles(self):
        for stream in self.handles:stream.close()
        self.handles=[]

    def poll(self):
        if self.process is None:return
        process=self.process
        try:
            code=process.poll()
            if code is None:
                if self.clock()-self.state['started']>WALL_SECONDS:
                    process.close();self.save(status='failed',error='check_worker_timeout')
                else:
                    try:require_snapshot(self.config,self.state['head'])
                    except ValueError:process.close();self.save(status='cancelled',error='source_changed_during_checks')
                    else:return
            else:
                process.close();self.save(status='queued' if code==0 else 'failed',exit_code=code,error=None if code==0 else 'independent_checks_failed')
        finally:
            if process.closed:self.process=None;self.close_handles()

    def tick(self):
        self.poll()
        if self.process is not None:return
        state=repository(self.config['source']);head=state['head']
        if state['branch']!=self.config['branch']:
            self.save(status='waiting_for_configured_branch',seen_head=None,stable_since=None);return
        if not state['clean']:
            self.save(status='waiting_for_development_finish',seen_head=None,stable_since=None);return
        if not state['reviewed']:
            self.save(status='waiting_for_reviewed_completion',seen_head=None,stable_since=None);return
        if head==self.config['baseline_head'] or any(item['head']==head for item in self.state.get('attempts',[])):
            return
        if self.state.get('seen_head')!=head:
            self.save(status='waiting_for_quiet_snapshot',seen_head=head,stable_since=self.clock());return
        if self.clock()-self.state['stable_since']<QUIET_SECONDS:return
        attempts=[item for item in self.state.get('attempts',[]) if item.get('checked',True) and self.clock()-item['time']<86400]
        if len(attempts)>=MAX_CHECKS:
            retry_at=sorted(item['time'] for item in attempts)[-MAX_CHECKS]+86400
            self.save(status='daily_check_limit',next_check_at=retry_at);return
        if not self.resources_changed():
            self.save(status='no_runtime_change',head=head,attempts=self.state.get('attempts',[])+[{'head':head,'time':self.clock(),'checked':False}]);return
        self.spawn(head)

    def close(self):
        if self.process is not None:
            self.process.close();self.process=None;self.close_handles()
            self.save(status='cancelled',error='management_paused')
