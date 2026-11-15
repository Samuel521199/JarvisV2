import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from host.repair_return import require_controller
from sdk.protocol import CoreError


class RepairControllerTests(unittest.TestCase):
    def test_unmanaged_development_needs_no_installed_identity(self):
        with tempfile.TemporaryDirectory() as folder:require_controller(Path(folder)/'data')

    def test_each_installation_marker_requires_verified_protocol6(self):
        for marker in ('JarvisLaunch.py','data/deployment/launcher.json','data/deployment/controller-protocol.json'):
            with self.subTest(marker=marker),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);path=base/marker;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
                for protocol in (1,4,5):
                    with patch('control.controller_pin.read',return_value={'controller_protocol':protocol}):
                        with self.assertRaises(CoreError) as error:require_controller(base/'data')
                        self.assertEqual(error.exception.code,'controller_protocol')
                with patch('control.controller_pin.read',return_value={'controller_protocol':6}):require_controller(base/'data')
                with patch('control.controller_pin.read',side_effect=CoreError('controller_integrity','bad')):
                    with self.assertRaises(CoreError):require_controller(base/'data')
