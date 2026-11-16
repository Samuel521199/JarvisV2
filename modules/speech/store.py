"""Durable bounded speech requests; restart preserves uncertainty instead of replaying."""
import json,sqlite3,time
from control.paths import child
from sdk.protocol import CoreError,canonical


class Store:
    def __init__(self,root):
        self.db=sqlite3.connect(child(root,'state/speech.sqlite3'),timeout=5,isolation_level=None);self.db.row_factory=sqlite3.Row
        version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0,1):self.db.close();raise CoreError('speech_schema','Unknown speech data version')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,body TEXT NOT NULL,state TEXT NOT NULL,result TEXT,error TEXT,created REAL NOT NULL,confirmation TEXT,turn_id TEXT UNIQUE);
PRAGMA user_version=1;
''')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(canonical({'enabled':True,'revision':0}),))
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def config(self):return json.loads(self.db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
    def get(self,ident):
        r=self.db.execute('SELECT * FROM requests WHERE id=?',(ident,)).fetchone()
        if not r:raise CoreError('speech_missing','Unknown speech request')
        value=dict(r)
        for key in ('body','result','confirmation'):value[key]=json.loads(value[key]) if value[key] else None
        return value
    def add(self,ident,body):
        row=self.db.execute('SELECT body FROM requests WHERE id=?',(ident,)).fetchone()
        if row:
            if row[0]!=canonical(body):raise CoreError('conflict','Speech request ID reused with different input')
            return False
        self.db.execute("INSERT INTO requests(id,body,state,created) VALUES(?,?,'QUEUED',?)",(ident,canonical(body),time.time()));return True
    def finish(self,ident,result):
        return bool(self.db.execute("UPDATE requests SET state='SUCCEEDED',result=? WHERE id=? AND state='RUNNING'",(canonical(result),ident)).rowcount)
    def confirm(self,ident,value):
        row=self.get(ident)
        if row['state']!='SUCCEEDED':raise CoreError('speech_stale','Speech result is unavailable')
        if row['confirmation'] is not None:
            if row['confirmation']!=value:raise CoreError('conflict','Confirmed speech request changed')
            return
        if not self.db.execute("UPDATE requests SET confirmation=?,turn_id=? WHERE id=? AND state='SUCCEEDED' AND confirmation IS NULL",(canonical(value),value['turn_id'],ident)).rowcount:raise CoreError('conflict','Speech changed while confirming')
