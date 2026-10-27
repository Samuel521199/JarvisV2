"""Transactional DPAPI objects. No plaintext full-text or vector index is created."""
from contextlib import contextmanager
import sqlite3

from control.credentials import crypt
from control.paths import child, data_root, reject_links
from sdk.protocol import CoreError, canonical, decode


class PrivateRecords:
    def __init__(self, root):
        self.path = child(data_root(root), 'private/family-records.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for name in ('-journal', '-wal', '-shm'): reject_links(self.path.with_name(self.path.name + name))
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1):
            self.db.close(); raise CoreError('family_schema', 'Unsupported private storage version')
        self.db.execute('CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, deleted INTEGER NOT NULL, payload BLOB NOT NULL)')
        self.db.execute('PRAGMA user_version=1'); self.db.commit()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise

    def read(self, ident):
        row = self.db.execute('SELECT * FROM objects WHERE id=?', (ident,)).fetchone()
        if not row or row['deleted']: raise CoreError('family_missing', 'Private record unavailable')
        body = decode(crypt(bytes(row['payload']), decrypt=True))
        if body.get('id') != ident or body.get('revision') != row['revision']:
            raise CoreError('family_corrupt', 'Private object envelope does not match')
        return body

    def ids(self):
        return [x[0] for x in self.db.execute('SELECT id FROM objects WHERE deleted=0 ORDER BY id')]

    def put(self, body, revision):
        ident = body['id']
        row = self.db.execute('SELECT revision,deleted FROM objects WHERE id=?', (ident,)).fetchone()
        if (row and (row['deleted'] or row['revision'] != revision)) or (not row and revision != 0):
            raise CoreError('conflict', 'Private record changed or was forgotten')
        if not row and self.db.execute('SELECT COUNT(*) FROM objects WHERE deleted=0').fetchone()[0] >= 5000:
            raise CoreError('family_capacity', 'Private record capacity reached')
        updated = {**body, 'revision': revision + 1}
        raw = canonical(updated).encode()
        if len(raw) > 250000: raise CoreError('family_capacity', 'Private object exceeds 250000 bytes; start another chat')
        protected = crypt(raw)
        self.db.execute('INSERT INTO objects VALUES(?,?,0,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload', (ident, revision + 1, protected))
        return updated

    def forget(self, ident, revision):
        row = self.read(ident)
        if row['revision'] != revision: raise CoreError('conflict', 'Private record changed')
        self.db.execute("UPDATE objects SET revision=revision+1,deleted=1,payload=X'' WHERE id=?", (ident,))

    def close(self): self.db.close()
