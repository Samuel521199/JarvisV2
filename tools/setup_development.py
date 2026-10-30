"""Prepare isolated development data and a narrow Google model proxy grant.

Never copies production memory, email credentials or tasks. Does not start any
service. Owner invokes this explicitly after reviewing the separate checkout.
"""
import argparse
import copy
import json
from pathlib import Path
import secrets

from control.atomic import write_json
from control.credentials import Credentials
from control.development_profile import write_secret, read, client_secret
from control.paths import data_root, child, reject_links
from host.core import Core
from host.development_bridge import Bridge
from modules.preferences.store import Preferences


def setup(production, development, bridge_port=18482, daily_calls=64):
    production = data_root(production)
    development = Path(development).absolute()
    reject_links(development)
    development = development.resolve()
    if (production == development or production in development.parents or development in production.parents):
        raise ValueError('Production and development data must be separate sibling trees')
    if not 1024 <= bridge_port <= 65535 or not 1 <= daily_calls <= 1000:
        raise ValueError('Invalid development port or model call budget')
    pending = read(development) if (development / 'config/development.json').exists() else None
    if (production / 'private/development-bridge.dpapi').exists():
        raise ValueError('A production-side grant already exists; it was not replaced')
    if not pending and development.exists() and any(development.iterdir()):
        raise ValueError('Use an empty development data folder; existing data was not overwritten')
    prefs = Preferences(production)
    try:
        state = prefs.read()
    finally:
        prefs.close()
    names = [name for name, item in state['catalog']['providers'].items()
             if item.get('adapter', name) in {'vertex', 'gemini'} and item.get('enabled', True)
             and Credentials(production).available(name, item.get('credential_id'))]
    if not names:
        raise ValueError('No configured Google provider to share')
    if pending:
        grant = client_secret(development)
        if (grant['allowed_providers'] != names or grant['daily_call_limit'] != daily_calls
                or pending['bridge_origin'] != 'http://127.0.0.1:' + str(bridge_port)):
            raise ValueError('Pending setup has a different sharing policy; it was not replaced')
        client = grant['client_id']
    else:
        client = secrets.token_hex(16)
        grant = {'client_id': client, 'token': secrets.token_urlsafe(32), 'allowed_providers': names,
                 'daily_call_limit': daily_calls, 'max_output_tokens': 4096}
    root = data_root(development, create=True)
    Core.initialize(root).close()
    profile = {'schema': 1, 'kind': 'development', 'client_id': client,
               'bridge_origin': 'http://127.0.0.1:' + str(bridge_port),
               'allowed_providers': names, 'external_actions': False, 'production_data': str(production)}
    # Initialize policy before any model route is exposed to the UI.
    write_json(child(root, 'config/development.json'), profile)
    write_secret(child(root, 'private/development-bridge.dpapi'), grant)
    # Resolve the public projection before writing anything to the production root.
    projection = object.__new__(Bridge)
    projection.policy = grant
    projection.catalog_loader = lambda: state
    config = projection.catalog()
    devprefs = Preferences(root)
    try:
        if not devprefs.read():
            devprefs.install(config['catalog'], config['coding'])
    finally:
        devprefs.close()
    write_secret(child(production, 'private/development-bridge.dpapi'), grant)
    return {'development_data': str(root), 'shared_providers': names,
            'production_memory_copied': False, 'production_credentials_copied': False,
            'bridge_origin': profile['bridge_origin'], 'daily_model_call_limit': daily_calls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-data', type=Path, required=True)
    parser.add_argument('--development-data', type=Path, required=True)
    parser.add_argument('--bridge-port', type=int, default=18482)
    parser.add_argument('--daily-model-calls', type=int, default=64)
    args = parser.parse_args()
    if not 1024 <= args.bridge_port <= 65535 or not 1 <= args.daily_model_calls <= 1000:
        parser.error('Invalid port or budget')
    print(json.dumps(setup(args.production_data, args.development_data, args.bridge_port,
                           args.daily_model_calls), ensure_ascii=False))
