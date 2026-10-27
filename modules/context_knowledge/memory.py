"""Bounded owner facts and reviewable candidates. No model inference or implicit sharing."""
import math
import re
import time
import uuid

from modules.context_knowledge import Facts, source_policy
from modules.context_knowledge.retrieval import rank
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge import conditions
from modules.context_knowledge import joint
from modules.context_knowledge.domains import Domains
from sdk.protocol import CoreError, canonical, contract, decode

KINDS = {'profile', 'preference', 'agreement', 'knowledge'}


class Memory:
    def __init__(self, db): self.db = db

    def epoch(self): return int(self.db.one("SELECT value FROM meta WHERE key='memory_epoch'")['value'])

    def list(self, scope):
        rows = self.db.all('SELECT f.*,u.kind,u.purpose,u.providers,u.paused,u.expires,u.updated FROM facts f '
                           'LEFT JOIN memory_usage u ON u.fact_id=f.id WHERE f.principal=? AND f.scope=? AND f.deleted=0 ORDER BY f.key', ('owner.local', scope))
        for row in rows:
            row['applicability']=conditions.get(self.db,row['id'])
            row['providers'] = decode(row['providers']) if row['providers'] else []
            row['kind'] = row['kind'] or 'knowledge'
            row['state'] = 'local' if row['purpose'] is None else ('paused' if row['paused'] else ('expired' if row['expires'] and row['expires'] <= time.time() else 'active'))
            if row['state']=='active' and row['applicability']['valid_from'] and row['applicability']['valid_from']>time.time():row['state']='scheduled'
            if row['source'].startswith('goal:') and self.db.one("SELECT value FROM meta WHERE key='completion_schema'"):
                goal=self.db.one('SELECT task_id FROM goal_plans WHERE id=?',(row['source'][5:],))
                feedback=self.db.one('SELECT kind FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(goal['task_id'],)) if goal else None
                completion=self.db.one('SELECT body FROM task_completion WHERE task_id=?',(goal['task_id'],)) if goal else None
                if (feedback and feedback['kind']=='reject') or (completion and decode(completion['body'])['state'] in {'NEEDS_CORRECTION','INVALIDATED','CANCELLED'}):
                    row['state']='source_invalid';row['providers']=[]
            if row['source'].startswith('knowledge:'):
                claim=self.db.one("SELECT c.*,s.text,s.status AS source_status,s.revision AS current_revision FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.id=? AND c.state='accepted'",(row['source'][10:],))
                row['providers'] = [p for p in row['providers'] if claim and claim['source_status']=='active' and claim['source_revision']==claim['current_revision'] and p in source_policy.destinations(self.db,claim['source_id'])]
                if claim:
                    row['evidence']={'source_id':claim['source_id'],'revision':claim['source_revision'],'start':claim['start'],'end':claim['end'],
                                     'line_start':claim['text'].count('\n',0,claim['start'])+1,'line_end':claim['text'].count('\n',0,claim['end']-1)+1,
                                     'trust':'owner_reviewed_claim','claim_id':claim['id']}
        return rows

    def save(self, item, revision, source='owner:explicit', candidate=None, source_candidate=None):
        fields = {'scope', 'key', 'value', 'kind', 'purpose', 'providers', 'paused', 'expires'}
        if not isinstance(item, dict) or set(item)-{'applicability'} != fields or type(revision) is not int or revision < 0:
            raise CoreError('memory_invalid', 'Invalid memory edit')
        joint.writable(item['scope'])
        if item['kind'] not in KINDS or item['purpose'] not in {'personal', 'style', 'project'} or type(item['paused']) is not bool:
            raise CoreError('memory_invalid', 'Invalid memory use')
        if (item['scope'] == 'personal') != (item['purpose'] != 'project') or (item['purpose'] == 'style' and item['kind'] != 'preference'):
            raise CoreError('memory_invalid', 'Project facts and shared communication preferences have distinct scopes')
        providers = item['providers']
        if not isinstance(providers, list) or len(providers) > 32 or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', p) for p in providers) or len(set(providers)) != len(providers):
            raise CoreError('memory_invalid', 'Invalid destination allowlist')
        expiry = item['expires']
        if expiry is not None and (type(expiry) not in (int, float) or not math.isfinite(expiry) or not 0 < expiry < 4102444800):
            raise CoreError('memory_invalid', 'Invalid expiry')
        if 'applicability' in item:
            conditions.validate(item['applicability'])
            if expiry is not None and item['applicability']['valid_from'] is not None and expiry<=item['applicability']['valid_from']:
                raise CoreError('memory_invalid','Effective end must follow start')
        fact = dict(schema='jarvis.fact.v1', principal_id='owner.local', scope_id=item['scope'], key=item['key'], value=item['value'], source=source)
        contract('fact', fact)
        with self.db.transaction() as tx:
            old=tx.execute('SELECT value,source FROM facts WHERE principal=? AND scope=? AND key=? AND deleted=0',('owner.local',item['scope'],item['key'])).fetchone()
            if not source_candidate and old and old['source'].startswith('knowledge:') and old['value']==item['value']:
                claim=tx.execute("SELECT c.source_id FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.id=? AND c.state='accepted' AND s.status='active' AND s.revision=c.source_revision",(old['source'][10:],)).fetchone()
                if not claim:raise CoreError('conflict','Source changed')
                allowed=set(source_policy.destinations(self.db,claim['source_id']))
                if item['kind']!='knowledge' or not set(providers)<=allowed:raise CoreError('memory_invalid','Source limits still apply to this knowledge')
                fact['source']=old['source']
            if source_candidate:
                claim=tx.execute('SELECT c.*,s.scope,s.revision AS current_revision,s.status FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.id=?',
                                 (source_candidate['id'],)).fetchone()
                if (not claim or claim['state']!='pending' or claim['revision']!=source_candidate['revision'] or
                    claim['status']!='active' or claim['source_revision']!=claim['current_revision']):
                    raise CoreError('conflict','Source or knowledge candidate changed')
                allowed=set(source_policy.destinations(self.db,claim['source_id']))
                if item['scope']!=claim['scope'] or item['kind']!='knowledge' or not set(providers)<=allowed:
                    raise CoreError('memory_invalid','Derived knowledge must retain source scope and destination limits')
            if candidate:
                row = tx.execute('SELECT * FROM memory_candidates WHERE id=?', (candidate['id'],)).fetchone()
                if not row or row['state'] != 'PENDING' or row['revision'] != candidate['revision']:
                    raise CoreError('conflict', 'Candidate changed')
            ident = Facts.write(tx, fact, revision)
            if 'applicability' in item:conditions.save(tx,ident,item['applicability'])
            tx.execute('INSERT INTO memory_usage VALUES(?,?,?,?,?,?,?) ON CONFLICT(fact_id) DO UPDATE SET kind=excluded.kind,purpose=excluded.purpose,providers=excluded.providers,paused=excluded.paused,expires=excluded.expires,updated=excluded.updated',
                       (ident, item['kind'], item['purpose'], canonical(providers), item['paused'], expiry, time.time()))
            if candidate:
                tx.execute("UPDATE memory_candidates SET state='ACCEPTED',fact_id=?,key='',value='',revision=revision+1 WHERE id=?", (ident, candidate['id']))
            if source_candidate:
                tx.execute("UPDATE knowledge_claims SET state='accepted',fact_id=?,revision=revision+1 WHERE id=?",(ident,source_candidate['id']))
            Facts.bump(tx)
            self.db.event(tx, None, 'memory.saved', {'id': ident, 'scope': item['scope']})
        return {'id': ident, 'revision': revision + 1, 'epoch': self.epoch()}

    def forget(self, scope, key, revision):
        Facts(self.db).forget('owner.local', scope, key, revision)
        return {'forgotten': True, 'epoch': self.epoch()}

    def candidates(self, scope):
        return self.db.all("SELECT * FROM memory_candidates WHERE scope=? AND state='PENDING' ORDER BY created DESC LIMIT 100", (scope,))

    def propose(self, source_id, source_revision, scope, text):
        joint.writable(scope)
        # Source uniqueness persists after dismissal/withdrawal; no silent resurrection.
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000: raise CoreError('memory_invalid', 'Candidate text limit')
        with self.db.transaction() as tx:
            old = tx.execute('SELECT id,state FROM memory_candidates WHERE source_id=?', (source_id,)).fetchone()
            if old: return dict(old)
            if tx.execute("SELECT count(*) FROM memory_candidates WHERE state='PENDING'").fetchone()[0] >= 200:
                raise CoreError('memory_capacity', 'Review pending memories first')
            ident = 'memory-' + uuid.uuid4().hex
            tx.execute("INSERT INTO memory_candidates(id,source_id,source_revision,scope,key,value,state,created) VALUES(?,?,?,?,?,?,'PENDING',?)",
                       (ident, source_id, source_revision, scope, text.strip()[:60], text.strip(), time.time()))
            return {'id': ident, 'state': 'PENDING'}

    def dismiss(self, ident, revision):
        with self.db.transaction() as tx:
            if tx.execute("UPDATE memory_candidates SET state='DISMISSED',key='',value='',revision=revision+1 WHERE id=? AND revision=? AND state='PENDING'", (ident, revision)).rowcount != 1:
                raise CoreError('conflict', 'Candidate changed')
        return {'dismissed': True}

    def eligible(self, scope, provider, enabled=True, selectors=None):
        if type(enabled) is not bool: raise CoreError('memory_invalid', 'Invalid memory switch')
        if scopes:=joint.members(scope):
            return list({r['id']:r for s in scopes for r in self.eligible(s,provider,enabled,selectors)}.values())
        domain=self.db.one('SELECT kind,archived FROM memory_domains WHERE id=?',(scope,))
        if domain and domain['archived']:return []
        rows = (([] if domain else self.list('personal')) + (self.list(scope) if scope != 'personal' else [])) if enabled else []
        return [r for r in rows if r['state']=='active' and provider in r['providers']
                and not (scope!='personal' and r['scope']=='personal' and r['purpose']!='style')
                and conditions.matches(r['applicability'],selectors)]

    def references(self, scope, provider, enabled=True, selectors=None):
        if type(enabled) is not bool:raise CoreError('memory_invalid','Invalid memory switch')
        if not enabled:return []
        if scopes:=joint.members(scope):
            return list({(r['id'],r['revision']):r for s in scopes for r in self.references(s,provider,enabled,selectors)}.values())
        domain=self.db.one('SELECT archived FROM memory_domains WHERE id=?',(scope,))
        if domain and domain['archived']:return []
        return ([{'id':r['id'],'revision':r['revision']} for r in self.eligible(scope,provider,enabled,selectors)]
                + Knowledge(self.db).references(scope,provider)+Domains(self.db).inherited(scope,provider,selectors,False))

    def references_valid(self, scope, provider, enabled, refs, selectors=None):
        if not isinstance(refs,list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str)
                or type(r.get('revision')) is not int for r in refs): return False
        current = {(r['id'],r['revision']) for r in self.references(scope,provider,enabled,selectors)}
        return all((r['id'],r['revision']) in current for r in refs)

    def view(self, scope, provider, enabled=True, query='', semantic=None, source_semantic=None, selectors=None):
        if not isinstance(query,str) or len(query)>20000: raise CoreError('memory_invalid','Invalid retrieval query')
        result = []; used = 0; valid_until = None
        # Filter BEFORE handing any content to the local ranker.
        scopes=joint.members(scope) or [scope]
        sources=[];routes=[]
        if enabled:
            for source_scope in scopes:
                found,route=Knowledge(self.db).search(source_scope,provider,query)
                for row in found:row['origin_scope']=source_scope
                sources.extend(found);routes.append({'scope':source_scope,**route})
        source_retrieval=routes[0] if len(routes)==1 else {'mode':'joint' if enabled else 'disabled','scopes':routes}
        if enabled and query.strip() and source_semantic:
            extra,semantic_status=source_semantic(self.db,scope,provider,query)
            for r in extra:
                overlap=next((x for x in sources if x['evidence']['source_id']==r['evidence']['source_id'] and
                              x['evidence']['start']<=r['evidence']['start'] and x['evidence']['end']>=r['evidence']['end']),None)
                if overlap:overlap['semantic_score']=max(overlap.get('semantic_score',-1),r['semantic_score'])
                else:sources.append(r)
            source_retrieval['semantic']=semantic_status
            if semantic_status.get('status') not in {'not_built','model_not_loaded'}:semantic=None  # One foreground encoder budget.
        inherited=[r|{'origin_scope':s} for s in scopes for r in Domains(self.db).inherited(s,provider,selectors)] if enabled else []
        if not query.strip():inherited=[r for r in inherited if r['kind']!='source']
        rows, retrieval = rank(self.eligible(scope,provider,enabled,selectors)+sources+inherited,query,semantic)
        info=source_retrieval.get('semantic',{})
        if info.get('status')=='ready':
            retrieval.update(semantic='persistent_ready',semantic_candidates=info.get('candidates',0),model=info.get('model'),vector_space=info.get('space'))
        for row in rows:
            part = {'id': row['id'], 'revision': row['revision'], 'key': row['key'], 'value': row['value'], 'kind': row['kind']}
            if row.get('evidence'):
                part['evidence']=row['evidence']
                if row['kind']=='source':part['id']=row['evidence']['source_id']
            if row.get('snapshot_domain'):part['snapshot_domain']=row['snapshot_domain']
            if len(scopes)>1:part['origin_scope']=row.get('origin_scope',row.get('scope'))
            size = len(canonical(part).encode())
            if len(result) >= 12 or used + size > 5000: continue
            result.append(part); used += size
            if row['expires']: valid_until = min(valid_until or row['expires'], row['expires'])
        return {'epoch':self.epoch(),'facts':result,'valid_until':valid_until,
                'retrieval':{**retrieval,'sources':source_retrieval,'selected':len(result),'bytes':used}}
