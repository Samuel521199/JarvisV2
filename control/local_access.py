"""Per-OS-user access key for the loopback workbench.

The workbench listens on 127.0.0.1. Every process on this PC, including
processes of other Windows accounts, can connect to that address, and a local
program can send any Host or Origin header it likes. Host/Origin checks and the
page nonce therefore stop hostile web pages, not hostile local programs.

This module adds the missing step when household login is not enabled:
a random access key is created once per data root and stored for the current
OS user only (DPAPI on Windows, a 0600 file elsewhere). The launcher opens the
workbench with the key in the URL fragment, which browsers never send over the
network; the page exchanges it once for an HttpOnly session cookie. Without
that cookie, data and control APIs answer 401 and the page nonce is not issued.

Residual risk (documented, not solved here): browsers do not isolate cookies by
port, so another local web server that the owner visits in the same browser
could read the session cookie. Household login has the same limitation.
"""
from __future__ import annotations

import base64
import os
import secrets
import threading
import time
from pathlib import Path

from control.atomic import write_json
from control.paths import child, data_root
from sdk.protocol import CoreError, read_json

SESSION_SECONDS = 12 * 3600
UNLOCK_ATTEMPTS_PER_MINUTE = 20
COOKIE_PREFIX = 'jarvis_local_'


def _key_path(root: Path) -> Path:
    return child(root, 'private/workbench-access.dpapi' if os.name == 'nt' else 'private/workbench-access.key')


def read_key(root) -> str | None:
    """Return the stored key for this OS user, or None when absent/unreadable."""
    path = _key_path(data_root(root))
    if not path.exists():
        return None
    try:
        if os.name == 'nt':
            from control.credentials import load_envelope
            value = load_envelope(path).get('key')
        else:
            value = path.read_text(encoding='ascii').strip()
    except (OSError, ValueError, CoreError):
        return None
    return value if isinstance(value, str) and 32 <= len(value) <= 128 else None


def load_or_create_key(root) -> str:
    existing = read_key(root)
    if existing:
        return existing
    root = data_root(root)
    path = _key_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    if os.name == 'nt':
        from control.credentials import crypt
        write_json(path, {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                          'payload': base64.b64encode(crypt(('{"key":"' + key + '"}').encode())).decode('ascii')})
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(key)
    return key


def cookie_name(port) -> str:
    return COOKIE_PREFIX + str(int(port))


def cookie_get(header, name) -> str:
    """Return one cookie by exact name.

    Parsed by hand: browsers send every 127.0.0.1 cookie to every port, and
    SimpleCookie.load stops at the first value it cannot parse (for example a
    JSON cookie set by another local dev server), which would lock the owner out.
    """
    if not isinstance(header, str):
        return ''
    for part in header.split(';'):
        key, sep, value = part.strip().partition('=')
        if sep and key.strip() == name:
            return value.strip().strip('"')
    return ''


def cookie_value(header, port) -> str:
    return cookie_get(header, cookie_name(port))


class LocalAccess:
    """Exchange the access key for short-lived, in-memory browser sessions."""

    def __init__(self, root, key: str | None = None):
        self.key = key or load_or_create_key(root)
        self.lock = threading.Lock()
        self.sessions: dict[str, float] = {}
        self.attempts: list[float] = []

    def unlock(self, candidate) -> str:
        now = time.monotonic()
        with self.lock:
            self.attempts = [t for t in self.attempts if now - t < 60]
            if len(self.attempts) >= UNLOCK_ATTEMPTS_PER_MINUTE:
                raise CoreError('local_access_rate', 'Too many access attempts; wait a minute')
            self.attempts.append(now)
            if not isinstance(candidate, str) or not candidate.isascii() or not secrets.compare_digest(candidate, self.key):
                raise CoreError('local_access', 'Open the workbench from StartJarvis or the link printed in its window')
            self.sessions = {k: v for k, v in self.sessions.items() if v > now}
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + SESSION_SECONDS
            return token

    def valid(self, token) -> bool:
        """Check a session; use extends it (sliding 12 h), so an open page is not cut off mid-day."""
        if not token or not isinstance(token, str):
            return False
        with self.lock:
            expires = self.sessions.get(token)
            if expires is None:
                return False
            now = time.monotonic()
            if expires <= now:
                del self.sessions[token]
                return False
            self.sessions[token] = now + SESSION_SECONDS
            return True


def install_client(origin, data_root_path=None):
    """Let local evaluation tools (urllib-based) reach a key-protected workbench.

    Reads this OS user's key for the data root (default: <project>/user-data, or
    JARVIS_DATA_ROOT), exchanges it for a session cookie and installs a global
    urllib opener that sends it. Servers without a key are left untouched.
    """
    import http.cookiejar
    import json
    import urllib.request
    root = Path(data_root_path or os.environ.get('JARVIS_DATA_ROOT') or Path(__file__).resolve().parents[1] / 'user-data')
    try:
        key = read_key(root)
    except CoreError:
        key = None
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    if key:
        request = urllib.request.Request(origin.rstrip('/') + '/api/local-access', data=json.dumps({'key': key}).encode(),
                                         headers={'Origin': origin.rstrip('/'), 'Content-Type': 'application/json'}, method='POST')
        try:
            opener.open(request, timeout=10).read()
        except OSError:
            pass  # older server without access keys, or wrong data root: the next request reports it
    urllib.request.install_opener(opener)
    return bool(key)
