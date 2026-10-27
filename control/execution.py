"""An OS-exclusive execution cohort with individually bound in-process permits.

Administrative/CLI executors retain RunLock. Recovery runs only before the
first cohort member, never while another member can still produce effects.
"""
import threading
from control.recovery.gate import RunLock
from sdk.protocol import CoreError


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
            permit = ExecutionPermit(self, task_id)
            self.members[task_id] = permit
            return permit

    def release(self, permit):
        with self.guard:
            if self.members.get(permit.task_id) is not permit:
                return
            del self.members[permit.task_id]
            if not self.members:
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
