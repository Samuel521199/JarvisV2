"""Real Windows lifecycle probes; no optional native runtime or account required."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from control.worker import process as owned
from sdk.protocol import CoreError


@unittest.skipUnless(os.name == 'nt', 'Windows creation-time Job boundary')
class WorkerProcess(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-worker-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.enterContext((self.root/'stdout').open('w+b'))
        self.err = self.enterContext((self.root/'stderr').open('w+b'))

    def start(self, code, **options):
        proc = owned.OwnedProcess([sys.executable, '-I', '-c', code],
            stdout=self.out, stderr=self.err, cwd=self.root, env=dict(os.environ), **options)
        self.addCleanup(proc.close)
        return proc

    def alive(self, pid):
        api = owned.n.bind()
        handle = owned.n.api('kernel32', 'OpenProcess', w.HANDLE, w.DWORD, w.BOOL, w.DWORD)(0x100000, False, pid)
        if not handle: return False
        try: return api['WaitForSingleObject'](handle, 0) == 258
        finally: api['CloseHandle'](handle)

    def eventually(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.02)
        self.fail('Lifecycle condition did not converge within 8 seconds')

    def tree(self, exit_parent=False):
        code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)']); print(p.pid,flush=True); "
        return self.start(code + ('' if exit_parent else 'time.sleep(60)'))

    def child_pid(self):
        self.eventually(lambda: (self.root/'stdout').stat().st_size > 0)
        return int((self.root/'stdout').read_text().strip())

    def test_stdin_output_environment_cwd_and_exit(self):
        proc = self.start("import sys,os; sys.stdout.buffer.write(sys.stdin.buffer.read()); print(os.getcwd()); print('err',file=sys.stderr); sys.exit(7)", input='请求\n'.encode())
        self.assertEqual(proc.wait(8), 7)
        self.out.seek(0); output = self.out.read()
        self.assertIn('请求'.encode(), output)
        self.assertIn(str(self.root).encode(), output)
        self.err.seek(0); self.assertIn(b'err', self.err.read())
        self.assertGreater(proc.resources()['peak_job_memory_bytes'], 0)
        proc.close(); proc.close()

    def test_close_kills_live_child_tree(self):
        proc = self.tree(); pid = self.child_pid()
        self.assertTrue(self.alive(pid)); proc.close()
        self.eventually(lambda: not self.alive(pid))

    def test_close_kills_descendant_after_leader_exited(self):
        proc = self.tree(True); pid = self.child_pid()
        self.assertEqual(proc.wait(8), 0)
        self.assertTrue(self.alive(pid)); proc.close()
        self.eventually(lambda: not self.alive(pid))

    def test_wait_timeout_then_kill_entire_job(self):
        proc = self.tree(); pid = self.child_pid()
        with self.assertRaises(subprocess.TimeoutExpired): proc.wait(.01)
        proc.kill(); proc.wait(5)
        self.eventually(lambda: not self.alive(pid))

    def test_cancel_before_resume_runs_no_worker_code(self):
        marker = self.root/'must-not-run'
        count = 0
        def cancel():
            nonlocal count
            count += 1
            if count == 2: raise CoreError('cancelled', 'test stop')
        with self.assertRaises(CoreError):
            self.start(f"from pathlib import Path;Path({str(marker)!r}).write_text('ran')", checkpoint=cancel)
        self.assertEqual(count, 2); self.assertFalse(marker.exists())

    def test_job_attribute_failure_does_not_launch(self):
        api = owned.n.bind(); marker = self.root/'must-not-run'
        update = api['UpdateProcThreadAttribute']
        def fail_job(storage, flags, key, *args):
            return 0 if key == 0x2000D else update(storage, flags, key, *args)
        api['UpdateProcThreadAttribute'] = fail_job
        with patch.object(owned.n, 'bind', return_value=api), self.assertRaises(CoreError):
            self.start(f"from pathlib import Path;Path({str(marker)!r}).write_text('ran')")
        self.assertFalse(marker.exists())

    def test_create_process_failure_is_reported(self):
        with self.assertRaises(CoreError):
            owned.OwnedProcess([str(self.root/'absent.exe')], stdout=self.out,
                stderr=self.err, cwd=self.root, env=dict(os.environ))

    def test_resource_limits_are_preserved_and_process_cap_enforced(self):
        proc = self.start("import subprocess,sys; subprocess.run([sys.executable,'-c','pass'],check=True)",
                          processes=1, cpu_seconds=30, memory_bytes=256*1024**2)
        limits = owned.n.JobLimit()
        self.assertTrue(proc.native['QueryInformationJobObject'](proc.job, 9, c.byref(limits), c.sizeof(limits), None))
        self.assertEqual(limits.basic.processes, 1)
        self.assertEqual(limits.basic.cpu, 30*10_000_000)
        self.assertEqual(limits.memory, 256*1024**2)
        self.assertEqual(limits.job_memory, 256*1024**2)
        self.assertNotEqual(proc.wait(8), 0)

    def test_abrupt_owner_exit_reaps_descendant(self):
        repo = str(Path(__file__).resolve().parents[1])
        owner_code = f"""
