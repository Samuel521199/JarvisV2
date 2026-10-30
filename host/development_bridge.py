"""Owner-started development sidecar: Google text models and metadata only.

No memory, mail, filesystem, shell or MCP execution endpoint. The production
service is not patched or restarted. Same-user malicious code is not isolated.
"""
import base64
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapters.models.native import NativeModel
from control.credentials import Credentials, crypt, load_envelope
from control.development_profile import bridge_lease
from control.network import NetworkGate
from control.paths import child, data_root
from control.recovery.gate import StopGate
from modules.preferences.store import Preferences, resolve
from sdk.protocol import CoreError, canonical, digest


class Bridge:
    def __init__(self, root, *, factory=None, catalog_loader=None):
        self.root = data_root(root)
        self.policy = load_envelope(child(self.root, 'private/development-bridge.dpapi'))
        self.factory = factory or (lambda route: NativeModel(route, Credentials(self.root).get, self.root / 'temp'))
        self.catalog_loader = catalog_loader
        self.slot = threading.BoundedSemaphore(1)
        self.closing = False
        self.dbpath = child(self.root, 'development/bridge.sqlite3')
        self.dbpath.parent.mkdir(exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,hash TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,result TEXT)')
            db.execute("UPDATE calls SET status='UNKNOWN' WHERE status='DISPATCHING'")

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.dbpath, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def authenticate(self, client, token):
        if not (client == self.policy['client_id'] and isinstance(token, str)
                and secrets.compare_digest(token, 'Bearer ' + self.policy['token'])):
            raise CoreError('development_unauthorized', 'Invalid development client')

    def configuration(self):
        if self.catalog_loader:
            state = self.catalog_loader()
        else:
            prefs = Preferences(self.root)
            try:
                state = prefs.read()
            finally:
                prefs.close()
        if not state:
            raise CoreError('development_catalog_missing', 'Production model settings are unavailable')
        return state

    def catalog(self):
        state = self.configuration()
        catalog = copy.deepcopy(state['catalog'])
        catalog['providers'] = {name: {k: v for k, v in item.items() if k not in {'credential_id', 'keys', 'balance_hint'}}
                                for name, item in catalog['providers'].items()
                                if name in self.policy['allowed_providers'] and item.get('enabled', True)
                                and item.get('adapter', name) in {'vertex', 'gemini'}}
        if not catalog['providers']:
            raise CoreError('development_route_not_allowed', 'No Google route is permitted')
        if catalog['default_provider'] not in catalog['providers']:
            catalog['default_provider'] = next(iter(catalog['providers']))
        catalog['fallback_order'] = [n for n in catalog.get('fallback_order', []) if n in catalog['providers']]
        return {'catalog': catalog, 'coding': {}}

    def status(self):
        with self.db() as db:
            count = db.execute('SELECT COUNT(*) FROM calls WHERE created>?', (time.time() - 86400,)).fetchone()[0]
        manifest = Path(__file__).resolve().parents[1] / 'runtime-manifest.json'
        build = json.loads(manifest.read_text(encoding='utf-8'))['build_id'] if manifest.exists() else 'working-tree'
        return {'profile': 'development-bridge', 'build_id': build, 'production_memory_exposed': False,
                'external_tools_exposed': False, 'allowed_providers': self.policy['allowed_providers'],
                'calls_in_24h': count, 'daily_call_limit': self.policy['daily_call_limit']}

    def model(self, value):
        self.require_current_grant()
        if self.closing:
            raise CoreError('development_closing', 'Development service is draining')
        fields = {'request_id', 'provider', 'model', 'messages', 'json_mode', 'reasoning'}
        if (not isinstance(value, dict) or set(value) != fields
                or not isinstance(value.get('request_id'), str)
                or not re.fullmatch(r'[a-f0-9]{32}', value.get('request_id', ''))
                or value.get('provider') not in self.policy['allowed_providers']
                or type(value.get('json_mode')) is not bool or not isinstance(value.get('reasoning'), dict)
                or len(canonical(value).encode()) > 65536):
            raise CoreError('development_request_invalid', 'Invalid development model request')
        messages = value['messages']
        if (not isinstance(messages, list) or not 1 <= len(messages) <= 41
                or any(not isinstance(m, dict) or set(m) != {'role', 'content'}
                       or m['role'] not in {'user', 'assistant'} or not isinstance(m['content'], str) for m in messages)):
            raise CoreError('development_request_invalid', 'Invalid development messages')
        config = self.configuration()['catalog']
        route = resolve(config, value['provider'], value['model'])
        if route['adapter'] not in {'vertex', 'gemini'}:
            raise CoreError('development_provider_changed', 'This bridge permits Google providers only')
        # Caller parameters are never trusted as arbitrary vendor options.
        if value['reasoning'] != route['parameters']:
            level = value['reasoning'].get('thinking_level', '')
            if not isinstance(level, str):
                raise CoreError('development_parameters_changed', 'Invalid reasoning level')
            adjusted = resolve(config, value['provider'], value['model'], level.lower())
            if adjusted['parameters'] != value['reasoning']:
                raise CoreError('development_parameters_changed', 'Use approved model profile parameters')
            route = adjusted
        route['max_output_tokens'] = min(route['max_output_tokens'], self.policy['max_output_tokens'])
        ident, signature = value['request_id'], digest(value)
        with self.db() as db:
            row = db.execute('SELECT hash,status,result FROM calls WHERE id=?', (ident,)).fetchone()
        if row:
            if row[0] != signature:
                raise CoreError('conflict', 'A request ID cannot change its body')
            if row[2]:
                return json.loads(crypt(base64.b64decode(row[2]), decrypt=True))
            return {'status': 'UNKNOWN', 'code': 'development_outcome_unknown'}
        if not self.slot.acquire(blocking=False):
            raise CoreError('development_busy', 'One development model request is already running')
        try:
            if self.closing:
                raise CoreError('development_closing', 'Development service is draining')
            StopGate(self.root).require_running()
            NetworkGate(self.root).require_online()
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                count = db.execute('SELECT COUNT(*) FROM calls WHERE created>?', (time.time() - 86400,)).fetchone()[0]
                if count >= self.policy['daily_call_limit']:
                    raise CoreError('development_budget', 'Development daily call budget is exhausted')
                db.execute("INSERT INTO calls VALUES(?,?,'DISPATCHING',?,NULL)", (ident, signature, time.time()))
            result = self.factory(route).complete(messages, lambda: (StopGate(self.root).require_running(),
                                                  NetworkGate(self.root).require_online(), self.require_current_grant()), json_mode=value['json_mode'])
            if result.get('status') not in {'SUCCEEDED', 'INVALID', 'REJECTED', 'UNKNOWN'}:
                raise CoreError('development_model_reply', 'Model returned an invalid status')
            encrypted = base64.b64encode(crypt(canonical(result).encode())).decode()
            with self.db() as db:
                db.execute('UPDATE calls SET status=?,result=? WHERE id=?', (result['status'], encrypted, ident))
            return result
        finally:
            self.slot.release()

    def require_current_grant(self):
        try:
            current = load_envelope(self.root / 'private/development-bridge.dpapi')
        except (OSError, ValueError, CoreError):
            raise CoreError('development_auth', 'Development sharing grant is unavailable') from None
        if not secrets.compare_digest(digest(current), digest(self.policy)):
            raise CoreError('development_auth', 'Development sharing changed; the old service cannot keep using its grant')


