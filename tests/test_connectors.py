from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.mcp.http import endpoint, Session
from control import receipts
from control.network import NetworkGate
from host.core import Core
from host import connectors, goals
from host.settings_operations import TaskRunner
from modules.registry_composer.extensions import Extensions
from modules.task_resource.plans import validate_proposal
from sdk.mcp_schema import normalize
from sdk.protocol import CoreError, canonical
from mcp_fixture import server
from test_preferences_dialogue import fixture
from test_development import Provider


class Connectors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jarvis-mcp-'); self.root = Path(self.tmp.name)
        self.core = Core.initialize(self.root); self.core.preferences.install(fixture(), {})
        self.server = server(); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port) + '/mcp'
        store = Extensions(self.root)
        try:
            self.config = {'transport': 'streamable-http', 'url': self.url, 'command': '', 'args': [], 'credential_ref': ''}
            self.ext = store.command({'action': 'save', 'id': '', 'revision': 0, 'kind': 'mcp', 'name': '本机模拟', 'config': self.config})['id']
        finally: store.close()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.core.close(); self.tmp.cleanup()

    def error(self, code, fn, *args):
        with self.assertRaises(CoreError) as exc: fn(*args)
        self.assertEqual(exc.exception.code, code)

    def discover(self): return connectors.command(self.root, {'action': 'discover', 'id': self.ext, 'revision': 1})

    def enable(self):
        row = self.discover()
        connectors.command(self.root, {'action': 'configure', 'id': self.ext, 'revision': row['revision'], 'selected': ['echo'], 'enabled': True})
        return connectors.listing(self.root)['catalog'][0]

    def request(self, ref):
        return {'action': 'submit', 'request_id': 'connector-test-0001', 'capability': ref['capability'], 'implementation': ref['active'],
                'revision': ref['revision'], 'arguments': {'text': 'Jarvis 中文：7'}}

    def task(self): return connectors.command(self.root, self.request(self.enable()))['id']
    def detail(self, ident): return connectors.command(self.root, {'action': 'detail', 'id': ident})

    def test_discovery_has_no_business_calls_and_needs_explicit_selection(self):
        self.assertEqual(connectors.listing(self.root)['catalog'], [])
        r = self.discover(); self.assertFalse(r['enabled']); self.assertTrue(r['current']); self.assertEqual(self.server.calls, 0)
        self.assertEqual(self.server.methods, ['initialize', 'notifications/initialized', 'tools/list'])
        self.assertEqual(connectors.listing(self.root)['catalog'], [])
        self.error('conflict', connectors.command, self.root, {'action': 'configure', 'id': self.ext, 'revision': 99, 'selected': ['echo'], 'enabled': True})

    def test_real_http_task_delivery_idempotence_and_artifact(self):
        ref = self.enable(); req = self.request(ref); ident = connectors.command(self.root, req)['id']
        self.assertEqual(self.server.calls, 0)
        self.assertEqual(self.core.run_task(ident)['status'], 'SUCCEEDED')
        result = self.detail(ident); self.assertEqual(result['actions'][0]['result']['text'], 'Jarvis 中文：7')
        artifact = result['actions'][1]['result']['relative_path']; self.assertTrue((self.root/artifact).exists())
        self.assertEqual(connectors.command(self.root, req)['id'], ident); self.core.run_task(ident)
        self.assertEqual(self.server.calls, 1); self.assertEqual(self.core.db.all('SELECT * FROM model_calls'), [])
        self.error('conflict', connectors.command, self.root, {**req, 'arguments': {'text': 'other'}})

    def test_bad_arguments_do_not_create_grants(self):
        ref = self.enable(); count = len(self.core.db.all('SELECT * FROM grants'))
        for args in [{'text': 3}, {'text': 'x', 'command': 'run'}, {}, {'text': 'x'*8001}]:
            self.error('mcp_arguments', connectors.command, self.root, {**self.request(ref), 'arguments': args})
        self.assertEqual(len(self.core.db.all('SELECT * FROM grants')), count)

    def test_schema_unsupported_is_visible_but_cannot_enable(self):
        self.server.mode = 'unsupported'; r = self.discover(); self.assertFalse(r['tools'][0]['supported'])
        self.error('mcp_schema', connectors.command, self.root, {'action': 'configure', 'id': self.ext, 'revision': r['revision'], 'selected': ['echo'], 'enabled': True})

    def test_sse_transport_and_cursor_bounds(self):
        self.server.mode = 'sse'; ident = self.task(); self.assertEqual(self.core.run_task(ident)['status'], 'SUCCEEDED')
        self.server.mode = 'cursor'; self.error('mcp_protocol', self.discover)

    def test_duplicate_ids_redirect_and_protocol_errors(self):
        for mode, code in [('duplicate', 'mcp_protocol'), ('bad_id', 'mcp_protocol'), ('redirect', 'mcp_redirect')]:
            self.server.mode = mode; self.error(code, self.discover)
        self.assertEqual(self.server.calls, 0)

    def test_disabled_or_changed_registration_cannot_execute_old_task(self):
        ident = self.task(); r = self.core.connectors.view(self.ext)
        self.core.connectors.configure(self.ext, r['revision'], [], False)
        self.assertEqual(self.core.run_task(ident)['status'], 'WAITING'); self.assertEqual(self.server.calls, 0)
        r = self.core.connectors.view(self.ext); self.core.connectors.configure(self.ext, r['revision'], ['echo'], True)
        self.assertEqual(self.core.run_task(ident)['error'], 'package_changed'); self.assertEqual(self.server.calls, 0)
        store = Extensions(self.root)
        try: store.command({'action': 'save', 'id': self.ext, 'revision': 1, 'kind': 'mcp', 'name': 'changed', 'config': self.config})
        finally: store.close()
        self.assertEqual(self.core.connectors.catalog(), [])

    def test_server_drift_blocks_call_without_silent_reapproval(self):
        ident = self.task(); self.server.description = 'changed'
        self.assertEqual(self.core.run_task(ident)['status'], 'WAITING'); self.assertEqual(self.server.calls, 0)
        # Conservatively UNKNOWN once dispatch is entered; never replay discovery/call.
        self.error('unknown_effect', self.core.run_task, ident)

    def test_error_result_is_confirmed_failure_not_success_or_retry(self):
        ident = self.task(); self.server.mode = 'error'
        self.assertEqual(self.core.run_task(ident)['status'], 'FAILED')
        d = self.detail(ident); self.assertEqual(d['task']['error'], 'mcp_tool_error')
        self.assertEqual(d['actions'][0]['status'], 'CONFIRMED'); self.assertEqual(len(d['actions']), 1)
        self.assertEqual(self.server.calls, 1)

    def test_disconnect_or_oversize_preserves_unknown_and_never_replays(self):
        for mode in ['disconnect', 'oversize', 'image']:
            ref = self.enable(); req = {**self.request(ref), 'request_id': 'failure-case-'+mode}
            ident = connectors.command(self.root, req)['id']; self.server.mode = mode
            self.assertEqual(self.core.run_task(ident)['status'], 'WAITING')
            self.error('unknown_effect', self.core.run_task, ident)
            self.error('unknown_effect', self.core.reconcile, ident)
            self.server.mode = ''
        self.assertEqual(self.server.calls, 3)

    def test_durable_receipt_recovers_crash_without_second_external_call(self):
        ident = self.task()
        with patch.object(self.core.tasks, 'confirm', side_effect=OSError('simulated crash after receipt')):
            self.assertEqual(self.core.run_task(ident)['status'], 'WAITING')
        self.assertEqual(self.server.calls, 1)
        self.core.reconcile(ident); self.assertEqual(self.core.run_task(ident)['status'], 'SUCCEEDED')
        self.assertEqual(self.server.calls, 1)

    def test_network_gate_blocks_local_and_remote_connector_dispatch(self):
        ident = self.task(); gate = NetworkGate(self.root); gate.update({'revision': 0, 'blocked': True})
        self.assertEqual(self.core.run_task(ident)['error'], 'network_disabled'); self.assertEqual(self.server.calls, 0)
        gate.update({'revision': 1, 'blocked': False})
        self.assertEqual(self.core.run_task(ident)['status'], 'SUCCEEDED')

    def test_cancel_active_only_stops_this_task_without_replay(self):
        ident = self.task(); self.server.mode = 'slow'; runner = TaskRunner(self.root)
        try:
            runner.start_connector({'id': ident}); self.assertTrue(self.server.called.wait(5))
            connectors.command(self.root, {'action': 'cancel', 'id': ident})
            deadline = time.monotonic()+5
            while runner.state()['status'] == 'running' and time.monotonic() < deadline: time.sleep(.02)
            self.assertEqual(self.detail(ident)['task']['status'], 'CANCELLED'); self.assertEqual(self.server.calls, 1)
            self.assertEqual(self.core.gate.state(), 'ready')
        finally: runner.close()

    def test_personal_goal_plans_external_input_then_admits_exact_call(self):
        ref = self.enable()
        ident = goals.command(self.root, {'action': 'create', 'request': {'request_id': 'goal-mcp-00001', 'goal': '使用已启用的模拟工具回显 Hello', 'input_text': 'Hello', 'provider': 'auto', 'model': '', 'reasoning': 'default'}})['id']
        proposal = {'schema': 'jarvis.goal-plan.v1', 'summary': '回显输入', 'input_text': '{"text":"Hello"}', 'questions': [],
                    'steps': [{'title': '调用已启用工具', 'capability': ref['capability'], 'source': 'input', 'expected': 'Hello'}]}
        provider = Provider([proposal])
        with patch('host.goals.NativeModel', return_value=provider): p = goals.execute(self.root, ident)
        self.assertEqual(p['status'], 'REVIEW', p); self.assertEqual(self.server.calls, 0)
        task = goals.command(self.root, {'action': 'approve', 'id': ident, 'revision': p['revision']})['task_id']
        self.assertEqual(self.core.run_task(task)['status'], 'SUCCEEDED'); self.assertEqual(self.server.calls, 1)
        self.assertEqual(goals.command(self.root, {'action': 'detail', 'id': ident})['actions'][0]['result']['text'], 'Hello')
        self.assertIn('input_schema', provider.prompts[0])

    def test_project_scope_and_unreviewed_dynamic_arguments_are_rejected(self):
        ref = self.enable()
        self.error('denied', self.core.registry.require_context, ref['capability'], ref['active'], {'scope_id': 'project-test', 'principal_id': 'owner.local'})
        proposal = {'schema': 'jarvis.goal-plan.v1', 'summary': '', 'input_text': '{}', 'questions': [],
                    'steps': [{'title': '', 'capability': ref['capability'], 'source': 'input', 'expected': ''}]*2}
        self.error('plan_capability', validate_proposal, proposal, [ref])

    def test_url_and_schema_constraints(self):
        for url in ['http://example.com/mcp', 'https://user:pass@example.com/mcp', 'https://example.com/mcp?key=x', 'https://example.com/#secret', 'https://example.com:bad', 'https://example.com/\n']:
            self.error('mcp_endpoint', endpoint, url)
        self.error('mcp_schema', normalize, {'type': 'string', 'pattern': '(a+)+$'})
        self.error('mcp_schema', normalize, {'type': 'object', 'additionalProperties': True})

    def test_stdio_or_credential_reference_never_silently_executes(self):
        for config in [{**self.config, 'credential_ref': 'gmail-secret'},
                       {'transport': 'stdio', 'command': 'untrusted-program', 'args': [], 'url': '', 'credential_ref': ''}]:
            store = Extensions(self.root)
            try:
                row = store.db.execute('SELECT revision FROM extensions WHERE id=?', (self.ext,)).fetchone()
                store.command({'action': 'save', 'id': self.ext, 'revision': row['revision'], 'kind': 'mcp', 'name': 'unsupported', 'config': config})
            finally: store.close()
            self.error('mcp_transport_unsupported', connectors.command, self.root, {'action': 'discover', 'id': self.ext, 'revision': row['revision']+1})
        self.assertEqual(self.server.methods, [])

    def test_stop_and_replan_refresh_do_not_reuse_disabled_catalog(self):
        ref = self.enable(); self.core.gate.stop()
        self.error('stopped', connectors.command, self.root, self.request(ref))
        self.assertEqual(self.server.calls, 0)
        self.core.gate.resume(self.core.gate.token())
        ident = goals.command(self.root, {'action': 'create', 'request': {'request_id': 'goal-refresh-0001', 'goal': '回显', 'input_text': '', 'provider': 'auto', 'model': '', 'reasoning': 'default'}})['id']
        p = goals.command(self.root, {'action': 'detail', 'id': ident})['plan']; self.assertEqual(len(p['catalog']), 1)
        view = self.core.connectors.view(self.ext); self.core.connectors.configure(self.ext, view['revision'], [], False)
        goals.command(self.root, {'action': 'amend', 'id': ident, 'revision': p['revision'], 'goal': '重新规划回显', 'input_text': ''})
        self.assertEqual(goals.command(self.root, {'action': 'detail', 'id': ident})['plan']['catalog'], [])


if __name__ == '__main__': unittest.main()
