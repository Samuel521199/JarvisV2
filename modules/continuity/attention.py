"""Owner read receipts only. Original task/result stores remain authoritative."""
import hashlib
import sqlite3
import time
from control.paths import child, data_root
from sdk.protocol import CoreError, canonical

TERMINAL = {'finished', 'failed', 'cancelled'}


def identity(item):
    key = item['source'] + ':' + item['id']
    version = hashlib.sha256(canonical([key, item['state'], item.get('raw_status'),
        item.get('result_revision'), item.get('reason', '')]).encode()).hexdigest()
    return key, version


class Attention:
    def __init__(self, root):
        target = child(data_root(root), 'state/attention.sqlite3')
        target.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(target, timeout=5)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS viewed(
            actor TEXT NOT NULL, item TEXT NOT NULL, version TEXT NOT NULL,
            viewed_at REAL NOT NULL, PRIMARY KEY(actor,item))''')

    def project(self, items):
        seen = {}
        keys = [identity(item)[0] for item in items]
        for offset in range(0, len(keys), 400):
            batch = keys[offset:offset+400]
            seen.update(self.db.execute("SELECT item,version FROM viewed WHERE actor='owner.local' AND item IN ("
                + ','.join('?' for _ in batch) + ')', batch))
        for item in items:
            key, version = identity(item)
            item['attention'] = {'key': key, 'version': version,
                'unread': item['state'] in TERMINAL and seen.get(key) != version}

    def acknowledge(self, item, version):
        key, current = identity(item)
        if current != version:
            raise CoreError('attention_stale', 'The result changed; open its current version')
        if item['state'] not in TERMINAL:
            raise CoreError('attention_pending', 'This work has no terminal result')
        with self.db:
            self.db.execute('INSERT INTO viewed VALUES(?,?,?,?) ON CONFLICT(actor,item) '
                'DO UPDATE SET version=excluded.version,viewed_at=excluded.viewed_at',
                ('owner.local', key, version, time.time()))
        return {'key': key, 'version': version, 'unread': False}

    def close(self):
        self.db.close()
