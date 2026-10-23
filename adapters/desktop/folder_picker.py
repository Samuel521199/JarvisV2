"""Native folder picker adapters. Manual absolute-path entry remains available."""
import ctypes
import os
import threading
import shutil
import subprocess
import sys
from ctypes import wintypes
from sdk.protocol import CoreError

PICKER_LOCK = threading.Lock()


def pick_folder():
    if os.name != 'nt': return pick_posix_folder()
    if not PICKER_LOCK.acquire(blocking=False): raise CoreError('picker_busy', 'A folder picker is already open')
    ole = ctypes.OleDLL('ole32'); shell = ctypes.WinDLL('shell32')
    class BrowseInfo(ctypes.Structure):
        _fields_ = [('hwndOwner', wintypes.HWND), ('pidlRoot', ctypes.c_void_p), ('pszDisplayName', wintypes.LPWSTR),
                    ('lpszTitle', wintypes.LPCWSTR), ('ulFlags', wintypes.UINT), ('lpfn', ctypes.c_void_p),
                    ('lParam', wintypes.LPARAM), ('iImage', ctypes.c_int)]
    shell.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BrowseInfo)]; shell.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]; shell.SHGetPathFromIDListW.restype = wintypes.BOOL
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]; ole.CoTaskMemFree.restype = None
    initialized = False; pidl = None
    try:
        ole.CoInitialize(None); initialized = True
        display = ctypes.create_unicode_buffer(260); result = ctypes.create_unicode_buffer(260)
        info = BrowseInfo(None, None, ctypes.cast(display, wintypes.LPWSTR), 'Jarvis — 选择项目文件夹', 0x51, None, 0, 0)
        pidl = shell.SHBrowseForFolderW(ctypes.byref(info))
        if not pidl: return {'path': None}
        if not shell.SHGetPathFromIDListW(pidl, result): raise CoreError('unsafe_path', 'Only file system folders are supported')
        return {'path': result.value}
    finally:
        if pidl: ole.CoTaskMemFree(pidl)
        if initialized: ole.CoUninitialize()
        PICKER_LOCK.release()


def pick_posix_folder():
    if not PICKER_LOCK.acquire(blocking=False): raise CoreError('picker_busy', 'A folder picker is already open')
    try:
        if sys.platform == 'darwin':
            args = ['/usr/bin/osascript','-e','try\nPOSIX path of (choose folder with prompt "Jarvis — 选择项目位置")\non error number -128\nreturn ""\nend try']
        elif shutil.which('zenity'):
            args = [shutil.which('zenity'),'--file-selection','--directory','--title=Jarvis — 选择项目位置']
        elif shutil.which('kdialog'):
            args = [shutil.which('kdialog'),'--getexistingdirectory',os.path.expanduser('~'),'--title','Jarvis — 选择项目位置']
        else: raise CoreError('picker_unavailable', 'Use manual path entry; no dialog utility is installed')
        try: result = subprocess.run(args,capture_output=True,timeout=180)
        except subprocess.TimeoutExpired: raise CoreError('picker_timeout','Folder selection timed out') from None
        if result.returncode == 1: return {'path':None}
        if result.returncode: raise CoreError('picker_unavailable','Native folder selection failed')
        return {'path':result.stdout.decode('utf-8').strip() or None}
    finally: PICKER_LOCK.release()