class Handler(BaseHTTPRequestHandler):
    timeout = 10

    def log_message(self, *args):
        pass

    def respond(self, value, status=200):
        raw = canonical(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def dispatch(self, write=False):
        try:
            if (self.headers.get('Host') != '127.0.0.1:' + str(self.server.server_port)
                    or self.headers.get('Origin') or self.headers.get('Transfer-Encoding')):
                return self.respond({'error': 'development_origin'}, 403)
            self.server.bridge.authenticate(self.headers.get('X-Jarvis-Client'), self.headers.get('Authorization', ''))
            if not write and self.path == '/status':
                return self.respond(self.server.bridge.status())
            if not write and self.path == '/catalog':
                return self.respond(self.server.bridge.catalog())
            if write and self.path == '/shutdown':
                if not self.server.bridge.slot.acquire(blocking=False):
                    return self.respond({'error': 'development_busy'}, 409)
                try:
                    self.server.bridge.closing = True
                    self.respond({'stopping': True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                finally:
                    self.server.bridge.slot.release()
            if write and self.path == '/model':
                size = int(self.headers.get('Content-Length', 0))
                if self.headers.get('Content-Type') != 'application/json' or not 0 < size <= 65536:
                    return self.respond({'error': 'development_size'}, 400)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    return self.respond({'error': 'development_size'}, 400)
                return self.respond(self.server.bridge.model(json.loads(raw)))
            return self.respond({'error': 'not_found'}, 404)
        except CoreError as error:
            return self.respond({'error': error.code}, 401 if error.code == 'development_unauthorized' else 409)
        except (OSError, ValueError, sqlite3.Error):
            return self.respond({'error': 'development_unavailable'}, 503)
        except Exception:
            return self.respond({'error': 'development_unknown'}, 503)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch(True)


def serve(root, port):
    root = data_root(root)
    with bridge_lease(root):
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        server.bridge = Bridge(root)
        try:
            server.serve_forever()
        finally:
            server.server_close()
