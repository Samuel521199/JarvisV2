import copy
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from control.atomic import write_json
from control.credentials import Credentials
from control.development_profile import read, write_secret, bridge_lease
from control.network import NetworkGate
from host.development_bridge import Bridge, Handler
from http.server import ThreadingHTTPServer
from sdk.protocol import CoreError


CATALOG = {'schema_version': 1, 'default_provider': 'google', 'automatic_fallback': False,
           'fallback_order': [], 'max_output_tokens': 512, 'max_prompt_bytes': 10000,
           'providers': {'google': {'adapter': 'gemini', 'enabled': True, 'model': 'configured-model',
                                    'keys': {'secret-reference': {'masked': 'not-a-secret'}},
                                    'credential_id': 'secret-reference',
                                    'models': {'configured-model': {'parameters': {}, 'reasoning_levels': []}}}}}


@unittest.skipUnless(os.name == 'nt', 'The credential bridge requires Windows DPAPI')
class DevelopmentBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jarvis-dev-bridge-')
        self.base = Path(self.tmp.name).resolve()
        self.prod = self.base / 'prod'
        self.dev = self.base / 'dev'
        for root in [self.prod, self.dev]:
            for name in ['config', 'private', 'state', 'temp']:
                (root / name).mkdir(parents=True, exist_ok=True)
        self.policy = {'client_id': secrets.token_hex(16), 'token': secrets.token_urlsafe(32),
                       'allowed_providers': ['google'], 'daily_call_limit': 2, 'max_output_tokens': 512}
        write_secret(self.prod / 'private/development-bridge.dpapi', self.policy)
        self.calls = 0
        self.routes = []

        def factory(route):
            self.routes.append(route)
            case = self
            class Model:
                def complete(self, messages, checkpoint, json_mode=False):
                    checkpoint()
                    case.calls += 1
                    return {'status': 'SUCCEEDED', 'text': 'synthetic result', 'usage': {'total_tokens': 4}}
            return Model()
        self.bridge = Bridge(self.prod, factory=factory, catalog_loader=lambda: {'catalog': copy.deepcopy(CATALOG)})

    def tearDown(self):
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith('jarvis-dev-bridge-'))
        self.tmp.cleanup()

    def request(self):
        return {'request_id': secrets.token_hex(16), 'provider': 'google', 'model': 'configured-model',
                'messages': [{'role': 'user', 'content': 'synthetic test'}], 'json_mode': False, 'reasoning': {}}

    def profile(self):
        write_json(self.dev / 'config/development.json', {'schema': 1, 'kind': 'development',
                   'client_id': self.policy['client_id'], 'bridge_origin': 'http://127.0.0.1:18482',
                   'allowed_providers': ['google'], 'external_actions': False})

    def test_catalog_and_status_never_expose_credentials(self):
        value = json.dumps(self.bridge.catalog())
        self.assertNotIn('credential_id', value)
        self.assertNotIn('secret-reference', value)
        self.assertNotIn(self.policy['token'], value + json.dumps(self.bridge.status()))

    def test_authentication_is_bound_to_client_and_secret(self):
        for client, token in [('other', 'Bearer '+self.policy['token']), (self.policy['client_id'], 'bad')]:
            with self.assertRaises(CoreError):
                self.bridge.authenticate(client, token)
        self.bridge.authenticate(self.policy['client_id'], 'Bearer ' + self.policy['token'])

    def test_identical_request_is_cached_without_a_second_model_call(self):
        value = self.request()
        self.assertEqual(self.bridge.model(value), self.bridge.model(value))
        self.assertEqual(self.calls, 1)
        raw = self.bridge.dbpath.read_bytes()
        self.assertNotIn(b'synthetic result', raw)
        changed = copy.deepcopy(value)
        changed['messages'][0]['content'] = 'changed'
        with self.assertRaises(CoreError):
            self.bridge.model(changed)

    def test_unknown_outcome_is_not_retried(self):
        value = self.request()
        from sdk.protocol import digest
        with self.bridge.db() as db:
            db.execute("INSERT INTO calls VALUES(?,?,'DISPATCHING',1,NULL)", (value['request_id'], digest(value)))
        self.assertEqual(self.bridge.model(value)['status'], 'UNKNOWN')
        self.assertEqual(self.calls, 0)

    def test_budget_survives_new_requests(self):
        self.bridge.model(self.request())
        self.bridge.model(self.request())
        with self.assertRaises(CoreError) as error:
            self.bridge.model(self.request())
        self.assertEqual(error.exception.code, 'development_budget')
        self.assertEqual(self.calls, 2)

    def test_private_route_retains_managed_credential_binding(self):
        self.bridge.model(self.request())
        self.assertEqual(self.routes[0]['credential_id'], 'secret-reference')
        self.assertNotIn('credential_id', self.bridge.catalog()['catalog']['providers']['google'])

    def test_native_development_adapter_uses_proxy_and_honours_offline(self):
        from adapters.models.native import NativeModel
        self.profile()
        route = {'id': 'google', 'adapter': 'gemini', 'model': 'configured-model', 'parameters': {},
                 'max_output_tokens': 512, 'max_prompt_bytes': 10000}
        model = NativeModel(route, lambda *_: self.fail('Development loaded a vendor credential'), self.dev / 'temp')
        with patch('adapters.development_bridge.exchange', return_value={'status': 'SUCCEEDED', 'text': 'synthetic'}) as proxy:
            self.assertEqual(model.complete([{'role': 'user', 'content': 'synthetic'}], lambda: None)['text'], 'synthetic')
            self.assertEqual(proxy.call_count, 1)
            gate = NetworkGate(self.dev)
            gate.update({'revision': gate.read()['revision'], 'blocked': True})
            blocked = model.complete([{'role': 'user', 'content': 'synthetic'}], lambda: None)
            self.assertEqual(blocked['status'], 'REJECTED')
            self.assertEqual(blocked['code'], 'network_disabled')
            self.assertEqual(proxy.call_count, 1)

    def test_unapproved_provider_and_parameters_are_rejected(self):
        for patch_value in [{'provider': 'other'}, {'reasoning': {'thinking_level': 'HIGH'}}]:
            with self.assertRaises(CoreError):
                self.bridge.model({**self.request(), **patch_value})
        self.assertEqual(self.calls, 0)

    def test_production_network_stop_is_respected(self):
        policy = NetworkGate(self.prod)
        policy.update({'revision': policy.read()['revision'], 'blocked': True})
        with self.assertRaises(CoreError):
            self.bridge.model(self.request())
        self.assertEqual(self.calls, 0)

    def test_development_cannot_read_credentials_or_connect_directly(self):
        self.profile()
        self.assertEqual(read(self.dev)['kind'], 'development')
        with self.assertRaises(CoreError):
            Credentials(self.dev).get('google')
        with self.assertRaises(CoreError):
            Credentials(self.dev).save({'google': {'api_key': 'synthetic'}})
        with self.assertRaises(CoreError):
            NetworkGate(self.dev).require_online()
        self.assertIsNone(read(self.prod))

    def test_corrupt_profile_fails_closed(self):
        write_json(self.dev / 'config/development.json', {'kind': 'wrong'})
        with self.assertRaises(CoreError):
            read(self.dev)

    def test_one_bridge_owns_the_data_root(self):
        with bridge_lease(self.prod):
            with self.assertRaises(CoreError):
                with bridge_lease(self.prod):
                    self.fail('second bridge acquired the production model grant')
        with bridge_lease(self.prod):
            pass

    def test_draining_rejects_new_model_work(self):
        self.bridge.closing = True
        with self.assertRaises(CoreError):
            self.bridge.model(self.request())
        self.assertEqual(self.calls, 0)

    def test_changed_grant_blocks_new_and_cached_model_requests(self):
        value = self.request()
        self.bridge.model(value)
        write_secret(self.prod / 'private/development-bridge.dpapi', {**self.policy, 'daily_call_limit': 1})
        with self.assertRaises(CoreError):
            self.bridge.model(value)
        self.assertEqual(self.calls, 1)

    def test_setup_can_resume_after_model_settings_installation_failure(self):
        from tools.setup_development import setup
        from modules.preferences.store import Preferences
        production, development = self.base / 'setup-prod', self.base / 'setup-dev'
        for name in ['config', 'private']:
            (production / name).mkdir(parents=True)
        prefs = Preferences(production)
        prefs.install(copy.deepcopy(CATALOG), {})
        prefs.close()
        with patch.object(Credentials, 'available', return_value=True):
            with patch.object(Preferences, 'install', side_effect=RuntimeError('synthetic interrupted setup')):
                with self.assertRaises(RuntimeError):
                    setup(production, development)
            before = read(development)['client_id']
            self.assertFalse((production / 'private/development-bridge.dpapi').exists())
            setup(production, development)
        self.assertTrue((production / 'private/development-bridge.dpapi').exists())
        self.assertEqual(read(development)['client_id'], before)
        self.assertEqual(read(development)['allowed_providers'], ['google'])

    def test_frozen_proxy_is_independent_and_detects_tampering(self):
        from host.development_runtime import freeze, verify
        package, build = freeze(self.base / 'proxy-releases')
        self.assertEqual(verify(package)['build_id'], build)
        self.assertFalse((package / 'user-data').exists())
        (package / 'host/development_bridge.py').write_text('# tampered\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            verify(package)

    def test_normal_start_keeps_the_approved_proxy_instead_of_freezing_development_edits(self):
        from host.development_runtime import selected_proxy, start
        import hashlib
        self.profile()
        with self.assertRaises(ValueError):
            selected_proxy(self.prod)
        package, build = selected_proxy(self.prod, adopt=True)
        metadata = {'service': 'jarvis-workbench', 'root_digest': hashlib.sha256(str(self.dev.resolve()).casefold().encode()).hexdigest()}
        with patch('host.development_runtime.freeze', side_effect=AssertionError('default start adopted mutable code')):
            with patch('host.development_runtime.exchange', return_value={'build_id': build}):
                with patch('host.development_runtime.json_get', return_value=metadata):
                    receipt = start(self.dev, self.prod, 18283)
        self.assertEqual(receipt['proxy_build'], build)
        self.assertEqual(receipt['started_pids'], {})

    def test_workbench_shutdown_refuses_work_then_stops_the_listener(self):
        from apps.workbench.server import Handler as WorkbenchHandler
        from host.core import Core
        from types import SimpleNamespace
        Core.initialize(self.dev).close()
        self.profile()
        activity = {'running': [1], 'queued': []}
        server = ThreadingHTTPServer(('127.0.0.1', 0), WorkbenchHandler)
        server.data_root = self.dev
        server.nonce = 'synthetic-page-token'
        server.dialogues = SimpleNamespace(state=lambda: activity)
        server.task_runner = SimpleNamespace(state=lambda: {'active': [], 'queued': []})
        server.background_lane = SimpleNamespace(state=lambda: {'status': 'idle'})
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        headers = {'Origin': origin, 'X-Jarvis-Token': server.nonce, 'Content-Type': 'application/json'}
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(origin + '/api/development/shutdown', data=b'{}', headers=headers))
            self.assertEqual(error.exception.code, 409)
            activity['running'] = []
            with urllib.request.urlopen(urllib.request.Request(origin + '/api/development/shutdown', data=b'{}', headers=headers)) as response:
                self.assertTrue(json.load(response)['stopping'])
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
        finally:
            server.shutdown()
            server.server_close()
            if hasattr(server, 'family'):
                server.family.close()

    def test_http_rejects_anonymous_and_browser_origins(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.bridge = self.bridge
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        url = 'http://127.0.0.1:' + str(server.server_port)
        headers = {'Authorization': 'Bearer ' + self.policy['token'], 'X-Jarvis-Client': self.policy['client_id']}
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(url + '/status')
            self.assertEqual(error.exception.code, 401)
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(url + '/status', headers={**headers, 'Origin': 'https://example.com'}))
            self.assertEqual(error.exception.code, 403)
            with urllib.request.urlopen(urllib.request.Request(url + '/status', headers=headers)) as result:
                self.assertFalse(json.load(result)['production_memory_exposed'])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(urllib.request.Request(url + '/memory', headers=headers))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
