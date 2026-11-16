"""Live and queued speech work participates in the original managed idle gate."""
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
import tempfile,threading,unittest
from host.runtime_participants import snapshot
from host.speech import Unavailable


class SpeechShutdownAdmission(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def view(self,**objects):return snapshot(self.root,SimpleNamespace(**objects))
    def row(self,view,name):return next(r for r in view['participants'] if r['id']==name)
    def test_missing_or_unavailable_optional_speech_is_not_running(self):
        for objects in ({},{'speech':Unavailable('missing_model')}):
            view=self.view(**objects);self.assertTrue(view['drained']);self.assertEqual(self.row(view,'speech')['state'],'not_started')
    def test_queued_and_running_jobs_both_block_idle(self):
        for running in (False,True):
            future=Future()
            if running:future.set_running_or_notify_cancel()
            view=self.view(speech=SimpleNamespace(lock=threading.RLock(),futures={'speech-example':future}))
            self.assertFalse(view['drained']);self.assertEqual(self.row(view,'speech')['active'],1)
    def test_completed_and_cancelled_jobs_no_longer_block_idle(self):
        complete=Future();complete.set_result(None);cancelled=Future();cancelled.cancel()
        view=self.view(speech=SimpleNamespace(lock=threading.RLock(),futures={'one':complete,'two':cancelled}))
        self.assertTrue(view['drained']);self.assertEqual(self.row(view,'speech')['active'],0)
    def test_inspection_failure_blocks_handoff(self):
        view=self.view(speech=SimpleNamespace(lock=threading.RLock(),futures={'broken':None}))
        self.assertFalse(view['drained']);self.assertEqual(self.row(view,'speech')['state'],'unknown')
        malformed=self.view(speech=SimpleNamespace(error='arbitrary_missing_lock'))
        self.assertFalse(malformed['drained']);self.assertEqual(self.row(malformed,'speech')['state'],'unknown')
    def test_stt_manager_inference_blocks_without_a_manager_future(self):
        manager=SimpleNamespace(lock=threading.RLock(),future=None,recall_future=None,speech=SimpleNamespace(busy=True))
        view=self.view(local_models=manager);self.assertFalse(view['drained']);self.assertEqual(self.row(view,'local_models')['active'],1)
        manager.speech.busy=False;self.assertTrue(self.view(local_models=manager)['drained'])


if __name__=='__main__':unittest.main()
