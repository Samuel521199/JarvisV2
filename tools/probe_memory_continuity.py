"""Isolated synthetic browser fixture; no production data, network or credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from host.core import Core
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.domains import Domains
from modules.context_knowledge.source_merge import SourceMerge
from modules.dialogue.store import Dialogues
from modules.workspace.store import Workspace
from modules.preferences.store import Preferences
from control.network import NetworkGate

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/memory-continuity-1.0.0'


def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-memory-continuity-') as temp:
        base=Path(temp);root=base/'data';root.mkdir();project=base/'project';project.mkdir();core=Core.initialize(root)
        try:
            prefs=Preferences(root)
            prefs.install({'schema_version':1,'default_provider':'openai','automatic_fallback':False,'fallback_order':['openai'],
                           'providers':{'openai':{'adapter':'openai','label':'隔离测试（无密钥）','model':'test-model',
                                                  'models':{'test-model':{'parameters':{},'reasoning_levels':[]}}}}},{})
            prefs.close();gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
            workspace=Workspace(root);p=workspace.open(str(project));workspace.update(p['id'],{'name':'记忆闭环测试'});workspace.close()
            mem=Memory(core.db)
            item={'scope':'personal','key':'称呼','value':'测试用户旧称呼','kind':'preference','purpose':'personal','providers':['openai'],'paused':False,'expires':None}
            mem.save(item,0);mem.save(item|{'value':'测试用户新称呼','applicability':{'valid_from':None,'conditions':{'channel':'chat'}}},1)
            mem.save(item|{'scope':p['id'],'purpose':'project','kind':'knowledge','key':'接口版本','value':'主项目 Alpha'},0)
            library=Knowledge(core.db)
            source=library.save({'id':'','scope':p['id'],'title':'接口说明','text':'# 开发接口\n当前接口的名字为 Alpha。\n# 发布状态\n状态待定。\n','providers':['openai'],'paused':False},0)
            branch=Domains(core.db).create(p['id'],'branch','feature-beta',True)
            draft=SourceMerge(core.db).fork(branch['id'],source['id'],1)
            library.save({'id':draft['id'],'scope':branch['id'],'title':'接口说明','text':'# 开发接口\n当前接口的名字为 Beta。\n# 发布状态\n状态待定。\n','providers':['openai'],'paused':False},1)
            library.save({'id':source['id'],'scope':p['id'],'title':'接口说明','text':'# 开发接口\n当前接口的名字为 Alpha。\n# 发布状态\n已通过发布检查。\n','providers':['openai'],'paused':False},1)
            mem.save(item|{'scope':branch['id'],'purpose':'project','kind':'knowledge','key':'接口版本','value':'分支 Beta'},0)
            chats=Dialogues(root);chat=chats.create(p['id']);chats.update(chat,{'title':'分支上下文验收'});chats.close()
        finally:core.close()
        process=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'apps/workbench/server.py'),'--data-root',str(root),'--port','18288','--insecure-no-access-key'],
                                 stdout=(EVIDENCE/'ui-stdout.log').open('w',encoding='utf-8'),stderr=(EVIDENCE/'ui-stderr.log').open('w',encoding='utf-8'),
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        stop=base/'stop-probe'
        info={'root':str(root),'stop':str(stop),'pid':process.pid,'port':18288,'project':p['id'],'branch':branch['id'],'chat':chat,'synthetic_only':True}
        (EVIDENCE/'ui-fixture.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(info,ensure_ascii=False),flush=True)
        try:
            while not stop.exists() and process.poll() is None:time.sleep(.2)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=15)
    return 0


if __name__=='__main__':raise SystemExit(main())
