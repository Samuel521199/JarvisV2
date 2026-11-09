"""Personal durable commitments; no executor, model, external notification or grant.

Schema 1 remains readable. A mail-source association atomically advances to 2;
unknown versions are never written. Revision is the user's schedule generation.
"""
from contextlib import contextmanager
from datetime import datetime
import re
import sqlite3
import time

from control.paths import child, data_root
from sdk.protocol import CoreError, canonical, decode, digest


def invalid(message): raise CoreError('commitment_invalid', message)


def check_compatible(root):
    path=child(data_root(root),'state/commitments.sqlite3')
    if not path.exists(): return
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
    try:
        version=db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (1,2):
            raise CoreError('commitment_schema','Unsupported commitment schema')
        db.execute('SELECT id,title,source,due_text,due_at,revision,status,posted_at,created,updated FROM commitments LIMIT 0')
        if version==2:db.execute('SELECT id,reference,family FROM mail_sources LIMIT 0')
    finally: db.close()


def due(value):
    if value is None: return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)', value):
        invalid('Use an exact date/time with seconds and an explicit UTC offset')
    try:
        if value[-1] != 'Z' and (int(value[-2:]) > 59 or int(value[-5:-3]) > 14 or (int(value[-5:-3]) == 14 and int(value[-2:]) != 0)):
            invalid('Invalid UTC offset')
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if not 2000 <= parsed.year <= 2100 or abs(parsed.utcoffset().total_seconds()) > 14*3600:
            invalid('Time is outside supported bounds')
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError): invalid('Invalid date/time')


