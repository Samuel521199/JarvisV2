"""Rebuildable local vectors. Authorization and source revision precede scoring.

No model dependency here: host supplies a bounded encoder. Little-endian float32
is portable across supported machines. Source ledger remains authoritative.
"""
from array import array
import heapq
import hashlib
import math
from pathlib import Path
import struct
import threading
import time

from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge import joint
from modules.context_knowledge import source_policy
from sdk.protocol import CoreError, digest

RECIPE = 'utf8-window-448b-400c-overlap-60c-title-48b-f32le-sha256-v2'


def windows(text):
    start=0
    while start<len(text):
        end=min(start+400,len(text))
        while len(text[start:end].encode('utf-8'))>448:end-=1
        if text[start:end].strip():yield start,end,text[start:end]
        if end==len(text):break
        start=max(start+1,end-60)


def passage(title,text):
    while len(title.encode('utf-8'))>48:title=title[:-1]
    return title+'\n'+text if title else text


def validate(vector,dimension):
    if len(vector)!=dimension or any(not math.isfinite(x) for x in vector) or not .98<=sum(x*x for x in vector)<=1.02:
        raise CoreError('knowledge_vector_invalid','Invalid normalized vector')


# Verified float32 vectors per (database, space). Checksums are verified and blobs
# unpacked once per table change instead of on every query. Loading runs on a
# background thread, so a foreground search never blocks on it: until the cache
# is warm it reports 'warming' and the caller keeps lexical retrieval.
# numpy is used when present (the optional local-embedding runtime pins it in
# the same interpreter); otherwise scoring stays pure standard library.
try:
    import numpy as _np
except ImportError:  # core installs stay standard-library only
    _np=None

_CACHE={}
_CACHE_GUARD=threading.Lock()
_CACHE_SPACES=4


class _Slot:
    def __init__(self):
        # data=(meta, vectors) is replaced as one tuple so a query never pairs
        # one load's chunk list with another load's vectors.
        self.stamp=None;self.data=([],None);self.error=None
        self.ready=threading.Event();self.loading=False


def _stamp(connection,space):
    return tuple(connection.execute('SELECT count(*),coalesce(max(rowid),0),total(rowid),total(start),total(end),'
                                    'total(length(vector)) FROM knowledge_vectors WHERE space=?',(space,)).fetchone())


def _load(slot,path,space,dimension):
    import sqlite3
    try:
        connection=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            connection.execute('BEGIN')  # one consistent snapshot for stamp and rows
            stamp=_stamp(connection,space);meta=[];values=[]
            for source_id,revision,start,end,blob in connection.execute(
                    'SELECT source_id,revision,start,end,vector FROM knowledge_vectors WHERE space=?',(space,)):
                meta.append((source_id,revision,start,end));values.append(unpack(blob,dimension))
            connection.execute('COMMIT')
        finally:connection.close()
        if _np is not None:
            vectors=_np.asarray(values,dtype=_np.float32).reshape(len(values),dimension)
        else:
            vectors=[array('f',v) for v in values]
        slot.data=(meta,vectors);slot.error=None;slot.stamp=stamp
    except CoreError:
        slot.error='corrupt';slot.stamp=None
    except Exception:
        slot.error='unavailable';slot.stamp=None
    finally:
        slot.loading=False;slot.ready.set()


def _slot(db,space,dimension,deadline):
    """Return a warm slot matching the current table, or None while it loads."""
    key=(str(Path(db.path).resolve()),space);stamp=_stamp(db.connection,space)
    with _CACHE_GUARD:
        slot=_CACHE.get(key)
        if slot is None:
            while len(_CACHE)>=_CACHE_SPACES:_CACHE.pop(next(iter(_CACHE)))
            slot=_CACHE[key]=_Slot()
        if slot.ready.is_set() and slot.stamp==stamp:return slot
        if not slot.loading:
            slot.loading=True;slot.ready.clear()
            threading.Thread(target=_load,args=(slot,db.path,space,dimension),daemon=True,name='jarvis-vector-cache').start()
    wait=30 if deadline is None else max(0,deadline-time.monotonic())
    if slot.ready.wait(wait) and (slot.stamp==stamp or slot.error):return slot
    return None


