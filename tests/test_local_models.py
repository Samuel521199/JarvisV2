import copy
import hashlib
import io
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from host.core import Core
from host.local_models import LocalModels,create_manager
from modules.local_models.catalog import builtin,validate,space
from adapters.models.local_download import fetch
from control.network import NetworkGate
from control.recovery.gate import StopGate
from sdk.protocol import CoreError


class FakeWorker:
    fail=False
    def __init__(self,folder):self.process=self;self.closed=False
    def poll(self):return 0 if self.closed else None
    def wait(self,check):check();return {'ready':True,'dimension':384}
    def request(self,texts,role,check):
        check()
        if self.fail:raise CoreError('local_inference','bad candidate')
        return {'dimension':384,'vectors':[[1.0]+[0.0]*383 for _ in texts],'memory':{'rss_bytes':123,'gpu_bytes':0}}
    def close(self):self.closed=True


class ModelsCase(unittest.TestCase):
    def setUp(self):
        self.runtime=patch('host.local_models.runtime_status',return_value={'ready':True});self.runtime.start()
        self.addCleanup(self.runtime.stop)
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-local-model-test-');self.root=Path(self.temp.name);Core.initialize(self.root).close();self.m=LocalModels(self.root,worker_factory=FakeWorker)
    def tearDown(self):self.m.close();self.temp.cleanup()
    def run_command(self,action,**kw):
        self.m.command({'action':action,'revision':self.m.snapshot()['revision'],**kw})
        return self.m.future.result(timeout=5)
    def fixture(self,id):
        item=copy.deepcopy(builtin()[0]);item['id']=id
        folder=self.m.folder(id);folder.mkdir()
        for f in item['files']:
            data=f['name'].encode();f['bytes']=len(data);f['sha256']=hashlib.sha256(data).hexdigest();(folder/f['name']).write_bytes(data)
        self.assertEqual(self.run_command('register',manifest=item)['status'],'succeeded');return item
    def test_multilingual_fixed_dimension_and_immutable_revision(self):
        a=self.fixture('a');bad=copy.deepcopy(a);bad['dimensions']=[128,384]
        with self.assertRaises(CoreError):validate(bad)
        bad=copy.deepcopy(a);bad['revision']='b'*40
        self.assertEqual(self.run_command('register',manifest=bad)['error'],'model_immutable')
        self.assertNotEqual(space(a),space(bad))
    def test_activation_failed_replacement_keeps_old_rollback_and_retirement(self):
        a=self.fixture('a');b=self.fixture('b');b['recipe']='e5-prefix-mean-l2-v1'
        self.assertEqual(self.run_command('activate',id='a')['status'],'succeeded')
        FakeWorker.fail=True
        try:self.assertEqual(self.run_command('activate',id='b')['status'],'failed')
        finally:FakeWorker.fail=False
        self.assertEqual(self.m.snapshot()['selected'],'a');self.assertEqual(self.m.loaded,'a')
        self.assertEqual(self.run_command('activate',id='b')['status'],'succeeded')
        self.assertEqual(self.run_command('uninstall',id='a')['error'],'model_in_use')
        self.run_command('rollback');self.assertEqual(self.m.loaded,'a')
        self.run_command('standby',id='a');self.assertIsNone(self.m.worker);self.assertTrue(self.m.folder('a').exists())
        self.run_command('retire_previous');self.assertEqual(self.run_command('uninstall',id='b')['status'],'succeeded')
    def test_offline_inference_and_no_raw_input_in_state(self):
        self.fixture('a');self.run_command('start',id='a');gate=NetworkGate(self.root);gate.update({'revision':gate.read()['revision'],'blocked':True})
        r=self.run_command('embed',texts=['private-canary'],role='query');self.assertEqual(r['status'],'succeeded')
        self.assertNotIn('vectors',json.dumps(self.m.snapshot()));self.assertNotIn('private-canary',self.m.path.read_bytes().decode(errors='ignore'))
        self.assertEqual(self.run_command('download',id='a')['error'],'model_in_use')
        self.run_command('standby',id='a');self.assertEqual(self.run_command('download',id='a')['error'],'network_disabled')
    def test_corruption_rejected_and_unknown_adapter_never_ready(self):
        a=self.fixture('a');(self.m.folder('a')/'model.onnx').write_bytes(b'corrupt')
        self.assertEqual(self.run_command('start',id='a')['error'],'model_integrity')
        self.assertEqual(self.run_command('start',id='qwen3-embedding-06b-q8')['error'],'model_adapter_missing')
    def test_stop_unloads_and_restart_does_not_autoload(self):
        self.fixture('a');self.run_command('activate',id='a');StopGate(self.root).stop();self.m.snapshot();self.assertIsNone(self.m.loaded)
        self.m.close();self.m=LocalModels(self.root,worker_factory=FakeWorker);self.assertIsNone(self.m.loaded);self.assertEqual(self.m.snapshot()['selected'],'a')
    def test_revision_and_single_owner(self):
        self.fixture('a')
        with self.assertRaises(CoreError):self.m.command({'action':'start','id':'a','revision':0})
        with self.assertRaises(CoreError):LocalModels(self.root)
    def test_missing_dependencies_low_memory_and_bad_fields(self):
        self.fixture('a')
        with patch('host.local_models.runtime_status',return_value={'ready':False}):
            self.assertEqual(self.run_command('start',id='a')['error'],'model_runtime_missing')
        with patch('host.local_models.resources',return_value={'memory_total':1024,'memory_used':1000}):
            self.assertEqual(self.run_command('start',id='a')['error'],'model_memory')
        for field,value in [('id',{}),('kind',[]),('source',None)]:
            bad=copy.deepcopy(builtin()[0]);bad[field]=value
            with self.assertRaises(CoreError):validate(bad)
        for name in ['..','CON','x.','model.onnx.part']:
            bad=copy.deepcopy(builtin()[0]);bad['files'][0]['name']=name
            with self.assertRaises(CoreError):validate(bad)
    def test_download_resume_full_response_restart_and_digest(self):
        data=b'abcdef';a={'bytes':6,'sha256':hashlib.sha256(data).hexdigest()};dest=self.root/'artifact';partial=self.root/'artifact.part';partial.write_bytes(b'abc')
        class Response(io.BytesIO):
            status=206;headers={'Content-Range':'bytes 3-5/6'}
        with patch('urllib.request.OpenerDirector.open',return_value=Response(b'def')):
            fetch('https://huggingface.co/x/y/resolve/'+'a'*40+'/m',dest,a,lambda:None,lambda n:None)
        self.assertEqual(dest.read_bytes(),data)
        dest.unlink();partial.write_bytes(b'abc')
        response=Response(data);response.status=200
        with patch('urllib.request.OpenerDirector.open',return_value=response):fetch('https://huggingface.co/x/y',dest,a,lambda:None,lambda n:None)
        self.assertEqual(dest.read_bytes(),data)
        dest.unlink()
        response=Response(b'xxxxxx');response.status=200
        with patch('urllib.request.OpenerDirector.open',return_value=response):
            with self.assertRaises(CoreError):fetch('https://huggingface.co/x/y',dest,a,lambda:None,lambda n:None)
        self.assertFalse(dest.exists());self.assertFalse(partial.exists())
    def test_corrupt_optional_state_does_not_prevent_core_and_releases_lease(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-model-corrupt-') as temp:
            root=Path(temp);Core.initialize(root).close();path=root/'config/local-models.sqlite3'
            path.write_bytes(b'not-sqlite')
            disabled=create_manager(root)
            self.assertEqual(disabled.snapshot()['manager']['status'],'unavailable')
            with self.assertRaises(CoreError):disabled.command({'action':'start'})
            # The independent core remains readable and the manager's lease was released.
            core=Core(root);self.assertEqual(core.status()['control'],'ready');core.close()
            path.unlink();manager=LocalModels(root)
            manager.close();disabled.close()
            db=sqlite3.connect(path)
            try:db.execute('PRAGMA user_version=3');db.commit()
            finally:db.close()
            self.assertEqual(create_manager(root).snapshot()['manager']['error'],'model_state_version')


if __name__=='__main__':unittest.main()
