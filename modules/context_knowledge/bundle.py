"""Public memory bundle, atomically restored with revocation floors and inert policy.

The format carries memory objects and their evidence, never executable grants,
secrets, active task state, private model files or derived search indexes.
"""
import re
import time
from modules.context_knowledge import Facts, conditions
from modules.context_knowledge.memory import Memory, KINDS
from modules.context_knowledge.transfer import Transfer, validate_bundle, MAX_TRANSFER_BYTES
from modules.context_knowledge.history import FIELDS, changed, record
from sdk.protocol import CoreError, canonical, contract, decode, digest

FORMAT='jarvis.memory-bundle.v1'
VERSION='memory-portability-1.0.0'
LIMIT=10000


def validate(bundle):
    try:return _validate(bundle)
    except (KeyError,TypeError,ValueError,OverflowError,RecursionError):
        raise CoreError('memory_bundle_invalid','Unsupported or damaged memory bundle') from None


def _validate(bundle):
    def bad():raise CoreError('memory_bundle_invalid','Unsupported or damaged memory bundle')
    if not isinstance(bundle,dict) or set(bundle)!={'format','sources','facts','candidates','claims','history','origins','checksum'}:bad()
    if bundle['format']!=FORMAT:bad()
    validate_bundle(bundle['sources']);scope=bundle['sources']['scope']
    for name in ('facts','candidates','claims','history','origins'):
        if not isinstance(bundle[name],list) or len(bundle[name])>LIMIT:bad()
    seen=set();keys=set();factids=set()
    for r in bundle['facts']:
        if not isinstance(r,dict) or set(r)!={'id','key','value','source','revision','deleted','kind','purpose','providers','paused','expires','applicability'}:bad()
        if not isinstance(r['id'],str) or not re.fullmatch('fact-[a-f0-9]{32}',r['id']) or r['id'] in seen or r['key'] in keys:bad()
        if type(r['revision']) is not int or not 1<=r['revision']<2**53 or type(r['deleted']) is not bool:bad()
        seen.add(r['id']);keys.add(r['key']);factids.add(r['id'])
        if r['kind'] not in KINDS or r['purpose'] not in {'personal','style','project'} or type(r['paused']) is not bool:bad()
        if (scope=='personal')!=(r['purpose']!='project') or (r['purpose']=='style' and r['kind']!='preference'):bad()
        if not isinstance(r['providers'],list) or len(r['providers'])>32 or any(not isinstance(p,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',p) for p in r['providers']):bad()
        rule=conditions.validate(r['applicability']);conditions.validate({'valid_from':r['expires'],'conditions':{}})
        if r['expires'] and rule['valid_from'] and r['expires']<=rule['valid_from']:bad()
        contract('fact',{'schema':'jarvis.fact.v1','principal_id':'owner.local','scope_id':scope,'key':r['key'],
                         'value':r['value'] if not r['deleted'] else 'deleted','source':r['source'] if not r['deleted'] else 'deleted'})
        if r['deleted'] and (r['value'] or r['source'] or r['providers']):bad()
    candidateids=set()
    for r in bundle['candidates']:
        if not isinstance(r,dict) or set(r)!={'id','source_id','source_revision','scope','key','value','state','created','fact_id','revision'}:bad()
        if not isinstance(r['id'],str) or not re.fullmatch('memory-[a-f0-9]{32}',r['id']) or r['id'] in seen or r['scope']!=scope:bad()
        if r['state'] not in {'PENDING','ACCEPTED','DISMISSED','WITHDRAWN'} or type(r['revision']) is not int or r['revision']<1:bad()
        if not all(isinstance(r[k],str) and len(r[k])<=4000 for k in ('source_id','source_revision','key','value')):bad()
        if r['state']!='PENDING' and (r['key'] or r['value']):bad()
        if r['fact_id'] is not None and r['fact_id'] not in factids:bad()
        if type(r['created']) not in (int,float) or not 0<=r['created']<4102444800:bad()
        seen.add(r['id']);candidateids.add(r['id'])
    sources={r['id']:r for r in bundle['sources']['sources']};claims={}
    for r in bundle['claims']:
        if not isinstance(r,dict) or set(r)!={'id','source_id','source_revision','start','end','key','quote','state','fact_id','revision','created'}:bad()
        if not isinstance(r['id'],str) or not re.fullmatch('claim-[a-f0-9]{32}',r['id']) or r['id'] in claims:bad()
        if r['state'] not in {'pending','accepted','dismissed','withdrawn'} or any(type(r[k]) is not int or r[k]<0 for k in ('revision','source_revision','start','end')):bad()
        if not isinstance(r['key'],str) or len(r['key'])>120 or not isinstance(r['quote'],str) or len(r['quote'])>80000:bad()
        if r['fact_id'] is not None and r['fact_id'] not in factids:bad()
        if type(r['created']) not in (int,float) or not 0<=r['created']<4102444800:bad()
        source=sources.get(r['source_id'])
        if r['state'] in {'pending','accepted'}:
            if not source or r['source_revision']!=source['revision'] or not 0<=r['start']<r['end']<=len(source['text']) or source['text'][r['start']:r['end']]!=r['quote']:bad()
        elif r['quote'] or r['key']:bad()
        claims[r['id']]=r
    for f in bundle['facts']:
        if f['source'].startswith('knowledge:'):
            c=claims.get(f['source'][10:])
            if not c or c['state']!='accepted' or c['fact_id']!=f['id']:bad()
    alive={('fact',f['id']) for f in bundle['facts'] if not f['deleted']}|{('source',s) for s in sources}
    historyseen=set()
    for r in bundle['history']:
        if not isinstance(r,dict) or set(r)!={'kind','id','revision','body','recorded'}:bad()
        if (r['kind'],r['id']) not in alive or type(r['revision']) is not int or r['revision']<1:bad()
        if r['recorded'] is not None and (type(r['recorded']) not in (int,float) or not 0<=r['recorded']<4102444800):bad()
        if not isinstance(r['body'],dict) or set(r['body'])!=set(FIELDS[r['kind']]) or any(not isinstance(x,str) for x in r['body'].values()):bad()
        key=(r['kind'],r['id'],r['revision'])
        if key in historyseen:bad()
        historyseen.add(key)
    originseen=set()
    for r in bundle['origins']:
        if not isinstance(r,dict) or set(r)!={'id','body','checksum'} or r['id'] not in factids|candidateids or r['id'] in originseen:bad()
        if not isinstance(r['body'],dict) or r['checksum']!=digest(r['body']):bad()
        if len(canonical(r['body']).encode())>200000:bad()
        originseen.add(r['id'])
    if bundle['checksum']!=digest({k:v for k,v in bundle.items() if k!='checksum'}):bad()
    if len(canonical(bundle).encode())>MAX_TRANSFER_BYTES-1000:raise CoreError('knowledge_transfer_size','Memory bundle exceeds 40 MB')
    return bundle


class Bundle:
    def __init__(self,db):self.db=db;self.sources=Transfer(db)

    def export(self,scope,origin=lambda kind,row:None):
        from modules.context_knowledge.source_policy import require_complete_export
        require_complete_export(self.db,scope)
        self.db.connection.execute('BEGIN')
        try:
            return self.snapshot(scope,origin)
        finally:self.db.connection.execute('ROLLBACK')

    def snapshot(self,scope,origin=lambda kind,row:None):
        live={r['id']:r for r in Memory(self.db).list(scope)};facts=[];origins=[]
        rows=self.db.all('SELECT * FROM facts WHERE principal=? AND scope=? ORDER BY id',('owner.local',scope))
        for r in rows:
            policy=live.get(r['id'],{})
            facts.append({k:r[k] for k in ('id','key','value','source','revision')}|{'deleted':bool(r['deleted']),
                'kind':policy.get('kind','knowledge'),'purpose':policy.get('purpose') or ('personal' if scope=='personal' else 'project'),
                'providers':policy.get('providers',[]),'paused':bool(policy.get('paused',True)),
                'expires':policy.get('expires'),'applicability':conditions.get(self.db,r['id'])})
        candidates=self.db.all('SELECT * FROM memory_candidates WHERE scope=? ORDER BY id',(scope,))
        claims=self.db.all('SELECT c.* FROM knowledge_claims c JOIN knowledge_sources s ON c.source_id=s.id WHERE s.scope=? ORDER BY c.id',(scope,))
        history=self.db.all('SELECT kind,id,revision,body,recorded FROM memory_history WHERE scope=? ORDER BY kind,id,revision',(scope,))
        for r in history:r['body']=decode(r['body'])
        for kind,objects in (('fact',rows),('candidate',candidates)):
            for r in objects:
                if r.get('deleted') or kind=='candidate' and r['state']!='PENDING':continue
                previous=self.db.one('SELECT body FROM memory_origins WHERE id=? AND scope=?',(r['id'],scope))
                body=decode(previous['body']) if previous else origin(kind,r)
                if body:origins.append({'id':r['id'],'body':body,'checksum':digest(body)})
        result={'format':FORMAT,'sources':self.sources.snapshot(scope),'facts':facts,'candidates':candidates,'claims':claims,'history':history,'origins':origins}
        result['checksum']=digest(result);return validate(result)

    def plan(self,scope,bundle):
        validate(bundle);sources=self.sources.plan(scope,bundle['sources']);actions=[]
        for r in bundle['facts']:
            old=self.db.one('SELECT * FROM facts WHERE principal=? AND scope=? AND key=?',('owner.local',scope,r['key']))
            collision=self.db.one('SELECT scope,key FROM facts WHERE id=?',(r['id'],))
            if collision and (collision['scope']!=scope or collision['key']!=r['key']):action='conflict'
            elif old and old['deleted']:action='skip_deleted'
            elif old and old['id']!=r['id']:action='conflict'
            elif r['deleted']:action='delete' if old else 'tombstone'
            elif not old:action='create'
            elif old['value']==r['value'] and old['source']==r['source']:action='unchanged'
            elif old['revision']<r['revision']:action='replace'
            else:action='conflict'
            actions.append({'id':r['id'],'key':r['key'],'action':action})
        conflicts=[]
        for r in bundle['candidates']:
            old=self.db.one('SELECT id,scope FROM memory_candidates WHERE id=? OR source_id=?',(r['id'],r['source_id']))
            if old and (old['id']!=r['id'] or old['scope']!=scope):conflicts.append(r['id'])
        for r in bundle['claims']:
            old=self.db.one('SELECT s.scope,c.source_id FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.id=?',(r['id'],))
            if old and (old['scope']!=scope or old['source_id']!=r['source_id']):conflicts.append(r['id'])
            same=self.db.one('SELECT id FROM knowledge_claims WHERE source_id=? AND source_revision=? AND start=? AND end=?',(r['source_id'],r['source_revision'],r['start'],r['end']))
            if same and same['id']!=r['id']:conflicts.append(r['id'])
        epoch=Memory(self.db).epoch()
        state=digest({'c':self.db.all('SELECT id,state,revision FROM memory_candidates ORDER BY id'),
                      'k':self.db.all('SELECT id,state,revision FROM knowledge_claims ORDER BY id')})
        return {'token':digest({'scope':scope,'checksum':bundle['checksum'],'epoch':epoch,'state':state}),
                'sources':sources,'facts':actions,'conflicts':conflicts,
                'can_apply':sources['can_apply'] and not conflicts and all(a['action']!='conflict' for a in actions),
                'policy':'paused_without_destinations','version':VERSION}

    def preview(self,scope,bundle):
        self.db.connection.execute('BEGIN')
        try:return self.plan(scope,bundle)
        finally:self.db.connection.execute('ROLLBACK')

    def restore(self,scope,bundle,token):
        validate(bundle)
        with self.db.transaction() as tx:
            plan=self.plan(scope,bundle)
            if token!=plan['token']:raise CoreError('conflict','Memory preview changed')
            if not plan['can_apply']:raise CoreError('memory_restore_conflict','Resolve memory conflicts before restore')
            return self.apply(tx,scope,bundle,plan)

    def apply(self,tx,scope,bundle,plan):
        self.sources.apply(tx,scope,bundle['sources'],plan['sources'])
        facts={r['id']:r for r in bundle['facts']};written=set()
        claims={r['id']:r for r in bundle['claims']}
        for a in plan['facts']:
            if a['action'] in {'skip_deleted','unchanged'}:continue
            r=facts[a['id']];old=tx.execute('SELECT * FROM facts WHERE id=?',(r['id'],)).fetchone()
            # A source tombstone in the same bundle may already have withdrawn this fact.
            if old and old['deleted'] and not r['deleted']:continue
            if r['source'].startswith('knowledge:'):
                c=claims[r['source'][10:]]
                source=tx.execute('SELECT * FROM knowledge_sources WHERE id=?',(c['source_id'],)).fetchone()
                prior=tx.execute('SELECT state FROM knowledge_claims WHERE id=?',(c['id'],)).fetchone()
                if not source or source['status']=='deleted' or prior and prior['state'] in {'dismissed','withdrawn'}:
                    r=r|{'deleted':True,'value':'','source':''}
            rev=max(r['revision'],old['revision']+1 if old else 1)
            if old and not old['deleted']:record(tx,'fact',old)
            tx.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value,source=excluded.source,revision=excluded.revision,deleted=excluded.deleted',
                       (r['id'],'owner.local',scope,r['key'],r['value'],r['source'],rev,int(r['deleted'])))
            tx.execute('DELETE FROM memory_usage WHERE fact_id=?',(r['id'],))
            if not r['deleted']:
                tx.execute('INSERT INTO memory_usage VALUES(?,?,?,?,?,?,?)',(r['id'],r['kind'],'personal' if scope=='personal' and r['purpose']=='project' else 'project' if scope!='personal' else r['purpose'],'[]',1,r['expires'],time.time()))
                conditions.save(tx,r['id'],r['applicability']);changed(tx,'fact',r['id']);written.add(r['id'])
            else:
                tx.execute("UPDATE memory_candidates SET state='WITHDRAWN',key='',value='',revision=revision+1 WHERE fact_id=?",(r['id'],))
                tx.execute("UPDATE knowledge_claims SET state='withdrawn',key='',quote='',revision=revision+1 WHERE fact_id=?",(r['id'],))
        for r in bundle['candidates']:
            if tx.execute('SELECT 1 FROM memory_candidates WHERE id=?',(r['id'],)).fetchone():
                if r['state']!='PENDING':tx.execute("UPDATE memory_candidates SET state='WITHDRAWN',key='',value='',revision=revision+1 WHERE id=? AND state='PENDING'",(r['id'],))
                continue
            dead=r['fact_id'] and tx.execute('SELECT deleted FROM facts WHERE id=?',(r['fact_id'],)).fetchone()[0]
            state='WITHDRAWN' if dead else r['state']
            tx.execute('INSERT INTO memory_candidates(id,source_id,source_revision,scope,key,value,state,created,fact_id,revision) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (r['id'],r['source_id'],r['source_revision'],scope,r['key'] if state=='PENDING' else '',r['value'] if state=='PENDING' else '',state,r['created'],r['fact_id'],r['revision']))
        for r in bundle['claims']:
            if tx.execute('SELECT 1 FROM knowledge_claims WHERE id=?',(r['id'],)).fetchone():
                if r['state'] in {'dismissed','withdrawn'}:
                    tx.execute("UPDATE knowledge_claims SET state='withdrawn',key='',quote='',revision=revision+1 WHERE id=? AND state IN ('pending','accepted')",(r['id'],))
                    tx.execute("UPDATE facts SET value='',source='',deleted=1,revision=revision+1 WHERE source=? AND deleted=0",('knowledge:'+r['id'],))
                    tx.execute('DELETE FROM memory_usage WHERE fact_id IN (SELECT id FROM facts WHERE deleted=1)')
                continue
            source=tx.execute('SELECT * FROM knowledge_sources WHERE id=?',(r['source_id'],)).fetchone()
            if not source:continue
            good=source['status']!='deleted' and source['text'][r['start']:r['end']]==r['quote']
            if r['fact_id']:
                f=tx.execute('SELECT deleted FROM facts WHERE id=?',(r['fact_id'],)).fetchone();good=good and f and not f['deleted']
            state=r['state'] if good else 'withdrawn'
            tx.execute('INSERT OR IGNORE INTO knowledge_claims VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (r['id'],r['source_id'],source['revision'] if good else r['source_revision'],r['start'],r['end'],r['key'] if good else '',r['quote'] if good else '',state,r['fact_id'],r['revision'],r['created']))
        for r in bundle['history']:
            table='facts' if r['kind']=='fact' else 'knowledge_sources'
            row=tx.execute(f'SELECT * FROM {table} WHERE id=? AND scope=?',(r['id'],scope)).fetchone()
            if row is None:continue
            if (r['kind']=='fact' and row['deleted']) or (r['kind']=='source' and row['status']=='deleted'):continue
            if r['revision']>=row['revision']:continue
            tx.execute('INSERT OR IGNORE INTO memory_history VALUES(?,?,?,?,?,?)',(r['kind'],r['id'],r['revision'],scope,canonical(r['body']),r['recorded']))
        for r in bundle['origins']:
            f=tx.execute('SELECT deleted FROM facts WHERE id=?',(r['id'],)).fetchone()
            c=tx.execute('SELECT state FROM memory_candidates WHERE id=?',(r['id'],)).fetchone()
            if f and f['deleted'] or c and c['state']!='PENDING':continue
            tx.execute('INSERT OR IGNORE INTO memory_origins VALUES(?,?,?,?)',(r['id'],scope,canonical(r['body']),r['checksum']))
        Facts.bump(tx);counts={'facts_written':len(written),'sources':plan['sources']['counts']}
        receipt='import-'+digest({'scope':scope,'checksum':bundle['checksum']})
        tx.execute('INSERT OR IGNORE INTO memory_imports VALUES(?,?,?,?,?)',(receipt,scope,bundle['checksum'],time.time(),canonical(counts)))
        return {'receipt':receipt,'counts':counts,'policy':'paused_without_destinations','version':VERSION}
