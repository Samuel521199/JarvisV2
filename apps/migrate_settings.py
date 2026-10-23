"""Explicit migration application; never execute the source application's code."""
import argparse
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control.atomic import write_json
from control.credentials import load_envelope
from control.paths import child, data_root, reject_links
from modules.preferences.store import Preferences, validate_catalog, validate_coding
from sdk.protocol import CoreError, decode, read_json


def migrate(source, destination):
    source = source.resolve(); reject_links(source)
    destination = data_root(destination)
    config_db = source/'user-data/data/model-admin.db'
    reject_links(config_db)
    if config_db.exists():
        with closing(sqlite3.connect(config_db.as_uri()+'?mode=ro', uri=True)) as db:
            revision, raw = db.execute('SELECT revision,config FROM settings WHERE id=1').fetchone()
        catalog = decode(raw)
    else:
        revision = 0; catalog = read_json(source/'config/model-profiles/providers.json')
    validate_catalog(catalog)
    coding_path = source/'user-data/data/coding-settings.db'; reject_links(coding_path)
    coding = {}
    if coding_path.exists():
        with closing(sqlite3.connect(coding_path.as_uri()+'?mode=ro', uri=True)) as db:
            row = db.execute('SELECT value FROM settings WHERE singleton=1').fetchone()
            if row: coding = decode(row[0])
    validate_coding(coding)
    origin = source/'user-data/private/credentials.dpapi'; reject_links(origin)
    credentials = load_envelope(origin)
    bound = []
    for name, item in catalog['providers'].items():
        kid = item.get('credential_id')
        if kid:
            stored = credentials.get('_managed', {}).get(kid, {})
            if stored.get('connection') != name or not isinstance(stored.get('credential'), dict):
                raise CoreError('migration_binding', 'Source credential binding does not match catalog')
            bound.append(name)
    target = child(destination, 'private/model-credentials.dpapi')
    settings = Preferences(destination)
    try:
        current = settings.read()
        if current and (current['catalog'] != catalog or current['coding'] != coding):
            raise CoreError('settings_exist', 'Destination has changed; migration will not overwrite it')
        target.parent.mkdir(exist_ok=True)
        raw = origin.read_bytes()
        if target.exists():
            if target.read_bytes() != raw: raise CoreError('vault_exists', 'Destination credentials differ; preserving them')
        else:
            # Encrypted bytes only. If interrupted here, the next run verifies and resumes.
            with target.open('xb') as stream:
                import os
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if load_envelope(target) != credentials: raise CoreError('migration_verify', 'Credential verification failed')
        if current is None: settings.install(catalog, coding)
        report = {'schema': 1, 'source_revision': revision, 'provider_count': len(catalog['providers']),
                  'model_count': sum(len(x['models']) for x in catalog['providers'].values()),
                  'credential_connections': bound, 'default_provider': catalog['default_provider'],
                  'default_model': catalog['providers'][catalog['default_provider']]['model'],
                  'fallback_order': catalog['fallback_order'], 'catalog_equal': settings.read()['catalog'] == catalog,
                  'encrypted_vault_equal': target.read_bytes() == raw,
                  'ciphertext_sha256': hashlib.sha256(raw).hexdigest(),
                  'runtime_legacy_dependency': False, 'imported_business_databases': False}
        write_json(child(destination, 'config/model-migration.json'), report)
        return report
    finally: settings.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--legacy-root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, default=ROOT/'user-data'); args = parser.parse_args()
    try:
        from sdk.protocol import canonical
        print(canonical(migrate(args.legacy_root, args.data_root)))
    except CoreError as exc:
        print('Migration stopped: '+exc.code); raise SystemExit(2)
