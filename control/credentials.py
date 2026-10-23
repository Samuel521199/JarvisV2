"""Current-user Windows DPAPI envelopes; no plaintext credential files."""
import base64
import ctypes
from ctypes import wintypes
import os

from control.atomic import write_json
from control.paths import child, reject_links
from sdk.protocol import CoreError, decode, canonical, read_json


def crypt(raw, *, decrypt=False):
    if os.name != 'nt':
        raise CoreError('vault_platform', 'Windows DPAPI is required for this credential store')
    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    source = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    incoming, outgoing = Blob(len(raw), source), Blob()
    dll = ctypes.WinDLL('crypt32', use_last_error=True)
    free = ctypes.WinDLL('kernel32').LocalFree
    free.argtypes = [ctypes.c_void_p]; free.restype = ctypes.c_void_p
    fn = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    try:
        if not fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
            raise CoreError('vault_unavailable', 'Credential decryption/encryption failed for this OS user')
        return ctypes.string_at(outgoing.data, outgoing.length)
    finally:
        ctypes.memset(source, 0, len(raw))
        if outgoing.data:
            ctypes.memset(outgoing.data, 0, outgoing.length); free(outgoing.data)


def load_envelope(path):
    reject_links(path)
    try:
        box = read_json(path)
        if set(box) != {'schema_version', 'format', 'payload'} or box['schema_version'] != 1 or box['format'] != 'windows-dpapi-current-user':
            raise ValueError()
        result = decode(crypt(base64.b64decode(box['payload'], validate=True), decrypt=True))
        if not isinstance(result, dict): raise ValueError()
        return result
    except (OSError, ValueError, TypeError, CoreError):
        raise CoreError('vault_unavailable', 'Local credential store is unavailable; it was not replaced') from None


class Credentials:
    def __init__(self, root):
        self.path = child(root, 'private/model-credentials.dpapi')

    def get(self, connection, key_id=None):
        data = load_envelope(self.path)
        if key_id:
            item = data.get('_managed', {}).get(key_id, {})
            if item.get('connection') != connection:
                raise CoreError('credential_binding', 'Credential is not bound to this provider')
            value = item.get('credential')
        else:
            value = data.get(connection)
        if not isinstance(value, dict) or not value:
            raise CoreError('credential_missing', 'Provider credential is not configured')
        return value

    def available(self, connection, key_id=None):
        try: return bool(self.get(connection, key_id))
        except CoreError: return False

    def put(self, connection, key_id, credential):
        data = load_envelope(self.path) if self.path.exists() else {}
        data.setdefault('_managed', {})[key_id] = {'connection': connection, 'credential': credential}
        self.save(data)

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.path, {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                              'payload': base64.b64encode(crypt(canonical(data).encode())).decode('ascii')})
