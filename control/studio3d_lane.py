"""Cooperative OS render lane shared by fixed Blender entrypoints.

This serializes trusted workers, not model knowledge or Windows permissions.
The parent's existing wall/memory limits continue to apply while waiting.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import time


@contextlib.contextmanager
def render_lane(folder, timeout=210):
    folder = Path(folder).resolve()
    # Standard Host layout: <data root>/artifacts/<registered tool>/<run>.
    artifacts = folder.parent.parent
    if artifacts.name != 'artifacts' or not folder.is_dir():
        raise ValueError('Render lane requires a Host artifact run folder')
    root = artifacts.parent
    state = root / 'state'
    if not state.is_dir():
        raise ValueError('Render lane data root is not initialized')
    started = time.monotonic()
    with (state / 'studio3d-render.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        acquired = False
        try:
            while not acquired:
                if (folder / 'cancel').exists() or (state / 'LATCH').exists() or (state / 'STOP').exists():
                    raise RuntimeError('Render cancelled while queued')
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() - started >= timeout:
                        raise TimeoutError('Shared 3D render lane wait budget exceeded')
                    time.sleep(.2)
            record = {'schema':'jarvis.studio3d.resource-lane.v1', 'pid':os.getpid(),
                      'queue_seconds':time.monotonic()-started, 'acquired_at':time.time(),
                      'scope':'cooperative fixed Blender workers; parent total deadline unchanged',
                      'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            (folder / 'resource-lane.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            try:
                yield record
            finally:
                record['released_at'] = time.time()
                (folder / 'resource-lane.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
