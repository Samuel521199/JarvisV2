from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "apps/cli/main.py"
NATIVE = ROOT / "control/bootstrap/target/debug" / ("jarvis-control.exe" if os.name == "nt" else "jarvis-control")


class CliNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-native-test-")
        self.root = Path(self.temp.name).resolve()
        assert self.root.parent == Path(tempfile.gettempdir()).resolve()
        assert self.root.name.startswith("jarvis-native-test-")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-I", "-B", str(CLI), "--data-root", str(self.root), *args],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def native(self, *args, expected=0):
        self.assertTrue(NATIVE.is_file(), "Build native control with cargo build --offline --locked first")
        result = subprocess.run([str(NATIVE), *args, "--data-root", str(self.root)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_cli_init_submit_run_query_and_error_envelopes(self):
        self.cli("status", expected=2)
        status = self.cli("init")
        identity = status["result"]["identity"]
        task = self.cli("submit", str(ROOT / "contracts/examples/text-report.task.json"))["result"]["task_id"]
        self.cli("run")
        self.assertEqual(self.cli("task", task)["result"]["task"]["status"], "SUCCEEDED")
        self.assertEqual(self.cli("status")["result"]["identity"], identity)
        self.assertEqual(self.cli("module", "stop", "text-analyzer", expected=2)["error"]["code"], "revision_required")

    def test_native_stop_and_status_work_without_python_and_latch_survives(self):
        self.cli("init")
        self.native("stop")
        self.assertIn(b"stopped", self.native("status").stdout)
        self.native("run", "--project-root", str(ROOT), "--python", "missing-python", expected=2)
        result = self.cli("status")["result"]
        self.cli("resume", "--token", result["stop_token"])
        self.native("latch")
        self.assertEqual(self.cli("resume", "--token", "any", expected=2)["error"]["code"], "latched")

    def test_native_starts_real_host_and_delivers_report(self):
        self.cli("init")
        ident = self.cli("submit", str(ROOT / "contracts/examples/text-report.task.json"))["result"]["task_id"]
        self.native("run", "--project-root", str(ROOT), "--python", sys.executable)
        self.assertEqual(self.cli("task", ident)["result"]["task"]["status"], "SUCCEEDED")

    def test_native_stop_terminates_hung_direct_child(self):
        self.cli("init")
        project = self.root / "hung-host-fixture"
        entry = project / "apps/cli/main.py"; entry.parent.mkdir(parents=True)
        marker = project / "started"
        # Synthetic host proves supervision only, not product isolation.
        entry.write_text("from pathlib import Path\nimport time\nPath('started').write_text('yes')\ntime.sleep(20)\n", encoding="utf-8")
        runner = subprocess.Popen([str(NATIVE), "run", "--data-root", str(self.root), "--project-root", str(project),
                                   "--python", sys.executable], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline and runner.poll() is None:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "Test host did not start")
            self.native("stop")
            stdout, stderr = runner.communicate(timeout=5)
            self.assertEqual(runner.returncode, 2, stdout + stderr)
            self.assertTrue((self.root / "state/STOP").exists())
        finally:
            if runner.poll() is None:
                runner.kill(); runner.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
