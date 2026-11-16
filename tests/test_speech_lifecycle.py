"""Managed startup initializes speech without admitting work before active."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from control.application_runtime import publish
from host.speech import Speech,Unavailable,create
from modules.speech.store import Store
from sdk.protocol import CoreError


class SpeechLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'state').mkdir()
        self.models=SimpleNamespace(speech=SimpleNamespace())

    def phase(self,value):publish(self.root,'a'*64,3,value)

    def test_starting_reconciles_unknown_but_commands_wait_for_active(self):
        with Store(self.root) as store:store.add('interrupted',{'operation':'transcribe','scope':{'purpose':'chat','chat_id':'synthetic','exercise_id':None}})
        self.phase('starting');speech=create(self.root,self.models,None)
        self.assertIsInstance(speech,Speech);self.addCleanup(speech.close)
        with Store(self.root) as store:
            self.assertEqual(store.get('interrupted')['state'],'UNKNOWN')
            before=store.config()
        with self.assertRaises(CoreError) as caught:
            speech.command({'action':'configure','enabled':False,'revision':0})
        self.assertEqual(caught.exception.code,'application_maintenance')
        with Store(self.root) as store:self.assertEqual(store.config(),before)
        self.assertEqual(speech.futures,{})
        self.phase('active')
        speech.command({'action':'configure','enabled':False,'revision':0})
        with Store(self.root) as store:self.assertEqual(store.config(),{'enabled':False,'revision':1})
        self.phase('draining')
        with self.assertRaises(CoreError):speech.command({'action':'configure','enabled':True,'revision':1})

    def test_draining_stopped_blocked_and_invalid_coordination_never_initialize(self):
        for phase in ('draining','stopped','blocked'):
            with self.subTest(phase=phase):
                self.phase(phase);speech=create(self.root,self.models,None)
                self.assertIsInstance(speech,Unavailable)
                self.assertEqual(speech.error,'application_maintenance')
                self.assertFalse((self.root/'state/speech.sqlite3').exists())
        (self.root/'state/application-host.json').write_text('{}')
        speech=create(self.root,self.models,None)
        self.assertIsInstance(speech,Unavailable)
        self.assertEqual(speech.error,'application_state_invalid')
        self.assertFalse((self.root/'state/speech.sqlite3').exists())

    def test_managed_startup_still_requires_a_valid_compatible_controller(self):
        self.phase('starting')
        (self.root/'deployment').mkdir()
        (self.root/'deployment/controller-protocol.json').write_text('{"schema":1,"minimum":10}')
        speech=create(self.root,self.models,None)
        self.assertIsInstance(speech,Unavailable)
        self.assertFalse((self.root/'state/speech.sqlite3').exists())
