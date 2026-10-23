"""Small Win32 binding surface for LPAC jobs; no third-party native code.

Windows owns the access checks. Filesystem staging and policy are separate.
"""
import ctypes as c
from ctypes import wintypes as w

PTR = c.c_void_p
SIZE = c.c_size_t


class Startup(c.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                ("title", w.LPWSTR), ("x", w.DWORD), ("y", w.DWORD),
                ("width", w.DWORD), ("height", w.DWORD), ("columns", w.DWORD),
                ("rows", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_data", PTR),
                ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]


class StartupEx(c.Structure):
    _fields_ = [("info", Startup), ("attributes", PTR)]


class Process(c.Structure):
    _fields_ = [("handle", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class Security(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", PTR), ("inherit", w.BOOL)]


class SidAttribute(c.Structure):
    _fields_ = [("sid", PTR), ("attributes", w.DWORD)]


class Capabilities(c.Structure):
    _fields_ = [("package", PTR), ("capabilities", PTR), ("count", w.DWORD), ("reserved", w.DWORD)]


class BasicLimit(c.Structure):
    _fields_ = [("cpu", c.c_longlong), ("job_cpu", c.c_longlong), ("flags", w.DWORD),
                ("min_ws", SIZE), ("max_ws", SIZE), ("processes", w.DWORD),
                ("affinity", SIZE), ("priority", w.DWORD), ("scheduling", w.DWORD)]


class JobLimit(c.Structure):
    _fields_ = [("basic", BasicLimit), ("io", c.c_ulonglong * 6),
                ("memory", SIZE), ("job_memory", SIZE), ("peak", SIZE), ("job_peak", SIZE)]


def api(library, name, result, *arguments):
    method = getattr(c.WinDLL(library, use_last_error=True), name)
    method.restype, method.argtypes = result, arguments
    return method


def bind():
    # Explicit signatures avoid truncating handles in 64-bit Python.
    specs = {
        "CreateAppContainerProfile": ("userenv", c.c_long, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, PTR, w.DWORD, PTR),
        "DeleteAppContainerProfile": ("userenv", c.c_long, w.LPCWSTR),
        "FreeSid": ("advapi32", PTR, PTR),
        "ConvertSidToStringSidW": ("advapi32", w.BOOL, PTR, PTR),
        "DeriveCapabilitySidsFromName": ("kernelbase", w.BOOL, w.LPCWSTR, PTR, PTR, PTR, PTR),
        "LocalFree": ("kernel32", PTR, PTR),
        "CloseHandle": ("kernel32", w.BOOL, w.HANDLE),
        "CreateJobObjectW": ("kernel32", w.HANDLE, PTR, w.LPCWSTR),
        "SetInformationJobObject": ("kernel32", w.BOOL, w.HANDLE, c.c_int, PTR, w.DWORD),
        "QueryInformationJobObject": ("kernel32", w.BOOL, w.HANDLE, c.c_int, PTR, w.DWORD, PTR),
        "TerminateJobObject": ("kernel32", w.BOOL, w.HANDLE, w.UINT),
        "CreatePipe": ("kernel32", w.BOOL, PTR, PTR, PTR, w.DWORD),
        "SetHandleInformation": ("kernel32", w.BOOL, w.HANDLE, w.DWORD, w.DWORD),
        "PeekNamedPipe": ("kernel32", w.BOOL, w.HANDLE, PTR, w.DWORD, PTR, PTR, PTR),
        "ReadFile": ("kernel32", w.BOOL, w.HANDLE, PTR, w.DWORD, PTR, PTR),
        "InitializeProcThreadAttributeList": ("kernel32", w.BOOL, PTR, w.DWORD, w.DWORD, PTR),
        "UpdateProcThreadAttribute": ("kernel32", w.BOOL, PTR, w.DWORD, SIZE, PTR, SIZE, PTR, PTR),
        "DeleteProcThreadAttributeList": ("kernel32", None, PTR),
        "CreateProcessW": ("kernel32", w.BOOL, w.LPCWSTR, w.LPWSTR, PTR, PTR, w.BOOL, w.DWORD, PTR, w.LPCWSTR, PTR, PTR),
        "ResumeThread": ("kernel32", w.DWORD, w.HANDLE),
        "WaitForSingleObject": ("kernel32", w.DWORD, w.HANDLE, w.DWORD),
        "GetExitCodeProcess": ("kernel32", w.BOOL, w.HANDLE, PTR),
        "OpenProcessToken": ("advapi32", w.BOOL, w.HANDLE, w.DWORD, PTR),
        "GetTokenInformation": ("advapi32", w.BOOL, w.HANDLE, c.c_int, PTR, w.DWORD, PTR),
        "EqualSid": ("advapi32", w.BOOL, PTR, PTR),
        "GetVolumePathNameW": ("kernel32", w.BOOL, w.LPCWSTR, w.LPWSTR, w.DWORD),
        "GetVolumeInformationW": ("kernel32", w.BOOL, w.LPCWSTR, w.LPWSTR, w.DWORD, PTR, PTR, PTR, w.LPWSTR, w.DWORD),
    }
    return {name: api(spec[0], name, *spec[1:]) for name, spec in specs.items()}
