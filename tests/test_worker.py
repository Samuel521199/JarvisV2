import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from control.recovery.gate import RunLock
from sdk.protocol import CoreError


@unittest.skipUnless(os.name == "nt", "Windows LPAC backend only")
class WorkerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-worker-")
        self.root = Path(self.temp.name).resolve()
        self.core = Core.initialize(self.root)
        self.core.worker.prepare()

    def tearDown(self):
        with RunLock(self.root): self.core.worker.recover()
        self.core.close(); self.temp.cleanup()

    def run_source(self, source, inputs=None, **kwargs):
        # Trusted test harness bypasses the recipe AST filter to probe the OS boundary.
        return self.core.worker.run({"main.py": source}, inputs or ["probe"], **kwargs)

    def test_host_read_write_staging_write_and_environment_denied(self):
        outside = self.root / "canary.txt"; outside.write_text("private-canary")
        os.environ["JARVIS_TEST_SECRET"] = "not-for-worker"
        try:
            source = '''import os,json
def run(text):
    results = {}
    for key, path, mode in [('read',text,'r'),('write',text,'w'),('stage','escape.txt','w')]:
        try:
            with open(path, mode) as f:
                if mode == 'w': f.write('changed')
                else: f.read()
            results[key] = 'allowed'
        except OSError: results[key] = 'denied'
    results['secret'] = os.environ.get('JARVIS_TEST_SECRET')
    return json.dumps(results)
'''
            outputs, evidence = self.run_source(source, [str(outside)])
            self.assertEqual(json.loads(outputs[0]), {"read": "denied", "write": "denied", "stage": "denied", "secret": None})
            self.assertEqual(outside.read_text(), "private-canary")
            self.assertTrue(evidence["appcontainer_verified"])
        finally: os.environ.pop("JARVIS_TEST_SECRET", None)

    def test_lpac_excludes_all_application_packages(self):
        canary = self.root / "aap-canary.txt"; canary.write_text("AAP only")
        icacls = Path(os.environ["SystemRoot"]) / "System32/icacls.exe"
        subprocess.run([str(icacls), str(canary), "/grant", "*S-1-15-2-1:(R)"], check=True, capture_output=True)
        outputs, _ = self.run_source("def run(text):\n    try:\n        return open(text).read()\n    except OSError:\n        return 'denied'\n", [str(canary)])
        self.assertEqual(outputs, ["denied"])

    def test_network_and_child_process_denied(self):
        listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(); listener.settimeout(.2)
        try:
            source = '''import socket,subprocess,sys,json
def run(text):
    result = {}
    try:
        s=socket.create_connection(('127.0.0.1',int(text)),timeout=.3);s.close();result['network']='allowed'
    except OSError: result['network']='denied'
    try:
        subprocess.run([sys.executable,'-c','pass'],timeout=1,check=True);result['child']='allowed'
    except (OSError,subprocess.SubprocessError): result['child']='denied'
    return json.dumps(result)
'''
            outputs, _ = self.run_source(source, [str(listener.getsockname()[1])])
            self.assertEqual(json.loads(outputs[0]), {"network": "denied", "child": "denied"})
            with self.assertRaises(socket.timeout): listener.accept()
        finally: listener.close()

    def test_wall_output_memory_and_stop_bounds(self):
        with self.assertRaises(CoreError) as caught:
            self.run_source("def run(text):\n    while True: pass\n", seconds=.4)
        self.assertEqual(caught.exception.code, "worker_timeout")
        with self.assertRaises(CoreError) as caught:
            self.run_source("def run(text):\n    while True: print('x'*16000)\n")
        self.assertEqual(caught.exception.code, "worker_output_limit")
        outputs, _ = self.run_source("def run(text):\n    try: value = bytearray(400*1024*1024)\n    except MemoryError: return 'bounded'\n    return 'unbounded'\n")
        self.assertEqual(outputs, ["bounded"])
        started = time.monotonic()
        def stop():
            if time.monotonic() - started > .3: raise CoreError("stopped", "test stop")
        with self.assertRaises(CoreError) as caught:
            self.run_source("def run(text):\n    while True: pass\n", checkpoint=stop)
        self.assertEqual(caught.exception.code, "stopped")
        self.assertLess(time.monotonic() - started, 3)

    def test_runtime_tamper_fails_closed(self):
        path = self.root / "worker-runtime/python313._pth"
        path.write_text(".\n")
        with self.assertRaises(CoreError) as result: self.run_source("def run(text): return text")
        self.assertEqual(result.exception.code, "worker_runtime_changed")

    def test_host_death_kills_worker_and_orphans_are_recovered(self):
        process = subprocess.Popen([sys.executable, "-I", "-B", str(ROOT / "tests/worker_crash.py"), str(self.root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 77, stderr)
            leases = list((self.root / "state/worker-leases").glob("*.json"))
            self.assertEqual(len(leases), 1)
            lease = json.loads(leases[0].read_text())
            self.assertIsInstance(lease["pid"], int)
            from control.worker.win32 import api, PTR
            from ctypes import wintypes as w
            import ctypes as c
            open_process = api("kernel32", "OpenProcess", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
            handle = open_process(0x1000, False, lease["pid"])
            if handle:
                code = w.DWORD()
                try:
                    api("kernel32", "GetExitCodeProcess", w.BOOL, w.HANDLE, PTR)(handle, c.byref(code))
                    self.assertNotEqual(code.value, 259, "Worker survived host death")
                finally: api("kernel32", "CloseHandle", w.BOOL, w.HANDLE)(handle)
            with RunLock(self.root): result = self.core.worker.recover()
            self.assertEqual(result, {"recovered": 1})
            self.assertEqual(list((self.root / "worker-runs").iterdir()), [])
            self.assertEqual(self.run_source("def run(text): return 'alive'")[0], ["alive"])
        finally:
            if process.poll() is None: process.kill(); process.wait()


if __name__ == "__main__": unittest.main()
