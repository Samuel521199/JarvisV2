"""One LPAC per invocation, read-only inputs, no network and a bounded Job.

Only the trusted host calls launch. A candidate cannot select native argv,
runtime, ACL targets, environment or inherited handles.
"""
from contextlib import ExitStack
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import time
import uuid

from control.paths import reject_links
from control.atomic import write_json
from control.worker import win32 as n
from sdk.protocol import CoreError


def require(value, operation):
    if not value:
        raise CoreError("worker_isolation", f"{operation} failed: Windows {c.get_last_error()}")
    return value


def acl(api, path, sid, remove=False):
    reject_links(path)
    volume = c.create_unicode_buffer(1024)
    flags = w.DWORD()
    require(api["GetVolumePathNameW"](str(path), volume, len(volume)), "volume")
    require(api["GetVolumeInformationW"](volume, None, 0, None, None, c.byref(flags), None, 0), "filesystem")
    if not flags.value & 8:
        raise CoreError("worker_filesystem", "Worker files require persistent Windows ACLs")
    command = [str(Path(os.environ["SystemRoot"]) / "System32/icacls.exe"), str(path)]
    command += ["/remove:g", "*" + sid] if remove else ["/grant", "*" + sid + ":(OI)(CI)(RX)"]
    reply = subprocess.run(command + ["/T", "/Q"], capture_output=True, timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    if reply.returncode:
        raise CoreError("worker_acl", "Cannot establish/remove owned staging ACL")


def inspect_token(api, process, sid):
    token, length = w.HANDLE(), w.DWORD()
    require(api["OpenProcessToken"](process, 8, c.byref(token)), "token")
    try:
        value = w.DWORD()
        require(api["GetTokenInformation"](token, 29, c.byref(value), 4, c.byref(length)), "AppContainer")
        if value.value != 1:
            raise CoreError("worker_isolation", "Not an AppContainer token")
        api["GetTokenInformation"](token, 31, None, 0, c.byref(length))
        storage = c.create_string_buffer(length.value)
        require(api["GetTokenInformation"](token, 31, storage, length, c.byref(length)), "package token")
        require(api["EqualSid"](c.cast(storage, c.POINTER(n.PTR))[0], sid), "package binding")
    finally:
        api["CloseHandle"](token)


def launch(runtime: Path, stage: Path, checkpoint=lambda: None, seconds=8, output_limit=262144, lease_path=None):
    if os.name != "nt":
        raise CoreError("worker_unavailable", "Windows LPAC backend required; no full-privilege fallback")
    if not 0.1 <= seconds <= 30 or not 1024 <= output_limit <= 262144:
        raise CoreError("worker_limits", "Unsupported worker bounds")
    reject_links(runtime); reject_links(stage)
    native = n.bind()
    name = "Jarvis2.Run." + uuid.uuid4().hex
    if lease_path:
        write_json(lease_path, {"profile": name, "stage": stage.name, "sid": None, "pid": None})
    package, text = n.PTR(), n.PTR()
    hr = native["CreateAppContainerProfile"](name, name, "Jarvis bounded pure worker", None, 0, c.byref(package))
    if hr < 0:
        raise CoreError("worker_isolation", f"AppContainer profile failed: {hr}")
    started = time.monotonic()
    try:
        with ExitStack() as cleanup:
            cleanup.callback(native["FreeSid"], package)
            require(native["ConvertSidToStringSidW"](package, c.byref(text)), "SID")
            cleanup.callback(native["LocalFree"], text)
            identity = c.wstring_at(text)
            if lease_path:
                write_json(lease_path, {"profile": name, "stage": stage.name, "sid": identity, "pid": None})
            # Never grant access on the original Python installation or data root.
            for directory in (runtime, stage):
                acl(native, directory, identity)
                cleanup.callback(acl, native, directory, identity, True)
            groups, caps = n.PTR(), n.PTR()
            ng, nc = w.DWORD(), w.DWORD()
            require(native["DeriveCapabilitySidsFromName"]("registryRead", c.byref(groups), c.byref(ng), c.byref(caps), c.byref(nc)), "capability")
            for pointer, count in ((groups, ng.value), (caps, nc.value)):
                cleanup.callback(native["LocalFree"], pointer)
                for i in range(count):
                    cleanup.callback(native["LocalFree"], c.cast(pointer, c.POINTER(n.PTR))[i])
            if nc.value != 1:
                raise CoreError("worker_isolation", "Unexpected fixed capability definition")
            capability = n.SidAttribute(c.cast(caps, c.POINTER(n.PTR))[0], 4)
            security = n.Capabilities(package, c.cast(c.pointer(capability), n.PTR), 1, 0)
            job = require(native["CreateJobObjectW"](None, None), "job")
            cleanup.callback(native["CloseHandle"], job)
            limits = n.JobLimit()
            limits.basic.flags = 0x2000 | 0x8 | 0x100 | 0x2
            limits.basic.processes, limits.basic.cpu = 1, 3 * 10_000_000
            limits.memory = 256 * 1024 * 1024
            require(native["SetInformationJobObject"](job, 9, c.byref(limits), c.sizeof(limits)), "job limits")
            handles = set()
            def close(handle):
                if handle in handles:
                    native["CloseHandle"](handle); handles.remove(handle)
            cleanup.callback(lambda: [close(h) for h in list(handles)])
            pipes = []
            sa = n.Security(c.sizeof(n.Security), None, True)
            for _ in range(3):
                reader, writer = w.HANDLE(), w.HANDLE()
                require(native["CreatePipe"](c.byref(reader), c.byref(writer), c.byref(sa), 0), "pipe")
                handles.update((reader.value, writer.value)); pipes.append((reader.value, writer.value))
            close(pipes[0][1])
            for handle in (pipes[1][0], pipes[2][0]):
                require(native["SetHandleInformation"](handle, 1, 0), "handle inheritance")
            attributes = [(0x20009, security), (0x2000F, w.DWORD(1)),
                          (0x2000E, w.DWORD(1)), (0x20012, w.DWORD(1)),
                          (0x20002, (w.HANDLE * 3)(pipes[0][0], pipes[1][1], pipes[2][1])),
                          (0x2000D, (w.HANDLE * 1)(job))]
            length = n.SIZE()
            native["InitializeProcThreadAttributeList"](None, len(attributes), 0, c.byref(length))
            storage = c.create_string_buffer(length.value)
            require(native["InitializeProcThreadAttributeList"](storage, len(attributes), 0, c.byref(length)), "attributes")
            cleanup.callback(native["DeleteProcThreadAttributeList"], storage)
            for key, value in attributes:
                require(native["UpdateProcThreadAttribute"](storage, 0, key, c.byref(value), c.sizeof(value), None, None), "process restriction")
            startup = n.StartupEx()
            startup.info.cb, startup.info.flags = c.sizeof(startup), 0x100
            startup.info.stdin, startup.info.stdout, startup.info.stderr = pipes[0][0], pipes[1][1], pipes[2][1]
            startup.attributes = c.cast(storage, n.PTR)
            process = n.Process()
            executable = str(runtime / "python.exe")
            argv = c.create_unicode_buffer(subprocess.list2cmdline([executable, "-I", "-B", str(stage / "entry.py")]))
            # No model key, account directory or host PATH is inherited.
            environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "USERPROFILE", "LOCALAPPDATA")}
            environment.update({"TEMP": str(stage), "TMP": str(stage)})
            block = c.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted(environment.items())) + "\0\0")
            checkpoint()
            require(native["CreateProcessW"](executable, argv, None, None, True,
                0x80000 | 0x400 | 0x8000000 | 0x4, block, str(stage), c.byref(startup), c.byref(process)), "restricted process")
            handles.update((process.handle, process.thread))
            if lease_path:
                write_json(lease_path, {"profile": name, "stage": stage.name, "sid": identity, "pid": process.pid})
            def kill():
                native["TerminateJobObject"](job, 1)
                native["WaitForSingleObject"](process.handle, 3000)
            cleanup.callback(kill)
            inspect_token(native, process.handle, package)
            checkpoint()
            if native["ResumeThread"](process.thread) == 0xFFFFFFFF:
                raise CoreError("worker_isolation", "Cannot resume verified worker")
            for handle in (pipes[0][0], pipes[1][1], pipes[2][1]): close(handle)
            buffers, drained = [bytearray(), bytearray()], False
            while True:
                checkpoint()
                if time.monotonic() - started > seconds:
                    raise CoreError("worker_timeout", "Worker wall-time limit reached")
                for index, handle in enumerate((pipes[1][0], pipes[2][0])):
                    # One bounded chunk per poll: infinite output cannot starve stop/deadline.
                    available = w.DWORD()
                    if not native["PeekNamedPipe"](handle, None, 0, None, c.byref(available), None):
                        if c.get_last_error() != 109: require(False, "pipe status")
                        continue
                    if available.value:
                        chunk = c.create_string_buffer(min(available.value, 16384)); used = w.DWORD()
                        require(native["ReadFile"](handle, chunk, len(chunk), c.byref(used), None), "output")
                        buffers[index].extend(chunk.raw[:used.value])
                        if len(buffers[index]) > (output_limit if index == 0 else 16384):
                            raise CoreError("worker_output_limit", "Worker output exceeded limit")
                ended = native["WaitForSingleObject"](process.handle, 0) == 0
                if ended and drained: break
                if ended:
                    remaining = []
                    for handle in (pipes[1][0], pipes[2][0]):
                        available = w.DWORD()
                        native["PeekNamedPipe"](handle, None, 0, None, c.byref(available), None)
                        remaining.append(available.value)
                    drained = not any(remaining)
                time.sleep(.01)
            code = w.DWORD(); measured = n.JobLimit()
            require(native["GetExitCodeProcess"](process.handle, c.byref(code)), "exit status")
            require(native["QueryInformationJobObject"](job, 9, c.byref(measured), c.sizeof(measured), None), "resources")
            return {"stdout": bytes(buffers[0]), "stderr": bytes(buffers[1]), "exit_code": code.value,
                    "evidence": {"backend": "windows-lpac-job", "appcontainer_verified": True,
                       "network_capabilities": [], "capabilities": ["registryRead"],
                       "active_process_limit": 1, "memory_limit_bytes": limits.memory,
                       "peak_memory_bytes": measured.peak, "cpu_limit_seconds": 3,
                       "wall_limit_seconds": seconds, "elapsed_seconds": round(time.monotonic() - started, 4)}}
    finally:
        if native["DeleteAppContainerProfile"](name) < 0:
            raise CoreError("worker_cleanup", "Worker ended but AppContainer profile cleanup failed")
        if lease_path and lease_path.exists(): lease_path.unlink()
