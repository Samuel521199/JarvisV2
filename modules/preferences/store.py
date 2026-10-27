from copy import deepcopy
import re
import sqlite3
from urllib.parse import urlsplit

from control.paths import child
from sdk.protocol import CoreError, canonical, decode
from sdk.pricing import validate_price

ADAPTERS = {'vertex', 'gemini', 'openai', 'bailian', 'xai', 'eachlabs', 'compatible', 'local'}
LEVELS = {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'off', 'on'}
PARAMS = {'max_output_tokens', 'reasoning_effort', 'thinking_level', 'enable_thinking'}


def validate_catalog(config):
    if not isinstance(config, dict) or config.get('schema_version') != 1:
        raise CoreError('settings_invalid', 'Unknown model catalog format')
    allowed = {'schema_version', 'default_provider', 'automatic_fallback', 'fallback_order', 'usage_policy',
               'max_prompt_bytes', 'max_output_tokens', 'local_max_prompt_bytes', 'local_max_output_tokens', 'providers', 'catalog_checked_at'}
    if set(config) - allowed or type(config.get('automatic_fallback')) is not bool:
        raise CoreError('settings_invalid', 'Invalid catalog fields')
    providers = config.get('providers')
    if not isinstance(providers, dict) or not 1 <= len(providers) <= 32:
        raise CoreError('settings_invalid', 'Invalid provider inventory')
    order = config.get('fallback_order', [])
    if not isinstance(order, list) or len(order) > 8 or len(set(order)) != len(order) or any(x not in providers for x in order):
        raise CoreError('settings_invalid', 'Invalid fallback order')
    if config.get('default_provider') not in providers: raise CoreError('settings_invalid', 'Missing default provider')
    for key, limit in [('max_prompt_bytes', 65536), ('max_output_tokens', 32768), ('local_max_prompt_bytes', 65536), ('local_max_output_tokens', 8192)]:
        if key in config and (type(config[key]) is not int or not 1 <= config[key] <= limit):
            raise CoreError('settings_invalid', 'Invalid model limits')
    for name, item in providers.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name) or not isinstance(item, dict):
            raise CoreError('settings_invalid', 'Invalid provider name')
        adapter = item.get('adapter', name)
        if adapter not in ADAPTERS or type(item.get('enabled', True)) is not bool:
            raise CoreError('settings_invalid', 'Unknown provider adapter')
        if set(item) - {'adapter', 'label', 'model', 'enabled', 'credential_id', 'keys', 'location', 'region', 'base_url', 'endpoint', 'balance_hint', 'models'}:
            raise CoreError('settings_invalid', 'Unexpected provider fields')
        if adapter == 'vertex' and item.get('location') != 'global': raise CoreError('settings_invalid', 'Only global Vertex endpoint is supported')
        if adapter == 'bailian' and item.get('region') not in {'beijing', 'singapore', 'us', 'hongkong'}: raise CoreError('settings_invalid', 'Unsupported Bailian region')
        if adapter == 'compatible':
            uri = urlsplit(item.get('base_url', ''))
            if uri.scheme != 'https' or not uri.hostname or uri.username or uri.password or uri.query or uri.fragment:
                raise CoreError('settings_invalid', 'Invalid custom endpoint')
        if adapter == 'local' and item.get('endpoint') != 'http://127.0.0.1:18180/v1/chat/completions':
            raise CoreError('settings_invalid', 'Local endpoint must be fixed loopback')
        models = item.get('models')
        if not isinstance(models, dict) or not 1 <= len(models) <= 128 or item.get('model') not in models:
            raise CoreError('settings_invalid', 'Invalid model inventory')
        for model, profile in models.items():
            if not re.fullmatch(r'[A-Za-z0-9._/-]{1,100}', model) or not isinstance(profile, dict):
                raise CoreError('settings_invalid', 'Invalid model identifier')
            if set(profile) - {'label', 'tier', 'parameters', 'reasoning_levels', 'price', 'enabled', 'notes'}:
                raise CoreError('settings_invalid', 'Unexpected model fields')
            levels = profile.get('reasoning_levels', [])
            params = profile.get('parameters', {})
            if not isinstance(levels, list) or any(v not in LEVELS for v in levels) or not isinstance(params, dict) or set(params) - PARAMS:
                raise CoreError('settings_invalid', 'Invalid reasoning options')
            for field, value in params.items():
                if ((field == 'max_output_tokens' and (type(value) is not int or not 64 <= value <= 32768))
                    or (field == 'enable_thinking' and type(value) is not bool)
                    or (field == 'reasoning_effort' and value not in LEVELS)
                    or (field == 'thinking_level' and value not in {'MINIMAL', 'LOW', 'MEDIUM', 'HIGH'})):
                    raise CoreError('settings_invalid', 'Invalid model parameter')
            validate_price(profile.get('price'))
            if type(profile.get('enabled', True)) is not bool: raise CoreError('settings_invalid', 'Invalid model enable flag')
        if not item.get('models', {}).get(item['model'], {}).get('enabled', True): raise CoreError('settings_invalid', 'Default model is disabled')
    if not providers[config['default_provider']].get('enabled', True): raise CoreError('settings_invalid', 'Default provider is disabled')
    return config


