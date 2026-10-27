"""Loopback workbench requires the launcher's access key when household login is off."""
from __future__ import annotations

import http.client
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.workbench.server import Handler
from control.local_access import LocalAccess, cookie_name, load_or_create_key, read_key
from host.core import Core
from sdk.protocol import CoreError, canonical, decode

KEY = 'k' * 43


class LocalAccessHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'data'
        Core.initialize(self.root).close()

    def tearDown(self):
        self.tmp.cleanup()

    def serve(self, access):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.data_root = self.root; server.nonce = 'fixture-nonce'
        if access: server.access = LocalAccess(self.root, key=KEY)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        origin = 'http://127.0.0.1:' + str(server.server_port)

        def request(method, path, value=None, cookie='', nonce=True):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Origin': origin, 'Content-Type': 'application/json'}
            if nonce: headers['X-Jarvis-Token'] = server.nonce
            if cookie: headers['Cookie'] = cookie
            connection.request(method, path, None if value is None else canonical(value), headers)
            response = connection.getresponse(); raw = response.read()
            result = (response.status, raw, dict(response.getheaders())); connection.close()
            return result
        return server, request

    def test_local_program_cannot_obtain_nonce_or_take_over_household(self):
        server, request = self.serve(access=True)
        status, raw, _ = request('GET', '/api/session')
        self.assertEqual((status, decode(raw)['error']), (401, 'local_access'))
        for path in ('/api/snapshot', '/api/chats', '/api/health', '/api/settings'):
            self.assertEqual(request('GET', path)[0], 401, path)
        # Even with a guessed nonce, writes without the access session are refused.
        self.assertEqual(request('POST', '/api/family/setup', {'password': 'x' * 16, 'policy': 'p'})[0], 401)
        self.assertEqual(request('POST', '/api/settings', {})[0], 401)
        # Static code and liveness stay reachable so the page can load and unlock itself.
        self.assertEqual(request('GET', '/')[0], 200)
        self.assertEqual(request('GET', '/ui.js')[0], 200)
        self.assertEqual(request('GET', '/api/instance')[0], 200)

    def test_key_exchange_issues_http_only_cookie_once_key_matches(self):
        server, request = self.serve(access=True)
        self.assertEqual(request('POST', '/api/local-access', {'key': 'wrong' * 9}, nonce=False)[0], 401)
        status, _, headers = request('POST', '/api/local-access', {'key': KEY}, nonce=False)
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie']
        self.assertTrue(cookie.startswith(cookie_name(server.server_port) + '='))
        self.assertIn('HttpOnly', cookie); self.assertIn('SameSite=Strict', cookie)
        session = cookie.split(';', 1)[0]
        status, raw, _ = request('GET', '/api/session', cookie=session)
        self.assertEqual(status, 200); self.assertEqual(decode(raw)['token'], 'fixture-nonce')
        self.assertEqual(request('GET', '/api/session', cookie=cookie_name(server.server_port) + '=forged')[0], 401)

    def test_unlock_attempts_are_rate_limited(self):
        access = LocalAccess(self.root, key=KEY)
        for _ in range(20):
            with self.assertRaises(CoreError): access.unlock('nope')
        with self.assertRaises(CoreError) as raised: access.unlock(KEY)
        self.assertEqual(raised.exception.code, 'local_access_rate')

    def test_embedded_server_without_key_keeps_previous_behaviour(self):
        _, request = self.serve(access=False)
        self.assertEqual(request('GET', '/api/session')[0], 200)

    def test_unexpected_handler_error_returns_json_500_and_is_logged(self):
        from unittest.mock import patch
        _, request = self.serve(access=False)
        with patch('host.workbench.read', side_effect=RuntimeError('synthetic')), self.assertLogs('jarvis.http', 'ERROR') as logged:
            status, raw, _ = request('GET', '/api/projects')
        self.assertEqual((status, decode(raw)['error']), (500, 'internal_error'))
        self.assertIn('/api/projects', logged.output[0])

    def test_cookie_survives_unparseable_cookies_from_other_local_apps(self):
        from control.local_access import cookie_value
        for header in ('other={"a":1}; jarvis_local_18282=tok', 'x=a b; jarvis_local_18282=tok', 'jarvis_local_18282=tok'):
            self.assertEqual(cookie_value(header, 18282), 'tok', header)
        self.assertEqual(cookie_value('jarvis_local_182820=no', 18282), '')

    @unittest.skipIf(os.name == 'nt', 'POSIX permission bits')
    def test_key_file_is_private_and_stable(self):
        key = load_or_create_key(self.root)
        self.assertEqual(read_key(self.root), key)
        self.assertEqual(load_or_create_key(self.root), key)
        mode = (self.root / 'private/workbench-access.key').stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == '__main__':
    unittest.main()
