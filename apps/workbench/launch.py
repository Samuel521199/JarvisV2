"""Owner-launched foreground workbench; reuse only the same local data root."""
import argparse
import http.client
import hashlib
import json
from pathlib import Path
import runpy
import socket
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[2]


def running(port, data_root):
    # A bind probe distinguishes a free port even when Windows filters connect probes.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try: probe.bind(('127.0.0.1', port))
        except OSError: pass
        else: return False
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('GET', '/api/instance')
        response = connection.getresponse(); raw = response.read(16385)
        if response.status == 200:
            value = json.loads(raw)
            expected = hashlib.sha256(str(data_root.resolve()).casefold().encode()).hexdigest()
            if len(raw) > 16384 or value.get('service') != 'jarvis-workbench' or value.get('root_digest') != expected: raise ValueError()
            return True
        # Compatibility with an already-running older local service.
        connection.request('GET', '/api/session')
        response = connection.getresponse(); raw = response.read(16385)
        if response.status != 200 or len(raw) > 16384: raise ValueError()
        value = json.loads(raw)
        if Path(value['data_root']).resolve() != data_root: raise ValueError()
        connection.request('GET', '/api/health')
        response = connection.getresponse(); health = json.loads(response.read(16385))
        if response.status != 200 or 'control' not in health: raise ValueError()
        return True
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        raise RuntimeError(f'Port {port} is occupied by another or unresponsive service. '
                           'Close it normally or choose --port; no process was stopped.') from None
    finally: connection.close()


def open_browser(url):
    try:
        if not webbrowser.open(url): print('[Jarvis] Open this address in your browser: ' + url, flush=True)
    except webbrowser.Error: print('[Jarvis] Open this address in your browser: ' + url, flush=True)


def main():
    parser = argparse.ArgumentParser(description='Start Jarvis and open its local workbench.')
    parser.add_argument('--port', type=int, default=18282)
    parser.add_argument('--data-root', type=Path, default=ROOT / 'user-data')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--check', action='store_true', help='Inspect an existing service without starting or modifying data.')
    args = parser.parse_args()
    if sys.version_info < (3, 13): parser.error('Python 3.13 or newer is required.')
    if not 1024 <= args.port <= 65535: parser.error('Port must be between 1024 and 65535.')
    root = args.data_root.resolve(); url = f'http://127.0.0.1:{args.port}/'
    if running(args.port, root):
        print('[Jarvis] Already running with this data folder: ' + url, flush=True)
        if not args.no_browser and not args.check: open_browser(url)
        return 0
    if args.check:
        print('[Jarvis] No running service for this data folder.', flush=True)
        return 1
    sys.path.insert(0, str(ROOT))
    from control.paths import data_root, child
    from host.core import Core
    # Initialize a new installation once. Existing state, credentials and stop controls stay intact.
    root = data_root(root, create=True)
    if not child(root, 'state/core.sqlite3').exists():
        print('[Jarvis] Preparing the new local data folder: ' + str(root), flush=True)
        Core.initialize(root).close()
    print('[Jarvis] Data: ' + str(root), flush=True)
    print('[Jarvis] Keep this window open. Press Ctrl+C to stop the service.', flush=True)
    done = threading.Event()
    def on_ready():
        deadline = time.monotonic() + 30
        while not done.wait(0.3) and time.monotonic() < deadline:
            try:
                if running(args.port, root):
                    print('[Jarvis] Ready: ' + url, flush=True)
                    if not args.no_browser: open_browser(url)
                    return
            except RuntimeError: continue  # Socket may open before the HTTP handler is ready.
        if not done.is_set(): print('[Jarvis] Still starting; see this window for details: ' + url, flush=True)
    threading.Thread(target=on_ready, daemon=True, name='jarvis-browser-launch').start()
    previous = sys.argv
    sys.argv = [str(ROOT / 'apps/workbench/server.py'), '--port', str(args.port), '--data-root', str(root)]
    try: runpy.run_path(str(ROOT / 'apps/workbench/server.py'), run_name='__main__')
    finally: done.set(); sys.argv = previous
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except KeyboardInterrupt: raise SystemExit(0)
    except Exception as exc:
        print('[Jarvis] ' + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
