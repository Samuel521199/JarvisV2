"""Explicit isolated-environment probe. --live-model spends one bounded Google request."""
import argparse
import json
import sqlite3
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

from adapters.development_bridge import exchange
from control.atomic import write_json
from control.local_access import install_client


def probe(root, live_model=False):
    origin, stable = 'http://127.0.0.1:18283', 'http://127.0.0.1:18282'

    def get(base, path):
        with urllib.request.urlopen(base + path, timeout=5) as response:
            return json.load(response)

    before = get(stable, '/api/instance')
    try:
        get(origin, '/api/environment')
        raise AssertionError('Anonymous development access was accepted')
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    install_client(origin, root)
    token = get(origin, '/api/session')['token']

    def post(path, value):
        request = urllib.request.Request(origin + path, data=json.dumps(value).encode(),
                                         headers={'Origin': origin, 'Content-Type': 'application/json',
                                                  'X-Jarvis-Token': token})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    environment = get(origin, '/api/environment')
    assert environment['kind'] == 'development'
    try:
        post('/api/mail/connect', {})
        raise AssertionError('Development mail action was accepted')
    except urllib.error.HTTPError as exc:
        assert exc.code == 403
    for name in ['model-credentials.dpapi', 'gmail.dpapi']:
        assert not (root / 'private' / name).exists()
    mailbox = root / 'private/mail.sqlite3'
    if mailbox.exists():
        database = sqlite3.connect(mailbox.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            assert database.execute("SELECT COUNT(*) FROM objects WHERE id IN ('account','client')").fetchone()[0] == 0
        finally:
            database.close()
    catalog = exchange(root, '/catalog')['catalog']
    assert all(item['adapter'] in {'vertex', 'gemini'} for item in catalog['providers'].values())
    assert all(not set(item).intersection({'keys', 'credential_id'}) for item in catalog['providers'].values())
    result = {'schema': 1, 'checked_at_unix': time.time(), 'development_data': str(root),
              'anonymous_rejected': True, 'mail_actions_rejected': True,
              'formal_mail_accounts_not_copied': True,
              'model_credentials_not_copied': True, 'google_only_public_catalog': True}
    if live_model:
        chat = post('/api/chats', {})['id']
        post('/api/chat/update', {'id': chat, 'patch': {'title': '开发环境 · Google 代理验收'}})
        connection = catalog['default_provider']
        model = catalog['providers'][connection]['model']
        request = uuid.uuid4().hex
        post('/api/chat/send', {'chat_id': chat, 'request_id': request,
                              'text': 'Only reply DEV_PROXY_OK. This is a synthetic connectivity test.',
                              'provider': connection, 'model': model, 'reasoning': 'default',
                              'memory_enabled': False, 'skill': 'none'})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            state = get(origin, '/api/chats/' + chat)
            turn = next(item for item in state['turns'] if item['id'] == request)
            if turn['status'] not in {'READY', 'RUNNING'}:
                result['live_chat'] = {'status': turn['status'], 'model': model,
                                       'reply_matched': 'DEV_PROXY_OK' in turn['reply'], 'usage': turn['usage'],
                                       'chat_id': chat, 'request_id': request}
                assert turn['status'] == 'SUCCEEDED' and result['live_chat']['reply_matched'], 'Synthetic chat did not pass'
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Model probe is unresolved; do not automatically retry it')
    after = get(stable, '/api/instance')
    assert before['boot_id'] == after['boot_id'], 'Stable service changed during the development probe'
    result['stable_boot_unchanged'] = True
    result['proxy'] = exchange(root, '/status')
    write_json(root / 'state/development-probe.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-data', type=Path, default=Path(__file__).resolve().parents[1] / 'user-data')
    parser.add_argument('--live-model', action='store_true')
    args = parser.parse_args()
    print(json.dumps(probe(args.development_data, args.live_model), ensure_ascii=False))
