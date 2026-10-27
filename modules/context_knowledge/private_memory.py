"""Household ACLs and private memory; owner access remains explicit and visible."""
import re
import time
import uuid

from adapters.storage.private_records import PrivateRecords
from sdk.protocol import CoreError


def text(value, maximum):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise CoreError('family_invalid', 'Invalid text length')
    return value.strip()


class PrivateMemory:
    def __init__(self, root): self.store = PrivateRecords(root)
    def close(self): self.store.close()

    @staticmethod
    def allowed(actor, row, write=False):
        return actor['role'] == 'owner' or row['owner'] == actor['id'] or (not write and actor['id'] in row.get('shared', []))

    def read(self, actor, ident, write=False):
        if not isinstance(ident, str) or not re.fullmatch('private-[0-9a-f]{32}', ident):
            raise CoreError('family_missing', 'Private record unavailable')
        row = self.store.read(ident)
        if not self.allowed(actor, row, write): raise CoreError('family_missing', 'Private record unavailable')
        return row

    def list(self, actor, kind='note', query=''):
        if kind not in {'note', 'chat'} or not isinstance(query, str) or len(query) > 200:
            raise CoreError('family_invalid', 'Invalid private query')
        result = []
        for ident in self.store.ids():
            row = self.store.read(ident)
            if row['kind'] != kind or not self.allowed(actor, row): continue
            if query and query.casefold() not in (row['title'] + ' ' + row.get('text', '')).casefold(): continue
            result.append({k: row[k] for k in ('id', 'revision', 'owner', 'title', 'kind', 'updated', 'shared', 'providers')})
        return sorted(result, key=lambda x: x['updated'], reverse=True)

    def save(self, actor, value, members):
        if not isinstance(value, dict) or set(value) != {'id', 'revision', 'title', 'text', 'shared', 'providers'} or type(value['revision']) is not int:
            raise CoreError('family_invalid', 'Invalid private note')
        shared, providers = value['shared'], value['providers']
        active = {x['id'] for x in members if x['active']}
        if (not isinstance(shared, list) or len(shared) > 32 or any(not isinstance(x, str) or x not in active for x in shared)
                or not isinstance(providers, list) or len(providers) > 40
                or any(not isinstance(x, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,80}', x) for x in providers)):
            raise CoreError('family_invalid', 'Invalid recipients')
        title, content = text(value['title'], 160), text(value['text'], 20000)
        with self.store.transaction():
            if value['id']:
                old = self.read(actor, value['id'], True)
                if old['kind'] != 'note': raise CoreError('family_invalid', 'Expected a note')
            else:
                old = {'id': 'private-' + uuid.uuid4().hex, 'owner': actor['id'], 'kind': 'note'}
            result = self.store.put({**old, 'title': title, 'text': content, 'shared': sorted(set(shared)),
                                     'providers': sorted(set(providers)), 'updated': time.time()}, value['revision'])
            self._redact_dependents(result['id'])
            return result

    def _redact_dependents(self, ident):
        # Retained responses may contain recalled material. Invalidate the entire
        # turn on any dependency change, including consent-only changes.
        for target in self.store.ids():
            row = self.store.read(target)
            if row['kind'] != 'chat': continue
            changed = False
            for turn in row['turns']:
                if any(x['id'] == ident for x in turn.get('dependencies', [])):
                    turn.update(text='', reply='', dependencies=[], status='WITHDRAWN', error='family_context_changed')
                    changed = True
            if changed: self.store.put(row, row['revision'])

    def forget(self, actor, ident, revision):
        if type(revision) is not int: raise CoreError('family_invalid', 'Invalid revision')
        with self.store.transaction():
            self.read(actor, ident, True)
            self._redact_dependents(ident)
            self.store.forget(ident, revision)
        return {'forgotten': True}

    def create_chat(self, actor, title):
        with self.store.transaction():
            return self.store.put({'id': 'private-' + uuid.uuid4().hex, 'owner': actor['id'], 'kind': 'chat',
                                   'title': text(title, 160), 'shared': [], 'providers': [], 'updated': time.time(), 'turns': []}, 0)

    def context(self, actor, ids, provider):
        if not isinstance(ids, list) or len(ids) > 8 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            raise CoreError('family_invalid', 'Choose up to 8 private notes')
        rows = []
        for ident in ids:
            row = self.read(actor, ident)
            if row['kind'] != 'note' or provider not in row['providers']:
                raise CoreError('family_destination', 'Note is not allowed for this model connection')
            rows.append(row)
        if sum(len(x['text'].encode()) for x in rows) > 12000:
            raise CoreError('family_context_size', 'Private context exceeds 12000 bytes')
        return rows
