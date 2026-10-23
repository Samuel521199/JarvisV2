import sqlite3
from pathlib import Path
from control.paths import child
from sdk.protocol import CoreError, read_json


class Skills:
    def __init__(self, root):
        self.items = read_json(Path(__file__).resolve().parents[2] / 'seed/skills/conversation.json')['skills']
        self.db = sqlite3.connect(child(root, 'config/skills.sqlite3'), timeout=5, isolation_level=None)
        self.db.execute('CREATE TABLE IF NOT EXISTS policy(id TEXT PRIMARY KEY,enabled INTEGER NOT NULL)')

    def close(self): self.db.close()

    def list(self):
        policy = dict(self.db.execute('SELECT id,enabled FROM policy'))
        return [{**item, 'enabled': bool(policy.get(item['id'], 1))} for item in self.items]

    def enable(self, ident, enabled):
        if type(enabled) is not bool or ident not in {x['id'] for x in self.items}: raise CoreError('skill_invalid', 'Unknown skill or policy')
        self.db.execute('INSERT INTO policy VALUES(?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled', (ident, int(enabled)))
        return {'ok': True}

    def select(self, ident, text):
        if not isinstance(ident, str) or not isinstance(text, str): raise CoreError('chat_invalid', 'Skill and text must be strings')
        if ident == 'none': return None
        usable = [x for x in self.list() if x['enabled'] and x['state'] == 'ready']
        if ident == 'auto':
            # Narrow, explainable matching; ordinary chat loads no guidance.
            return next((x for x in usable if any(word in text.lower() for word in x['triggers'])), None)
        match = next((x for x in usable if x['id'] == ident), None)
        if match is None: raise CoreError('skill_unavailable', 'Skill disabled or adapter not ready')
        return match
