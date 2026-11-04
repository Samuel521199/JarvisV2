"""Real managed workbench lifecycle with synthetic data; no model or mailbox access."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from unittest.mock import Mock
import threading

from adapters.application_host import WorkbenchProcess
from control.application_runtime import LocalApprovals, publish
from control.local_access import LocalAccess, install_client, read_key
from host.core import Core

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Managed session persistence currently uses Windows DPAPI')
class ApplicationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-runtime-test-')
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'data'
        Core.initialize(self.root).close()

    def tearDown(self):
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith('jarvis-runtime-test-'))
        self.temp.cleanup()

    def test_managed_browser_session_survives_host_restart(self):
        first = LocalAccess(self.root, persist_sessions=True)
        token = first.unlock(first.key)
        second = LocalAccess(self.root, persist_sessions=True)
        self.assertTrue(second.valid(token))
        self.assertNotIn(token.encode(), (self.root / 'private/workbench-sessions.dpapi').read_bytes())

    def test_key_rotation_does_not_restore_old_browser_sessions(self):
        first = LocalAccess(self.root, key='a' * 43, persist_sessions=True)
        token = first.unlock(first.key)
        self.assertFalse(LocalAccess(self.root, key='b' * 43, persist_sessions=True).valid(token))

    def test_expired_browser_session_is_not_revived_by_restart(self):
        with patch('time.time', return_value=100000):
            first = LocalAccess(self.root, persist_sessions=True)
            token = first.unlock(first.key)
        with patch('time.time', return_value=200000):
            self.assertFalse(LocalAccess(self.root, persist_sessions=True).valid(token))

    def test_corrupt_browser_session_state_cannot_unlock(self):
        first = LocalAccess(self.root, persist_sessions=True)
        token = first.unlock(first.key)
        (self.root / 'private/workbench-sessions.dpapi').write_bytes(b'corrupt synthetic state')
        self.assertFalse(LocalAccess(self.root, persist_sessions=True).valid(token))

    def test_queued_dialogue_waits_during_handoff_and_resumes_once(self):
        from host.dialogue import DialogueHost
        from types import SimpleNamespace
        host = object.__new__(DialogueHost)
        host.root, host.closing = self.root, threading.Event()
        host.running, host.pending = {}, {'synthetic-turn': {'chat_id': 'synthetic-chat', 'lane': 'foreground'}}
        submit = Mock()
        host.pool = host.background_pool = SimpleNamespace(submit=submit)
        publish(self.root, 'a' * 64, 1, 'draining')
        host._pump()
        self.assertEqual(submit.call_count, 0)
        self.assertTrue(host.pending)
        publish(self.root, 'a' * 64, 1, 'active')
        host._pump(); host._pump()
        self.assertEqual(submit.call_count, 1)

    def test_background_model_lane_cannot_admit_new_work_during_handoff(self):
        from host.background import BackgroundLane
        from sdk.protocol import CoreError
        lane = BackgroundLane(self.root)
        callback = Mock()
        try:
            publish(self.root, 'a' * 64, 1, 'draining')
            with self.assertRaises(CoreError): lane.submit('synthetic', 'one', callback)
            self.assertEqual(callback.call_count, 0)
        finally:
            lane.close()

    def test_real_workbench_drain_restart_cookie_and_chat_continuity(self):
        LocalApprovals(self.root).initialize()
        with socket.socket() as free:
            free.bind(('127.0.0.1', 0))
            port = free.getsockname()[1]
        driver = WorkbenchProcess(self.root, port, timeout=15)
        origin = driver.origin
        processes = []

        def launch(build, epoch):
            publish(self.root, build, epoch, 'starting')
            selected = {'build': build, 'epoch': epoch, 'slot': 'A' if epoch == 1 else 'B'}
            with (self.base / ('stderr-' + str(epoch))).open('wb') as error, (self.base / ('stdout-' + str(epoch))).open('wb') as out:
                process = subprocess.Popen([sys.executable, '-I', '-B', str(ROOT / 'apps/workbench/server.py'),
                    '--data-root', str(self.root), '--port', str(port), '--application-build', build,
                    '--application-epoch', str(epoch)], stdout=out, stderr=error,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            processes.append(process)
            driver.processes[epoch] = process
            driver.health(selected, epoch)
            return selected

        try:
            first = launch('a' * 64, 1)
            publish(self.root, first['build'], 1, 'active')
            driver.activate(first, 1)
            install_client(origin, self.root)
            with urllib.request.urlopen(origin + '/api/session') as response:
                old_nonce = json.load(response)['token']
            request = urllib.request.Request(origin + '/api/chats', data=b'{}',
                headers={'Origin': origin, 'Content-Type': 'application/json', 'X-Jarvis-Token': old_nonce})
            with urllib.request.urlopen(request) as response:
                chat = json.load(response)['id']
            old_boot = driver.metadata()['boot_id']
            stale_proof = LocalApprovals(self.root).sign({'build': first['build'], 'epoch': 1,
                                                        'boot_id': old_boot, 'action': 'shutdown'})
            publish(self.root, first['build'], 1, 'draining')
            with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(request)
            driver.drain(first, 1)
            driver.stop(first, 1)
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(read_key(self.root) not in (self.base / 'stdout-1').read_text(encoding='utf-8'))
            second = launch('b' * 64, 2)
            # Original browser cookie remains accepted; no key/Google reauthorization.
            with urllib.request.urlopen(origin + '/api/session') as response:
                self.assertTrue(json.load(response)['token'] != old_nonce)
            with urllib.request.urlopen(origin + '/api/chats/' + chat) as response:
                self.assertEqual(json.load(response)['id'], chat)
            replay = urllib.request.Request(origin + '/api/runtime/shutdown',
                data=json.dumps({'build': first['build'], 'epoch': 1}).encode(),
                headers={'Origin': origin, 'Content-Type': 'application/json', 'X-Jarvis-Application-Proof': stale_proof})
            with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(replay)
            self.assertEqual(error.exception.code, 403)
            self.assertEqual(driver.metadata()['application_epoch'], 2)
            publish(self.root, second['build'], 2, 'active')
            driver.activate(second, 2)
            publish(self.root, second['build'], 2, 'draining')
            driver.stop(second, 2)
        finally:
            # Only subprocess handles created by this disposable test are terminated on failure.
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
