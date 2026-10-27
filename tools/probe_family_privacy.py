"""Synthetic household UI fixture, isolated from production data and credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from control.family_identity import FamilyIdentity
from control.network import NetworkGate
from host.core import Core
from modules.context_knowledge.private_memory import PrivateMemory
from modules.preferences.store import Preferences

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/evidence/family-private-1.0.0'


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-family-ui-') as temp:
        root = Path(temp)/'data'; root.mkdir()
        Core.initialize(root).close()
        prefs = Preferences(root)
        prefs.install({'schema_version':1,'default_provider':'openai','automatic_fallback':False,'fallback_order':['openai'],
                       'providers':{'openai':{'adapter':'openai','label':'隔离验收 · 无真实密钥','model':'test-model',
                                              'models':{'test-model':{'parameters':{},'reasoning_levels':[]}}}}}, {})
        prefs.close()
        gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
        identities=FamilyIdentity(root);token=identities.setup('synthetic-only-password-2026');owner=identities.principal(token)
        for ident,name in [('alice','小晴（测试成员）'),('bob','小宇（测试成员）')]:
            identities.manage(owner,{'id':ident,'name':name,'active':True,'password':'synthetic-only-password-2026'})
        alice=identities.principal(identities.login('alice','synthetic-only-password-2026'))
        bob=identities.principal(identities.login('bob','synthetic-only-password-2026'))
        memory=PrivateMemory(root)
        try:
            for actor,title,body,shared in [(owner,'家庭出游清单','这是公开给家庭成员的合成测试资料。',['alice','bob']),
                                          (alice,'学习习惯','合成资料：晚上喜欢用中文复习，周末练习英文。',[]),
                                          (bob,'小宇的私密记录','此条仅小宇和主人可见，用于验证成员隔离。',[])]:
                memory.save(actor,{'id':'','revision':0,'title':title,'text':body,'shared':shared,'providers':[]},identities.members())
        finally:memory.close()
        with (EVIDENCE/'ui-stdout.log').open('w',encoding='utf-8') as out,(EVIDENCE/'ui-stderr.log').open('w',encoding='utf-8') as err:
            process=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'apps/workbench/server.py'),'--data-root',str(root),'--port','18288'],
                                     stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            stop=Path(temp)/'stop-probe'
            info={'root':str(root),'stop':str(stop),'pid':process.pid,'port':18288,'synthetic_only':True}
            (EVIDENCE/'ui-fixture.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(info),flush=True)
            try:
                while not stop.exists() and process.poll() is None:time.sleep(.2)
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=15)
    return 0


if __name__=='__main__':raise SystemExit(main())
