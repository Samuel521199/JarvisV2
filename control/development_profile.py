"""Cooperative development profile; directory separation is not an OS sandbox."""
import base64
from contextlib import contextmanager
import os
import re

from control.atomic import write_json
from control.credentials import crypt, load_envelope
from control.paths import child
from sdk.protocol import CoreError, canonical, read_json


def read(root):
    path = child(root, 'config/development.json')
    if not path.exists():
        return None
    value = read_json(path)
    if (not isinstance(value, dict) or value.get('schema') != 1
            or value.get('kind') != 'development'
            or value.get('external_actions') is not False
            or not isinstance(value.get('client_id'), str)
            or not re.fullmatch(r'[a-f0-9]{32}', value.get('client_id', ''))
            or not isinstance(value.get('bridge_origin'), str)
            or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}', value.get('bridge_origin', ''))
            or not 1024 <= int(value['bridge_origin'].rsplit(':', 1)[1]) <= 65535
            or not isinstance(value.get('allowed_providers'), list)
            or not 1 <= len(value['allowed_providers']) <= 16
            or any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name)
                   for name in value['allowed_providers'])):
        raise CoreError('development_profile_invalid', 'Development profile is invalid; access remains closed')
    return value


def write_secret(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                      'payload': base64.b64encode(crypt(canonical(value).encode())).decode('ascii')})


def client_secret(root):
    return load_envelope(child(root, 'private/development-bridge.dpapi'))


def deny_external(root):
    if read(root):
        raise CoreError('development_external_denied', 'Development uses the shared model proxy; direct external actions are disabled')


@contextmanager
def bridge_lease(root):
    path = child(root, 'development/bridge.instance.lock')
    path.parent.mkdir(exist_ok=True)
    stream = path.open('a+b')
    locked = False
    try:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise CoreError('development_bridge_busy', 'One shared development model service is already active') from None
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()
