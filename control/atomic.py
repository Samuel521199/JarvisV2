"""Atomic replacement for small owned control records (not a disk snapshot)."""
import os
import time
import uuid
from control.paths import reject_links
from sdk.protocol import canonical


def replace_control_file(temporary, path):
    # Windows readers can briefly deny delete-sharing even for a tiny
    # control record. Retry the same atomic replacement, never truncate it.
    delays=(0.01,0.02,0.04,0.08,0.16,0.32,None)
    for delay in delays:
        try:
            os.replace(temporary,path)
            return
        except PermissionError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in {5,32,33} or delay is None:
                raise
            time.sleep(delay)


def write_json(path, value):
    reject_links(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        replace_control_file(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()
