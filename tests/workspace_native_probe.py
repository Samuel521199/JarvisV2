"""Launch only an owned fixture shell, read its Win32 window state, then stop it."""
import ctypes,json,os,socket,subprocess,sys,threading
from ctypes import wintypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

folder=Path(sys.argv[1]).resolve();binary=Path(sys.argv[2]).resolve();fixture=json.loads((folder/'fixture.json').read_bytes())
with socket.socket() as sock:sock.bind(('127.0.0.1',0));cdp=sock.getsockname()[1]
environment={**os.environ,'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS':f'--remote-debugging-address=127.0.0.1 --remote-debugging-port={cdp}'}
payload={'protocol':2,'data_root':fixture['root'],'origin':'http://127.0.0.1:'+str(fixture['port'])+'/','access':fixture['key']}
user=ctypes.WinDLL('user32',use_last_error=True);user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsWindowVisible.restype=wintypes.BOOL
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM);user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
with (folder/'native.stderr.log').open('wb') as errors:
    child=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors,env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    child.stdin.write(json.dumps(payload).encode());child.stdin.close()
    def windows():
        result=[]
        @callback
        def visit(handle,_):
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value==child.pid:
                title=ctypes.create_unicode_buffer(512);user.GetWindowTextW(handle,title,512)
                if title.value=='Jarvis 工作台':result.append({'handle':int(handle),'visible':bool(user.IsWindowVisible(handle))})
            return True
        user.EnumWindows(visit,0);return result
    class Probe(BaseHTTPRequestHandler):
        def do_GET(self):
            raw=json.dumps({'workbench':windows()}).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Probe);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        result=subprocess.run(['node',str(Path(__file__).with_name('native-upgrade.cjs' if '--upgrade' in sys.argv[3:] else 'workspace-native.cjs')),str(folder),str(cdp),str(server.server_port)],env=environment,timeout=90,capture_output=True,text=True,encoding='utf-8');print(result.stdout);print(result.stderr)
    finally:
        server.shutdown();server.server_close()
        if child.poll() is None:child.terminate()
        child.wait(timeout=10)
    raise SystemExit(result.returncode)
