import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('managed_launcher',ROOT/'apps/workbench/launch.py')
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)


class ManagedLauncher(unittest.TestCase):
    def test_unmanaged_data_does_not_create_deployment_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertFalse(launch.managed_start(root,18282))
            self.assertFalse((root/'deployment').exists())

    def test_selected_version_started_and_never_unmanaged_fallback_on_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'deployment').mkdir();(root/'deployment/control.sqlite3').touch()
            state={'active':{'build':'a'*64},'pending':None,'phase':'stopped','epoch':4}
            app=Mock();app.state.return_value=state;app.start.return_value={**state,'phase':'active'}
            driver=Mock()
            with patch('modules.release_recovery.application.Applications',return_value=app),patch('adapters.application_host.WorkbenchProcess',return_value=driver):
                self.assertTrue(launch.managed_start(root,18282));app.start.assert_called_once_with(driver)
                app.start.side_effect=RuntimeError('approval or integrity failed')
                with self.assertRaises(RuntimeError):launch.managed_start(root,18282)

    def test_interrupted_transition_reconciles_before_running(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'deployment').mkdir();(root/'deployment/control.sqlite3').touch()
            state={'active':{'build':'a'*64},'pending':{'build':'b'*64},'phase':'starting','epoch':5}
            app=Mock();app.state.return_value=state;app.recover.return_value={**state,'phase':'active','pending':None}
            driver=Mock();driver.running.return_value=True
            with patch('modules.release_recovery.application.Applications',return_value=app),patch('adapters.application_host.WorkbenchProcess',return_value=driver):
                self.assertTrue(launch.managed_start(root,18282));app.recover.assert_called_once_with(driver);app.start.assert_not_called()
