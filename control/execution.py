"""An OS-exclusive execution cohort with individually bound in-process permits.

Administrative/CLI executors retain RunLock. Recovery runs only before the
first cohort member, never while another member can still produce effects.

`admission()` is for operations that admit, revise or resume work without
executing it (approve a goal, submit a tool call, create a rework draft).
They only need to exclude executors and recovery in *other* processes. While
this process's cohort holds the OS lock, recovery cannot run here or elsewhere,
so admission proceeds under its own SQLite transaction instead of failing with
``busy`` whenever background work is running.
"""
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from control.recovery.gate import RunLock
from sdk.protocol import CoreError

_LEASES = {}
_LEASES_GUARD = threading.Lock()
# Admissions in one process are serialized per data root, as RunLock did before:
# their bodies (idempotency check, grant, submit) are not one SQLite transaction.
_ADMIT = {}


def _admit_lock(root):
    key = Path(root).resolve()
    with _LEASES_GUARD:
        return _ADMIT.setdefault(key, threading.RLock())


def executor_held(root):
    """True when a cohort in this process currently owns the executor lock."""
    with _LEASES_GUARD:
        return Path(root).resolve() in _LEASES


@contextmanager
def admission(root, wait=3.0):
    """Exclude other processes' executors without blocking on our own cohort.

    Ownership is checked once at entry. If our cohort releases the OS lock while
    an admission is still running, the admission body must stay safe on its own
    (it only inserts READY work or resumes a task inside its own transaction).
    """
    guard = _admit_lock(root)
    if not guard.acquire(timeout=max(wait, 0.1)):
        raise CoreError('busy', 'Another admission is still running')
    try:
        with _admission(root, wait) as lock:
            yield lock
    finally:
        guard.release()


@contextmanager
def _admission(root, wait):
    if executor_held(root):
        yield None
        return
    deadline = time.monotonic() + wait
    while True:
        try:
            lock = RunLock(Path(root))
            lock.__enter__()
            break
        except CoreError as exc:
            if exc.code != 'busy' or time.monotonic() >= deadline:
                raise
            if executor_held(root):
                # Our own cohort started meanwhile; it now excludes other processes.
                lock = None
                break
            time.sleep(0.05)
    try:
        yield lock
    finally:
        if lock is not None:
            lock.__exit__(None, None, None)


class ExecutionCohort:
    def __init__(self, root):
        self.root = root.resolve()
        self.guard = threading.RLock()
        self.lease = None
        self.members = {}

    def acquire(self, task_id, recover):
        with self.guard:
            if task_id in self.members:
                raise CoreError('task_busy', 'Task already has an execution owner')
            if self.lease is None:
                lease = RunLock(self.root)
                lease.__enter__()
                try:
                    recover()
                except BaseException:
                    lease.__exit__(None, None, None)
                    raise
                self.lease = lease
                with _LEASES_GUARD:
                    _LEASES[self.root] = self
            permit = ExecutionPermit(self, task_id)
            self.members[task_id] = permit
            return permit

    def release(self, permit):
        with self.guard:
            if self.members.get(permit.task_id) is not permit:
                return
            del self.members[permit.task_id]
            if not self.members:
                with _LEASES_GUARD:
                    if _LEASES.get(self.root) is self:
                        del _LEASES[self.root]
                self.lease.__exit__(None, None, None)
                self.lease = None


class ExecutionPermit:
    def __init__(self, cohort, task_id):
        self.cohort, self.task_id = cohort, task_id
        self.thread = None

    def bind(self, root, task_id):
        with self.cohort.guard:
            if (root.resolve() != self.cohort.root or task_id != self.task_id
                    or self.cohort.members.get(task_id) is not self or self.thread is not None):
                raise CoreError('execution_owner', 'Execution permit is stale or already used')
            self.thread = threading.get_ident()

    def check(self, root, task_id):
        with self.cohort.guard:
            if (root.resolve() != self.cohort.root or task_id != self.task_id
                    or self.cohort.members.get(task_id) is not self
                    or self.thread != threading.get_ident()):
                raise CoreError('execution_owner', 'Task execution owner changed')

    def close(self):
        self.cohort.release(self)
