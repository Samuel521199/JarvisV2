"""Explicit context domains and immutable, reference-only branch snapshots.

Snapshot bodies stay in the original revision ledger. Current revocation and
destination policy always take precedence over a historical snapshot.
"""
import time
import uuid
from modules.context_knowledge import Facts
from modules.context_knowledge.history import record
from sdk.protocol import CoreError, decode


class Domains:
    def __init__(self,db):self.db=db

    def list(self,parent):return self.db.all('SELECT * FROM memory_domains WHERE parent=? ORDER BY created',(parent,))

    def get(self,ident):
        row=self.db.one('SELECT * FROM memory_domains WHERE id=?',(ident,))
        if not row or row['archived']:raise CoreError('memory_domain_missing','Memory domain unavailable')
        return row

    def create(self,parent,kind,name,snapshot):
        from modules.context_knowledge.joint import writable
        writable(parent)
        if kind not in {'branch','task','world'} or not isinstance(name,str) or not 1<=len(name.strip())<=80 or type(snapshot) is not bool:
            raise CoreError('memory_invalid','Invalid memory domain')
        if snapshot and kind!='branch':raise CoreError('memory_invalid','Only branches inherit an explicit snapshot')
        if self.db.one('SELECT 1 FROM memory_domains WHERE id=?',(parent,)):raise CoreError('memory_invalid','Nested domains are not supported')
        if kind=='branch' and parent=='personal':raise CoreError('memory_invalid','A branch belongs to a project')
        ident='domain-'+uuid.uuid4().hex
        with self.db.transaction() as tx:
            if tx.execute('SELECT count(*) FROM memory_domains WHERE archived=0').fetchone()[0]>=100:raise CoreError('memory_capacity','Domain limit reached')
            tx.execute('INSERT INTO memory_domains VALUES(?,?,?,?,1,0,?)',(ident,parent,kind,name.strip(),time.time()))
            if snapshot:
                for typ,table,predicate in (('fact','facts','deleted=0'),('source','knowledge_sources',"status!='deleted'")):
                    for row in tx.execute(f'SELECT * FROM {table} WHERE scope=? AND {predicate}',(parent,)).fetchall():
                        record(tx,typ,row)
                        tx.execute('INSERT INTO memory_snapshots VALUES(?,?,?,?)',(ident,typ,row['id'],row['revision']))
            Facts.bump(tx)
        return self.get(ident)

    def archive(self,ident,revision,archived):
        if type(revision) is not int or type(archived) is not bool:raise CoreError('memory_invalid','Invalid domain revision')
        with self.db.transaction() as tx:
            if tx.execute('UPDATE memory_domains SET archived=?,revision=revision+1 WHERE id=? AND revision=?',(int(archived),ident,revision)).rowcount!=1:
                raise CoreError('conflict','Domain changed')
            Facts.bump(tx)
        return {'archived':archived}

    def inherited(self,scope,provider,selectors=None,fragments=True):
        domain=self.db.one("SELECT * FROM memory_domains WHERE id=? AND archived=0 AND kind='branch'",(scope,))
        if not domain:return []
        from modules.context_knowledge.memory import Memory
        from modules.context_knowledge.knowledge import Knowledge, fragments as split
        parent=domain['parent'];facts={r['id']:r for r in Memory(self.db).eligible(parent,provider,True,selectors) if r['scope']==parent}
        sources={r['id']:r['revision'] for r in Knowledge(self.db).references(parent,provider)}
        shadows={r['key'] for r in self.db.all('SELECT key FROM facts WHERE scope=?',(scope,))}
        source_shadows={r['parent_id'] for r in self.db.all('SELECT parent_id FROM memory_source_branches WHERE domain_id=?',(scope,))}
        rows=[]
        for snap in self.db.all('SELECT * FROM memory_snapshots WHERE domain_id=?',(scope,)):
            if snap['kind']=='fact':
                current=facts.get(snap['id'])
                if not current or current['key'] in shadows:continue
            else:
                if snap['id'] not in sources or snap['id'] in source_shadows:continue
                current=Knowledge(self.db).detail(parent,snap['id'])
            old=self.db.one('SELECT body FROM memory_history WHERE kind=? AND id=? AND revision=?',(snap['kind'],snap['id'],snap['revision']))
            if not old:continue
            body=decode(old['body'])
            if not fragments:rows.append({'id':snap['id'],'revision':snap['revision']});continue
            if snap['kind']=='fact':
                rows.append(current|body|{'revision':snap['revision'],'snapshot_domain':scope,'scope':scope})
            else:
                for start,end,first,last,text in split(body['text']):
                    rows.append({'id':snap['id']+':'+str(start),'revision':snap['revision'],'key':body['title'],'value':text,'kind':'source','expires':None,
                                 'evidence':{'source_id':snap['id'],'revision':snap['revision'],'start':start,'end':end,'line_start':first,'line_end':last,
                                             'trust':'historical_reference_unverified','snapshot_domain':scope,'source_scope':parent}})
        return rows

    def historical_source(self,scope,ident,revision):
        domain=self.get(scope)
        if not self.db.one("SELECT 1 FROM memory_snapshots WHERE domain_id=? AND kind='source' AND id=? AND revision=?",(scope,ident,revision)):
            raise CoreError('memory_missing','Source is not in this snapshot')
        if not self.db.one("SELECT 1 FROM knowledge_sources WHERE id=? AND scope=? AND status!='deleted'",(ident,domain['parent'])):
            raise CoreError('memory_missing','Original source was forgotten')
        old=self.db.one("SELECT body FROM memory_history WHERE kind='source' AND id=? AND revision=?",(ident,revision))
        if not old:raise CoreError('memory_missing','Source version unavailable')
        return decode(old['body'])|{'id':ident,'revision':revision,'scope':scope,'historical':True}
