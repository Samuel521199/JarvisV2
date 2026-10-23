"""Ephemeral PKCS#8 signing with Windows CNG, not Python RSA arithmetic."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import os
import re


def sign_rs256(pem, message):
    if os.name != 'nt': raise ValueError('signing_platform')
    match = re.fullmatch(r'\s*-----BEGIN PRIVATE KEY-----\s+([A-Za-z0-9+/=\s]+)-----END PRIVATE KEY-----\s*', pem)
    if not match: raise ValueError('key_format')
    raw = base64.b64decode(''.join(match[1].split()), validate=True)
    if not 512 <= len(raw) <= 16384: raise ValueError('key_size')
    dll = ctypes.WinDLL('ncrypt')
    handle = ctypes.c_size_t
    pointer = ctypes.c_void_p
    signatures = {
        'NCryptOpenStorageProvider': ([ctypes.POINTER(handle), wintypes.LPCWSTR, wintypes.DWORD],),
        'NCryptImportKey': ([handle, handle, wintypes.LPCWSTR, pointer, ctypes.POINTER(handle), pointer, wintypes.DWORD, wintypes.DWORD],),
        'NCryptSignHash': ([handle, pointer, pointer, wintypes.DWORD, pointer, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD],),
        'NCryptFreeObject': ([handle],)}
    for name, (args,) in signatures.items():
        fn = getattr(dll, name); fn.argtypes = args; fn.restype = wintypes.LONG
    class Padding(ctypes.Structure): _fields_ = [('algorithm', wintypes.LPCWSTR)]
    provider, key = handle(), handle()
    storage = ctypes.create_string_buffer(raw)
    hashed = ctypes.create_string_buffer(hashlib.sha256(message).digest())
    padding = Padding('SHA256'); needed = wintypes.DWORD()
    def check(code):
        if code != 0: raise ValueError('signing_failed')
    try:
        check(dll.NCryptOpenStorageProvider(ctypes.byref(provider), 'Microsoft Software Key Storage Provider', 0))
        # No key name: CNG treats the imported key as ephemeral, without disk persistence.
        check(dll.NCryptImportKey(provider, 0, 'PKCS8_PRIVATEKEY', None, ctypes.byref(key), storage, len(raw), 0x40))
        check(dll.NCryptSignHash(key, ctypes.byref(padding), hashed, 32, None, 0, ctypes.byref(needed), 2 | 0x40))
        if not 128 <= needed.value <= 2048: raise ValueError('signature_size')
        output = ctypes.create_string_buffer(needed.value)
        check(dll.NCryptSignHash(key, ctypes.byref(padding), hashed, 32, output, len(output), ctypes.byref(needed), 2 | 0x40))
        return output.raw[:needed.value]
    finally:
        ctypes.memset(storage, 0, len(storage))
        if key.value: dll.NCryptFreeObject(key)
        if provider.value: dll.NCryptFreeObject(provider)
