"""Injected native capabilities. Plain Python never imports Blender on demand.

The fixed Blender process binds this interface once, before loading authoring
code. This dependency boundary is not an operating-system security sandbox.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BlenderAPI:
    bpy: Any
    bmesh: Any
    mathutils: Any
    bvhtree: Any
    geometry: Any
    kdtree: Any
    version: int = 1


_native = ContextVar('jarvis_blender_capabilities', default=None)


def require_blender():
    value = _native.get()
    if value is None:
        raise RuntimeError('Blender capabilities require the verified native worker bootstrap')
    return value


def bind_blender(value):
    if not isinstance(value, BlenderAPI) or value.version != 1:
        raise ValueError('Unsupported Blender capability interface')
    return _native.set(value)


@contextmanager
def using_blender(value):
    token = bind_blender(value)
    try:
        yield value
    finally:
        _native.reset(token)
