"""Opt-in real E5 calibration/benchmark; no download and no production policy edit."""
import json
from pathlib import Path
import shutil
import tempfile
import time
from host.core import Core
from host.local_models import LocalModels
from control.network import NetworkGate
from sdk.protocol import PROJECT


def main():
    ident='e5-multilingual-small-int8'
    with tempfile.TemporaryDirectory(prefix='jarvis-model-calibration-') as temp:
        root=Path(temp);Core.initialize(root).close();m=LocalModels(root)
        try:
            shutil.copytree(PROJECT/'user-data/local-models'/ident,m.folder(ident))
            gate=NetworkGate(root);gate.update({'revision':gate.read()['revision'],'blocked':True})
            start=time.perf_counter()
            m.command({'action':'benchmark','id':ident,'revision':m.snapshot()['revision']})
            result=m.future.result(timeout=120)
            if result['status']!='succeeded':raise RuntimeError(result)
            state=m.snapshot();row=next(x for x in state['models'] if x['id']==ident)
            report={'module_version':state['manager']['version'],'scope':'Windows current machine; CPU 2 threads; application network disabled, not OS air gap',
                    'model':ident,'total_seconds':time.perf_counter()-start,'assessment':row['assessment'],
                    'standby_restored':m.loaded is None,'disk_bytes':row['disk_bytes']}
            m.close();m=LocalModels(root)
            after=next(x for x in m.snapshot()['models'] if x['id']==ident)
            report['restart_preserved']=after['assessment']['expected']==row['assessment']['expected'] and after['assessment']['benchmark']==row['assessment']['benchmark']
            if not report['restart_preserved'] or not report['standby_restored']:raise RuntimeError('Calibration persistence regression')
        finally:m.close()
    path=PROJECT/'docs/evidence/local-model-assessments-1.1.0.json'
    path.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'evidence':str(path),'metrics':report['assessment']['benchmark'],'memory':report['assessment']['measured']},ensure_ascii=False))


if __name__=='__main__':main()
