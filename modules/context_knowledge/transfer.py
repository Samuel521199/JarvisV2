"""Portable source ledger, with explicit preview and tombstone-preserving restore.

This is a local import/export format, not an authenticated synchronization protocol.
Indexes, secrets, model grants and conversations are deliberately not portable here.
"""
import json
import re
import time

from modules.context_knowledge.knowledge import Knowledge, MAX_SOURCES, SLOTS, VERSION, fragments
from modules.context_knowledge.history import record, changed
from sdk.protocol import CoreError, canonical, digest

MAX_TRANSFER_BYTES = 40000000
FORMAT = 'jarvis.knowledge-bundle.v1'


def decode_transfer(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_TRANSFER_BYTES:
        raise CoreError('knowledge_transfer_size', 'Bundle exceeds transfer limit')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise CoreError('invalid_json', 'Duplicate bundle key')
            out[key] = value
        return out
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        canonical(value).encode('utf-8')
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise CoreError('invalid_json', 'Invalid transfer JSON') from None


def validate_bundle(bundle):
    def bad(): raise CoreError('knowledge_bundle_invalid', 'Unsupported or damaged source bundle')
    if not isinstance(bundle, dict) or set(bundle) != {'format','scope','sources','tombstones','checksum'}: bad()
    if bundle['format'] != FORMAT or not isinstance(bundle['scope'], str) or not 1 <= len(bundle['scope']) <= 120: bad()
    if not isinstance(bundle['sources'], list) or len(bundle['sources']) > MAX_SOURCES: bad()
    if not isinstance(bundle['tombstones'], list) or len(bundle['tombstones']) > 10000: bad()
    seen = set()
    for deleted, rows in ((False,bundle['sources']), (True,bundle['tombstones'])):
        for row in rows:
            if not isinstance(row, dict) or set(row) != ({'id','revision'} if deleted else {'id','revision','title','text','providers','paused'}): bad()
            if (not isinstance(row['id'],str) or not re.fullmatch(r'source-[a-f0-9]{32}',row['id'])
                or row['id'] in seen or type(row['revision']) is not int or not 1 <= row['revision'] <= 2**53-2): bad()
            seen.add(row['id'])
            if not deleted:
                Knowledge.validate({k:v for k,v in row.items() if k!='revision'} | {'scope':bundle['scope']}, row['revision'])
    if not isinstance(bundle['checksum'],str) or bundle['checksum'] != digest({k:v for k,v in bundle.items() if k!='checksum'}): bad()
    return bundle


class Transfer:
    def __init__(self, db): self.db = db; self.library = Knowledge(db)

    def export(self, scope):
        from modules.context_knowledge.source_policy import require_complete_export
        require_complete_export(self.db,scope)
        # One read snapshot: sources, permissions and tombstones cannot mix revisions.
        self.db.connection.execute('BEGIN')
        try:
            bundle=self.snapshot(scope)
            self.db.connection.execute('COMMIT')
            return bundle
        except BaseException:self.db.connection.execute('ROLLBACK');raise

    def snapshot(self,scope):
        sources=[];tombstones=[]
        for row in self.db.all('SELECT * FROM knowledge_sources WHERE scope=? ORDER BY id',(scope,)):
            ref={k:row[k] for k in ('id','revision')}
            if row['status']=='deleted':tombstones.append(ref);continue
            sources.append(ref | {k:row[k] for k in ('title','text')} | {
                'paused':row['status']=='paused',
                'providers':[p['provider'] for p in self.db.all('SELECT provider FROM knowledge_destinations WHERE source_id=? ORDER BY provider',(row['id'],))]})
        bundle={'format':FORMAT,'scope':scope,'sources':sources,'tombstones':tombstones}
        bundle['checksum']=digest(bundle)
        validate_bundle(bundle)
        if len(canonical(bundle).encode()) > MAX_TRANSFER_BYTES-1000:
            raise CoreError('knowledge_transfer_size','Bundle exceeds transfer limit')
        return bundle

    def plan(self, scope, bundle):
        validate_bundle(bundle)
        actions=[];conflicts=[]
        for deleted, rows in ((True,bundle['tombstones']),(False,bundle['sources'])):
            for row in rows:
                old=self.db.one('SELECT * FROM knowledge_sources WHERE id=?',(row['id'],))
                reason=None
                if old and old['scope']!=scope:action='conflict';reason='different_scope'
                elif old and old['status']=='deleted':action='skip_deleted'
                elif deleted:action='delete' if old else 'tombstone'
                elif not old:action='create'
                elif old['text']==row['text'] and old['title']==row['title']:action='unchanged'
                elif row['revision']>old['revision']:action='replace'
                else:action='conflict';reason='newer_or_divergent_local'
                item={'id':row['id'],'action':action,'revision':row['revision'],
                      'title':row.get('title') or (old['title'] if old else '')}
                if reason:item['reason']=reason;conflicts.append(item)
                actions.append(item)
        active=self.db.one("SELECT count(*) AS n FROM knowledge_sources WHERE status!='deleted'")['n']
        counts={name:sum(a['action']==name for a in actions) for name in ('create','replace','delete','tombstone','unchanged','skip_deleted','conflict')}
        capacity_ok=active+counts['create']-counts['delete']<=MAX_SOURCES
        epoch=self.library.epoch()
        return {'token':digest({'scope':scope,'bundle':bundle['checksum'],'epoch':epoch}),
                'source_scope':bundle['scope'],'target_scope':scope,'epoch':epoch,'counts':counts,
                'actions':actions,'can_apply':not conflicts and capacity_ok,'capacity_ok':capacity_ok,
                'restored_policy':'paused_without_destinations','version':VERSION}

    def preview(self, scope, bundle):
        self.db.connection.execute('BEGIN')
        try:return self.plan(scope,bundle)
        finally:self.db.connection.execute('ROLLBACK')

    def restore(self, scope, bundle, token):
        validate_bundle(bundle)
        with self.db.transaction() as tx:
            plan=self.plan(scope,bundle)
            if token!=plan['token']:raise CoreError('conflict','Preview is stale; preview again')
            if not plan['can_apply']:raise CoreError('knowledge_restore_conflict','Resolve restore conflicts first')
            return self.apply(tx,scope,bundle,plan)

    def apply(self,tx,scope,bundle,plan):
        # Bounded parsing never executes the imported text.
        parts={r['id']:list(fragments(r['text'])) for r in bundle['sources']}
        rows={r['id']:r for r in bundle['sources']+bundle['tombstones']}
        now=time.time()
        changes=[a for a in plan['actions'] if a['action'] in {'create','replace','delete','tombstone'}]
        if changes:
            # FTS is disposable. Rebuild outside this atomic ledger transaction.
            tx.execute("UPDATE meta SET value='' WHERE key='knowledge_index'")
            for slot in SLOTS:tx.execute(f'DROP TABLE IF EXISTS {slot}')
        for action in changes:
            row=rows[action['id']];ident=row['id'];deleted=action['action'] in {'delete','tombstone'}
            old=tx.execute('SELECT * FROM knowledge_sources WHERE id=?',(ident,)).fetchone()
            if old and old['status']!='deleted':record(tx,'source',old)
            revision=max(row['revision'],old['revision']+1 if old else 1)
            tx.execute('INSERT INTO knowledge_sources VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,text=excluded.text,revision=excluded.revision,status=excluded.status,bytes=excluded.bytes,updated=excluded.updated',
                (ident,scope,'' if deleted else row['title'],'' if deleted else row['text'],revision,
                 'deleted' if deleted else 'paused',0 if deleted else len(row['text'].encode()),now,now))
            tx.execute('DELETE FROM knowledge_destinations WHERE source_id=?',(ident,))
            tx.execute('DELETE FROM knowledge_chunks WHERE source_id=?',(ident,))
            if not deleted:
                import uuid
                tx.executemany('INSERT INTO knowledge_chunks(id,source_id,revision,start,end,line_start,line_end,text) VALUES(?,?,?,?,?,?,?,?)',
                    [('chunk-'+uuid.uuid4().hex,ident,revision,*p) for p in parts[ident]])
            self.library.changed(tx,ident,revision,'restore_'+action['action'],0 if deleted else len(parts[ident]))
            if not deleted:changed(tx,'source',ident)
        return {'applied':len(changes),'counts':plan['counts'],'requires_index_rebuild':bool(changes),
                'restored_policy':'paused_without_destinations','version':VERSION}
