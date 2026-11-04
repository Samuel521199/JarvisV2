"""Install a pinned recovery controller and preserve the owner's original launcher.

Business files are not copied, migrated or restored by this code installation.
The caller must already have accepted the candidate and backed up live state.
"""
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from control.atomic import write_json
from control.paths import reject_links
from modules.release_recovery.application import inspect_package
from sdk.protocol import CoreError

ROOT=Path(__file__).resolve().parents[1]
# Owner launcher is an installed platform asset, independent of mutable checkout files.
LAUNCHER_TEMPLATE=b'@echo off\r\nsetlocal DisableDelayedExpansion\r\npushd "%~dp0" || exit /b 1\r\ntitle Jarvis Workbench\r\n\r\nif defined JARVIS_PYTHON goto custom_python\r\nif exist ".venv\\Scripts\\python.exe" (\r\n    set "JARVIS_LAUNCH_PYTHON=%~dp0.venv\\Scripts\\python.exe"\r\n    goto use_python\r\n)\r\npython -I -B -c "import sys; sys.exit(sys.version_info < (3,13))" >nul 2>&1\r\nif not errorlevel 1 (\r\n    set "JARVIS_LAUNCH_PYTHON=python"\r\n    goto use_python\r\n)\r\npy -3.13 -I -B -c "import sys" >nul 2>&1\r\nif not errorlevel 1 goto use_py\r\necho [Jarvis] Python 3.13 or newer was not found.\r\necho Install Python, or set JARVIS_PYTHON to the full python.exe path.\r\ngoto failure\r\n\r\n:custom_python\r\nset "JARVIS_LAUNCH_PYTHON=%JARVIS_PYTHON%"\r\n:use_python\r\n"%JARVIS_LAUNCH_PYTHON%" -X utf8 -I -B "JarvisLaunch.py" %*\r\ngoto result\r\n\r\n:use_py\r\npy -3.13 -X utf8 -I -B "JarvisLaunch.py" %*\r\n:result\r\nif errorlevel 1 goto failure\r\npopd\r\nexit /b 0\r\n\r\n:failure\r\necho.\r\necho [Jarvis] Startup failed. See the message above.\r\nif not defined JARVIS_NO_PAUSE pause\r\npopd\r\nexit /b 1\r\n'


def install(root, installation, package, *, port=18282):
    root,installation,package=map(lambda p:Path(p).resolve(),(root,installation,package))
    reject_links(root);reject_links(installation)
    if root!=installation/'user-data' or not 1024<=port<=65535:
        raise CoreError('application_installation','Expected the installation-local user-data directory')
    build,manifest=inspect_package(package)
    from modules.release_recovery.application import Applications
    selected=Applications(root).state()['active']
    if not selected or selected['build']!=build:
        raise CoreError('application_installation','Only the adopted active build can install the daily launcher')
    base=root/'deployment/controllers';base.mkdir(exist_ok=True)
    controller=base/build
    reject_links(controller)
    files={name:(package/name).read_bytes() for name in manifest['files']}
    # The independent controller keeps its original checker and regression bodies.
    from sdk.application_policy import TESTS, TEST_SUPPORT
    for name in ['tools/check_architecture.py',*('tests/'+name for name in TESTS + TEST_SUPPORT)]:
        files[name]=(ROOT/name).read_bytes()
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())}
    if controller.exists():
        if any(not (controller/name).is_file() or hashlib.sha256((controller/name).read_bytes()).hexdigest()!=sha for name,sha in hashes.items()):
            raise CoreError('application_controller_changed','Existing recovery controller differs; preserve it for inspection')
    else:
        pending=base/(build+'.pending-'+uuid.uuid4().hex)
        pending.mkdir()
        for name,raw in files.items():
            target=pending/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        pending.rename(controller)
    inventory=json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()
    (controller/'controller-files.json').write_bytes(inventory)
    expected=hashlib.sha256(inventory).hexdigest()
    # Embed the inventory digest in the tiny root bootstrap: changed controller
    # code is rejected before any of it is imported. Same-user OS compromise is
    # outside this integrity check's threat model.
    bootstrap='''"""Pinned Jarvis recovery-controller bootstrap (no user data migration)."""
from pathlib import Path
import hashlib,json,runpy,sys
base=Path(__file__).resolve().parent
root=base/'user-data'
controller=root/'deployment/controllers'/BUILD
inventory=(controller/'controller-files.json').read_bytes()
if hashlib.sha256(inventory).hexdigest()!=EXPECTED:raise RuntimeError('Recovery controller inventory changed')
for name,sha in json.loads(inventory).items():
    path=(controller/name).resolve()
    if not path.is_relative_to(controller.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise RuntimeError('Recovery controller code changed: '+name)
sys.path.insert(0,str(controller))
sys.argv=[str(controller/'apps/workbench/launch.py'),'--data-root',str(root),'--port',str(PORT),*sys.argv[1:]]
runpy.run_path(str(controller/'apps/workbench/launch.py'),run_name='__main__')
'''.replace('BUILD',repr(build)).replace('EXPECTED',repr(expected)).replace('PORT',str(port))
    launcher=LAUNCHER_TEMPLATE
    if b'JarvisLaunch.py' not in launcher:raise CoreError('application_installation','Unsupported launcher template')
    backup=root/'deployment/launcher-backups'/uuid.uuid4().hex;backup.mkdir(parents=True)
    for name in ('StartJarvis.bat','JarvisLaunch.py'):
        path=installation/name;reject_links(path)
        if path.exists():shutil.copyfile(path,backup/name)
    # Save the original before atomic replacement; no source checkout is reset.
    try:
        for name,raw in (('JarvisLaunch.py',bootstrap.encode()),('StartJarvis.bat',launcher)):
            target=installation/name;pending=target.with_suffix(target.suffix+'.pending')
            reject_links(pending);pending.write_bytes(raw);pending.replace(target)
    except Exception:
        for name in ('StartJarvis.bat','JarvisLaunch.py'):
            original=backup/name
            if original.exists():shutil.copyfile(original,installation/name)
        raise
    result={'schema':1,'build':build,'controller':str(controller),'controller_inventory_sha256':expected,
            'launcher_backup':str(backup),'data_root':str(root),'port':port}
    write_json(root/'deployment/launcher.json',result)
    return result
