"""Encrypted mailbox objects, isolated from chats, knowledge and model credentials."""
from contextlib import contextmanager,nullcontext
import sqlite3
import time
import uuid

from control.credentials import crypt
from control.paths import child,reject_links
from sdk.protocol import CoreError,canonical,decode,digest


class MailStore:
    def __init__(self,root):
        path=child(root,'private/mail.sqlite3');path.parent.mkdir(parents=True,exist_ok=True)
        for suffix in ('-journal','-wal','-shm'):reject_links(path.with_name(path.name+suffix))
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,kind TEXT NOT NULL,revision INTEGER NOT NULL,payload BLOB NOT NULL)')
    def close(self):self.db.close()
    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:yield;self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def get(self,ident,missing=False):
        row=self.db.execute('SELECT * FROM objects WHERE id=?',(ident,)).fetchone()
        if not row:
            if missing:return None
            raise CoreError('mail_missing','Mail record is unavailable')
        value=decode(crypt(bytes(row['payload']),decrypt=True))
        if value.get('id')!=ident or value.get('kind')!=row['kind'] or value.get('revision')!=row['revision']:
            raise CoreError('mail_corrupt','Encrypted mailbox record does not match its index')
        return value
    def put(self,value,revision):
        ident=value['id'];old=self.get(ident,True)
        if (old['revision'] if old else 0)!=revision:raise CoreError('conflict','Mail record changed')
        value={**value,'revision':revision+1,'updated':time.time()}
        raw=canonical(value).encode()
        if len(raw)>300000:raise CoreError('mail_capacity','Encrypted mailbox record exceeds the limit')
        if not old and self.db.execute('SELECT COUNT(*) FROM objects').fetchone()[0]>=5000:raise CoreError('mail_capacity','Mailbox cache is full')
        self.db.execute('INSERT INTO objects VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
                        (ident,value['kind'],value['revision'],crypt(raw)))
        return value
    def listing(self,kind,limit=100):
        return [self.get(row[0]) for row in self.db.execute('SELECT id FROM objects WHERE kind=? ORDER BY rowid DESC LIMIT ?',(kind,limit))]
    def update(self,ident,**patch):
        with self.transaction():
            old=self.get(ident);return self.put({**old,**patch},old['revision'])
    def job(self,request_id,operation,payload,*,approved=False):
        if not isinstance(request_id,str) or not 8<=len(request_id)<=100:raise CoreError('mail_invalid','Provide a unique bounded request ID')
        ident='job-'+digest(request_id)[:40];signature=digest({'operation':operation,'payload':payload,'approved':approved})
        with (nullcontext() if self.db.in_transaction else self.transaction()):
            old=self.get(ident,True)
            if old:
                if old['signature']!=signature:raise CoreError('conflict','Request ID was already used for another operation')
                return old,False
            return self.put({'id':ident,'kind':'job','operation':operation,'payload':payload,'signature':signature,'approved':approved,
                             'status':'READY','error':None,'result':None,'effect_started':False,'cancel':False,'created':time.time()},0),True
    def recover(self):
        with self.transaction():
            for row in self.listing('job',500):
                if row['status'] in {'READY','RUNNING'}:
                    self.put({**row,'status':'UNKNOWN' if row['effect_started'] else 'WAITING','error':'mail_interrupted'},row['revision'])