def fallback_routes(catalog, primary, *, limit=None):
    """Enabled routes after ``primary`` in the owner's fallback order.

    Single source for chat, planning and mail; only used when the request chose
    provider 'auto'. ``limit`` bounds paid retries for a caller (planning uses 1).
    """
    routes = []
    if catalog.get('automatic_fallback'):
        for name in catalog.get('fallback_order', []):
            if name != primary['id'] and catalog['providers'][name].get('enabled', True):
                routes.append(resolve(catalog, name))
                if limit and len(routes) >= limit: break
    return routes


def resolve(config, provider=None, model=None, reasoning='default'):
    provider = config['default_provider'] if provider in (None, 'auto') else provider
    item = config['providers'].get(provider)
    if not item or not item.get('enabled', True): raise CoreError('model_disabled', 'Provider is not enabled')
    model = model or item['model']; profile = item['models'].get(model)
    if not profile or not profile.get('enabled', True): raise CoreError('model_disabled', 'Model is not enabled')
    params = deepcopy(profile.get('parameters', {}))
    if reasoning != 'default':
        if reasoning not in profile.get('reasoning_levels', []): raise CoreError('reasoning_invalid', 'Unsupported reasoning level for this model')
        adapter = item.get('adapter', provider)
        if adapter in {'vertex', 'gemini'}: params['thinking_level'] = reasoning.upper()
        elif adapter == 'bailian': params['enable_thinking'] = reasoning == 'on'
        else: params['reasoning_effort'] = reasoning
    limit = config.get('local_max_output_tokens', 256) if item.get('adapter', provider) == 'local' else config.get('max_output_tokens', 4096)
    return {'id': provider, 'adapter': item.get('adapter', provider), 'model': model,
            'credential_id': item.get('credential_id'), 'parameters': params,
            'max_output_tokens': params.get('max_output_tokens', limit), 'timeout_seconds': 120,
            'max_prompt_bytes': config.get('max_prompt_bytes', 50000),
            'region': item.get('region'), 'location': item.get('location'),
            'base_url': item.get('base_url'), 'endpoint': item.get('endpoint'),
            'billing_profile': {'adapter': item.get('adapter',provider), 'connection_label':item.get('label',provider), 'key_label':item.get('keys',{}).get(item.get('credential_id'),{}).get('label',''), 'price':deepcopy(profile.get('price'))}}


