"""Synthetic, offline, real E5 -> fact retrieval -> dialogue receipt -> correction probe."""
import json
from pathlib import Path
import shutil
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
from host.core import Core
from host import memory
from host.local_models import LocalModels
from modules.context_knowledge.memory import Memory
from modules.dialogue.store import Dialogues
from control.network import NetworkGate


def main():
    report={'version':'memory-retrieval-1.0.0','environment':'Current Windows PC; CPU 2 threads; application network blocked, not OS air gap',
            'model':'e5-multilingual-small-int8','cloud_calls':0,'checks':[]}
    with tempfile.TemporaryDirectory(prefix='jarvis-memory-real-') as temp:
        root=Path(temp);core=Core.initialize(root);m=Memory(core.db);models=LocalModels(root);chats=Dialogues(root)
        try:
            shutil.copytree(ROOT/'user-data/local-models'/report['model'],models.folder(report['model']))
            gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
            models.command({'action':'activate','id':report['model'],'revision':models.snapshot()['revision']})
            activation=models.future.result(timeout=60)
            if activation['status']!='succeeded':raise RuntimeError(activation)
            def save(key,value,revision=0):
                return m.save(dict(scope='personal',key=key,value=value,kind='knowledge',purpose='personal',providers=['openai'],paused=False,expires=None),revision)
            for i in range(20):save(f'其他资料{i:02d}',f'样品编号 {i} 在仓库中。')
            save('会议安排','项目会议在周五下午三点召开。')
            save('饮食偏好','用户喜欢在晚上喝茶。')
            save('保养手册','The car needs an oil change.')
            queries=[('会议是什么时候？','会议安排'),('What does the user like drinking?','饮食偏好'),('汽车需要做什么保养？','保养手册')]
            for query,expected in queries:
                start=time.perf_counter();v=memory.retrieve(root,'personal','openai',True,query)
                report['checks'].append({'query':query,'expected':expected,'returned':[f['key'] for f in v['facts']],
                    'expected_present':expected in [f['key'] for f in v['facts']], 'retrieval':v['retrieval'],
                    'elapsed_ms':(time.perf_counter()-start)*1000})
            chat=chats.create()
            def context(ident):
                chats.begin(dict(chat_id=chat,request_id=ident,text='会议是什么时候？',provider='openai',model='synthetic',reasoning='default'),[])
                v=memory.dialogue_view(root,chats.read(chat),{'id':'openai'},True,'会议是什么时候？')
                body=chats.context(ident,v);chats.finish(ident,{'status':'SUCCEEDED','text':'synthetic answer','provider':'openai'})
                return json.dumps(body,ensure_ascii=False)
            before=context('before');save('会议安排','项目会议改为周六上午十点召开。',1);after=context('after')
            report['correction']={'old_value_used': '周五下午三点' in before,'new_value_used':'周六上午十点' in after,'old_value_excluded':'周五下午三点' not in after}
            m.forget('personal','会议安排',2)
            models.command({'action':'standby','id':report['model'],'revision':models.snapshot()['revision']});models.future.result(timeout=10)
            chats.close();core.close();core=Core(root);chats=Dialogues(root)
            forgotten=memory.retrieve(root,'personal','openai',True,'会议是什么时候？')
            report['restart_forget']={'selected':len(forgotten['facts']),'mode':forgotten['retrieval']['mode'],'semantic':forgotten['retrieval']['semantic']}
            report['passed']=all(report['correction'].values()) and not forgotten['facts'] and all(c['expected_present'] for c in report['checks'])
        finally:chats.close();models.close();core.close()
    target=ROOT/'docs/evidence/memory-retrieval-1.0.0';target.mkdir(exist_ok=True)
    (target/'real-encoder.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
