"""Extractive knowledge compilation with exact evidence and explicit owner review."""
import time
import uuid

from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.memory import Memory
from sdk.protocol import CoreError


class Claims:
    def __init__(self,db):self.db=db

    def compile(self,scope,ident,revision):
        if type(revision) is not int or revision<1:raise CoreError('knowledge_invalid','Invalid source revision')
        with self.db.transaction() as tx:
            source=Knowledge(self.db).detail(scope,ident)
            if source['revision']!=revision:raise CoreError('conflict','Source changed')
            if source['status']!='active':raise CoreError('knowledge_paused','Resume the source before compilation')
            rows=self.db.all('SELECT * FROM knowledge_chunks WHERE source_id=? ORDER BY start',(ident,))
            pending=tx.execute("SELECT count(*) FROM knowledge_claims WHERE state='pending'").fetchone()[0]
            added=0
            for r in rows:
                if tx.execute('SELECT 1 FROM knowledge_claims WHERE source_id=? AND source_revision=? AND start=? AND end=?',
                              (ident,revision,r['start'],r['end'])).fetchone():continue
                if pending+added>=200:raise CoreError('memory_capacity','Review pending knowledge first')
                tx.execute('INSERT INTO knowledge_claims(id,source_id,source_revision,start,end,key,quote,state,created) VALUES(?,?,?,?,?,?,?,\'pending\',?)',
                           ('claim-'+uuid.uuid4().hex,ident,revision,r['start'],r['end'],source['title'][:50]+(' · '+str(r['start']+1) if len(rows)>1 else ''),r['text'],time.time()))
                added+=1
            return {'added':added,'method':'extractive-v1','model_calls':0,'verified':False}

    def model_candidates(self,scope,ident,revision,provider,output,job_id=None,window=None):
        """Models only nominate exact evidence; no generated claim is trusted as fact.

        window=(offset, length) limits matching to the part of a long source the model
        actually saw; a quote must then be unique inside that part.
        """
        if not isinstance(output,dict) or set(output)!={'claims'} or not isinstance(output['claims'],list) or len(output['claims'])>24:
            raise CoreError('knowledge_extraction_invalid','Expected at most 24 exact-source candidates')
        source=Knowledge(self.db).detail(scope,ident)
        if source['revision']!=revision or source['status']!='active' or provider not in source['providers']:
            raise CoreError('knowledge_changed','Source or permission changed')
        prepared=[];seen=set()
        for value in output['claims']:
            if (not isinstance(value,dict) or set(value)!={'key','quote'} or not isinstance(value['key'],str)
                or not 1<=len(value['key'].strip())<=120 or not isinstance(value['quote'],str) or not 8<=len(value['quote'])<=4000):
                raise CoreError('knowledge_extraction_invalid','Invalid exact-source candidate')
            low,high=(0,len(source['text'])) if window is None else (window[0],window[0]+window[1])
            start=source['text'].find(value['quote'],low,high);end=start+len(value['quote'])
            if start<0 or source['text'].find(value['quote'],start+1,high)>=0 or (start,end) in seen:
                raise CoreError('knowledge_extraction_invalid','Candidate is fabricated, ambiguous or duplicated')
            seen.add((start,end));prepared.append((start,end,value['key'].strip(),value['quote']))
        with self.db.transaction() as tx:
            current=Knowledge(self.db).detail(scope,ident)
            if job_id:
                job=tx.execute('SELECT cancel,state FROM knowledge_extractions WHERE id=?',(job_id,)).fetchone()
                if not job or job['cancel'] or job['state']!='running':raise CoreError('knowledge_cancelled','Extraction cancelled before commit')
            if current['revision']!=revision or current['status']!='active' or provider not in current['providers']:
                raise CoreError('knowledge_changed','Source changed before candidate commit')
            pending=tx.execute("SELECT count(*) FROM knowledge_claims WHERE state='pending'").fetchone()[0];added=0
            for start,end,key,quote in prepared:
                if tx.execute('SELECT 1 FROM knowledge_claims WHERE source_id=? AND source_revision=? AND start=? AND end=?',(ident,revision,start,end)).fetchone():continue
                if pending+added>=200:raise CoreError('memory_capacity','Review existing candidates first')
                tx.execute("INSERT INTO knowledge_claims(id,source_id,source_revision,start,end,key,quote,state,created) VALUES(?,?,?,?,?,?,?,'pending',?)",
                           ('claim-'+uuid.uuid4().hex,ident,revision,start,end,key,quote,time.time()));added+=1
            return {'added':added,'method':'model_exact_quote_v1','verified':False}

    def list(self,scope):
        return self.db.all('SELECT c.*,s.title,s.status AS source_status FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id '
                           "WHERE s.scope=? ORDER BY CASE WHEN c.state='pending' THEN 0 ELSE 1 END,c.created DESC LIMIT 200",(scope,))

    def accept(self,scope,ident,revision,item,fact_revision):
        if not isinstance(item,dict) or type(revision) is not int or item.get('scope')!=scope:raise CoreError('memory_invalid','Invalid knowledge review')
        return Memory(self.db).save(item,fact_revision,source='knowledge:'+ident,source_candidate={'id':ident,'revision':revision})

    def dismiss(self,scope,ident,revision):
        if not isinstance(ident,str) or type(revision) is not int or revision<1:raise CoreError('knowledge_invalid','Invalid candidate revision')
        with self.db.transaction() as tx:
            if tx.execute("UPDATE knowledge_claims SET state='dismissed',key='',quote='',revision=revision+1 WHERE id=? AND revision=? AND state='pending' "
                          'AND source_id IN (SELECT id FROM knowledge_sources WHERE scope=?)',(ident,revision,scope)).rowcount!=1:
                raise CoreError('conflict','Knowledge candidate changed')
        return {'dismissed':True}
