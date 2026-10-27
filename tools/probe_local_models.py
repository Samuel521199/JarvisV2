"""Opt-in real artifact test, isolated network policy and synthetic text only."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
from host.core import Core
from host.local_models import LocalModels
from control.network import NetworkGate


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ident='e5-multilingual-small-int8';report={'scope':'Windows current machine; CPU 2 threads; synthetic samples; application network disabled, not OS air gap','model':ident,'checks':[]}
    with tempfile.TemporaryDirectory(prefix='jarvis-local-model-real-') as temp:
        root=Path(temp);Core.initialize(root).close();m=LocalModels(root)
        try:
            source=ROOT/'user-data/local-models'/ident;shutil.copytree(source,m.folder(ident))
            gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
            def command(action,**kw):
                m.command({'action':action,'revision':m.snapshot()['revision'],**kw});r=m.future.result(timeout=90)
                if r['status']!='succeeded':raise RuntimeError(r)
                return r['result']
            start=time.monotonic();command('activate',id=ident);report['cold_start_seconds']=time.monotonic()-start
            docs=['用户喜欢在晚上喝茶。','The car needs an oil change.','El gato duerme en el sofá.','明天上午十点开项目会议。']
            dv=command('embed',role='passage',texts=docs)['vectors']
            queries=['What does the user like drinking?','汽车需要做什么保养？','¿Dónde duerme el gato?','When is the project meeting?']
            q=command('embed',role='query',texts=queries);report['memory']=q['memory'];report['query_batch_seconds']=q['elapsed_seconds'];report['vector_space']=q['vector_space']
            for i,v in enumerate(q['vectors']):
                scores=[sum(a*b for a,b in zip(v,d)) for d in dv];rank=max(range(len(scores)),key=scores.__getitem__)
                report['checks'].append({'query':queries[i],'expected':i,'actual':rank,'passed':rank==i,'scores':scores})
            command('standby',id=ident);report['standby_loaded']=m.loaded;report['disk_bytes']=sum(p.stat().st_size for p in m.folder(ident).iterdir())
            command('start',id=ident);report['offline_restart_passed']=m.loaded==ident
            report['worker_runtime']=m.worker.request(['hello'],'query',m._check)['memory']
        finally:m.close()
    dest=ROOT/'docs/evidence/local-model-manager-2026-10-23.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
    if not all(x['passed'] for x in report['checks']):sys.exit(1)


if __name__=='__main__':main()
