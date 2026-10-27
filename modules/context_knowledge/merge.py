"""Explicit three-way owner review of branch facts; never an automatic truth merge."""
import time
from modules.context_knowledge import Facts,conditions
from modules.context_knowledge.domains import Domains
from modules.context_knowledge.memory import Memory
from sdk.protocol import CoreError,canonical,decode,digest


class Merge:
    def __init__(self,db):self.db=db

    def preview(self,scope):
        with self.db.read_snapshot():return self.plan(scope)

    def plan(self,scope):
        domain=Domains(self.db).get(scope)
        if domain['kind']!='branch':raise CoreError('memory_invalid','Only project branches have a parent merge')
        base={}
        for row in self.db.all("SELECT h.body FROM memory_snapshots s JOIN memory_history h ON h.kind=s.kind AND h.id=s.id AND h.revision=s.revision WHERE s.domain_id=? AND s.kind='fact'",(scope,)):
            body=decode(row['body']);base[body['key']]=body['value']
        items=[]
        for local in self.db.all('SELECT * FROM facts WHERE scope=? ORDER BY key',(scope,)):
            target=self.db.one('SELECT * FROM facts WHERE scope=? AND key=?',(domain['parent'],local['key']))
            before=base.get(local['key']);value=None if local['deleted'] else local['value']
            current=None if not target or target['deleted'] else target['value']
            state=('forgotten' if target and target['deleted'] else 'unchanged' if value==current or (local['key'] in base and value==before)
                   else 'conflict' if current!=before else 'delete' if local['deleted'] else 'replace' if target else 'create')
            items.append({'id':local['id'],'key':local['key'],'base':before,'parent_value':current,'branch_value':value,
                          'branch_revision':local['revision'],'parent_id':target['id'] if target else None,
                          'parent_revision':target['revision'] if target else 0,'state':state})
        token=digest({'domain':domain,'epoch':Memory(self.db).epoch(),'items':items})
        return {'scope':scope,'parent':domain['parent'],'items':items,'token':token,
                'policy':'owner_reviewed_independent_fact_paused_without_destinations','version':'memory-branch-merge-1.0.0'}

    def apply(self,scope,token,choices):
        if not isinstance(token,str) or not isinstance(choices,dict) or len(choices)>10000 or any(v not in {'branch','parent'} for v in choices.values()):
            raise CoreError('memory_invalid','Review each changed fact explicitly')
        receipt='merge-'+digest({'scope':scope,'token':token,'choices':choices})
        with self.db.transaction() as tx:
            prior=tx.execute('SELECT counts FROM memory_imports WHERE id=?',(receipt,)).fetchone()
            if prior:return decode(prior['counts'])|{'replayed':True}
            plan=self.plan(scope)
            if token!=plan['token']:raise CoreError('conflict','Branch or parent changed; preview again')
            actions={r['id']:r for r in plan['items'] if r['state'] not in {'forgotten','unchanged'}}
            if set(choices)!=set(actions):raise CoreError('memory_invalid','Every change needs an explicit branch or parent choice')
            changed=0
            for ident,choice in choices.items():
                if choice=='parent':continue
                row=actions[ident]
                if row['branch_value'] is None:
                    if row['parent_id']:
                        tx.execute("UPDATE facts SET deleted=1,value='',source='',revision=revision+1 WHERE id=?",(row['parent_id'],))
                        tx.execute('DELETE FROM memory_usage WHERE fact_id=?',(row['parent_id'],))
                        tx.execute("UPDATE memory_candidates SET state='WITHDRAWN',key='',value='',revision=revision+1 WHERE fact_id=?",(row['parent_id'],))
                        tx.execute("UPDATE knowledge_claims SET state='withdrawn',quote='',key='',revision=revision+1 WHERE fact_id=? AND state='accepted'",(row['parent_id'],))
                else:
                    source=f"owner:branch-merge:{scope}:{ident}:{row['branch_revision']}"
                    target=Facts.write(tx,{'principal_id':'owner.local','scope_id':plan['parent'],'key':row['key'],
                                          'value':row['branch_value'],'source':source},row['parent_revision'])
                    usage=tx.execute('SELECT kind,expires FROM memory_usage WHERE fact_id=?',(ident,)).fetchone()
                    tx.execute('INSERT INTO memory_usage VALUES(?,?,?,?,?,?,?) ON CONFLICT(fact_id) DO UPDATE SET kind=excluded.kind,purpose=excluded.purpose,providers=excluded.providers,paused=1,expires=excluded.expires,updated=excluded.updated',
                               (target,usage['kind'] if usage else 'knowledge','project','[]',1,usage['expires'] if usage else None,time.time()))
                    conditions.save(tx,target,conditions.get(self.db,ident))
                changed+=1
            if changed:Facts.bump(tx)
            result={'changed':changed,'kept_parent':sum(v=='parent' for v in choices.values()),'receipt':receipt,'replayed':False,'policy':plan['policy']}
            tx.execute('INSERT INTO memory_imports VALUES(?,?,?,?,?)',(receipt,plan['parent'],digest(choices),time.time(),canonical(result)))
            return result
