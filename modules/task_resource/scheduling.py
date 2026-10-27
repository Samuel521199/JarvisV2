"""Durable dispatch intent and priority metadata attached to original task IDs."""
import time
from contextlib import nullcontext
from sdk.protocol import CoreError, canonical, decode

DEFAULTS = {'max_workers': 2, 'queue_limit': 32, 'memory_reserve_mib': 2048,
            'cpu_ceiling': 80, 'revision': 1}
TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELLED'}
INTENT_LIMIT = 100  # Includes runnable and capacity-waiting intents; no unbounded backlog.


class Scheduling:
    def __init__(self, db):
        self.db = db
        if db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='task_dispatch'"):
            return
        with db.transaction() as tx:
            tx.execute('''CREATE TABLE IF NOT EXISTS task_dispatch(
                task_id TEXT PRIMARY KEY REFERENCES tasks(id), requested INTEGER NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 1, importance INTEGER NOT NULL DEFAULT 1,
                due_at REAL, reason TEXT NOT NULL DEFAULT '普通优先级', revision INTEGER NOT NULL DEFAULT 1,
                queued_at REAL NOT NULL, started_at REAL, finished_at REAL, wait_reason TEXT)''')
            tx.execute("INSERT OR IGNORE INTO meta VALUES('scheduler_policy',?)", (canonical(DEFAULTS),))

    def policy(self):
        row = self.db.one("SELECT value FROM meta WHERE key='scheduler_policy'")
        return decode(row['value'])

    def configure(self, value):
        if not isinstance(value, dict) or set(value) != set(DEFAULTS):
            raise CoreError('scheduler_invalid', 'Expected bounded scheduling settings')
        bounds = {'max_workers': (1, 4), 'queue_limit': (4, 100),
                  'memory_reserve_mib': (1024, 32768), 'cpu_ceiling': (30, 90), 'revision': (1, 2**31)}
        if any(type(value[k]) is not int or not low <= value[k] <= high for k, (low, high) in bounds.items()):
            raise CoreError('scheduler_invalid', 'Scheduling setting exceeds supported bounds')
        with self.db.transaction() as tx:
            current = self.policy()
            if value['revision'] != current['revision']:
                raise CoreError('conflict', 'Scheduling configuration changed')
            updated = {**value, 'revision': value['revision'] + 1}
            tx.execute("UPDATE meta SET value=? WHERE key='scheduler_policy'", (canonical(updated),))
        return updated

    def enqueue(self, task_ids, *, transaction=None):
        now = time.time()
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            pending = tx.execute('SELECT COUNT(*) FROM task_dispatch WHERE requested=1').fetchone()[0]
            new = [i for i in dict.fromkeys(task_ids) if not tx.execute('SELECT 1 FROM task_dispatch WHERE task_id=? AND requested=1', (i,)).fetchone()]
            if pending + len(new) > self.policy()['queue_limit']:
                raise CoreError('task_capacity', 'Dispatch queue is full; tasks remain in the ledger')
            for ident in new:
                row = tx.execute('SELECT status,cancel FROM tasks WHERE id=?', (ident,)).fetchone()
                if not row or row['status'] not in {'READY', 'WAITING'} or row['cancel']:
                    raise CoreError('invalid_state', 'Task is not dispatchable')
                if tx.execute("SELECT 1 FROM actions WHERE task_id=? AND status='UNKNOWN'", (ident,)).fetchone():
                    raise CoreError('unknown_effect', 'Reconcile the original task first')
                tx.execute('''INSERT INTO task_dispatch(task_id,requested,queued_at) VALUES(?,1,?)
                    ON CONFLICT(task_id) DO UPDATE SET requested=1,queued_at=excluded.queued_at,
                    started_at=NULL,finished_at=NULL,wait_reason=NULL''', (ident, now))
                self.db.event(tx, ident, 'scheduler.queued', {})
        return {'accepted': new, 'existing': [i for i in task_ids if i not in new]}

    def request_execution(self, task_id, *, transaction):
        """Atomically attach an execution intent to goal admission.

        requested=2 is bounded capacity waiting in this same dispatch ledger.
        Only requested=1 can be dispatched; promotion never bypasses enqueue.
        """
        tx = transaction
        old = tx.execute('SELECT requested FROM task_dispatch WHERE task_id=?', (task_id,)).fetchone()
        if old and old['requested']:
            return self.intent(task_id)
        count = tx.execute('SELECT COUNT(*) FROM task_dispatch WHERE requested IN (1,2)').fetchone()[0]
        if count >= INTENT_LIMIT:
            raise CoreError('task_capacity', 'Execution intent limit reached; goal admission was not committed')
        row = tx.execute('SELECT status,cancel FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row or row['status'] != 'READY' or row['cancel']:
            raise CoreError('invalid_state', 'Only a ready goal can request initial execution')
        tx.execute('''INSERT INTO task_dispatch(task_id,requested,queued_at,wait_reason) VALUES(?,2,?,?)
            ON CONFLICT(task_id) DO UPDATE SET requested=2,queued_at=excluded.queued_at,
            started_at=NULL,finished_at=NULL,wait_reason=excluded.wait_reason''',
            (task_id, time.time(), '等待队列容量'))
        self.db.event(tx, task_id, 'scheduler.execution_requested', {})
        try:
            self.enqueue([task_id], transaction=tx)
        except CoreError as exc:
            if exc.code != 'task_capacity':
                raise
        return self.intent(task_id)

    def intent(self, task_id):
        row = self.db.one('SELECT requested,wait_reason FROM task_dispatch WHERE task_id=?', (task_id,))
        return {'state': 'WAITING_CAPACITY' if row and row['requested'] == 2 else
                'QUEUED' if row and row['requested'] == 1 else 'NOT_PENDING',
                'reason': row['wait_reason'] if row else None}

    def admit_waiting(self):
        """Called by the existing runner; cancelled/expired intents never revive."""
        with self.db.transaction() as tx:
            rows = tx.execute('''SELECT d.task_id,t.status,t.cancel,t.deadline FROM task_dispatch d
                JOIN tasks t ON t.id=d.task_id WHERE d.requested=2 ORDER BY d.queued_at,d.task_id LIMIT 100''').fetchall()
            for row in rows:
                if row['cancel'] or row['status'] in TERMINAL or row['deadline'] <= time.time():
                    tx.execute('UPDATE task_dispatch SET requested=0,finished_at=?,wait_reason=? WHERE task_id=?',
                               (time.time(), 'cancelled' if row['cancel'] else 'deadline' if row['deadline'] <= time.time() else 'finished', row['task_id']))
                    continue
                try:
                    self.enqueue([row['task_id']], transaction=tx)
                except CoreError as exc:
                    if exc.code == 'task_capacity':
                        continue
                    tx.execute('UPDATE task_dispatch SET requested=0,finished_at=?,wait_reason=? WHERE task_id=?',
                               (time.time(), exc.code, row['task_id']))

    def prioritize(self, value):
        required = {'id', 'revision', 'priority', 'importance', 'due_at', 'reason'}
        if not isinstance(value, dict) or set(value) != required:
            raise CoreError('scheduler_invalid', 'Expected task priority and revision')
        if (type(value['revision']) is not int or value['revision'] < 0
                or any(type(value[k]) is not int or not 0 <= value[k] <= 3 for k in ('priority', 'importance'))
                or not isinstance(value['reason'], str) or not 1 <= len(value['reason'].strip()) <= 200
                or value['due_at'] is not None and (type(value['due_at']) not in (int, float)
                    or not 0 < value['due_at'] < 32503680000)):
            raise CoreError('scheduler_invalid', 'Invalid priority, due date or explanation')
        with self.db.transaction() as tx:
            task = tx.execute('SELECT status FROM tasks WHERE id=?', (value['id'],)).fetchone()
            if not task or task['status'] in TERMINAL:
                raise CoreError('invalid_state', 'Only unfinished work can be prioritized')
            old = tx.execute('SELECT revision FROM task_dispatch WHERE task_id=?', (value['id'],)).fetchone()
            revision = old['revision'] if old else 0
            if value['revision'] != revision:
                raise CoreError('conflict', 'Task priority changed')
            tx.execute('''INSERT INTO task_dispatch(task_id,priority,importance,due_at,reason,revision,queued_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET priority=excluded.priority,
                importance=excluded.importance,due_at=excluded.due_at,reason=excluded.reason,revision=excluded.revision''',
                (value['id'], value['priority'], value['importance'], value['due_at'], value['reason'].strip(), revision+1, time.time()))
            self.db.event(tx, value['id'], 'scheduler.priority', {k: value[k] for k in required - {'id'}})
        return {'id': value['id'], 'revision': revision+1}

    def pending(self):
        rows = self.db.all('''SELECT d.*,t.status,t.cancel,t.deadline,t.body FROM task_dispatch d
            JOIN tasks t ON t.id=d.task_id WHERE d.requested=1''')
        now = time.time()
        # Explicit class first; ageing eventually gives ordinary tasks a turn.
        def rank(row):
            age = min(24, int(max(0, now-row['queued_at']) / 60))
            due = row['due_at']
            urgency = 2 if due and due-now < 300 else 1 if due and due-now < 3600 else 0
            return (-(row['priority']*4 + row['importance'] + urgency + age), due or float('inf'), row['queued_at'], row['task_id'])
        return sorted(rows, key=rank)

    def mark(self, ident, *, started=False, finished=False, reason=None):
        with self.db.transaction() as tx:
            if started:
                tx.execute('UPDATE task_dispatch SET started_at=?,wait_reason=NULL WHERE task_id=?', (time.time(), ident))
            elif finished:
                tx.execute('UPDATE task_dispatch SET requested=0,finished_at=?,wait_reason=? WHERE task_id=?', (time.time(), reason, ident))
            else:
                tx.execute('UPDATE task_dispatch SET wait_reason=? WHERE task_id=? AND wait_reason IS NOT ?', (reason, ident, reason))

    def rows(self):
        return self.db.all('SELECT * FROM task_dispatch ORDER BY queued_at DESC LIMIT 100')


def resources(body):
    """Conservative conflict classes until an adapter proves narrower effects."""
    caps = [step['capability'] for step in body['steps']]
    conflicts = set()
    if any(c.startswith('plugin.') for c in caps):
        conflicts.add('restricted-runtime-acl')
    if any(c.startswith('mcp.') for c in caps):
        # Remote annotations cannot prove independent file/device side effects.
        conflicts.add('external-effects')
    return {'memory_mib': 256 if 'restricted-runtime-acl' in conflicts else 96 if conflicts else 32,
            'conflicts': conflicts}
