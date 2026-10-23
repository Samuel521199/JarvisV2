"""The durable bridge from one unresolved goal to one bounded development run."""
import time
from sdk.protocol import CoreError, canonical, contract, decode


def get(db, goal_id):
    row=db.one('SELECT * FROM goal_growth WHERE goal_id=?',(goal_id,))
    if row:
        for key in ('draft','prior_proposal','prior_catalog'):
            if row[key] is not None:row[key]=decode(row[key])
    return row


def validate(draft):
    contract('capability-draft',draft)
    if draft['supported'] and not draft['questions']:
        if not draft['description'].strip() or not draft['public_cases'] or not draft['evaluation_cases']:
            raise CoreError('growth_incomplete','Review needs behavior and both public and held-out examples')
        public={c['input'] for c in draft['public_cases']}
        if any(c['input'] in public for c in draft['evaluation_cases']):
            raise CoreError('growth_incomplete','Held-out examples must differ from public examples')
        cases=draft['public_cases']+draft['evaluation_cases']
        if len({c['input'] for c in cases})!=len(cases):raise CoreError('growth_incomplete','Use distinct examples')
    return draft


def create(db,plan,tx):
    now=time.time()
    tx.execute("INSERT INTO goal_growth(goal_id,status,prior_proposal,prior_catalog,created,deadline) VALUES(?,'NEW',?,?,?,?)",
               (plan['id'],canonical(plan['proposal']),canonical(plan['catalog']),now,now+600))
    db.event(tx,None,'goal.growth_requested',{'goal_id':plan['id']})


def edit(db,goal_id,revision,draft):
    validate(draft)
    status='REVIEW' if draft['supported'] and not draft['questions'] else 'NEEDS_INPUT'
    with db.transaction() as tx:
        changed=tx.execute("UPDATE goal_growth SET draft=?,status=?,revision=revision+1,error=NULL WHERE goal_id=? AND revision=? AND development_id IS NULL AND status IN ('NEW','WAITING','REVIEW','NEEDS_INPUT') AND EXISTS(SELECT 1 FROM goal_plans WHERE id=? AND cancel=0 AND task_id IS NULL)",
                           (canonical(draft),status,goal_id,revision,goal_id)).rowcount
        if changed!=1:raise CoreError('conflict','Growth review changed or goal cancelled')
        db.event(tx,None,'goal.growth_edited',{'goal_id':goal_id,'revision':revision+1})
    return get(db,goal_id)
