"""Owner-imported text sources, revisioned fragments and replaceable local FTS.

Sources are references, never verified facts or executable instructions. No file
system access, third-party parser, remote fetch, model or implicit sharing.
"""
import bisect
import re
import sqlite3
import time
import uuid

from modules.context_knowledge import Facts, source_policy
from modules.context_knowledge.retrieval import lexical, tokens, query_words
from modules.context_knowledge.history import record, changed
from sdk.protocol import CoreError, contract

VERSION = 'knowledge-library-1.2.0'
MAX_BYTES = 80000
MAX_SOURCES = 200
SLOTS = ('knowledge_fts_a', 'knowledge_fts_b')


def fragments(text):
    lines = [0] + [m.end() for m in re.finditer('\n', text)]
    start = 0
    while start < len(text):
        end = min(start + 560, len(text))
        if end < len(text):
            split = text.rfind('\n', start + 280, end)
            if split >= 0: end = split + 1
        if text[start:end].strip():
            yield (start, end, bisect.bisect_right(lines, start), bisect.bisect_right(lines, end-1), text[start:end])
        start = end


def terms(text):
    return ' '.join(term for term, count in tokens(text).items() for _ in range(min(count, 8)))


class Knowledge:
    def __init__(self, db): self.db = db

    def epoch(self): return int(self.db.one("SELECT value FROM meta WHERE key='knowledge_epoch'")['value'])

    def slot(self):
        value = self.db.one("SELECT value FROM meta WHERE key='knowledge_index'")['value']
        return value if value in SLOTS else None

    def list(self, scope):
        rows = self.db.all("SELECT s.id,s.scope,s.title,s.revision,s.status,s.bytes,s.updated,count(c.id) AS chunks "
                           "FROM knowledge_sources s LEFT JOIN knowledge_chunks c ON c.source_id=s.id "
                           "WHERE s.scope=? AND s.status!='deleted' GROUP BY s.id ORDER BY s.updated DESC", (scope,))
        for r in rows: r['providers'] = source_policy.destinations(self.db,r['id'])
        return rows

    def detail(self, scope, ident):
        row = self.db.one("SELECT * FROM knowledge_sources WHERE id=? AND scope=? AND status!='deleted'", (ident, scope))
        if not row: raise CoreError('knowledge_missing', 'Source unavailable')
        row['providers'] = source_policy.destinations(self.db,ident)
        return row

    @staticmethod
    def validate(item, revision):
        contract('knowledge-source',item)
        if (not isinstance(item, dict) or set(item) != {'id','scope','title','text','providers','paused'}
            or type(revision) is not int or revision < 0 or type(item['paused']) is not bool
            or any(not isinstance(item[k], str) for k in ('id','scope','title','text'))):
            raise CoreError('knowledge_invalid', 'Invalid source edit')
        if (not 1 <= len(item['title'].strip()) <= 160 or not item['text'].strip()
            or len(item['text'].encode('utf-8')) > MAX_BYTES or '\x00' in item['text']
            or any(ord(c) < 32 and c not in '\t\r\n' for c in item['text'])):
            raise CoreError('knowledge_invalid', 'Use plain UTF-8 text, at most 80,000 bytes')
        p = item['providers']
        if not isinstance(p, list) or len(p)>32 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',x) for x in p) or len(p)!=len(set(p)):
            raise CoreError('knowledge_invalid', 'Invalid destinations')

    def save(self, item, revision):
        self.validate(item, revision)
        parts = list(fragments(item['text']))
        with self.db.transaction() as tx:return self.save_in(tx,item,revision,parts)

    def save_in(self,tx,item,revision,parts=None):
        self.validate(item,revision)
        parts=list(fragments(item['text'])) if parts is None else parts;now=time.time()
        old = tx.execute('SELECT * FROM knowledge_sources WHERE id=?', (item['id'],)).fetchone() if item['id'] else None
        if item['id'] and (not old or old['scope'] != item['scope'] or old['status']=='deleted'):
            raise CoreError('knowledge_missing', 'Source unavailable; deleted IDs cannot be reused')
        if revision != (old['revision'] if old else 0): raise CoreError('conflict', 'Source revision changed')
        if not old:
            if tx.execute("SELECT count(*) FROM knowledge_sources WHERE status!='deleted'").fetchone()[0] >= MAX_SOURCES:
                raise CoreError('knowledge_capacity', 'Initial library limit reached')
            # Idempotent identical imports within one scope, without widening existing policy.
            duplicate=tx.execute("SELECT id FROM knowledge_sources WHERE scope=? AND title=? AND text=? AND status!='deleted'", (item['scope'],item['title'].strip(),item['text'])).fetchone()
            if duplicate:return {'id':duplicate['id'],'existing':True,'version':VERSION}
        ident = old['id'] if old else 'source-' + uuid.uuid4().hex
        record(tx,'source',old)
        rev = revision + 1
        tx.execute('INSERT INTO knowledge_sources VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,text=excluded.text,revision=excluded.revision,status=excluded.status,bytes=excluded.bytes,updated=excluded.updated',
                   (ident,item['scope'],item['title'].strip(),item['text'],rev,'paused' if item['paused'] else 'active',len(item['text'].encode()),now,now))
        self.remove_index(tx,ident)
        tx.execute('DELETE FROM knowledge_chunks WHERE source_id=?',(ident,))
        tx.execute('DELETE FROM knowledge_destinations WHERE source_id=?',(ident,))
        tx.executemany('INSERT INTO knowledge_destinations VALUES(?,?)',[(ident,p) for p in item['providers']])
        for start,end,line_start,line_end,text in parts:
            tx.execute('INSERT INTO knowledge_chunks(id,source_id,revision,start,end,line_start,line_end,text) VALUES(?,?,?,?,?,?,?,?)',
                       ('chunk-'+uuid.uuid4().hex,ident,rev,start,end,line_start,line_end,text))
        self.add_index(tx,ident)
        self.changed(tx,ident,rev,'updated' if old else 'imported',len(parts))
        changed(tx,'source',ident)
        return {'id':ident,'revision':rev,'chunks':len(parts),'version':VERSION}

    def changed(self,tx,ident,revision,operation,count):
        # Source changes revoke derived knowledge in the same transaction. Manual
        # owner corrections have another provenance and are never silently erased.
        tx.execute('DELETE FROM knowledge_vectors WHERE source_id=?',(ident,))
        claims=tx.execute("SELECT id,fact_id FROM knowledge_claims WHERE source_id=? AND state IN ('pending','accepted')",(ident,)).fetchall()
        for claim in claims:
            if claim['fact_id']:
                changed=tx.execute("UPDATE facts SET deleted=1,value='',source='',revision=revision+1 WHERE id=? AND source=? AND deleted=0",
                                   (claim['fact_id'],'knowledge:'+claim['id'])).rowcount
                if changed:tx.execute('DELETE FROM memory_usage WHERE fact_id=?',(claim['fact_id'],))
        tx.execute("UPDATE knowledge_claims SET state='withdrawn',quote='',key='',revision=revision+1 WHERE source_id=? AND state IN ('pending','accepted')",(ident,))
        tx.execute('INSERT INTO knowledge_changes(source_id,revision,operation,chunks,occurred) VALUES(?,?,?,?,?)',(ident,revision,operation,count,time.time()))
        tx.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='knowledge_epoch'")
        Facts.bump(tx)
        # Parent tombstones erase derivative branch bodies and their claims in
        # this transaction, including archived branches and restored bundles.
        if tx.execute("SELECT status FROM knowledge_sources WHERE id=?",(ident,)).fetchone()[0]=='deleted':
            for child in tx.execute("SELECT s.scope,s.id,s.revision FROM memory_source_branches b JOIN knowledge_sources s ON s.id=b.source_id WHERE b.parent_id=? AND s.status!='deleted'",(ident,)).fetchall():
                self.delete_in(tx,child['scope'],child['id'],child['revision'])

    def remove_index(self,tx,ident):
        # Remove both live and shadow copies so a pending rebuild cannot retain deleted text.
        for slot in SLOTS:
            if tx.execute("SELECT 1 FROM sqlite_master WHERE name=?",(slot,)).fetchone():
                try:tx.execute(f'DELETE FROM {slot} WHERE rowid IN (SELECT seq FROM knowledge_chunks WHERE source_id=?)',(ident,))
                except sqlite3.DatabaseError:
                    tx.execute(f'DROP TABLE {slot}')
                    tx.execute("UPDATE meta SET value='' WHERE key='knowledge_index' AND value=?",(slot,))

    def add_index(self,tx,ident):
        slot=self.slot()
        if not slot:return
        try:
            for row in tx.execute('SELECT c.seq,c.text,s.title FROM knowledge_chunks c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.source_id=?',(ident,)).fetchall():
                tx.execute(f'INSERT INTO {slot}(rowid,terms) VALUES(?,?)',(row['seq'],terms(row['title']+' '+row['text'])))
        except sqlite3.DatabaseError:
            tx.execute("UPDATE meta SET value='' WHERE key='knowledge_index'")

    def delete(self,scope,ident,revision):
        if type(revision) is not int:raise CoreError('knowledge_invalid','Invalid revision')
        with self.db.transaction() as tx:return self.delete_in(tx,scope,ident,revision)

    def delete_in(self,tx,scope,ident,revision):
        row=tx.execute("SELECT revision FROM knowledge_sources WHERE id=? AND scope=? AND status!='deleted'",(ident,scope)).fetchone()
        if not row or row['revision']!=revision:raise CoreError('conflict','Source changed')
        self.remove_index(tx,ident)
        count=tx.execute('DELETE FROM knowledge_chunks WHERE source_id=?',(ident,)).rowcount
        tx.execute('DELETE FROM knowledge_destinations WHERE source_id=?',(ident,))
        tx.execute("UPDATE knowledge_sources SET title='',text='',bytes=0,status='deleted',revision=revision+1,updated=? WHERE id=?",(time.time(),ident))
        self.changed(tx,ident,revision+1,'deleted',count)
        return {'deleted':True,'cleared_chunks':count,'historical_outputs_cleared':False,'version':VERSION}

    @staticmethod
    def permitted():
        return "s.scope=? AND "+source_policy.permitted()

    def references(self,scope,provider):
        return self.db.all('SELECT s.id,s.revision FROM knowledge_sources s WHERE '+self.permitted(),(scope,provider))

    def search(self,scope,provider,query):
        if not query.strip():return [],{'mode':'not_requested'}
        base='SELECT c.*,s.title FROM knowledge_chunks c JOIN knowledge_sources s ON s.id=c.source_id '
        slot=self.slot();words=query_words(query)
        mode='fts5' if slot and words else 'scan'
        try:
            if mode=='fts5':
                match=' OR '.join('"'+w.replace('"','""')+'"' for w in words)
                rows=self.db.all(base+f'JOIN {slot} ON {slot}.rowid=c.seq WHERE '+self.permitted()+f' AND {slot} MATCH ? ORDER BY bm25({slot}),c.seq LIMIT 64',(scope,provider,match))
            else: rows=self.db.all(base+'WHERE '+self.permitted(),(scope,provider))
        except sqlite3.DatabaseError:
            mode='scan_fallback';rows=self.db.all(base+'WHERE '+self.permitted(),(scope,provider))
        items=[{'id':r['id'],'revision':r['revision'],'key':r['title'],'value':r['text'],'kind':'source','expires':None,
                'evidence':{'source_id':r['source_id'],'chunk_id':r['id'],'revision':r['revision'],'start':r['start'],'end':r['end'],
                            'line_start':r['line_start'],'line_end':r['line_end'],'trust':'reference_unverified'}} for r in rows]
        scores=lexical(items,query)
        items=sorted((r for r in items if scores[r['id']]>0),key=lambda r:(-scores[r['id']],r['id']))[:64]
        return items,{'mode':mode,'candidates':len(items),'version':VERSION}

    def rebuild(self,checkpoint=lambda:None,progress=lambda value:None):
        """Build a bounded snapshot, then replay current source deltas before switching."""
        with self.db.read_snapshot():
            watermark=self.db.one('SELECT coalesce(max(seq),0) AS n FROM knowledge_changes')['n']
            ceiling=self.db.one('SELECT coalesce(max(seq),0) AS n FROM knowledge_chunks')['n']
        slot=SLOTS[1] if self.slot()==SLOTS[0] else SLOTS[0]
        with self.db.transaction() as tx:
            tx.execute(f'DROP TABLE IF EXISTS {slot}')
            tx.execute(f'CREATE VIRTUAL TABLE {slot} USING fts5(terms, tokenize="unicode61")')
        cursor=0;count=0
        try:
            while True:
                checkpoint()
                rows=self.db.all('SELECT c.seq,c.text,s.title FROM knowledge_chunks c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.seq>? AND c.seq<=? ORDER BY c.seq LIMIT 8',(cursor,ceiling))
                if not rows:break
                prepared=[(r['seq'],terms(r['title']+' '+r['text'])) for r in rows]
                with self.db.transaction() as tx:
                    tx.executemany(f'INSERT INTO {slot}(rowid,terms) VALUES(?,?)',prepared)
                cursor=rows[-1]['seq'];count+=len(rows);progress(count)
                time.sleep(.002)  # Yield the GIL/CPU between bounded batches to foreground work.
            # Continuous writers get a bounded retry failure; an obsolete shadow
            # is never made active. Model inference is not part of this rebuild.
            for attempt in range(3):
                checkpoint()
                with self.db.read_snapshot():
                    current=self.epoch()
                    dirty=[r['source_id'] for r in self.db.all('SELECT DISTINCT source_id FROM knowledge_changes WHERE seq>?',(watermark,))]
                    replay=[]
                    for ident in dirty:
                        checkpoint()
                        replay.extend((r['seq'],terms(r['title']+' '+r['text'])) for r in self.db.all(
                            "SELECT c.seq,c.text,s.title FROM knowledge_chunks c JOIN knowledge_sources s ON s.id=c.source_id WHERE c.source_id=? AND s.status!='deleted' AND c.revision=s.revision",(ident,)))
                checkpoint()
                with self.db.transaction() as tx:
                    if self.epoch()!=current:continue
                    # A deletion may race a prepared initial batch. Purge orphan
                    # rowids so old text staged after its deletion cannot survive.
                    tx.execute(f'DELETE FROM {slot} WHERE rowid NOT IN (SELECT seq FROM knowledge_chunks)')
                    for ident in dirty:tx.execute(f'DELETE FROM {slot} WHERE rowid IN (SELECT seq FROM knowledge_chunks WHERE source_id=?)',(ident,))
                    tx.executemany(f'INSERT INTO {slot}(rowid,terms) VALUES(?,?)',replay)
                    actual=tx.execute(f'SELECT count(*) FROM {slot}').fetchone()[0]
                    expected=tx.execute('SELECT count(*) FROM knowledge_chunks').fetchone()[0]
                    if actual!=expected:raise CoreError('knowledge_changed','Shadow projection coverage changed')
                    tx.execute("UPDATE meta SET value=? WHERE key='knowledge_index'",(slot,))
                    other=SLOTS[1] if slot==SLOTS[0] else SLOTS[0]
                    tx.execute(f'DROP TABLE IF EXISTS {other}')
                return {'indexed_chunks':actual,'epoch':current,'mode':'fts5','version':VERSION,
                        'index_version':'knowledge-fts-incremental-1.0.0','replayed_sources':len(dirty),'reconcile_attempts':attempt+1}
            raise CoreError('knowledge_changed','Sources keep changing; active projection preserved, retry later')
        except BaseException:
            with self.db.transaction() as tx:tx.execute(f'DROP TABLE IF EXISTS {slot}')
            raise
