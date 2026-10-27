"""Isolated real HTTP/UI/scheduler check of linked pure-text rework; no model calls."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from host import goals
from host.core import Core
from tools.probe_concurrency import Fixture
from sdk.protocol import decode


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget',action='store_true',help='Exercise the shared budget controls with the same isolated runtime')
    parser.add_argument('--closure',action='store_true',help='Exercise conservative automatic impact and work closure')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='jarvis-rework-ui-') as tmp:
        root=Path(tmp);fixture=Fixture(root)
        fixture.server.development_runner=SimpleNamespace(state=lambda:{'status':'idle'})
        try:
            shutil.copytree(Path(__file__).resolve().parents[1]/'user-data/worker-runtime',root/'worker-runtime')
            core=Core(root)
            try:
                spec={'schema':'jarvis.development.v1','request_id':'rework-ui-tool','principal_id':'owner.local','scope_id':'personal',
                    'grant_id':'fixture-unused','goal':'Uppercase synthetic text','capability':'plugin.rework-upper.v1','description':'Convert letters to uppercase',
                    'public_cases':[{'input':'hello 中文','expected':'HELLO 中文'}],
                    'evaluation_cases':[{'input':'Abc','expected':'ABC'},{'input':'x y','expected':'X Y'}],
                    'sample_input':'hello 中文','limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
                package=core.packages.stage({'schema':'jarvis.code-candidate.v1','summary':'First-party synthetic uppercase fixture',
                    'files':[{'path':'main.py','content':'def run(text):\n    return text.upper()\n'}]},spec)
                if not core.packages.verify(package)['passed']:raise RuntimeError('Fixture verification failed')
                core.packages.activate(package,0)
                chat_id=None
                if args.closure:
                    from host import assistant
                    from modules.dialogue.store import Dialogues
                    chats=Dialogues(root)
                    try:
                        chat_id=chats.create()
                        chats.begin({'chat_id':chat_id,'request_id':'closure-original-turn','text':'转换两段文字处理步骤，并保存结果',
                            'provider':'openai','model':'fixture','reasoning':'default','assistant_mode':True},[])
                        chats.finish('closure-original-turn',{'status':'SUCCEEDED','text':'离线夹具：拟订待核对目标',
                            'provider':'openai','model':'fixture','assistant_action':{'kind':'goal','target':'',
                            'goal':'转换两段文字处理步骤，并保存结果','input_text':'hello 中文'}})
                    finally:chats.close()
                    ident=assistant.goal_from_turn(root,'closure-original-turn')['id']
                else:
                    ident=goals.command(root,{'action':'create','request':{'request_id':'rework-ui-original','goal':'转换两段文字处理步骤，并保存结果',
                        'input_text':'hello 中文','provider':'auto','model':'','reasoning':'default'}})['id']
                step={'title':'文字转大写','capability':spec['capability'],'source':'input','expected':'HELLO 中文'}
                goals.command(root,{'action':'edit','id':ident,'revision':1,'proposal':{'schema':'jarvis.goal-plan.v1',
                    'summary':'合成两步任务，用于检查局部返工','input_text':'hello 中文','steps':[step,{**step,'source':'previous'}],'questions':[]}})
                (out/'fixture.json').write_text(json.dumps({'id':ident,'chat_id':chat_id,'settings':core.preferences.public(core.credentials.available)},ensure_ascii=False),encoding='utf-8')
                subprocess.run(['node',str(Path(__file__).with_name('probe_closure_ui.cjs' if args.closure else 'probe_budget_ui.cjs' if args.budget else 'probe_rework_ui.cjs')),fixture.base,str(out)],check=True,timeout=90)
                rows=core.db.all('SELECT id,spent,status FROM tasks ORDER BY created');calls=core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n']
                report={'model_calls':calls,'tasks':rows,'work':core.works.projection(ident),
                    'actions':[{**a,'arguments':decode(a['arguments']),'result':decode(a['result'])} for t in rows for a in core.tasks.actions(t['id'])],
                    'production_deployed':False,'scope':'Synthetic two-step chain; '+('conservative structural impact and current-work closure' if args.closure else 'explicitly chosen suffix; no semantic impact analysis')}
                (out/'runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                assert calls==0 and [t['spent'] for t in rows]==[3,2] and all(t['status']=='SUCCEEDED' for t in rows)
            finally:core.close()
        finally:fixture.close()


if __name__=='__main__':main()
