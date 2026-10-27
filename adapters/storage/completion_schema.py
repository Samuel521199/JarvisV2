"""Additive completion, feedback and conditional-method reference storage."""
from contextlib import nullcontext
from sdk.protocol import CoreError


def ensure(db):
    row = db.one("SELECT value FROM meta WHERE key='completion_schema'")
    if row:
        if row['value'] not in {'1','2'}: raise CoreError('completion_schema', 'Unsupported completion schema')
        if row['value']=='2': return
    with (nullcontext(db.connection) if db.connection.in_transaction else db.transaction()) as tx:
        row=tx.execute("SELECT value FROM meta WHERE key='completion_schema'").fetchone()
        if row:
            if row[0] not in {'1','2'}: raise CoreError('completion_schema','Unsupported completion schema')
            if row[0]=='1':
                history(tx)
                tx.execute("UPDATE meta SET value='2' WHERE key='completion_schema'")
            return
        tx.execute('''CREATE TABLE task_acceptance(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            revision INTEGER NOT NULL,body TEXT NOT NULL,created REAL NOT NULL)''')
        tx.execute('''CREATE TABLE completion_feedback(id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id),
            request_id TEXT NOT NULL,digest TEXT NOT NULL,fingerprint TEXT NOT NULL,kind TEXT NOT NULL,
            note TEXT NOT NULL,created REAL NOT NULL,UNIQUE(task_id,request_id))''')
        tx.execute('''CREATE TABLE task_completion(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            body TEXT NOT NULL,checked REAL NOT NULL)''')
        tx.execute('''CREATE TABLE experience_methods(id TEXT PRIMARY KEY,scope TEXT NOT NULL,recipe TEXT NOT NULL,
            bindings TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,
            review_after REAL NOT NULL DEFAULT 0)''')
        tx.execute('''CREATE TABLE experience_sources(task_id TEXT PRIMARY KEY REFERENCES tasks(id),method_id TEXT NOT NULL
            REFERENCES experience_methods(id),fingerprint TEXT NOT NULL,input_digest TEXT NOT NULL,state TEXT NOT NULL)''')
        tx.execute('''CREATE TABLE experience_uses(task_id TEXT PRIMARY KEY REFERENCES tasks(id),method_id TEXT NOT NULL
            REFERENCES experience_methods(id),method_revision INTEGER NOT NULL,source_task TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,created REAL NOT NULL)''')
        history(tx)
        tx.execute("INSERT INTO meta VALUES('completion_schema','2')")


def history(tx):
    tx.execute('''CREATE TABLE completion_history(task_id TEXT NOT NULL REFERENCES tasks(id),
        fingerprint TEXT NOT NULL,body TEXT NOT NULL,created REAL NOT NULL,
        PRIMARY KEY(task_id,fingerprint))''')
