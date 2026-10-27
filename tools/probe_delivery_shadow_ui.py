"""Original workbench + real HTTP + durable shadow observations, with no paid calls."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

from tools.probe_concurrency import Fixture
from sdk.protocol import canonical
from host.core import Core


class ShadowFixture(Fixture):
    def complete(self,messages,checkpoint,**kwargs):
        checkpoint();text=messages[-1]['content']
        reply='数据导出失败，原因未知。'
        if '第二轮' in text:reply='导出尚未开始。\n周五9点检查日志，不重跑导出。'
        if '清空依据' in text:reply='已收到本轮资料。'
        return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':reply,'action':{'kind':'chat','goal':'','input_text':'','target':''}}),'usage':{}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='jarvis-shadow-ui-') as tmp:
        fixture=ShadowFixture(Path(tmp));fixture.server.development_runner=SimpleNamespace(state=lambda:{'status':'idle'})
        try:
            (out/'fixture.json').write_text(json.dumps({'chat':fixture.chat,'root_is_temporary':True})+'\n',encoding='utf-8')
            result=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs')),fixture.base,str(out)],timeout=100,capture_output=True,text=True,encoding='utf-8',errors='replace')
            (out/'node.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            core=Core(fixture.root)
            try:tasks=core.db.one('SELECT COUNT(*) AS n FROM tasks')['n']
            finally:core.close()
            value=fixture.call('/api/chats/'+fixture.chat)
            (out/'runtime.json').write_text(json.dumps({'chat':value,'tasks':tasks,'production_deployed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            assert tasks==0
            if result.returncode:raise RuntimeError('Shadow browser probe failed; inspect node.log and browser.json')
            print('PASS shadow browser; original replies persisted, no tasks executed')
        finally:
            if hasattr(fixture.server,'mailbox'):fixture.server.mailbox.close()
            if hasattr(fixture.server,'local_models'):fixture.server.local_models.close()
            fixture.close()


if __name__=='__main__':main()