class Commitments:
    def __init__(self, root):
        self.path = child(data_root(root), 'state/commitments.sqlite3')
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            with self.tx():
                version = self.db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1, 2): raise CoreError('commitment_schema', 'Unsupported commitment schema; no changes made')
                if version==2:self.db.execute('SELECT id,reference,family FROM mail_sources LIMIT 0')
                if version == 0:
                    if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                        raise CoreError('commitment_schema', 'Unversioned database is not empty')
                    self.db.execute('''CREATE TABLE commitments(id TEXT PRIMARY KEY,title TEXT NOT NULL,
                        source TEXT NOT NULL,due_text TEXT,due_at REAL,revision INTEGER NOT NULL,
                        status TEXT NOT NULL,posted_at REAL,created REAL NOT NULL,updated REAL NOT NULL)''')
                    self.db.execute('CREATE INDEX due_queue ON commitments(status,due_at)')
                    self.db.execute('''CREATE TABLE operations(request_id TEXT PRIMARY KEY,digest TEXT NOT NULL,
                        id TEXT NOT NULL,accepted_revision INTEGER NOT NULL)''')
                    self.db.execute('''CREATE TABLE history(seq INTEGER PRIMARY KEY,id TEXT NOT NULL,
                        revision INTEGER NOT NULL,event TEXT NOT NULL,body TEXT NOT NULL,at REAL NOT NULL)''')
                    self.db.execute('PRAGMA user_version=1')
        except BaseException:
            self.db.close(); raise

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try: yield; self.db.commit()
        except BaseException: self.db.rollback(); raise

    def read(self, ident):
        row = self.db.execute('SELECT * FROM commitments WHERE id=?', (ident,)).fetchone()
        if not row: raise CoreError('commitment_missing', 'Commitment does not exist')
        return dict(row)

    def listing(self):
        return [dict(row) for row in self.db.execute('''SELECT * FROM commitments ORDER BY
            CASE status WHEN 'DUE' THEN 0 WHEN 'OPEN' THEN 1 ELSE 2 END,
            CASE WHEN status IN ('DUE','OPEN') THEN COALESCE(due_at,1e20) ELSE -updated END LIMIT 200''')]

    def event(self, ident, name, now):
        row = self.read(ident)
        self.db.execute('INSERT INTO history(id,revision,event,body,at) VALUES(?,?,?,?,?)',
                        (ident,row['revision'],name,canonical(row),now))

    def command(self, body, *, now=None, origin=None):
        now = time.time() if now is None else now
        if not isinstance(body, dict): invalid('Expected one commitment command')
        action = body.get('action')
        fields = {'create':{'title','source','due_at'}, 'reschedule':{'revision','due_at'},
                  'complete':{'revision'}, 'cancel':{'revision'}}
        if not isinstance(action,str) or action not in fields or set(body) != {'action','id','request_id'} | fields[action]:
            invalid('Unexpected commitment command fields')
        for key in ('id','request_id'):
            if not isinstance(body[key],str) or not re.fullmatch('[a-f0-9]{32}',body[key]): invalid('Invalid command identity')
        when = due(body['due_at']) if action in ('create','reschedule') else None
        if action == 'create':
            for key, limit in [('title',200),('source',2000)]:
                if not isinstance(body[key],str) or not body[key].strip() or len(body[key]) > limit or '\x00' in body[key]:
                    invalid('Title and the original user note are required')
        elif type(body['revision']) is not int or body['revision'] < 1: invalid('Expected the current schedule revision')
        mail_origin=isinstance(origin,dict) and set(origin)=={'mail_reference','mail_family'}
        if mail_origin and (action!='create' or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in origin.values())):
            invalid('Invalid internal mail origin')
        if origin is not None and not mail_origin and (not isinstance(origin,dict) or set(origin)!={'chat_id','turn_id','source_digest'}
                or any(not isinstance(v,str) or not v or len(v)>200 for v in origin.values())):
            invalid('Invalid internal conversation origin')
        request_digest=digest(body) if origin is None else digest({'command':body,'origin':origin})
        with self.tx():
            previous = self.db.execute('SELECT * FROM operations WHERE request_id=?',(body['request_id'],)).fetchone()
            if previous:
                if previous['digest'] != request_digest: raise CoreError('conflict','Command identity has different content')
                return {'id':previous['id'],'accepted_revision':previous['accepted_revision'],
                        'current':self.read(previous['id']),'existing':True}
            if action == 'create':
                if self.db.execute('SELECT 1 FROM commitments WHERE id=?',(body['id'],)).fetchone():
                    raise CoreError('conflict','Commitment identity is already used')
                if self.db.execute("SELECT COUNT(*) FROM commitments WHERE status IN ('OPEN','DUE')").fetchone()[0] >= 100:
                    raise CoreError('commitment_capacity','At most 100 active personal commitments')
                self.db.execute('INSERT INTO commitments VALUES(?,?,?,?,?,1,\'OPEN\',NULL,?,?)',
                    (body['id'],body['title'],body['source'],body['due_at'],when,now,now))
            else:
                row = self.read(body['id'])
                if row['revision'] != body['revision']: raise CoreError('conflict','Schedule revision changed; reload the current item')
                if row['status'] not in ('OPEN','DUE'): raise CoreError('commitment_terminal','Completed or cancelled commitments cannot be revived')
                if action == 'reschedule':
                    self.db.execute("UPDATE commitments SET revision=revision+1,due_text=?,due_at=?,status='OPEN',posted_at=NULL,updated=? WHERE id=?",
                        (body['due_at'],when,now,body['id']))
                else:
                    self.db.execute('UPDATE commitments SET revision=revision+1,status=?,updated=? WHERE id=?',
                        ('DONE' if action == 'complete' else 'CANCELLED',now,body['id']))
            self.event(body['id'],action,now)
            current = self.read(body['id'])
            self.db.execute('INSERT INTO operations VALUES(?,?,?,?)',
                (body['request_id'],request_digest,body['id'],current['revision']))
            if mail_origin:
                self.db.execute('CREATE TABLE IF NOT EXISTS mail_sources(id TEXT PRIMARY KEY,reference TEXT NOT NULL,family TEXT NOT NULL)')
                self.db.execute('CREATE INDEX IF NOT EXISTS mail_family ON mail_sources(family)')
                self.db.execute('INSERT INTO mail_sources VALUES(?,?,?)',(body['id'],origin['mail_reference'],origin['mail_family']))
                self.db.execute('PRAGMA user_version=2')
            elif origin is not None:
                # Additive schema-1 extension: the previous reader/writer ignores
                # this provenance table and retains all base records unchanged.
                self.db.execute('''CREATE TABLE IF NOT EXISTS conversation_operations(
                    request_id TEXT PRIMARY KEY,id TEXT NOT NULL,chat_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,source_digest TEXT NOT NULL,operation TEXT NOT NULL)''')
                self.db.execute('INSERT INTO conversation_operations VALUES(?,?,?,?,?,?)',
                    (body['request_id'],body['id'],origin['chat_id'],origin['turn_id'],origin['source_digest'],action))
            return {'id':body['id'],'accepted_revision':current['revision'],'current':current,'existing':False}

    def operation(self, request_id):
        row=self.db.execute('SELECT * FROM operations WHERE request_id=?',(request_id,)).fetchone()
        return {**dict(row),'current':self.read(row['id'])} if row else None

    def mail_source(self,ident):
        if self.db.execute('PRAGMA user_version').fetchone()[0]!=2:return None
        row=self.db.execute('SELECT * FROM mail_sources WHERE id=?',(ident,)).fetchone()
        return dict(row) if row else None

    def mail_items(self,family):
        if self.db.execute('PRAGMA user_version').fetchone()[0]!=2:return []
        return [dict(row) for row in self.db.execute('SELECT c.* FROM commitments c JOIN mail_sources s ON s.id=c.id WHERE s.family=? ORDER BY c.created DESC LIMIT 100',(family,))]

    def origin(self, ident):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='conversation_operations'").fetchone():return None
        row=self.db.execute("SELECT * FROM conversation_operations WHERE id=? AND operation='create'",(ident,)).fetchone()
        return dict(row) if row else None

    def conversation_operation(self, request_id):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='conversation_operations'").fetchone():return None
        row=self.db.execute('SELECT * FROM conversation_operations WHERE request_id=?',(request_id,)).fetchone()
        return dict(row) if row else None

    def accepted_record(self, request_id):
        row=self.db.execute('''SELECT h.body FROM operations o JOIN conversation_operations c ON c.request_id=o.request_id
            JOIN history h ON h.id=o.id AND h.revision=o.accepted_revision AND h.event=c.operation
            WHERE o.request_id=? ORDER BY h.seq LIMIT 1''',(request_id,)).fetchone()
        if not row:raise CoreError('commitment_source','Accepted operation history is missing')
        return decode(row['body'])

    def conversation_items(self, chat_id):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='conversation_operations'").fetchone():return []
        return [dict(r) for r in self.db.execute('''SELECT c.* FROM commitments c JOIN conversation_operations o
            ON o.id=c.id WHERE o.chat_id=? AND o.operation='create'
            ORDER BY CASE WHEN c.status IN ('OPEN','DUE') THEN 0 ELSE 1 END,c.created DESC LIMIT 106''',(chat_id,))]

    def advance(self, *, now=None):
        now = time.time() if now is None else now
        with self.tx():
            rows = list(self.db.execute("SELECT id,revision FROM commitments WHERE status='OPEN' AND due_at<=? ORDER BY due_at LIMIT 32",(now,)))
            for row in rows:
                self.db.execute("UPDATE commitments SET status='DUE',posted_at=?,updated=? WHERE id=? AND revision=? AND status='OPEN'",
                    (now,now,row['id'],row['revision']))
                self.event(row['id'],'due',now)
        return len(rows)

    def history(self, ident):
        self.read(ident)
        return [{'event':r['event'],'at':r['at'],'record':decode(r['body'])} for r in self.db.execute(
            'SELECT * FROM history WHERE id=? ORDER BY seq DESC LIMIT 100',(ident,))]

    def close(self): self.db.close()

    def __enter__(self): return self

    def __exit__(self,*exc): self.close()
