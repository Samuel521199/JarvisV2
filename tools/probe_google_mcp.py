"""Explicit live Google -> synthetic local MCP -> Google compatibility probe.

No Skill/model binding, third-party installation, WeChat access or production
task dispatch. Uses the configured Google route, at most two model requests
and exactly one local echo call. Production agent tool use remains separate.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.error

from adapters.mcp.http import Session
from adapters.models.native_transport import post, request
from control.credentials import Credentials
from control.network import NetworkGate
from control.paths import data_root
from control.recovery.gate import StopGate
from modules.preferences.store import Preferences, resolve


ROOT = Path(__file__).resolve().parents[1]


def google_route(root):
    settings = Preferences(root)
    try:
        state = settings.read()
    finally:
        settings.close()
    if not state:
        raise ValueError('model_settings_missing')
    catalog = state['catalog']
    order = list(dict.fromkeys([catalog['default_provider'],
                              *catalog.get('fallback_order', []),
                              *catalog['providers']]))
    for name in order:
        item = catalog['providers'].get(name, {})
        if item.get('adapter', name) in {'vertex', 'gemini'} and item.get('enabled', True):
            route = resolve(catalog, name)
            if Credentials(root).available(route['id'], route.get('credential_id')):
                return route
    raise ValueError('configured_google_route_unavailable')


def probe(root):
    proof = root / 'google-mcp-proof' / 'verification.json'
    result = {'status': 'STARTED', 'checked_at': time.time(), 'model_calls_started': 0,
              'mcp_calls': 0, 'wechat_accessed': False, 'remote_writes': 0,
              'third_party_installed': False, 'production_agent_loop': False,
              'synthetic_data_only': True, 'skill_bound_to_model': False}

    def save():
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def check():
        StopGate(root).require_running()
        NetworkGate(root).require_online()

    save()
    srv = thread = None
    try:
        check()
        route = google_route(root)
        result.update(provider=route['id'], adapter=route['adapter'], model=route['model'])
        credential = Credentials(root).get(route['id'], route.get('credential_id'))
        url, headers, body = request(route, credential, [{'role': 'user', 'content':
            'Call echo once with text jarvis_google_mcp_probe. Then report the receipt '
            'from its result. This is synthetic data, not a desktop task.'}], False)
        del credential
        body['systemInstruction'] = {'parts': [{'text':
            'Only the echo function is available. Call it once, then report its receipt. '
            'Do not claim to access WeChat or any external account.'}]}
        body['generationConfig']['maxOutputTokens'] = 2048
        body['tools'] = [{'functionDeclarations': [{
            'name': 'echo', 'description': 'Synthetic local MCP echo. No external actions.',
            'parameters': {'type': 'OBJECT', 'properties': {'text': {'type': 'STRING'}},
                           'required': ['text']}}]}]
        body['toolConfig'] = {'functionCallingConfig': {'mode': 'ANY', 'allowedFunctionNames': ['echo']}}

        def generate(payload):
            check()
            if result['model_calls_started'] >= 2:
                raise ValueError('probe_budget_exhausted')
            result['model_calls_started'] += 1
            result['status'] = 'MODEL_OUTCOME_PENDING'
            save()
            value = post(url, payload, headers, timeout=35)
            result.setdefault('usage', []).append({k: v for k, v in value.get('usageMetadata', {}).items()
                                                   if type(v) is int and v >= 0})
            save()
            return value

        first = generate(body)
        content = first.get('candidates', [{}])[0].get('content', {})
        calls = [p['functionCall'] for p in content.get('parts', []) if 'functionCall' in p]
        if (len(calls) != 1 or calls[0].get('name') != 'echo'
                or calls[0].get('args') != {'text': 'jarvis_google_mcp_probe'}):
            raise ValueError('expected_single_synthetic_call')
        fixture = importlib.util.spec_from_file_location('jarvis_google_probe_fixture', ROOT / 'tests/mcp_fixture.py')
        module = importlib.util.module_from_spec(fixture)
        fixture.loader.exec_module(module)
        srv = module.server()
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        client = Session('http://127.0.0.1:' + str(srv.server_port) + '/mcp', checkpoint=check, timeout=10)
        client.initialize()
        if [t['name'] for t in client.tools()] != ['echo']:
            raise ValueError('unexpected_fixture_tools')
        check()
        tool_result = client.request('tools/call', {'name': calls[0]['name'], 'arguments': calls[0]['args']})
        result['mcp_calls'] = srv.calls
        if srv.calls != 1 or tool_result.get('isError') or tool_result.get('content') != [
                {'type': 'text', 'text': 'jarvis_google_mcp_probe'}]:
            raise ValueError('mcp_fixture_result_mismatch')
        receipt = 'local_mcp_receipt_' + secrets.token_hex(12)
        response_part = {'name': 'echo', 'response': {'text': tool_result['content'][0]['text'], 'receipt': receipt}}
        if 'id' in calls[0]:
            response_part['id'] = calls[0]['id']
        follow = copy.deepcopy(body)
        follow['toolConfig'] = {'functionCallingConfig': {'mode': 'NONE'}}
        follow['contents'] += [content, {'role': 'user', 'parts': [{'functionResponse': response_part}]}]
        final = generate(follow)
        parts = final.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
        if receipt not in text or any('functionCall' in p for p in parts):
            raise ValueError('model_did_not_report_mcp_receipt')
        result.update(status='SUCCEEDED', function_call_verified=True, tool_response_verified=True)
    except Exception as error:
        result.update(status='FAILED', error_type=type(error).__name__)
        if isinstance(error, urllib.error.HTTPError):
            result['http_status'] = error.code
        elif isinstance(error, ValueError):
            result['error_code'] = str(error)[:90]
        else:
            result['error_code'] = getattr(error, 'code', 'probe_failed')
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
        if thread:
            thread.join(timeout=2)
        save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live explicitly permits up to two Google model requests with synthetic data')
    result = probe(data_root(ROOT / 'user-data'))
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'SUCCEEDED' else 1)


if __name__ == '__main__':
    main()