def warm(db,space,dimension):
    """Load the cache after an index build so the first foreground query is fast."""
    return _slot(db,space,dimension,None)


def pack(vector,dimension):
    validate(vector,dimension);raw=struct.pack('<'+'f'*dimension,*vector)
    return hashlib.sha256(raw).digest()+raw


def unpack(blob,dimension):
    if len(blob)!=32+4*dimension or hashlib.sha256(blob[32:]).digest()!=blob[:32]:
        raise CoreError('knowledge_vector_invalid','Embedding checksum mismatch; rebuild this projection')
    return struct.unpack('<'+'f'*dimension,blob[32:])


class Vectors:
    def __init__(self,db):self.db=db

    def status(self):
        active=self.db.one("SELECT value FROM meta WHERE key='knowledge_vector_active'")['value']
        row=self.db.one('SELECT * FROM knowledge_vector_spaces WHERE space=?',(active,))
        compatible=bool(row and row['space']==digest({'model':row['model_space'],'dimension':row['dimension'],'recipe':RECIPE}))
        staging=self.db.all("SELECT s.space,s.state,count(v.start) AS vectors FROM knowledge_vector_spaces s LEFT JOIN knowledge_vectors v ON v.space=s.space WHERE s.state='building' GROUP BY s.space")
        return {'active':row,'vectors':self.db.one('SELECT count(*) AS n FROM knowledge_vectors WHERE space=?',(active,))['n'],
                'stale':bool(row and (row['epoch']!=Knowledge(self.db).epoch() or not compatible)),
                'recipe_current':compatible,'staging':staging,'recipe':RECIPE}

    def build(self,model_space,dimension,encode,checkpoint=lambda:None,progress=lambda n:None):
        identity=digest({'model':model_space,'dimension':dimension,'recipe':RECIPE})
        epoch=Knowledge(self.db).epoch()
        with self.db.transaction() as tx:
            active=tx.execute("SELECT value FROM meta WHERE key='knowledge_vector_active'").fetchone()[0]
            tx.execute('DELETE FROM knowledge_vectors WHERE space NOT IN (?,?)',(active,identity))
            tx.execute('DELETE FROM knowledge_vector_spaces WHERE space NOT IN (?,?)',(active,identity))
            tx.execute('INSERT INTO knowledge_vector_spaces VALUES(?,?,?,?,?,?) ON CONFLICT(space) DO UPDATE SET state=excluded.state,updated=excluded.updated',
                       (identity,model_space,dimension,epoch,'building',time.time()))
        processed=0;encoded=0;replayed=set()
        def build_source(source):
            nonlocal processed,encoded
            existing=set()
            parts=list(windows(source['text']));expected_offsets={(p[0],p[1]) for p in parts}
            for r in self.db.all('SELECT start,end,vector FROM knowledge_vectors WHERE space=? AND source_id=? AND revision=?',
                                 (identity,source['id'],source['revision'])):
                try:
                    if (r['start'],r['end']) not in expected_offsets:raise CoreError('knowledge_vector_invalid','Projection offsets changed')
                    validate(unpack(r['vector'],dimension),dimension);existing.add(r['start'])
                except (CoreError,struct.error):pass  # Repair only invalid projection rows.
            with self.db.transaction() as tx:
                # Drop malformed rows, including out-of-range offsets, before reuse.
                for r in tx.execute('SELECT start FROM knowledge_vectors WHERE space=? AND source_id=? AND revision=?',
                                    (identity,source['id'],source['revision'])).fetchall():
                    if r['start'] not in existing:
                        tx.execute('DELETE FROM knowledge_vectors WHERE space=? AND source_id=? AND revision=? AND start=?',
                                   (identity,source['id'],source['revision'],r['start']))
            batch=[]
            def flush():
                nonlocal processed,encoded
                if not batch:return
                checkpoint();values=encode([passage(source['title'],v[2]) for v in batch])
                if len(values)!=len(batch):raise CoreError('knowledge_vector_invalid','Embedding count mismatch')
                packed=[]
                for (start,end,_),v in zip(batch,values):
                    packed.append((identity,source['id'],source['revision'],start,end,pack(v,dimension)))
                checkpoint()
                with self.db.transaction() as tx:
                    current=tx.execute('SELECT revision,status FROM knowledge_sources WHERE id=?',(source['id'],)).fetchone()
                    if not current or current['status']=='deleted' or current['revision']!=source['revision']:
                        # Source edits clear all their vectors in the source transaction.
                        # Never reinsert stale output from an already-running encoder.
                        batch.clear();return False
                    tx.executemany('INSERT OR REPLACE INTO knowledge_vectors VALUES(?,?,?,?,?,?)',packed)
                encoded+=len(batch);processed+=len(batch);progress(processed);batch.clear()
                time.sleep(.01)
                return True
            for part in parts:
                checkpoint()
                if part[0] in existing:processed+=1;progress(processed);continue
                batch.append(part)
                if len(batch)==4 and flush() is False:return
            flush()
        # One snapshot pass plus at most three catch-up passes. Valid batches are
        # reused after cancellation/restart; inference never holds a write lock.
        for attempt in range(4):
            checkpoint()
            with self.db.read_snapshot():
                epoch=Knowledge(self.db).epoch()
                sources=self.db.all("SELECT id,title,text,revision FROM knowledge_sources WHERE status!='deleted' ORDER BY id")
            for source in sources:
                if attempt:replayed.add(source['id'])
                build_source(source)
            checkpoint()
            expected=sum(sum(1 for _ in windows(s['text'])) for s in sources)
            with self.db.transaction() as tx:
                if Knowledge(self.db).epoch()!=epoch:continue
                tx.execute('DELETE FROM knowledge_vectors WHERE space=? AND NOT EXISTS('
                           "SELECT 1 FROM knowledge_sources s WHERE s.id=source_id AND s.revision=knowledge_vectors.revision AND s.status!='deleted')",(identity,))
                actual=tx.execute('SELECT count(*) FROM knowledge_vectors WHERE space=?',(identity,)).fetchone()[0]
                if actual!=expected:raise CoreError('knowledge_vector_invalid','Projection coverage is incomplete; resume repair')
                tx.execute("UPDATE knowledge_vector_spaces SET epoch=?,state='ready',updated=? WHERE space=?",(epoch,time.time(),identity))
                tx.execute("UPDATE meta SET value=? WHERE key='knowledge_vector_active'",(identity,))
                # Only projections retire; source revisions and tombstones stay authoritative.
                tx.execute('DELETE FROM knowledge_vectors WHERE space!=?',(identity,))
                tx.execute('DELETE FROM knowledge_vector_spaces WHERE space!=?',(identity,))
            warm(self.db,identity,dimension)  # build runs in the background; spare the first query the load
            return self.status()|{'build_version':'knowledge-vectors-incremental-1.0.0','encoded':encoded,
                                 'rechecked_sources':len(replayed),'reconcile_attempts':attempt}
        raise CoreError('knowledge_changed','Sources keep changing; active space preserved, resume later')

    def search(self,scope,provider,model_space,vector,deadline=None):
        state=self.status();active=state['active']
        if not active:return [],{'status':'not_built'}
        if active['model_space']!=model_space:return [],{'status':'space_changed'}
        if not state['recipe_current']:return [],{'status':'recipe_changed'}
        dimension=active['dimension'];validate(vector,dimension)
        scopes=joint.members(scope) or [scope]
        # Authorization first: only active, provider-permitted sources at their current revision.
        allowed={r['id']:r for r in self.db.all('SELECT s.id,s.revision,s.title,s.scope FROM knowledge_sources s WHERE s.scope IN ('
                                               +','.join('?' for _ in scopes)+') AND '+source_policy.permitted(),(*scopes,provider))}
        slot=_slot(self.db,active['space'],dimension,deadline)
        if slot is None:return [],{'status':'warming','scanned':0}
        if slot.error:return [],{'status':slot.error,'scanned':0}
        meta,vectors=slot.data;indexes=[i for i,(source_id,revision,_,_) in enumerate(meta)
                                if (source:=allowed.get(source_id)) is not None and source['revision']==revision]
        count=len(indexes)
        if deadline and time.monotonic()>deadline:return [],{'status':'timeout','scanned':0}
        # Keep the eight best by (score, source, offset): the same order as before caching.
        if _np is not None and count:
            scores=vectors[indexes]@_np.asarray(vector,dtype=_np.float32)
            floor=_np.partition(scores,-8)[-8] if count>8 else scores.min()
            scored=heapq.nlargest(8,((float(scores[j]),meta[indexes[j]][0],meta[indexes[j]][2],indexes[j])
                                     for j in _np.nonzero(scores>=floor)[0]))
        else:
            scored=[]
            for n,i in enumerate(indexes):
                if deadline and n%256==0 and time.monotonic()>deadline:return [],{'status':'timeout','scanned':n}
                entry=(math.sumprod(vector,vectors[i]),meta[i][0],meta[i][2],i)
                if len(scored)<8:heapq.heappush(scored,entry)
                elif entry>scored[0]:heapq.heapreplace(scored,entry)
        best=[]
        for score,_,_,i in scored:
            source_id,revision,start,end=meta[i];source=allowed[source_id]
            best.append((score,source_id,start,{'source_id':source_id,'revision':revision,'start':start,'end':end,
                                                 'title':source['title'],'scope':source['scope']}))
        best.sort(key=lambda r:r[:3],reverse=True)
        cutoff=max(.70,(best[0][0]-.025) if best else 1)
        rows=[]
        for score,ident,start,r in best:
            if score<cutoff:continue
            # Deduplicate overlapping windows; preserve exact offsets for citations.
            if any(x['evidence']['source_id']==ident and abs(x['evidence']['start']-start)<120 for x in rows):continue
            source=self.db.one('SELECT text,revision FROM knowledge_sources WHERE id=?',(ident,))
            if not source or source['revision']!=r['revision']:continue
            end=r['end'];text=source['text'];chunk=f"vector:{ident}:{r['revision']}:{start}"
            # Return the containing source fragment, not a contextless 120-character
            # vector window. Offsets still refer to the exact original revision.
            containing=self.db.one('SELECT * FROM knowledge_chunks WHERE source_id=? AND revision=? AND start<=? AND end>? ORDER BY start DESC LIMIT 1',
                                   (ident,r['revision'],start,start))
            if containing and containing['end']>=end:
                start,end,chunk=containing['start'],containing['end'],containing['id']
            else:
                # A match spanning a stored chunk boundary must retain the entire
                # matching window, with nearby context and exact source offsets.
                start=max(0,start-80);end=min(len(text),start+560)
                chunk=f"vector:{ident}:{r['revision']}:{start}:{end}"
            if any(x['evidence']['chunk_id']==chunk for x in rows):continue
            rows.append({'id':chunk,'revision':r['revision'],'key':r['title'],'value':text[start:end],
                         'kind':'source','expires':None,'semantic_score':score,'origin_scope':r['scope'],
                         'evidence':{'source_id':ident,'chunk_id':chunk,'revision':r['revision'],'start':start,'end':end,
                                     'line_start':text.count('\n',0,start)+1,'line_end':text.count('\n',0,end-1)+1,'trust':'reference_unverified'}})
            if len(rows)==4:break
        return rows,{'status':'ready','space':active['space'],'scanned':count,'candidates':len(rows),'stale':state['stale']}
