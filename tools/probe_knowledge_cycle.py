"""Offline real-encoder integration, using synthetic sources in an isolated root."""
import json
from pathlib import Path
import shutil
import tempfile
import time

from host.core import Core
from host import memory, knowledge_vectors
from host.local_models import LocalModels
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.claims import Claims
from modules.context_knowledge.vectors import Vectors
from control.network import NetworkGate
from sdk.protocol import CoreError

ROOT=Path(__file__).resolve().parents[1]


def main():
    report={'version':'knowledge-library-1.2.0','model':'e5-multilingual-small-int8','cloud_calls':0,
            'scope':'Synthetic integration; Windows current PC; CPU 2 threads; application network blocked, not OS air gap',
            'checks':[]}
    with tempfile.TemporaryDirectory(prefix='jarvis-knowledge-cycle-') as temp:
        root=Path(temp);core=Core.initialize(root);models=LocalModels(root)
        try:
            shutil.copytree(ROOT/'user-data/local-models'/report['model'],models.folder(report['model']))
            gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
            models.command({'action':'activate','id':report['model'],'revision':models.snapshot()['revision']})
            result=models.future.result(timeout=60)
            if result['status']!='succeeded':raise RuntimeError(result)
            library=Knowledge(core.db);sources=[]
            for title,text in [('饮食','用户喜欢在晚上喝茶。'),('保养','The car needs an oil change.'),('动物','El gato duerme en el sofá.'),('时间','项目会议在周五下午三点召开。')]:
                sources.append(library.save({'id':'','scope':'personal','title':title,'text':text,'paused':False,'providers':['openai']},0))
            start=time.perf_counter();knowledge_vectors.build(root,core.db,lambda:None,lambda n:None)
            report['build_seconds']=time.perf_counter()-start;report['index']=Vectors(core.db).status()
            for query,expected in [('What does the user like drinking?',0),('汽车需要做什么保养？',1),('Where does the cat sleep?',2),('When is the project meeting?',3)]:
                start=time.perf_counter();v=memory.retrieve(root,'personal','openai',True,query)
                report['checks'].append({'query':query,'expected_present':sources[expected]['id'] in [r['id'] for r in v['facts']],
                                        'returned':[r['key'] for r in v['facts']],'retrieval':v['retrieval'],'elapsed_ms':1000*(time.perf_counter()-start)})
            c=Claims(core.db);c.compile('personal',sources[3]['id'],1);claim=c.list('personal')[0]
            item={'scope':'personal','key':'会议时间','value':'项目会议在周五下午三点召开。','kind':'knowledge','purpose':'personal','providers':['openai'],'paused':False,'expires':None}
            accepted=c.accept('personal',claim['id'],1,item,0)
            row=library.detail('personal',sources[3]['id']);updated={k:row[k] for k in ('id','scope','title','text','providers')}
            updated.update(text='项目会议改为周六上午十点。',paused=False);library.save(updated,1)
            report['source_correction_withdraws_claim']=not core.db.one('SELECT 1 FROM facts WHERE id=? AND deleted=0',(accepted['id'],))
            info=models.knowledge_encoder();knowledge_vectors.build(root,core.db,lambda:None,lambda n:None)
            vector=models.encode_knowledge(['When is the project meeting?'],'query',info['space'])[0]
            core.close();core=Core(root)
            rows,state=Vectors(core.db).search('personal','openai',info['space'],vector)
            report['restart_persistent_recall']=any('周六' in r['value'] for r in rows) and all('周五' not in r['value'] for r in rows)
            models.command({'action':'standby','id':report['model'],'revision':models.snapshot()['revision']});models.future.result(timeout=10)
            report['standby_fallback']=memory.retrieve(root,'personal','openai',True,'项目会议')['retrieval']['sources']['semantic']['status']=='model_not_loaded'
            report['passed']=all(c['expected_present'] for c in report['checks']) and all(report[k] for k in ('source_correction_withdraws_claim','restart_persistent_recall','standby_fallback'))
        finally:models.close();core.close()
    target=ROOT/'docs/evidence/knowledge-library-1.2.0';target.mkdir(parents=True,exist_ok=True)
    (target/'real-encoder.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
