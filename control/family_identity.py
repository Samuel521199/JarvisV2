"""Opt-in local household authentication; identity is never supplied by a model."""
import base64
import hashlib
from http.cookies import SimpleCookie
import re
import secrets
import threading
import time

from control.atomic import write_json
from control.credentials import crypt, load_envelope
from control.paths import child, data_root
from sdk.protocol import CoreError, canonical

POLICY = 'owner_all_member_own_and_explicit_shared_v1'
ITERATIONS = 600000


def password_record(password, salt=None):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise CoreError('family_password', 'Use a password of 12 to 256 characters')
    salt = salt or secrets.token_hex(16)
    return {'salt': salt, 'hash': hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()}


def identity(value):
    if not isinstance(value, str) or not re.fullmatch('[a-z][a-z0-9_-]{0,31}', value):
        raise CoreError('family_invalid', 'Invalid member identifier')
    return value


class FamilyIdentity:
    def __init__(self, root):
        self.path = child(data_root(root), 'private/family-identity.dpapi')
        self.lock = threading.RLock()
        self.sessions = {}
        self.attempts = []
        self.hash_slots = threading.BoundedSemaphore(2)
        self.enabled = self.path.exists()
        self.data = load_envelope(self.path) if self.enabled else {'schema': 1, 'policy': POLICY, 'members': {}}
        if self.data.get('schema') != 1 or self.data.get('policy') != POLICY or (self.enabled and self.data.get('members', {}).get('owner', {}).get('role') != 'owner'):
            raise CoreError('family_unavailable', 'Household identity state is invalid')

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.path, {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                              'payload': base64.b64encode(crypt(canonical(data).encode())).decode('ascii')})
        self.data = data
        self.enabled = True

    def setup(self, password):
        record = password_record(password)
        with self.lock:
            if self.enabled: raise CoreError('conflict', 'Household authentication is already enabled')
            self._save({'schema': 1, 'policy': POLICY, 'members': {'owner': {'name': '主人', 'role': 'owner', 'active': True, **record}}})
            return self._session('owner')

    def _session(self, ident):
        now = time.monotonic()
        self.sessions = {key: value for key, value in self.sessions.items() if value['expires'] > now and value['absolute'] > now}
        if len(self.sessions) >= 100: raise CoreError('family_capacity', 'Too many login sessions')
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {'id': ident, 'expires': now + 1800, 'absolute': now + 28800}
        return token

    def login(self, ident, password):
        if not isinstance(ident, str) or len(ident) > 32 or not isinstance(password, str) or len(password) > 256:
            raise CoreError('family_login', 'Login failed')
        if not self.hash_slots.acquire(blocking=False): raise CoreError('family_rate', 'Login rate limited')
        try:
            with self.lock:
                now = time.monotonic()
                self.attempts = [x for x in self.attempts if x > now - 60]
                if len(self.attempts) >= 10: raise CoreError('family_rate', 'Login rate limited')
                self.attempts.append(now)
                record = dict(self.data['members'].get(ident, {}))
            value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(record.get('salt', '00'*16)), ITERATIONS).hex()
            with self.lock:
                if (not record.get('active') or not secrets.compare_digest(value, record.get('hash', ''))
                        or record != self.data['members'].get(ident)):
                    raise CoreError('family_login', 'Login failed')
                return self._session(ident)
        finally: self.hash_slots.release()

    def principal(self, token, *, touch=True):
        with self.lock:
            row = self.sessions.get(token)
            now = time.monotonic()
            if not row or row['expires'] <= now or row['absolute'] <= now:
                self.sessions.pop(token, None)
                return None
            member = self.data['members'].get(row['id'], {})
            if not member.get('active'): return None
            if touch: row['expires'] = now + 1800
            return {'id': row['id'], 'name': member['name'], 'role': member['role']}

    def logout(self, token):
        with self.lock: self.sessions.pop(token, None)

    def members(self):
        with self.lock:
            return [{'id': key, **{k: value[k] for k in ('name', 'role', 'active')}} for key, value in self.data['members'].items()]

    def manage(self, actor, value):
        if actor['role'] != 'owner': raise CoreError('family_forbidden', 'Owner required')
        if not isinstance(value, dict) or set(value) != {'id', 'name', 'active', 'password'}:
            raise CoreError('family_invalid', 'Invalid member fields')
        ident = identity(value['id'])
        if ident == 'owner' or not isinstance(value['name'], str) or not 1 <= len(value['name'].strip()) <= 80 or type(value['active']) is not bool or not isinstance(value['password'], str):
            raise CoreError('family_invalid', 'Invalid member')
        record = password_record(value['password']) if value['password'] else None
        with self.lock:
            data = {**self.data, 'members': {k: dict(v) for k, v in self.data['members'].items()}}
            if ident not in data['members'] and (record is None or len(data['members']) >= 32):
                raise CoreError('family_invalid', 'A new member requires a password; maximum 32 members')
            data['members'][ident] = {**data['members'].get(ident, {}), **(record or {}), 'role': 'member', 'name': value['name'].strip(), 'active': value['active']}
            self._save(data)
            self.sessions = {k: v for k, v in self.sessions.items() if v['id'] != ident}
            return {'ok': True}

    def change_password(self, actor, current, password):
        replacement = password_record(password)
        with self.lock: old = dict(self.data['members'][actor['id']])
        if not isinstance(current, str) or len(current) > 256:
            raise CoreError('family_login', 'Current password required')
        checked = hashlib.pbkdf2_hmac('sha256', current.encode(), bytes.fromhex(old['salt']), ITERATIONS).hex()
        with self.lock:
            if not secrets.compare_digest(checked, old['hash']) or old != self.data['members'][actor['id']]:
                raise CoreError('family_login', 'Current password required')
            data = {**self.data, 'members': {k: dict(v) for k, v in self.data['members'].items()}}
            data['members'][actor['id']].update(replacement)
            self._save(data)
            self.sessions = {k: v for k, v in self.sessions.items() if v['id'] != actor['id']}
            return {'ok': True}


def cookie_token(header, port):
    try:
        cookie = SimpleCookie(); cookie.load(header or '')
        item = cookie.get('jarvis_family_' + str(port))
        return item.value if item else ''
    except (ValueError, TypeError): return ''
