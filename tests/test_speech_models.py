"""Independent purpose defaults, dependency admission, cancellation and reader gates."""
import copy,hashlib,json,sqlite3,unittest
from pathlib import Path
from unittest.mock import patch
import test_local_models as embedding_fixture
from host.local_models import LocalModels
from modules.local_models.catalog import builtin
from control.application_compatibility import require_compatible
from sdk.protocol import CoreError

class FakeSpeech:
    def __init__(self,folder):self.process=self;self.closed=False
    def poll(self):return 0 if self.closed else None
    def wait(self,check):check();return {'ready':True,'kind':'stt','memory':{'rss_bytes':400000000,'gpu_bytes':0}}
    def close(self):self.closed=True

class SpeechModelsCase(unittest.TestCase):
    setUp=embedding_fixture.ModelsCase.setUp;tearDown=embedding_fixture.ModelsCase.tearDown
    run_command=embedding_fixture.ModelsCase.run_command;fixture=embedding_fixture.ModelsCase.fixture
    def speech_fixture(self,ident):
        self.m.speech.factory=FakeSpeech;item=copy.deepcopy(next(x for x in builtin() if x['runtime']=='onnx-sensevoice-v1'));item['id']=ident
        folder=self.m.folder(ident);folder.mkdir()
        for f in item['files']:
            data=f['name'].encode();f.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());(folder/f['name']).write_bytes(data)
        self.assertEqual(self.run_command('register',manifest=item)['status'],'succeeded');return item
    def test_stt_selection_and_rollback_never_replace_embedding_default(self):
        self.fixture('embedding');self.run_command('activate',id='embedding');worker=self.m.worker
        self.speech_fixture('speech-a');self.speech_fixture('speech-b')
        for ident in ('speech-a','speech-b'):self.assertEqual(self.run_command('activate',id=ident)['status'],'succeeded')
        self.assertEqual(self.m.snapshot()['selected'],'embedding');self.assertIs(self.m.worker,worker);self.assertEqual(self.m.snapshot()['manager']['state_schema'],3)
        self.assertEqual(self.run_command('uninstall',id='speech-a')['error'],'model_in_use')
        self.assertEqual(self.run_command('speech_rollback')['status'],'succeeded');self.assertEqual(self.m.speech.state()['selected'],'speech-a')
        self.run_command('speech_unselect');self.run_command('speech_retire_previous');self.m.close();self.m=LocalModels(self.root,worker_factory=embedding_fixture.FakeWorker)
        self.assertEqual(self.m.snapshot()['selected'],'embedding');self.assertIsNone(self.m.speech.state()['selected']);self.assertIsNone(self.m.speech.loaded)
    def test_missing_changed_dependency_low_memory_and_benchmark_fail_closed(self):
        self.fixture('embedding');self.run_command('activate',id='embedding');self.speech_fixture('speech-a')
        with patch('modules.local_models.runtime.status',return_value={'ready':False}):self.assertEqual(self.run_command('start',id='speech-a')['error'],'model_runtime_missing')
        with patch('adapters.desktop.resources.sample',return_value={'memory_total':1000,'memory_used':999}):self.assertEqual(self.run_command('start',id='speech-a')['error'],'model_memory')
        self.assertEqual(self.run_command('benchmark',id='speech-a')['error'],'model_benchmark_kind');self.assertEqual(self.m.loaded,'embedding')
    def test_controller9_cannot_write_new_purpose_selection(self):
        self.speech_fixture('speech-a');(self.root/'deployment').mkdir();(self.root/'deployment/controller-protocol.json').write_text('{}')
        with patch('control.controller_pin.read',return_value={'controller_protocol':9}):self.assertEqual(self.run_command('activate',id='speech-a')['error'],'controller_protocol')
        self.assertIsNone(self.m.speech.state()['selected']);self.assertIsNone(self.m.speech.worker)
    def test_new_schema_blocks_old_reader_before_any_data_rewrite(self):
        self.speech_fixture('speech-a');self.run_command('activate',id='speech-a')
        before=self.m.path.read_bytes();old=self.root/'old';(old/'config').mkdir(parents=True)
        with self.assertRaises(CoreError):require_compatible(self.root,old)
        self.assertEqual(self.m.path.read_bytes(),before)
        (old/'config/local-models-compatibility.json').write_text('{"schema":1,"local_models_schema":3}')
        self.assertTrue(require_compatible(self.root,old)['compatible'])

if __name__=='__main__':unittest.main()
