"""Shared action-unit constraints; spending facts stay exclusively in the original Ledger."""
import re
import time
from adapters.storage.work_schema import ensure
from sdk.protocol import CoreError, canonical, decode, digest


class WorkBudgets:
    def __init__(self, db):self.db=db;ensure(db)

    def owner(self, goal):
        return self.db.one('''SELECT w.* FROM work_owners w JOIN work_revisions r
            ON r.root_goal=w.root_goal WHERE r.goal_id=?''',(goal,))

    def rows(self, root):
        return self.db.all('''SELECT t.id,t.body,t.spent,t.status,t.cancel,a.units,
            EXISTS(SELECT 1 FROM actions x WHERE x.task_id=t.id AND x.status IN ('UNKNOWN','DISPATCHING')) AS unresolved
            FROM work_revisions r JOIN goal_plans p ON p.id=r.goal_id JOIN tasks t ON t.id=p.task_id
            LEFT JOIN work_allocations a ON a.task_id=t.id WHERE r.root_goal=? ORDER BY r.ordinal''',(root,))

    @staticmethod
    def reservation(row):
        units=row['units'] if row['units'] is not None else decode(row['body'])['limits']['max_cost_units']
        terminal=row['status'] in {'SUCCEEDED','FAILED','CANCELLED'}
        return max(0,units-row['spent']) if not terminal or row['unresolved'] else 0

    def projection(self, goal):
        owner=self.owner(goal)
        if not owner:return None
        budget=self.db.one('SELECT * FROM work_budgets WHERE root_goal=?',(owner['root_goal'],))
        rows=self.rows(owner['root_goal']);spent=sum(r['spent'] for r in rows);reserved=sum(self.reservation(r) for r in rows)
        return {'scope':'linked_task_action_units','enforced':budget is not None,
                'limit_units':budget['limit_units'] if budget else None,'revision':budget['revision'] if budget else 0,
                'spent_units':spent,'reserved_units':reserved,'committed_units':spent+reserved,
                'available_units':max(0,budget['limit_units']-spent-reserved) if budget else None,
                'unresolved_tasks':sum(bool(r['unresolved']) for r in rows),
                'integrity':'complete' if not budget or all(r['units'] is not None for r in rows) else 'missing_allocation'}

    @staticmethod
    def validate_limit(limit):
        if type(limit) is not int or not 1<=limit<=1000:
            raise CoreError('work_budget_invalid','Expected an integer action-unit limit from 1 to 1000')

    def admit(self, goal, task_id, units, tx, requested_limit=None):
        owner=self.owner(goal)
        if not owner or owner['cancelled'] or owner['current_goal']!=goal:
            raise CoreError('work_conflict','Work changed before reservation')
        root=owner['root_goal'];budget=self.db.one('SELECT * FROM work_budgets WHERE root_goal=?',(root,))
        if requested_limit is not None:
            self.validate_limit(requested_limit)
            if budget or goal!=root:raise CoreError('work_budget_conflict','Change an existing shared budget separately')
        if not budget:
            if goal!=root:raise CoreError('work_budget_required','Adopt a shared budget before admitting legacy follow-up work')
            limit=requested_limit if requested_limit is not None else units*4
            self.validate_limit(limit)
            tx.execute('INSERT INTO work_budgets VALUES(?,?,1,?)',(root,limit,time.time()))
            self.db.event(tx,task_id,'work.budget_created',{'root_goal':root,'limit_units':limit,'defaulted':requested_limit is None})
            budget={'limit_units':limit}
        if self.db.one('SELECT 1 FROM work_allocations WHERE task_id=?',(task_id,)):
            raise CoreError('work_budget_conflict','Task already reserved')
        others=[r for r in self.rows(root) if r['id']!=task_id]
        if any(r['units'] is None for r in others):raise CoreError('work_budget_invalid','Prior budget allocation missing')
        committed=sum(r['spent']+self.reservation(r) for r in others)
        if committed+units>budget['limit_units']:raise CoreError('work_budget_exhausted','Shared work budget cannot reserve this plan')
        tx.execute('INSERT INTO work_allocations VALUES(?,?,?,?)',(task_id,root,units,budget['limit_units']))
        self.db.event(tx,task_id,'work.budget_reserved',{'root_goal':root,'units':units,'limit_units':budget['limit_units']})

    def configure(self, goal, revision, request_id, limit, note, tx):
        self.validate_limit(limit)
        if (type(revision) is not int or revision<0 or not isinstance(request_id,str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request_id) or not isinstance(note,str) or not 1<=len(note.strip())<=1000):
            raise CoreError('work_budget_invalid','Expected a revision, request ID and bounded budget reason')
        owner=self.owner(goal)
        if not owner:raise CoreError('work_budget_required','Work has not been registered')
        root=owner['root_goal'];fingerprint=digest([goal,revision,limit,note])
        old=self.db.one('SELECT * FROM work_budget_changes WHERE root_goal=? AND request_id=?',(root,request_id))
        if old:
            if old['digest']!=fingerprint:raise CoreError('work_budget_conflict','Budget request ID changed')
            return {**decode(old['result']),'existing':True}
        if owner['cancelled']:raise CoreError('work_conflict','Cancelled work cannot receive a new budget')
        current=self.projection(goal)
        if current['revision']!=revision:raise CoreError('work_budget_conflict','Budget changed since review')
        if current['integrity']!='complete':raise CoreError('work_budget_invalid','Do not replace missing allocations')
        if limit<current['committed_units']:raise CoreError('work_budget_committed','Limit cannot fall below spent and reserved units')
        tx.execute('''INSERT INTO work_budgets VALUES(?,?,?,?) ON CONFLICT(root_goal)
            DO UPDATE SET limit_units=excluded.limit_units,revision=excluded.revision''',(root,limit,revision+1,time.time()))
        if not current['enforced']:
            for row in self.rows(root):
                units=decode(row['body'])['limits']['max_cost_units']
                tx.execute('INSERT INTO work_allocations VALUES(?,?,?,?)',(row['id'],root,units,limit))
        result={'root_goal':root,'revision':revision+1,'limit_units':limit,'existing':False}
        tx.execute('INSERT INTO work_budget_changes VALUES(?,?,?,?)',(root,request_id,fingerprint,canonical(result)))
        self.db.event(tx,None,'work.budget_changed',{'root_goal':root,'revision':revision+1,'old_limit':current['limit_units'],
                      'limit_units':limit,'reason':note,'adopted_legacy':not current['enforced']})
        return result

    def check_dispatch(self, task_id, *, charging=True):
        """Called inside Ledger's charging transaction; no reserve or charge is added here."""
        link=self.db.one('''SELECT r.goal_id,r.root_goal FROM work_revisions r JOIN goal_plans p
            ON p.id=r.goal_id WHERE p.task_id=?''',(task_id,))
        if not link:return
        budget=self.projection(link['goal_id'])
        if not budget['enforced']:return  # Legacy already-admitted tasks retain their original limits.
        owner=self.owner(link['goal_id'])
        if owner['cancelled'] or owner['current_goal']!=link['goal_id']:raise CoreError('work_conflict','Work is no longer current')
        row=self.db.one('SELECT a.units,t.spent FROM tasks t JOIN work_allocations a ON a.task_id=t.id WHERE t.id=?',(task_id,))
        if budget['integrity']!='complete' or not row:raise CoreError('work_budget_invalid','Required task reservation missing')
        if row['spent']+int(charging)>row['units'] or budget['committed_units']>budget['limit_units']:
            raise CoreError('work_budget_exhausted','Shared work budget does not cover dispatch')
