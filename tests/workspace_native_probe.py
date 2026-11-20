"""Launch only an owned fixture shell, read its Win32 window state, then stop it."""
import ctypes,json,os,socket,subprocess,sys,threading
from ctypes import wintypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

folder=Path(sys.argv[1]).resolve();binary=Path(sys.argv[2]).resolve();fixture=json.loads((folder/'fixture.json').read_bytes())
with socket.socket() as sock:sock.bind(('127.0.0.1',0));cdp=sock.getsockname()[1]
environment={**os.environ,'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS':f'--remote-debugging-address=127.0.0.1 --remote-debugging-port={cdp}'}
payload={'protocol':2,'data_root':fixture['root'],'origin':'http://127.0.0.1:'+str(fixture['port'])+'/','access':fixture['key']}
user=ctypes.WinDLL('user32',use_last_error=True);user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4));user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsWindowVisible.restype=wintypes.BOOL
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user.GetForegroundWindow.restype=wintypes.HWND
user.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];user.MonitorFromWindow.restype=wintypes.HMONITOR
class MonitorInfo(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
user.GetMonitorInfoW.argtypes=[wintypes.HMONITOR,ctypes.POINTER(MonitorInfo)]
mode='playful' if '--motion' in sys.argv[3:] else 'still' if '--motion-still' in sys.argv[3:] else None
if mode:
    preference=Path(fixture['root'])/'optional/desktop-presence/motion-mode'
    preference.parent.mkdir(parents=True,exist_ok=True)
    assert not preference.exists(),'Use a clean isolated fixture for mode verification'
    if mode=='still':preference.write_text('still\n',encoding='ascii')
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM);user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
with (folder/'native.stderr.log').open('wb') as errors:
    child=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors,env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    child.stdin.write(json.dumps(payload).encode());child.stdin.close()
    def windows():
        result={"workbench":[],"robot":[],"dock":[]}
        @callback
        def visit(handle,_):
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value==child.pid:
                title=ctypes.create_unicode_buffer(512);user.GetWindowTextW(handle,title,512)
                role={'Jarvis \u5de5\u4f5c\u53f0':'workbench','Jarvis \u7cbe\u7075':'robot','Jarvis \u6807\u7b7e\u4e0e\u5361\u7247':'dock'}.get(title.value)
                if role:
                    item={'handle':int(handle),'visible':bool(user.IsWindowVisible(handle))}
                    if mode and role!='workbench':
                        rect=wintypes.RECT();work=MonitorInfo();work.size=ctypes.sizeof(work)
                        if user.GetWindowRect(handle,ctypes.byref(rect)):item['rect']=[rect.left,rect.top,rect.right,rect.bottom]
                        if user.GetMonitorInfoW(user.MonitorFromWindow(handle,2),ctypes.byref(work)):item['work']=[work.work.left,work.work.top,work.work.right,work.work.bottom]
                    result[role].append(item)
            return True
        user.EnumWindows(visit,0)
        if mode:result['foreground']=user.GetForegroundWindow()
        return result
    class Probe(BaseHTTPRequestHandler):
        def do_GET(self):
            raw=json.dumps(windows()).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Probe);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        script='companion-motion-native.cjs' if mode else 'native-upgrade.cjs' if '--upgrade' in sys.argv[3:] else 'workspace-native.cjs'
        result=subprocess.run(['node',str(Path(__file__).with_name(script)),str(folder),str(cdp),str(server.server_port),mode or ''],env=environment,timeout=90,capture_output=True,text=True,encoding='utf-8');print(result.stdout);print(result.stderr)
    finally:
        server.shutdown();server.server_close()
        if child.poll() is None:child.terminate()
        child.wait(timeout=10)
    raise SystemExit(result.returncode)
