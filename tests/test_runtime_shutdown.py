"""Shutdown must independently enforce the durable host drain barrier."""
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from apps.workbench import runtime_http
from control.application_runtime import publish
from control.runtime_activity import RequestActivity
from host.core import Core
from sdk.protocol import CoreError


class RuntimeShutdown(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Core.initialize(self.root).close()
        self.build = 'd' * 64
        publish(self.root, self.build, 1, 'draining')
        self.stopped = threading.Event()
        self.server = SimpleNamespace(data_root=self.root, application_build=self.build,
            application_epoch=1, request_activity=RequestActivity(), shutdown=Mock(side_effect=self.stopped.set))
        self.handler = SimpleNamespace(server=self.server, json=Mock())

    def shutdown(self):
        return runtime_http.post(self.handler, '/api/runtime/shutdown', {'build':self.build, 'epoch':1})

    def test_inflight_request_blocks_direct_shutdown(self):
        with self.server.request_activity.track():
            with self.assertRaises(CoreError) as error: self.shutdown()
        self.assertEqual(error.exception.code, 'application_not_drained')
        self.server.shutdown.assert_not_called()
        self.handler.json.assert_not_called()

    def test_unknown_participant_blocks_shutdown_without_details(self):
        self.server.dialogues = SimpleNamespace(state=Mock(side_effect=RuntimeError('private-data')))
        with self.assertRaises(CoreError) as error: self.shutdown()
        self.assertEqual(error.exception.code, 'application_not_drained')
        self.assertNotIn('private-data', str(error.exception))
        self.server.shutdown.assert_not_called()

    def test_idle_host_can_shutdown(self):
        self.assertTrue(self.shutdown())
        self.assertTrue(self.stopped.wait(1))
        self.server.shutdown.assert_called_once()
        self.handler.json.assert_called_once_with({'stopping':True})


if __name__ == '__main__': unittest.main()
