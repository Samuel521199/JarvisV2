"""Real HTTP/browser chat flow with a transparent local model substitute."""
from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from apps.workbench.server import Handler
from control.local_access import LocalAccess,read_key
from control.runtime_activity import RequestActivity
from host.core import Core
from host.dialogue import DialogueHost
from host.task_scheduler import TaskRunner
from host import assistant
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments
from sdk.protocol import canonical
from test_preferences_dialogue import fixture


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False);root=work/'data'
    core=Core.initialize(root);core.preferences.install(fixture(),{});baseline_grants=core.db.one('SELECT COUNT(*) AS n FROM grants')['n'];core.close()
    class Client:
        def __init__(self,*args):pass
        def available(self):return True
        def complete(self,messages,checkpoint,**kwargs):
            checkpoint();text=messages[-1]['content'].split('\n\n')[0]
            db=Dialogues(root)
            try:chat_id=db.db.execute("SELECT chat_id FROM turns WHERE status='RUNNING' ORDER BY created DESC LIMIT 1").fetchone()[0]
            finally:db.close()
            items=assistant.context(root,chat_id)
            title='回邮件';operation='create';target=basis=''
            if text=='明天下午提醒我整理周报':title='整理周报'
            elif text=='明天下午提醒我检查日志':title='检查日志'
            elif text=='15:00 UTC+08:00':
                draft=next(i for i in items if i.get('resource')=='commitment_draft' and i['title']=='整理周报');title=draft['title'];basis=draft['id']
            elif text=='取消回邮件':
                row=next(i for i in items if i.get('resource')=='commitment' and i['title']=='回邮件');target=row['id'];operation='cancel'
            elif text!='2030-01-01T12:00:00+08:00提醒我回邮件':raise ValueError('Unexpected fixture input')
            return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':'模型声称已执行',
                'action':{'kind':'commitment','goal':'','input_text':'','target':target,'commitment':{'operation':operation,
                'title':title,'quote':text,'due_at':'2099-01-01T12:00:00+08:00','time_text':'model suggestion','basis_turn':basis}}})}
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=root;server.nonce='synthetic-local-nonce'
    server.access=LocalAccess(root);server.request_activity=RequestActivity();server.dialogues=DialogueHost(root);server.task_runner=TaskRunner(root)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    config=work/'browser.json';config.write_text(json.dumps({'origin':f'http://127.0.0.1:{server.server_port}','key':read_key(root),'screenshot':str(work/'receipt.png')}),encoding='utf-8')
    try:
        with patch('host.dialogue.NativeModel',Client):
            playwright=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
            result=subprocess.run(['node',str(HERE/'browser.cjs'),playwright,str(config)],capture_output=True,text=True,encoding='utf-8',timeout=90)
        (HERE/'browser.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        report={'passed':result.returncode==0,'scope':'disposable local host; real browser/HTTP with substituted model; no paid API or daily data',
            'work_root':str(work),'sources_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
                'host/assistant.py','host/assistant_commitments.py','host/dialogue.py','host/commitments.py',
                'modules/task_resource/commitments.py','modules/task_resource/commitment_intent.py',
                'contracts/schemas/assistant-turn.v1.json','apps/workbench/assistant-actions.js','apps/workbench/assistant-commitments.js','apps/workbench/app.js']}}
        if report['passed']:report['browser']=json.loads(result.stdout)
        core=Core(root)
        try:report.update(core_goals=core.db.one('SELECT COUNT(*) AS n FROM goal_plans')['n'],core_grants=core.db.one('SELECT COUNT(*) AS n FROM grants')['n'],baseline_grants=baseline_grants,grants_added=core.db.one('SELECT COUNT(*) AS n FROM grants')['n']-baseline_grants)
        finally:core.close()
        (HERE/'runtime-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False));raise SystemExit(not report['passed'])
    finally:
        server.shutdown();thread.join(5);server.server_close();server.dialogues.close();server.task_runner.close(drain=False)
