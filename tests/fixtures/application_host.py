"""Synthetic host for process/installer fault tests; no mail, models or user tools."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from control.application_runtime import LocalApprovals, coordination
from control.recovery.gate import RunLock

parser = argparse.ArgumentParser()
parser.add_argument('--data-root', type=Path)
parser.add_argument('--port', type=int)
parser.add_argument('--application-build')
parser.add_argument('--application-epoch', type=int)
args = parser.parse_args()
boot = secrets.token_hex(12)
version = (Path(__file__).resolve().parents[2] / 'VERSION').read_text()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def respond(self, value, code=200):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != '/api/instance': return self.respond({}, 404)
        self.respond({'service': 'jarvis-workbench', 'boot_id': boot,
            'root_digest': hashlib.sha256(str(args.data_root.resolve()).casefold().encode()).hexdigest(),
            'application_build': args.application_build, 'application_epoch': args.application_epoch})

    def do_POST(self):
        action = self.path.rsplit('/', 1)[1]
        try:
            LocalApprovals(args.data_root).verify({'build': args.application_build, 'epoch': args.application_epoch,
                'boot_id': boot, 'action': action}, self.headers.get('X-Jarvis-Application-Proof', ''))
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body == {'build': args.application_build, 'epoch': args.application_epoch}
            current = coordination(args.data_root)
            assert current['epoch'] == args.application_epoch and current['build'] == args.application_build
        except Exception:
            return self.respond({'error': 'fixture_auth'}, 403)
        if action == 'health': return self.respond({'healthy': True}, 503 if 'bad' in version else 200)
        if action == 'drain': return self.respond({'drained': True})
        if action == 'activate': return self.respond({'active': True})
        if action == 'shutdown':
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return self.respond({'stopping': True})
        self.respond({}, 404)


with RunLock(args.data_root, 'workbench-host'):
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    try: server.serve_forever()
    finally: server.server_close()
