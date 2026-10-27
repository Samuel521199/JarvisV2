"""One default responsible Bot and bounded immutable goal-version links; no executor."""
import time
from adapters.storage.work_schema import ensure, ensure_recoveries
from modules.task_resource.work_budgets import WorkBudgets
from sdk.protocol import CoreError, canonical, decode, digest


class Works:
    def __init__(self, db):
        self.db = db; ensure(db);ensure_recoveries(db)

    def owner(self, ident):
        return self.db.one('''SELECT w.* FROM work_owners w JOIN work_revisions r
            ON r.root_goal=w.root_goal WHERE r.goal_id=?''', (ident,))

    def link(self, ident):
        return self.db.one('SELECT * FROM work_revisions WHERE goal_id=?', (ident,))

    def recovery(self, ident):
        row=self.db.one('SELECT * FROM work_recoveries WHERE goal_id=?',(ident,))
        if not row:return None
        body=decode(row['body'])
        if digest(body)!=row['digest']:raise CoreError('rework_source_changed','Recovery checkpoint integrity changed')
        return body

    def save_recovery(self, ident, body, tx):
        tx.execute('INSERT INTO work_recoveries VALUES(?,?,?)',(ident,canonical(body),digest(body)))

    def has_recovery(self, ident):
        return bool(self.db.one('''SELECT 1 FROM work_revisions r JOIN work_revisions current
            ON r.root_goal=current.root_goal WHERE current.goal_id=? AND r.ordinal<=current.ordinal
            AND r.kind='recovery' LIMIT 1''',(ident,)))

    def register(self, ident, assistant_id, tx, registration='admission'):
        if self.owner(ident): return
        tx.execute('INSERT INTO work_owners VALUES(?,?,?,?,1,0,?,?)',
                   (ident, ident, assistant_id, 'default', registration, time.time()))
        tx.execute("INSERT INTO work_revisions VALUES(?,?,1,NULL,'original','',1,NULL,NULL,NULL)", (ident, ident))
        self.db.event(tx, None, 'work.registered', {'goal_id':ident, 'assistant_id':assistant_id, 'registration':registration})

    def append(self, parent, ident, revision, kind, note, start, source, request_id, request_digest, tx):
        owner = self.owner(parent)
        old = self.link(parent)
        if not owner or owner['cancelled'] or owner['current_goal'] != parent or owner['revision'] != revision:
            raise CoreError('work_conflict', 'The current work version changed or was cancelled')
        if old['ordinal'] >= 4: raise CoreError('work_limit', 'At most three reviewed follow-ups per work')
        changed = tx.execute('''UPDATE work_owners SET current_goal=?,revision=revision+1
            WHERE root_goal=? AND current_goal=? AND revision=? AND cancelled=0''',
            (ident, owner['root_goal'], parent, revision)).rowcount
        if changed != 1: raise CoreError('work_conflict', 'Work changed')
        tx.execute('INSERT INTO work_revisions VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (ident, owner['root_goal'], old['ordinal']+1, parent, kind, note, start, source, request_id, request_digest))
        self.db.event(tx, None, 'work.revision_created', {'root_goal':owner['root_goal'], 'goal_id':ident,
                      'parent_goal':parent, 'kind':kind, 'start_step':start, 'revision':revision+1})

    def projection(self, ident):
        owner = self.owner(ident)
        if not owner: return None
        rows = self.db.all('''SELECT r.goal_id,r.ordinal,r.parent_goal,r.kind,r.note,r.start_step,
            p.task_id,p.status,p.cancel,t.status AS task_status,COALESCE(t.spent,0) AS spent
            FROM work_revisions r JOIN goal_plans p ON p.id=r.goal_id LEFT JOIN tasks t ON t.id=p.task_id
            WHERE r.root_goal=? ORDER BY r.ordinal''', (owner['root_goal'],))
        budget=WorkBudgets(self.db).projection(ident)
        return {**owner, 'schema':'jarvis.work.v1', 'ownership_mode':'default_projection',
                'versions':rows, 'spent_cost_units':sum(r['spent'] for r in rows),
                'remaining_followups':4-len(rows), 'cumulative_budget_enforced':budget['enforced'],'budget':budget}
