"""Pinned local Codex CLI as a candidate-only model provider, never a publisher."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from control.paths import child, reject_links
from sdk.protocol import CoreError, canonical, decode

DISABLED=('shell_tool','unified_exec','apps','plugins','remote_plugin','multi_agent','multi_agent_v2',
          'browser_use','browser_use_external','in_app_browser','image_generation','view_image','hooks','skill_mcp_dependency_install')


def discover():
    binary=shutil.which('codex.exe')
    if not binary:return {'available':False,'error':'codex_missing'}
    path=Path(binary).resolve();reject_links(path)
    try:
        result=subprocess.run([str(path),'--version'],capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        version=result.stdout.decode('utf-8',errors='replace').strip()
        if result.returncode or not re.fullmatch(r'codex-cli [0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',version):return {'available':False,'error':'codex_version'}
        return {'available':True,'executable':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'version':version}
    except (OSError,subprocess.TimeoutExpired):return {'available':False,'error':'codex_probe_failed'}


def route(model,reasoning):
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',model) or reasoning not in {'default','low','medium','high','xhigh','max','ultra'}:
        raise CoreError('development_invalid','Invalid Codex model or reasoning')
    probe=discover()
    if not probe['available']:raise CoreError(probe['error'],'Install and sign into Codex before selecting this route')
    return {'id':'codex-cli','adapter':'codex-cli','model':model,'parameters':{'reasoning':reasoning},
            'executable':probe['executable'],'executable_sha256':probe['sha256'],'version':probe['version'],
            'max_output_tokens':8192,'max_prompt_bytes':50000,'timeout_seconds':180,'billing_profile':None}


def arguments(config,workspace,schema):
    args=[config['executable'],'exec','--ignore-user-config','--ignore-rules','--ephemeral','--strict-config',
          '--sandbox','read-only','--skip-git-repo-check','--cd',str(workspace),'--json','--color','never',
          '--output-schema',str(schema),'--model',config['model'],
          '-c','approval_policy="never"','-c','web_search="disabled"','-c','project_doc_max_bytes=0',
          '-c','mcp_servers={}','-c','history.persistence="none"']
    for feature in DISABLED:args.extend(['--disable',feature])
    reasoning=config['parameters']['reasoning']
    if reasoning!='default':args.extend(['-c','model_reasoning_effort='+canonical(reasoning)])
    return args+['-']


def parse_events(raw,returncode):
    usage={};message=None;started=False;finished=False
    for line in raw.splitlines():
        if not line.strip():continue
        event=decode(line);kind=event.get('type');started|=kind=='turn.started'
        if kind=='turn.completed':finished=True;usage=normalize_usage(event.get('usage',{}))
        item=event.get('item',{})
        if item.get('type') in {'command_execution','file_change','mcp_tool_call','web_search','collab_tool_call'}:
            return {'status':'INVALID','code':'codex_tool_event'}
        if kind=='item.completed' and item.get('type')=='agent_message':message=item.get('text')
    if returncode or not finished or not message:return {'status':'UNKNOWN' if started else 'REJECTED','code':'codex_incomplete'}
    try:value=decode(message)
    except CoreError:return {'status':'INVALID','code':'model_json','usage':usage}
    return {'status':'SUCCEEDED','value':value,'usage':usage}


def normalize_usage(raw):
    if not isinstance(raw,dict):return {}
    result=dict(raw)
    for source,target in [('input_tokens','prompt_tokens'),('output_tokens','completion_tokens'),('cached_input_tokens','cache_read_tokens'),('cache_write_input_tokens','cache_write_tokens'),('reasoning_output_tokens','reasoning_tokens')]:
        if type(raw.get(source)) is int and raw[source]>=0:result[target]=raw[source]
    if all(type(result.get(k)) is int for k in ('prompt_tokens','completion_tokens')):
        result['total_tokens']=result['prompt_tokens']+result['completion_tokens']
    return result


class CodexModel:
    def __init__(self,config,root):self.config,self.root=config,root

    def available(self):
        p=Path(self.config['executable'])
        try:reject_links(p);return p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==self.config['executable_sha256']
        except (OSError,CoreError):return False

    def generate(self,prompt,checkpoint=lambda:None):
        if not self.available():return {'status':'REJECTED','code':'codex_binary_changed'}
        if len(prompt.encode())>self.config['max_prompt_bytes']:return {'status':'REJECTED','code':'model_input_limit'}
        envelope=decode(prompt)
        if envelope.get('output_schema',{}).get('properties',{}).get('schema',{}).get('const')!='jarvis.code-candidate.v1':
            return {'status':'REJECTED','code':'codex_candidate_only'}
        checkpoint();parent=child(self.root,'temp');parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='codex-candidate-',dir=parent) as temporary:
            workspace=Path(temporary);schema=workspace/'output-schema.json';schema.write_text(canonical(envelope['output_schema']),encoding='utf-8')
            environment={k:os.environ[k] for k in ('SystemRoot','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA','CODEX_HOME') if k in os.environ}
            environment.update(TEMP=str(workspace),TMP=str(workspace))
            payload=('Return only the requested JSON candidate. No tools, commands, workspace reads, file edits, installs or external actions are needed. The host will verify the candidate independently.\n'+prompt).encode()
            with (workspace/'events.jsonl').open('w+b') as output, (workspace/'errors.log').open('w+b') as errors:
                process=subprocess.Popen(arguments(self.config,workspace,schema),stdin=subprocess.PIPE,stdout=output,stderr=errors,
                                         env=environment,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                deadline=time.monotonic()+self.config['timeout_seconds']
                try:
                    while True:
                        checkpoint()
                        if time.monotonic()>deadline:return {'status':'UNKNOWN','code':'codex_timeout'}
                        if max(os.fstat(output.fileno()).st_size,os.fstat(errors.fileno()).st_size)>2_000_000:return {'status':'UNKNOWN','code':'codex_output_limit'}
                        try:process.communicate(payload,timeout=.1);break
                        except subprocess.TimeoutExpired:payload=None
                    checkpoint();output.seek(0)
                    try:
                        result=parse_events(output.read(2_000_001),process.returncode)
                        if result['status']=='REJECTED':
                            errors.seek(0);diagnostic=errors.read(10000).decode('utf-8',errors='replace').lower()
                            for marker,code in [('unknown configuration','codex_config'),('unknown field','codex_config'),('unknown feature','codex_config'),('unexpected argument','codex_config'),('not supported','codex_model'),('unauthorized','codex_auth'),('not logged','codex_auth')]:
                                if marker in diagnostic:result['code']=code;break
                        return result
                    except (CoreError,ValueError,AttributeError):return {'status':'UNKNOWN','code':'codex_invalid_receipt'}
                finally:
                    if process.poll() is None:
                        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                        else:process.kill()
                    process.communicate()
