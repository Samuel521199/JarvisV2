"""Atomic replacement for small owned control records (not a disk snapshot)."""
import os
import uuid
from control.paths import reject_links
from sdk.protocol import canonical


def write_json(path, value):
    reject_links(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()
