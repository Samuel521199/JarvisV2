"""Reproducible synthetic source/index checks; no credentials, model calls or network."""
import json
from pathlib import Path
import statistics
import tempfile
import threading
import time

from host.core import Core
from host import memory
from modules.context_knowledge.knowledge import Knowledge

ROOT=Path(__file__).resolve().parents[1]


def timed(call):
    start=time.perf_counter();value=call();return value,(time.perf_counter()-start)*1000


def summary(values):
    ordered=sorted(values)
    return {'n':len(values),'p50_ms':statistics.median(values),'p95_ms':ordered[int((len(ordered)-1)*.95)],'max_ms':max(values)}


def main():
    report={'version':'knowledge-library-1.0.0','cloud_calls':0,'environment':'Current Windows development PC; synthetic text, lexical retrieval, no models',
            'scope':'10k-scale development probe, not held-out answer quality or 30-day/low-memory acceptance'}
    with tempfile.TemporaryDirectory(prefix='jarvis-knowledge-probe-') as folder:
        root=Path(folder);core=Core.initialize(root);library=Knowledge(core.db)
        try:
            t=time.perf_counter()
            for i in range(100):
                text=''.join(f'Entry {i:03d}-{j:04d}: ordinary reference material in this section.\n' for j in range(1000))
                text+=f'\nSPEC{i:03d} torque is {37+i} Nm.\n'
                library.save({'id':'','scope':'personal','title':f'Handbook {i:03d}','text':text,'providers':['openai'],'paused':False},0)
            report['ingest_ms']=(time.perf_counter()-t)*1000
            report['chunks']=core.db.one('SELECT count(*) AS n FROM knowledge_chunks')['n']
            report['build'],report['build_ms']=timed(library.rebuild)
            def recall(i=77):return memory.retrieve(root,'personal','openai',True,f'SPEC{i:03d}')
            first,report['first_after_build_ms']=timed(recall)
            for i in range(40):recall(i)
            baseline=[];success=[]
            for i in range(60):
                result,ms=timed(lambda:recall(i%40));baseline.append(ms)
                success.append(any(f'SPEC{i%40:03d}' in r['value'] for r in result['facts']))
            report['warm']=summary(baseline);report['targets_found']=sum(success)
            started=threading.Event();outcome={}
            def background():
                db,_=memory.open_memory(root)
                try:outcome['result']=Knowledge(db).rebuild(progress=lambda _:started.set())
                except Exception as e:outcome['error']=type(e).__name__
                finally:db.close()
            worker=threading.Thread(target=background);worker.start();started.wait(10)
            concurrent=[]
            while worker.is_alive() and len(concurrent)<60:
                _,ms=timed(lambda:recall(len(concurrent)%40));concurrent.append(ms)
            worker.join();report['rebuild_concurrent']=summary(concurrent) if concurrent else None;report['background']=outcome
            report['core_database_bytes']=(root/'state/core.sqlite3').stat().st_size
            report['sqlite_files_bytes']=sum(p.stat().st_size for p in (root/'state').glob('core.sqlite3*'))
            report['paired_query_sequence']='SPEC000..SPEC039 then SPEC000..SPEC019; warmup all 40 before baseline'
            report['passed']=all(success) and 'error' not in outcome and first['retrieval']['sources']['mode']=='fts5'
            report['timing_targets']={'lexical_warm_p95_100ms':report['warm']['p95_ms']<=100,
                'foreground_p95_increase_20pct':bool(concurrent) and report['rebuild_concurrent']['p95_ms']<=report['warm']['p95_ms']*1.2}
        finally:core.close()
    target=ROOT/'docs/evidence/knowledge-library-1.0.0';target.mkdir(exist_ok=True)
    (target/'scale-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
