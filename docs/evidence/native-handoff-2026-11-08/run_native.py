"""Existing reviewed runtimes, disposable data, actual Blender/engineering/handoff.

Run with --installation <existing install> --work-root <new disposable directory>.
Only optional-runtime preparation records are read from the existing installation.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from adapters.application_host import WorkbenchProcess
from control.application_runtime import LocalApprovals, publish
from control.local_access import install_client
from control.worker.process import OwnedProcess
from host.core import Core
from host import anatomy_engineering as engineering, studio3d_learning as learning


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(args, folder, name, env=None):
    with (folder/(name+'.stdout')).open('wb') as out, (folder/(name+'.stderr')).open('wb') as err:
        with OwnedProcess(args, stdout=out, stderr=err, env=env or dict(os.environ), cwd=folder,
                          processes=2, cpu_seconds=1200, memory_bytes=4*1024**3) as proc:
            code = proc.wait(300)
            if code: raise RuntimeError(name+' failed; see retained native logs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installation', required=True, type=Path)
    parser.add_argument('--work-root', required=True, type=Path)
    args = parser.parse_args()
    work = args.work_root.resolve(); work.mkdir(parents=True, exist_ok=False)
    data = work/'data'; Core.initialize(data).close()
    report = {'scope':'development checkout; real native execution with synthetic inputs; not deployment',
              'work_root':str(work), 'status':'running', 'stages':{}, 'production_records_read':[]}
    report['sources_sha256'] = {name:sha(ROOT/name) for name in [
        'control/worker/process.py','host/studio3d.py','host/studio3d_learning.py',
        'host/anatomy_engineering.py','apps/workbench/runtime_http.py',
        'sdk/application_policy.py','modules/skills/studio3d/worker-programs.json']}
    def save(): (HERE/'native-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    def passed(name, value):
        report['stages'][name] = value; save(); print(name+': passed', flush=True)
    save()
    try:
        records = {}
        for kind in ('studio3d', 'anatomy'):
            source = args.installation.resolve()/'user-data/optional'/kind/'prepared.json'
            raw = source.read_bytes(); records[kind] = json.loads(raw)
            target = data/'optional'/kind/'prepared.json'; target.parent.mkdir(parents=True); target.write_bytes(raw)
            report['production_records_read'].append({'path':str(source),'sha256':sha(source)})
        blender = Path(records['studio3d']['executable'])
        python = args.installation.resolve()/'.venv/anatomy/Scripts/python.exe'
        assert blender.is_file() and sha(blender) == records['studio3d']['executable_sha256']
        assert sha(ROOT/'modules/skills/studio3d/runtime.json') == records['studio3d']['runtime_sha256']
        assert sha(ROOT/'modules/skills/anatomy/runtime-lock.json') == records['anatomy']['lock_sha256']
        assert python.is_file() and python.resolve() == Path(records['anatomy']['python']).resolve()
        metadata_code = "import importlib.metadata as m,json;print(json.dumps({k:m.version(k) for k in ['cadquery-ocp','cantera','numpy']}))"
        bounded([str(python), '-I', '-c', metadata_code], work, 'engineering-versions')
        versions = json.loads((work/'engineering-versions.stdout').read_text())
        lock = json.loads((ROOT/'modules/skills/anatomy/runtime-lock.json').read_text())
        for package in lock['packages']:
            if package['name'] in versions: assert versions[package['name']] == package['version']
        passed('runtime_identity', {'blender_sha256':sha(blender),'python_sha256':sha(python),'package_versions':versions})

        # Route only runtime location/preparation discovery to the copied test
        # record and reviewed existing interpreter. No solver/worker is mocked.
        with patch.object(engineering, 'installation_data_root', return_value=data), patch.object(engineering, 'runtime_python', return_value=python):
            suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_anatomy_engineering.py')
            with (HERE/'engineering.log').open('w',encoding='utf-8') as stream:
                result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        passed('engineering', {'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)})
        assert result.wasSuccessful() and not result.skipped, 'Native engineering acceptance failed'

        # Real managed HTTP host, ephemeral port, actual native render and signed
        # drain/shutdown requests. No model route or user asset is used.
        LocalApprovals(data).initialize()
        with socket.socket() as free: free.bind(('127.0.0.1',0)); port=free.getsockname()[1]
        driver = WorkbenchProcess(data, port, timeout=30)
        selected = {'build':'e'*64,'epoch':1,'slot':'A'}
        publish(data, selected['build'], 1, 'starting')
        out = (work/'host.stdout').open('wb'); err = (work/'host.stderr').open('wb')
        process = subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'apps/workbench/server.py'),
            '--data-root',str(data),'--port',str(port),'--application-build',selected['build'],'--application-epoch','1'],
            stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        driver.processes[1] = process
        def request(path, body=None):
            req = urllib.request.Request(driver.origin+path, data=json.dumps(body).encode() if body is not None else None,
                headers={'Origin':driver.origin,'Content-Type':'application/json','X-Jarvis-Token':token})
            with urllib.request.urlopen(req, timeout=8) as reply: return json.load(reply)
        try:
            driver.health(selected,1); publish(data,selected['build'],1,'active'); driver.activate(selected,1)
            install_client(driver.origin, data)
            with urllib.request.urlopen(driver.origin+'/api/session') as reply: token=json.load(reply)['token']
            scene={'schema':'jarvis.studio3d.v1','units':'m','title':'Lifecycle cube',
                'materials':[{'id':'paint','color':'#3187a8'}],
                'objects':[{'id':'support','kind':'box','material':'paint','params':{'size':[1,.8,.1]}}],
                'unfulfilled':['Synthetic process acceptance; no art or manufacturing score.'],
                'render':{'engine':'CYCLES','quality':'preview','view':'front'}}
            ident='1'*32
            request('/api/studio3d/jobs',{'id':ident,'scene':scene})
            deadline=time.monotonic()+90
            stdout=data/'artifacts/studio3d'/ident/'stdout.log'
            while not (stdout.exists() and stdout.stat().st_size):
                state=request('/api/studio3d/jobs/'+ident)
                assert state['status'] not in ('FAILED','UNKNOWN','CANCELLED'), state
                if time.monotonic()>deadline: raise RuntimeError('Native render did not begin')
                time.sleep(.05)
            publish(data,selected['build'],1,'draining')
            busy=driver.request(selected,1,'drain')
            assert not busy['drained'] and any(r['id']=='studio3d' and r['active'] for r in busy['participants'])
            try: driver.request(selected,1,'shutdown')
            except urllib.error.HTTPError as error:
                refusal=json.load(error); assert refusal['error']=='application_not_drained',refusal
            else: raise AssertionError('Shutdown accepted while real native render was active')
            assert process.poll() is None
            try: request('/api/studio3d/jobs',{'id':'2'*32,'scene':scene})
            except urllib.error.HTTPError as error:
                rejected=json.load(error); assert rejected['error']=='application_maintenance',rejected
            else: raise AssertionError('New work accepted during drain')
            driver.drain(selected,1)
            state=request('/api/studio3d/jobs/'+ident)
            assert state['status']=='DELIVERED',state
            resource=json.loads((data/'artifacts/studio3d'/ident/'execution.json').read_text())
            assert resource['exit_code']==0 and resource['peak_job_memory_bytes']>0
            receipt=json.loads(state['receipt']) if isinstance(state.get('receipt'),str) else state['receipt']
            assert all(sha(data/'artifacts/studio3d'/ident/name)==row['sha256'] for name,row in receipt['files'].items())
            driver.stop(selected,1); assert process.poll() is not None
            passed('native_drain_shutdown', {'busy_snapshot':busy,'shutdown_refusal':refusal,
                'new_work_refusal':rejected,'final_status':state['status'],'resources':resource,'host_exit_code':process.returncode})
        finally:
            if process.poll() is None: process.terminate()
            process.wait(10); out.close(); err.close()

        # Authored tiny defective coupons; real fixed learning/repair tools.
        bounded([str(blender),'--background','--factory-startup','--disable-autoexec','--python-exit-code','2',
            '--python',str(ROOT/'tools/create_studio3d_learning_fixtures.py'),'--',str(work/'fixtures')], work,'fixture-build')
        folder=work/'fixtures/plate'
        receipt=learning.run(data,(folder/'source.glb').read_bytes(),json.loads((folder/'contract.json').read_text()),repair=True,render=True)
        assert receipt['status']=='REPAIRED_DECLARED_CHECKS',receipt['status']
        assert len(receipt['adoptions'])==2 and receipt['result']['gltf_validation']['issues']['numErrors']==0
        passed('native_learning',{'status':receipt['status'],'adoptions':receipt['adoptions'],
            'receipt':str(Path(receipt['folder'])/'receipt.json'),'model_calls':receipt['cost']['model_calls']})
        report['status']='passed'; save()
    except BaseException as error:
        report.update(status='failed',error=type(error).__name__+': '+str(error)); save(); raise


if __name__=='__main__': main()
