"""Scoped Studio3D methods and append-only adoption outcomes; no model weights."""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from control.paths import child

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'modules/skills/studio3d/experience-cards.json'


def catalog():
    value = json.loads(CATALOG.read_text(encoding='utf-8'))
    ids = set()
    for row in value['methods']:
        if row['id'] in ids: raise ValueError('Duplicate experience method')
        ids.add(row['id'])
    return value


def source_current(card):
    for row in card['sources']:
        try:
            path=child(ROOT,row['path'])
            if not path.is_file() or path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
                return False
        except (OSError,ValueError,KeyError): return False
    return True


class Studio3DExperience:
    def __init__(self, root):
        path = child(Path(root), 'state/studio3d-experience.sqlite3')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS method_state(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS episodes(run_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, receipt_hash TEXT NOT NULL, outcome TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS uses(run_id TEXT NOT NULL, method_id TEXT NOT NULL, method_revision INTEGER NOT NULL, PRIMARY KEY(run_id,method_id));
        CREATE TABLE IF NOT EXISTS feedback(event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
        ''')

    def close(self): self.db.close()

    def retrieve(self, context, limit=6):
        if not isinstance(limit, int) or not 1 <= limit <= 12: raise ValueError('Invalid retrieval limit')
        rows, rejected = [], []
        states = {r['id']: dict(r) for r in self.db.execute('SELECT * FROM method_state')}
        for card in catalog()['methods']:
            state = states.get(card['id'], {'status': 'SEED', 'revision': card['revision']})
            reason = None
            if state['status'] == 'QUARANTINED': reason = 'quarantined'
            elif context.get('family') not in card['families']: reason = 'family_mismatch'
            elif card.get('asset_ids') and context.get('asset_id') not in card['asset_ids']: reason = 'asset_mismatch'
            elif card.get('tool_version') and context.get('tool_version') != card['tool_version']: reason = 'tool_version_mismatch'
            elif not set(context.get('symptoms', [])) & set(card['symptoms']): reason = 'symptom_mismatch'
            elif any(context.get(k) != v for k, v in card['requires'].items()): reason = 'precondition_mismatch'
            elif not source_current(card): reason = 'source_changed_or_missing'
            if reason: rejected.append({'id': card['id'], 'reason': reason}); continue
            rows.append({**card, 'state': state['status'], 'revision': state['revision']})
        return {'methods': rows[:limit], 'rejected': rejected, 'scope': 'conditional method retrieval, not historical or art approval'}

    def record(self, receipt):
        if receipt.get('schema') != 'jarvis.studio3d.learning.receipt.v1': raise ValueError('Unknown receipt')
        run = receipt['id']; body = json.dumps(receipt, sort_keys=True, ensure_ascii=False, allow_nan=False)
        sha = hashlib.sha256(body.encode()).hexdigest()
        old = self.db.execute('SELECT receipt_hash FROM episodes WHERE run_id=?', (run,)).fetchone()
        if old:
            if old['receipt_hash'] != sha: raise ValueError('Run already has different evidence')
            return {'existing': True}
        # These records are authored only by the host after actual execution.
        # A tool pass certifies its declared scope, never the asset's visual quality.
        cards = {c['id']: c for c in catalog()['methods']}
        for use in receipt['adoptions']:
            if use['id'] not in cards or use['tool'] not in cards[use['id']]['tools']: raise ValueError('Unknown executable adoption')
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?)', (run, receipt['asset_id'], sha, receipt['status'], body, time.time()))
            for use in receipt['adoptions']:
                self.db.execute('INSERT INTO uses VALUES(?,?,?)', (run, use['id'], use['revision']))
        return {'existing': False}

    def feedback(self, event_id, run_id, method_id, reason):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1200: raise ValueError('Explain the counterexample')
        if not all(isinstance(v, str) and 1 <= len(v) <= 100 for v in (event_id, run_id, method_id)): raise ValueError('Invalid feedback identity')
        use = self.db.execute('SELECT * FROM uses WHERE run_id=? AND method_id=?', (run_id, method_id)).fetchone()
        if not use: raise ValueError('Feedback must reference an actual adoption')
        body = json.dumps({'method_id': method_id, 'reason': reason}, sort_keys=True, ensure_ascii=False)
        old = self.db.execute('SELECT * FROM feedback WHERE event_id=?', (event_id,)).fetchone()
        if old:
            if old['run_id'] != run_id or old['body'] != body: raise ValueError('Feedback ID conflict')
            return {'existing': True, 'status': 'QUARANTINED'}
        with self.db:
            self.db.execute('INSERT INTO feedback VALUES(?,?,?,?)', (event_id, run_id, body, time.time()))
            self.db.execute('''INSERT INTO method_state VALUES(?,?,'QUARANTINED',?)
                ON CONFLICT(id) DO UPDATE SET revision=method_state.revision+1,status='QUARANTINED',reason=excluded.reason''',
                (method_id, use['method_revision'] + 1, reason))
        return {'existing': False, 'status': 'QUARANTINED', 'causality': 'counterexample requires review; not a proven root cause'}

    def summary(self):
        return {'catalog_version': catalog()['version'], 'seed_methods': len(catalog()['methods']),
                'states': [dict(r) for r in self.db.execute('SELECT * FROM method_state ORDER BY id')],
                'episodes': self.db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0],
                'distinct_assets': self.db.execute('SELECT COUNT(DISTINCT asset_id) FROM episodes').fetchone()[0],
                'automatic_promotion': False, 'cross_asset_art_gain_verified': False}