import os,sys,time
sys.path.insert(0,{repo!r})
from control.worker.process import OwnedProcess
with open('stdout','wb') as out, open('stderr','wb') as err:
 p=OwnedProcess([sys.executable,'-I','-c',"import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)']);print(p.pid,flush=True);time.sleep(60)"],stdout=out,stderr=err,cwd=os.getcwd(),env=dict(os.environ))
 open('leader','w').write(str(p.pid))
 while True:time.sleep(.1)
"""
        owner = subprocess.Popen([sys.executable, '-I', '-c', owner_code], cwd=self.root,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(lambda: owner.wait(timeout=5))
        self.addCleanup(lambda: owner.kill() if owner.poll() is None else None)
        pid = self.child_pid()
        leader = int((self.root/'leader').read_text())
        self.assertTrue(self.alive(pid)); owner.kill(); owner.wait(5)
        self.eventually(lambda: not self.alive(leader) and not self.alive(pid))

    def test_candidate_adapter_real_process_success_and_cleanup(self):
        from adapters.models import codex_cli as cli
        model, prompt = self.candidate()
        receipt = b'{"type":"turn.completed"}\n{"type":"item.completed","item":{"type":"agent_message","text":"{\\"answer\\":1}"}}'
        code = f"import sys;assert sys.stdin.buffer.read();sys.stdout.buffer.write({receipt!r})"
        with patch.object(cli, 'arguments', return_value=[sys.executable, '-I', '-c', code]):
            result = model.generate(prompt)
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertEqual(list((self.root/'temp').iterdir()), [])

    def candidate(self):
        from adapters.models import codex_cli as cli
        config = {'executable':sys.executable,
                  'executable_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                  'max_prompt_bytes':50000, 'timeout_seconds':3}
        return cli.CodexModel(config, self.root), json.dumps({'output_schema':{'properties':{'schema':{'const':'jarvis.code-candidate.v1'}}}})

    def test_candidate_adapter_timeout_cancel_and_output_limit_reap_tree(self):
        from adapters.models import codex_cli as cli
        for mode in ('timeout', 'cancel', 'output_limit', 'output_limit_fast_exit'):
            with self.subTest(mode=mode):
                marker = self.root/(mode + '.pid')
                model, prompt = self.candidate()
                code = ("import subprocess,sys,time;from pathlib import Path;"
                    "p=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)']);"
                    f"Path({str(marker)!r}).write_text(str(p.pid));")
                if mode.startswith('output_limit'): code += "sys.stdout.buffer.write(b'x'*2000001);sys.stdout.flush();"
                if mode != 'output_limit_fast_exit': code += 'time.sleep(60)'
                def checkpoint():
                    if mode == 'cancel' and marker.exists(): raise CoreError('cancelled', 'test stop')
                with patch.object(cli, 'arguments', return_value=[sys.executable, '-I', '-c', code]):
                    if mode == 'cancel':
                        with self.assertRaises(CoreError): model.generate(prompt, checkpoint)
                    else:
                        self.assertEqual(model.generate(prompt)['code'], 'codex_' + ('output_limit' if mode.startswith('output_limit') else mode))
                self.assertTrue(marker.is_file())
                pid = int(marker.read_text())
                self.eventually(lambda: not self.alive(pid))
                self.assertEqual(list((self.root/'temp').iterdir()), [])


if __name__ == '__main__': unittest.main()
