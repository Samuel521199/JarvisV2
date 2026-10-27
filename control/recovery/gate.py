from __future__ import annotations

import os
import uuid
from pathlib import Path

from control.paths import child
from sdk.protocol import CoreError


class StopGate:
    def __init__(self, root: Path):
        self.root = root

    def state(self):
        if child(self.root, "state/LATCH").exists():
            return "latched"
        if child(self.root, "state/STOP").exists():
            return "stopped"
        return "ready"

    def require_running(self):
        if self.state() != "ready":
            raise CoreError("stopped", "Actions are stopped; no automatic restart")

    def stop(self, *, latch=False):
        name = "LATCH" if latch else "STOP"
        target = child(self.root, f"state/{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create: a concurrent stop cannot silently replace its generation.
        try:
            with target.open("x", encoding="ascii") as stream:
                stream.write(uuid.uuid4().hex)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        return self.state()

    def token(self):
        target = child(self.root, "state/STOP")
        return target.read_text(encoding="ascii") if target.exists() else None

    def resume(self, expected_token: str):
        if self.state() == "latched":
            raise CoreError("latched", "Latch release is not implemented; keep this instance stopped")
        if not expected_token or expected_token != self.token():
            raise CoreError("conflict", "Stop generation changed")
        child(self.root, "state/STOP").unlink()


class RunLock:
    """One executor per data root. OS releases the lock on process death."""
    def __init__(self, root: Path, lane="executor"):
        if lane not in {"executor", "development", "dialogue", "planning", "local-models", "image-generation", "mail", "task-runner"}:
            raise CoreError("invalid_lock", "Unknown runtime lock lane")
        self.path = child(root, "state/" + lane + ".lock")
        self.stream = None

    def __enter__(self):
        self.stream = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise CoreError("busy", "Another executor is active") from exc
        return self

    def __exit__(self, *_):
        if self.stream:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            self.stream.close()
