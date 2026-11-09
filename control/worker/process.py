"""Owned native process lifetime, not a security sandbox.

Windows binds the Job in CreateProcess itself, before any child code runs.
Only private copies of the three standard handles are inherited. Callers own
wall/output limits and must close this object in a finally block.
"""
from contextlib import ExitStack
import ctypes as c
from ctypes import wintypes as w
import os
import subprocess
import tempfile
import time

from control.worker import win32 as n
from sdk.protocol import CoreError


class JobAccounting(c.Structure):
    _fields_ = [('user_time', c.c_longlong), ('kernel_time', c.c_longlong),
                ('period_user_time', c.c_longlong), ('period_kernel_time', c.c_longlong),
                ('page_faults', w.DWORD), ('total', w.DWORD),
                ('active', w.DWORD), ('terminated', w.DWORD)]


def require(value, operation):
    if not value:
        raise CoreError('worker_lifetime', f'{operation} failed: Windows {c.get_last_error()}')
    return value


class OwnedProcess:
    def __init__(self, args, *, stdout, stderr, env, cwd=None, input=b'',
                 processes=None, cpu_seconds=None, memory_bytes=None, checkpoint=lambda: None):
        self.args, self.returncode = args, None
        self.job = self.handle = None
        self.native = self.fallback = None
        self.closed = False
        self.exit_handles = []
        self.terminated = False
        try:
            # Finite request data avoids a blocking pipe write before cancellation
            # can be polled. This file lives in the caller's temporary workspace.
            with tempfile.TemporaryFile(dir=cwd or env.get('TEMP')) as source:
                source.write(input); source.seek(0)
                checkpoint()
                if os.name != 'nt':
                    self.fallback = subprocess.Popen(args, stdin=source, stdout=stdout,
                        stderr=stderr, env=env, cwd=cwd)
                    self.pid = self.fallback.pid
                else:
                    self._start(args, source, stdout, stderr, env, cwd,
                                processes, cpu_seconds, memory_bytes, checkpoint)
        except BaseException:
            self.close()
            raise

    def _start(self, args, source, stdout, stderr, env, cwd, processes, cpu, memory, checkpoint):
        import msvcrt
        self.native = api = n.bind()
        self.job = require(api['CreateJobObjectW'](None, None), 'create lifetime Job')
        limits = n.JobLimit(); limits.basic.flags = 0x2000
        if processes is not None:
            limits.basic.flags |= 0x8; limits.basic.processes = processes
        if cpu is not None:
            limits.basic.flags |= 0x2; limits.basic.cpu = cpu * 10_000_000
        if memory is not None:
            limits.basic.flags |= 0x100 | 0x200; limits.memory = limits.job_memory = memory
        require(api['SetInformationJobObject'](self.job, 9, c.byref(limits), c.sizeof(limits)), 'Job limits')
        duplicate = n.api('kernel32', 'DuplicateHandle', w.BOOL,
                          w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD)
        with ExitStack() as cleanup:
            handles = []
            for stream in (source, stdout, stderr):
                target = w.HANDLE()
                require(duplicate(w.HANDLE(-1), msvcrt.get_osfhandle(stream.fileno()),
                    w.HANDLE(-1), c.byref(target), 0, True, 2), 'duplicate standard handle')
                handles.append(target.value)
                cleanup.callback(api['CloseHandle'], target.value)
            attributes = [(0x20002, (w.HANDLE * 3)(*handles)),
                          (0x2000D, (w.HANDLE * 1)(self.job))]
            length = n.SIZE()
            api['InitializeProcThreadAttributeList'](None, len(attributes), 0, c.byref(length))
            storage = c.create_string_buffer(length.value)
            require(api['InitializeProcThreadAttributeList'](storage, len(attributes), 0, c.byref(length)), 'attributes')
            cleanup.callback(api['DeleteProcThreadAttributeList'], storage)
            for key, value in attributes:
                require(api['UpdateProcThreadAttribute'](storage, 0, key, c.byref(value), c.sizeof(value), None, None), 'creation attributes')
            startup = n.StartupEx(); startup.info.cb = c.sizeof(startup); startup.info.flags = 0x100
            startup.info.stdin, startup.info.stdout, startup.info.stderr = handles
            startup.attributes = c.cast(storage, n.PTR)
            process = n.Process()
            command = c.create_unicode_buffer(subprocess.list2cmdline([os.fspath(a) for a in args]))
            block = c.create_unicode_buffer('\0'.join(k + '=' + v for k, v in sorted(env.items(), key=lambda x:x[0].upper())) + '\0\0')
            require(api['CreateProcessW'](os.fspath(args[0]), command, None, None, True,
                0x80000 | 0x400 | 0x8000000 | 0x4, block,
                os.fspath(cwd) if cwd else None, c.byref(startup), c.byref(process)), 'create bound process')
            self.handle, self.pid = process.handle, process.pid
            cleanup.callback(api['CloseHandle'], process.thread)
            checkpoint()
            if api['ResumeThread'](process.thread) == 0xFFFFFFFF:
                require(False, 'resume bound process')

    def poll(self):
        if self.fallback:
            self.returncode = self.fallback.poll()
        elif self.handle and self.returncode is None:
            state = self.native['WaitForSingleObject'](self.handle, 0)
            if state == 0:
                code = w.DWORD()
                require(self.native['GetExitCodeProcess'](self.handle, c.byref(code)), 'exit status')
                self.returncode = code.value
            elif state != 258:
                require(False, 'process status')
        return self.returncode

    def wait(self, timeout=None):
        if self.fallback:
            self.returncode = self.fallback.wait(timeout=timeout)
        elif self.handle and self.returncode is None:
            state = self.native['WaitForSingleObject'](self.handle,
                0xFFFFFFFF if timeout is None else min(0xFFFFFFFE, max(0, int(timeout * 1000))))
            if state == 258:
                raise subprocess.TimeoutExpired(self.args, timeout)
            require(state == 0, 'wait for process')
            self.poll()
        return self.returncode

    def resources(self):
        if not self.job: return {}
        measured = n.JobLimit()
        require(self.native['QueryInformationJobObject'](self.job, 9, c.byref(measured), c.sizeof(measured), None), 'Job measurement')
        return {'peak_process_memory_bytes': measured.peak, 'peak_job_memory_bytes': measured.job_peak}

    def kill(self):
        if self.job and not self.terminated:
            # Keep waitable handles before termination removes members from the
            # Job's active list. ActiveProcesses==0 alone is not an I/O barrier.
            class ProcessIds(c.Structure):
                _fields_ = [('assigned', w.DWORD), ('count', w.DWORD), ('ids', n.SIZE * 4096)]
            members = ProcessIds()
            require(self.native['QueryInformationJobObject'](self.job, 3,
                c.byref(members), c.sizeof(members), None), 'owned process list')
            open_process = n.api('kernel32', 'OpenProcess', w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
            in_job = n.api('kernel32', 'IsProcessInJob', w.BOOL, w.HANDLE, w.HANDLE, c.POINTER(w.BOOL))
            for pid in members.ids[:members.count]:
                handle = open_process(0x100000 | 0x1000, False, pid)
                if not handle:
                    if c.get_last_error() == 87: continue  # already exited
                    require(False, 'open owned process for wait')
                belongs = w.BOOL()
                try:
                    require(in_job(handle, self.job, c.byref(belongs)), 'confirm process ownership')
                    if belongs.value:
                        self.exit_handles.append(handle); handle = None
                finally:
                    if handle: self.native['CloseHandle'](handle)
            require(self.native['TerminateJobObject'](self.job, 1), 'terminate owned process tree')
            self.terminated = True
        elif self.fallback and self.fallback.poll() is None:
            self.fallback.kill()

    def close(self):
        if self.closed: return
        try:
            # Close even after the leader exits: descendants may still be alive.
            if self.job:
                self.kill()
                deadline = time.monotonic() + 5
                for handle in self.exit_handles:
                    state = self.native['WaitForSingleObject'](handle, max(0, int((deadline-time.monotonic())*1000)))
                    if state != 0:
                        raise CoreError('worker_cleanup', 'Owned descendant exit was not confirmed')
                while True:
                    measured = JobAccounting()
                    require(self.native['QueryInformationJobObject'](self.job, 1,
                        c.byref(measured), c.sizeof(measured), None), 'Job exit accounting')
                    if not measured.active: break
                    if time.monotonic() >= deadline:
                        raise CoreError('worker_cleanup', 'Owned process tree did not finish within five seconds')
                    time.sleep(.01)
            elif self.fallback and self.fallback.poll() is None:
                self.fallback.kill()
            if self.handle or self.fallback: self.wait(timeout=5)
        finally:
            for handle in self.exit_handles: self.native['CloseHandle'](handle)
            self.exit_handles.clear()
            if self.job:
                self.native['CloseHandle'](self.job); self.job = None
            if self.handle:
                self.native['CloseHandle'](self.handle); self.handle = None
            self.closed = True

    def __enter__(self): return self

    def __exit__(self, *exc): self.close()