def validate_coding(value):
    if not isinstance(value, dict) or set(value) - {'revision', 'enabled', 'model', 'reasoning'}:
        raise CoreError('settings_invalid', 'Unexpected external coding preference')
    if value and (type(value.get('revision')) is not int or value['revision'] < 0
                  or type(value.get('enabled')) is not bool
                  or not isinstance(value.get('model'), str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', value['model'])
                  or value.get('reasoning') not in LEVELS):
        raise CoreError('settings_invalid', 'Invalid external coding preference')
    return value


class Preferences:
    def __init__(self, root):
        path = child(root, 'config/settings.sqlite3'); path.parent.mkdir(exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,catalog TEXT NOT NULL,coding TEXT NOT NULL);'
                             'CREATE TABLE IF NOT EXISTS ui(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);'
                             "INSERT OR IGNORE INTO ui VALUES(1,'{}');")

    def close(self): self.db.close()

    def read(self):
        row = self.db.execute('SELECT * FROM models WHERE id=1').fetchone()
        return {'revision': row['revision'], 'catalog': validate_catalog(decode(row['catalog'])), 'coding': validate_coding(decode(row['coding']))} if row else None

    def install(self, catalog, coding):
        validate_catalog(catalog); validate_coding(coding)
        if self.read(): raise CoreError('settings_exist', 'Existing settings are not overwritten by migration')
        self.db.execute('INSERT INTO models VALUES(1,1,?,?)', (canonical(catalog), canonical(coding)))

    def update(self, command):
        if not isinstance(command, dict) or set(command) != {'revision', 'provider', 'model', 'reasoning', 'automatic_fallback', 'fallback_order'}:
            raise CoreError('settings_invalid', 'Unexpected settings command')
        if type(command['revision']) is not int: raise CoreError('settings_invalid', 'Revision must be an integer')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current = self.read()
            if not current or current['revision'] != command['revision']: raise CoreError('conflict', 'Settings changed; refresh before saving')
            config = current['catalog']; selected = resolve(config, command['provider'], command['model'], command['reasoning'])
            config['default_provider'] = selected['id']; item = config['providers'][selected['id']]
            item['model'] = selected['model']; item['models'][selected['model']]['parameters'] = selected['parameters']
            config['automatic_fallback'] = command['automatic_fallback']; config['fallback_order'] = command['fallback_order']
            validate_catalog(config)
            self.db.execute('UPDATE models SET revision=revision+1,catalog=? WHERE id=1', (canonical(config),))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise
        return self.read()

    def ui(self): return decode(self.db.execute('SELECT value FROM ui WHERE id=1').fetchone()[0])

    def save_ui(self, patch):
        if not isinstance(patch, dict) or set(patch) - {'nav_width', 'panel_width', 'motion_off', 'page', 'theme', 'sound'}:
            raise CoreError('settings_invalid', 'Invalid appearance settings')
        for key, value in patch.items():
            if key in {'nav_width', 'panel_width'}:
                bounds = (180, 340) if key == 'nav_width' else (260, 700)
                if type(value) is not int or not bounds[0] <= value <= bounds[1]: raise CoreError('settings_invalid', 'Invalid panel size')
            if key == 'motion_off' and type(value) is not bool: raise CoreError('settings_invalid', 'Invalid animation preference')
            if key == 'sound' and type(value) is not bool: raise CoreError('settings_invalid', 'Invalid sound preference')
            if key == 'theme' and value not in {'dark', 'light', 'warm', 'mist', 'forest', 'midnight', 'system'}: raise CoreError('settings_invalid', 'Invalid theme')
            if key == 'page' and value not in {'chat', 'overview', 'tasks', 'releases', 'models'}: raise CoreError('settings_invalid', 'Invalid page')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            value = {**self.ui(), **patch}; self.db.execute('UPDATE ui SET value=? WHERE id=1', (canonical(value),)); self.db.execute('COMMIT')
        except BaseException: self.db.execute('ROLLBACK'); raise
        return value

    def public(self, credential_available=lambda *_: False):
        value = self.read()
        if value is None: return {'configured': False, 'revision': 0, 'connections': [], 'ui': self.ui()}
        config = value['catalog']; connections = []
        for name, item in config['providers'].items():
            adapter = item.get('adapter', name)
            connections.append({'id': name, 'adapter': adapter, 'label': item.get('label', name), 'model': item['model'],
                'enabled': item.get('enabled', True), 'credential_available': adapter != 'local' and credential_available(name, item.get('credential_id')),
                'runtime_state': 'not_prepared' if adapter == 'local' else 'configured',
                'base_url':item.get('base_url',item.get('endpoint','')), 'region':item.get('region',item.get('location','')),
                'keys':[{'id':key,'label':v.get('label','本机凭据'),'masked':v.get('masked','••••••••'),'enabled':v.get('enabled',True),'created_at':v.get('created_at',''),'active':key==item.get('credential_id')} for key,v in item.get('keys',{}).items()],
                'models': [{'id': mid, 'label': m.get('label', mid), 'enabled': m.get('enabled', True),
                            'reasoning_levels': m.get('reasoning_levels', []), 'parameters': m.get('parameters', {}),
                            'tier': m.get('tier', ''),'price':m.get('price'),'notes':m.get('notes','')} for mid, m in item['models'].items()]})
        return {'configured': True, 'revision': value['revision'], 'default_provider': config['default_provider'],
                'automatic_fallback': config['automatic_fallback'], 'fallback_order': config['fallback_order'],
                'connections': connections, 'coding': {**value['coding'], 'adapter_state': 'not_implemented'}, 'ui': self.ui()}
