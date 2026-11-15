"""Terminate only a verified disposable fixture host; prove stale-active rejection."""
from pathlib import Path
import ctypes,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from control.controller_pin import read
from modules.release_recovery.application import Applications
from tools.workstation import require_live_daily

def main():
    q=json.loads((OUT/'qualified.json').read_text());n=json.loads((OUT/'native/result.json').read_text());root=Path(n['root']);app=Applications(root);controller=Path(read(root)['controller']);port=n['port']
    assert root.is_relative_to(Path('E:/Jarvis/validation/english-voice-native-20261116')) and app.state()['phase']=='stopped'
    def release(action):
        p=subprocess.run([sys.executable,'-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(root),'--port',str(port)],capture_output=True,text=True,timeout=60)
        assert p.returncode==0,p.stderr;return json.loads(p.stdout)
    release('start');before=app.state();require_live_daily(root)
    path=root/'deployment/logs'/(str(before['epoch'])+'.lifecycle.json');record=json.loads(path.read_text());pid=record['host_pid']
    command=subprocess.check_output(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter "ProcessId={pid}").CommandLine'],text=True)
    assert str(root) in command and 'server.py' in command and str(before['epoch']) in command
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p;kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(1,False,pid);assert handle
    try:assert kernel.TerminateProcess(handle,93)
    finally:kernel.CloseHandle(handle)
    for _ in range(40):
        record=json.loads(path.read_text())
        if record['finished'] is not None:break
        time.sleep(.1)
    assert record['exit_code']==93 and app.state()==before
    try:require_live_daily(root)
    except ValueError as error:message=str(error)
    else:raise AssertionError('Persisted active was mistaken for a live process')
    release('stop');assert app.state()['phase']=='stopped'
    result={'passed':True,'scope':'Disposable empty fixture, forced exit93; no daily process terminated and no actual OS shutdown performed','root':str(root),'exit_record':record,'persisted_active_unchanged_after_exit':True,'offline_guard_error':message,'fixture_stopped':True,'automatic_restart':False}
    (OUT/'exit-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'exit_code':93,'fixture_stopped':True}))
if __name__=='__main__':main()
