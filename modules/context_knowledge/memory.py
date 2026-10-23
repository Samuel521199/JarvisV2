"""Bounded owner facts and reviewable candidates. No model inference or implicit sharing."""
import math
import re
import time
import uuid

from modules.context_knowledge import Facts
from sdk.protocol import CoreError, canonical, contract, decode

KINDS = {'profile', 'preference', 'agreement', 'knowledge'}


class Memory:
    def __init__(self, db): self.db = db

    def epoch(self): return int(self.db.one("SELECT value FROM meta WHERE key='memory_epoch'")['value'])

    def list(self, scope):
        rows = self.db.all('SELECT f.*,u.kind,u.purpose,u.providers,u.paused,u.expires,u.updated FROM facts f '
                           'LEFT JOIN memory_usage u ON u.fact_id=f.id WHERE f.principal=? AND f.scope=? AND f.deleted=0 ORDER BY f.key', ('owner.local', scope))
        for row in rows:
            row['providers'] = decode(row['providers']) if row['providers'] else []
            row['kind'] = row['kind'] or 'knowledge'
            row['state'] = 'local' if row['purpose'] is None else ('paused' if row['paused'] else ('expired' if row['expires'] and row['expires'] <= time.time() else 'active'))
        return rows

    def save(self, item, revision, source='owner:explicit', candidate=None):
        fields = {'scope', 'key', 'value', 'kind', 'purpose', 'providers', 'paused', 'expires'}
        if not isinstance(item, dict) or set(item) != fields or type(revision) is not int or revision < 0:
            raise CoreError('memory_invalid', 'Invalid memory edit')
        if item['kind'] not in KINDS or item['purpose'] not in {'personal', 'style', 'project'} or type(item['paused']) is not bool:
            raise CoreError('memory_invalid', 'Invalid memory use')
        if (item['scope'] == 'personal') != (item['purpose'] != 'project') or (item['purpose'] == 'style' and item['kind'] != 'preference'):
            raise CoreError('memory_invalid', 'Project facts and shared communication preferences have distinct scopes')
        providers = item['providers']
        if not isinstance(providers, list) or len(providers) > 32 or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', p) for p in providers) or len(set(providers)) != len(providers):
            raise CoreError('memory_invalid', 'Invalid destination allowlist')
        expiry = item['expires']
        if expiry is not None and (type(expiry) not in (int, float) or not math.isfinite(expiry) or not 0 < expiry < 4102444800):
            raise CoreError('memory_invalid', 'Invalid expiry')
        fact = dict(schema='jarvis.fact.v1', principal_id='owner.local', scope_id=item['scope'], key=item['key'], value=item['value'], source=source)
        contract('fact', fact)
        with self.db.transaction() as tx:
            if candidate:
                row = tx.execute('SELECT * FROM memory_candidates WHERE id=?', (candidate['id'],)).fetchone()
                if not row or row['state'] != 'PENDING' or row['revision'] != candidate['revision']:
                    raise CoreError('conflict', 'Candidate changed')
            ident = Facts.write(tx, fact, revision)
            tx.execute('INSERT INTO memory_usage VALUES(?,?,?,?,?,?,?) ON CONFLICT(fact_id) DO UPDATE SET kind=excluded.kind,purpose=excluded.purpose,providers=excluded.providers,paused=excluded.paused,expires=excluded.expires,updated=excluded.updated',
                       (ident, item['kind'], item['purpose'], canonical(providers), item['paused'], expiry, time.time()))
            if candidate:
                tx.execute("UPDATE memory_candidates SET state='ACCEPTED',fact_id=?,key='',value='',revision=revision+1 WHERE id=?", (ident, candidate['id']))
            Facts.bump(tx)
            self.db.event(tx, None, 'memory.saved', {'id': ident, 'scope': item['scope']})
        return {'id': ident, 'revision': revision + 1, 'epoch': self.epoch()}

    def forget(self, scope, key, revision):
        Facts(self.db).forget('owner.local', scope, key, revision)
        return {'forgotten': True, 'epoch': self.epoch()}

    def candidates(self, scope):
        return self.db.all("SELECT * FROM memory_candidates WHERE scope=? AND state='PENDING' ORDER BY created DESC LIMIT 100", (scope,))

    def propose(self, source_id, source_revision, scope, text):
        # Source uniqueness persists after dismissal/withdrawal; no silent resurrection.
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000: raise CoreError('memory_invalid', 'Candidate text limit')
        with self.db.transaction() as tx:
            old = tx.execute('SELECT id,state FROM memory_candidates WHERE source_id=?', (source_id,)).fetchone()
            if old: return dict(old)
            if tx.execute("SELECT count(*) FROM memory_candidates WHERE state='PENDING'").fetchone()[0] >= 200:
                raise CoreError('memory_capacity', 'Review pending memories first')
            ident = 'memory-' + uuid.uuid4().hex
            tx.execute("INSERT INTO memory_candidates(id,source_id,source_revision,scope,key,value,state,created) VALUES(?,?,?,?,?,?,'PENDING',?)",
                       (ident, source_id, source_revision, scope, text.strip()[:60], text.strip(), time.time()))
            return {'id': ident, 'state': 'PENDING'}

    def dismiss(self, ident, revision):
        with self.db.transaction() as tx:
            if tx.execute("UPDATE memory_candidates SET state='DISMISSED',key='',value='',revision=revision+1 WHERE id=? AND revision=? AND state='PENDING'", (ident, revision)).rowcount != 1:
                raise CoreError('conflict', 'Candidate changed')
        return {'dismissed': True}

    def view(self, scope, provider, enabled=True):
        if type(enabled) is not bool: raise CoreError('memory_invalid', 'Invalid memory switch')
        result = []; used = 0; valid_until = None
        if enabled:
            # Filter scopes and destination before any prompt construction. No all-project scan.
            rows = self.list('personal') + (self.list(scope) if scope != 'personal' else [])
            for row in rows:
                if row['state'] != 'active' or provider not in row['providers']: continue
                if scope != 'personal' and row['scope'] == 'personal' and row['purpose'] != 'style': continue
                part = {'id': row['id'], 'revision': row['revision'], 'key': row['key'], 'value': row['value'], 'kind': row['kind']}
                size = len(canonical(part).encode())
                if len(result) >= 12 or used + size > 5000: continue
                result.append(part); used += size
                if row['expires']: valid_until = min(valid_until or row['expires'], row['expires'])
        return {'epoch': self.epoch(), 'facts': result, 'valid_until': valid_until}
