"""Desktop filesystem policy; no model or project knowledge in this adapter."""
import ctypes
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys

from control.paths import reject_links
from sdk.protocol import CoreError


def choose_test_base(platform, home, system_drive='', fixed_drives=(), data_mounts=()):
    """Pure policy, independently testable without assuming the host OS."""
    if platform == 'win32':
        system = system_drive.rstrip('\\/').casefold()
        others = [d for d in fixed_drives if d.rstrip('\\/').casefold() != system]
        others.sort(key=lambda d: (not d.upper().startswith('D:'), d.casefold()))
        drive = others[0] if others else system_drive
        if not drive: raise CoreError('location_unavailable', 'System drive is unknown')
        return str(PureWindowsPath(drive + '\\') / 'jarvisTest')
    candidates = sorted(data_mounts)
    return str(Path(candidates[0] if candidates else home) / 'jarvisTest')


def test_location():
    if sys.platform == 'win32':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        drives = [chr(i) + ':\\' for i in range(65, 91) if kernel.GetDriveTypeW(chr(i) + ':\\') == 3]
        system = os.environ.get('SystemDrive') or Path(sys.executable).anchor
        return Path(choose_test_base(sys.platform, str(Path.home()), system, drives))
    # Only local, writable mounted data volumes; never scan arbitrary file trees.
    mounts = []
    if sys.platform.startswith('linux'):
        try:
            for line in Path('/proc/mounts').read_text().splitlines():
                fields = line.split()
                if len(fields) < 4 or fields[2] not in {'ext4','ext3','xfs','btrfs','ntfs','ntfs3','exfat','vfat'}: continue
                p = Path(fields[1].replace('\\040', ' '))
                if str(p).startswith(('/media/', '/run/media/', '/mnt/')) and os.access(p, os.W_OK): mounts.append(str(p))
        except OSError: pass
    elif sys.platform == 'darwin':
        import plistlib
        volumes = Path('/Volumes')
        if volumes.is_dir():
            for p in volumes.iterdir():
                if p.is_symlink() or not os.path.ismount(p): continue
                try:
                    info = subprocess.run(['/usr/sbin/diskutil','info','-plist',str(p)], capture_output=True, timeout=3, check=True)
                    data = plistlib.loads(info.stdout)
                    if data.get('Internal') and data.get('Writable') and p.stat().st_dev != Path('/').stat().st_dev: mounts.append(str(p))
                except (OSError, ValueError, subprocess.SubprocessError): continue
    return Path(choose_test_base(sys.platform, str(Path.home()), data_mounts=mounts))


def folder_name(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 80 or value != value.strip()
            or value in {'.','..'} or value.endswith(('.', ' ')) or re.search(r'[<>:"/\\|?*\x00-\x1f]',value)
            or value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))}):
        raise CoreError('folder_name_invalid', 'Choose a portable single folder name')
    return value


def reveal_folder(path):
    path = Path(path); reject_links(path)
    if not path.is_dir(): raise CoreError('project_missing', 'Folder is unavailable')
    if sys.platform == 'win32': os.startfile(str(path), 'explore')
    else:
        command = '/usr/bin/open' if sys.platform == 'darwin' else shutil.which('xdg-open')
        if not command: raise CoreError('desktop_unavailable', 'Copy the path on a headless host')
        subprocess.Popen([command,str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    return {'ok': True}
