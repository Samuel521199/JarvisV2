"""Durable module recovery waits for previously requested tasks, with bounded wakes."""
import time
from sdk.protocol import CoreError,decode


class Waiting:
    def __init__(self,db):
        self.db=db
        if db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='task_waits'"):return
        with db.transaction() as tx:
            tx.execute('''CREATE TABLE IF NOT EXISTS task_waits(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
                task_revision INTEGER NOT NULL,source_watermark INTEGER NOT NULL,state TEXT NOT NULL,
                reason TEXT NOT NULL,deadline REAL NOT NULL,wake_count INTEGER NOT NULL,checked REAL NOT NULL)''')

    def advance(self, check, enqueue):
        with self.db.transaction() as tx:
            # Reconcile from original state as well as events: recovery may precede registration.
            rows=self.db.all('''SELECT t.* FROM tasks t JOIN task_dispatch d ON d.task_id=t.id
                LEFT JOIN task_waits w ON w.task_id=t.id
                WHERE t.status='WAITING' AND t.error='module_disabled' AND d.requested=0 AND d.started_at IS NOT NULL
                AND (w.task_id IS NULL OR w.task_revision<>t.revision)
                ORDER BY t.created LIMIT 32''')
            watermark=tx.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            for task in rows:
                old=self.db.one('SELECT * FROM task_waits WHERE task_id=?',(task['id'],))
                if old and old['wake_count']>=3:
                    tx.execute("UPDATE task_waits SET state='BLOCKED',reason='wake_budget',task_revision=? WHERE task_id=?",(task['revision'],task['id']))
                    continue
                if old and old['task_revision']==task['revision']:continue
                tx.execute('''INSERT INTO task_waits VALUES(?,?,?,'WAITING','module_disabled',?,0,0)
                    ON CONFLICT(task_id) DO UPDATE SET task_revision=excluded.task_revision,
                    source_watermark=excluded.source_watermark,state='WAITING',reason='module_disabled' ''',
                    (task['id'],task['revision'],watermark,task['deadline']))
            rows=self.db.all("SELECT * FROM task_waits WHERE state='WAITING' ORDER BY checked LIMIT 4")
            for wait in rows:
                task=self.db.one('SELECT * FROM tasks WHERE id=?',(wait['task_id'],))
                state,reason='WAITING','module_disabled'
                if task['cancel'] or task['status']=='CANCELLED':state,reason='CANCELLED','cancelled'
                elif task['deadline']<=time.time():state,reason='EXPIRED','deadline'
                elif task['status']!='WAITING' or task['revision']!=wait['task_revision']:state,reason='SUPERSEDED','task_changed'
                elif self.db.one("SELECT 1 FROM actions WHERE task_id=? AND status IN ('UNKNOWN','DISPATCHING')",(task['id'],)):state,reason='BLOCKED','unknown_effect'
                elif wait['wake_count']>=3:state,reason='BLOCKED','wake_budget'
                else:
                    try:
                        check(task,tx)
                        enqueue([task['id']],transaction=tx)
                        state,reason='QUEUED','module_ready'
                        self.db.event(tx,task['id'],'wait.resumed',{'task_revision':wait['task_revision'],'source_watermark':wait['source_watermark']})
                    except CoreError as exc:
                        reason=exc.code
                        if reason not in {'module_disabled','stopped','task_capacity'}:state='BLOCKED'
                tx.execute('UPDATE task_waits SET state=?,reason=?,checked=?,wake_count=wake_count+? WHERE task_id=?',
                           (state,reason,time.time(),int(state=='QUEUED'),task['id']))
