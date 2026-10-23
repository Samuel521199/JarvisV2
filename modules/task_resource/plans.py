"""Editable proposals; only the host can atomically admit one into a task."""
import time
import uuid

from sdk.protocol import CoreError, canonical, contract, decode, digest


def planning_key(row):
    return row['id'] + ('-return' if row.get('planning_round',0) else '') + ('-g'+str(row['generation']) if row.get('generation',0) else '')


def validate_proposal(proposal, catalog):
    contract('goal-plan', proposal)
    allowed = {r['capability'] for r in catalog}
    for i, step in enumerate(proposal['steps']):
        if step['capability'] not in allowed or i == 0 and step['source'] != 'input':
            raise CoreError('plan_capability', 'Plan must use available tools and earlier text only')
        if step['capability'].startswith('mcp.') and (i != 0 or step['source'] != 'input'):
            raise CoreError('plan_capability', 'External arguments must be reviewed before execution')
    return proposal


class Plans:
    def __init__(self, db): self.db = db

    def get(self, ident):
        row = self.db.one('SELECT * FROM goal_plans WHERE id=?', (ident,))
        if not row: raise CoreError('not_found', 'Goal does not exist')
        for name in ('request','catalog','routes','proposal'):
            if row[name] is not None: row[name] = decode(row[name])
        return row

    def create(self, request, catalog, routes, tx):
        old = tx.execute('SELECT id,digest FROM goal_plans WHERE request_id=?',(request['request_id'],)).fetchone()
        if old:
            if old['digest'] != digest(request): raise CoreError('conflict','Goal request changed')
            return old['id'], False
        ident = 'goal-' + uuid.uuid4().hex; now = time.time()
        tx.execute("INSERT INTO goal_plans(id,request_id,digest,request,catalog,routes,status,created,deadline) VALUES(?,?,?,?,?,?,'NEW',?,?)",
                   (ident,request['request_id'],digest(request),canonical(request),canonical(catalog),canonical(routes),now,now+600))
        self.db.event(tx,None,'goal.created',{'goal_id':ident})
        return ident, True

    def edit(self, ident, revision, proposal):
        row=self.get(ident);validate_proposal(proposal,row['catalog'])
        state='REVIEW' if proposal['steps'] and not proposal['questions'] else 'NEEDS_INPUT'
        with self.db.transaction() as tx:
            growth=tx.execute('SELECT status FROM goal_growth WHERE goal_id=?',(ident,)).fetchone()
            if growth and growth['status'] not in {'REJOINED','CANCELLED'}:raise CoreError('growth_active','Finish or cancel the attached development first')
            if tx.execute("UPDATE goal_plans SET proposal=?,status=?,error=NULL,revision=revision+1 WHERE id=? AND revision=? AND cancel=0 AND status IN ('NEW','REVIEW','NEEDS_INPUT','WAITING')",
                          (canonical(proposal),state,ident,revision)).rowcount!=1:raise CoreError('conflict','Goal is no longer editable')
            self.db.event(tx,None,'goal.edited',{'goal_id':ident,'revision':revision+1})
        return self.get(ident)

    def finish(self, ident, status, proposal=None, error=None):
        if proposal is not None:validate_proposal(proposal,self.get(ident)['catalog'])
        with self.db.transaction() as tx:
            changed=tx.execute("UPDATE goal_plans SET status=?,proposal=COALESCE(?,proposal),error=?,revision=revision+1 WHERE id=? AND status='PLANNING' AND cancel=0",
                               (status,canonical(proposal) if proposal is not None else None,error,ident)).rowcount
            if changed:self.db.event(tx,None,'goal.planning_finished',{'goal_id':ident,'status':status,'error':error})
        return self.get(ident)
