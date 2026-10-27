"""Synthetic 10k-vector projection timing, not semantic answer quality."""
import json
from pathlib import Path
import statistics
import tempfile
import time

from host.core import Core
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.vectors import Vectors, pack
from sdk.protocol import digest


def main():
    report={'version':'knowledge-library-1.2.0','scope':'Current Windows PC, synthetic vectors; no encoder or LLM latency included','samples':60}
    with tempfile.TemporaryDirectory(prefix='jarvis-vector-scale-') as temp:
        core=Core.initialize(Path(temp))
        try:
            library=Knowledge(core.db);ident='synthetic-scale';dimension=384
            raw=pack([1.]+[0.]*383,dimension)
            for i in range(100):
                source=library.save({'id':'','scope':'personal','title':f'压力样本{i}','text':'甲'*10000,'providers':['openai'],'paused':False},0)
                with core.db.transaction() as tx:
                    tx.executemany('INSERT INTO knowledge_vectors VALUES(?,?,?,?,?,?)',[(ident,source['id'],1,j*100,j*100+100,raw) for j in range(100)])
            with core.db.transaction() as tx:
                tx.execute('INSERT INTO knowledge_vector_spaces VALUES(?,?,?,?,?,?)',(ident,'test',dimension,library.epoch(),'ready',time.time()))
                tx.execute("UPDATE meta SET value=? WHERE key='knowledge_vector_active'",(ident,))
            index=Vectors(core.db);query=[1.]+[0.]*383;elapsed=[];states=[]
            for i in range(report['samples']+5):
                started=time.perf_counter();rows,state=index.search('personal','openai','test',query,time.monotonic()+.35)
                if i>=5:elapsed.append(1000*(time.perf_counter()-started));states.append(state['status'])
            report.update(vectors=10000,dimensions=dimension,p50_ms=statistics.median(elapsed),p95_ms=sorted(elapsed)[56],max_ms=max(elapsed),
                          timeouts=states.count('timeout'),returned_states=sorted(set(states)))
            report['passed']=not report['timeouts'] and report['p95_ms']<=350
        finally:core.close()
    target=Path(__file__).resolve().parents[1]/'docs/evidence/knowledge-library-1.2.0/vector-scale.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
