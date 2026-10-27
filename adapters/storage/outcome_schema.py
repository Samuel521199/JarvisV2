"""Additive observer storage; never migrates execution, identity or permissions."""
from sdk.protocol import CoreError
from contextlib import nullcontext


def ensure(db):
    row = db.one("SELECT value FROM meta WHERE key='outcome_schema'")
    if row:
        if row['value'] != '1':
            raise CoreError('outcome_schema', 'Unsupported outcome schema')
        return
    with (nullcontext(db.connection) if db.connection.in_transaction else db.transaction()) as tx:
        # Another Host may have initialized this optional domain while we waited.
        row = tx.execute("SELECT value FROM meta WHERE key='outcome_schema'").fetchone()
        if row:
            if row[0] != '1': raise CoreError('outcome_schema', 'Unsupported outcome schema')
            return
        tx.execute('''CREATE TABLE outcome_assessments(
            id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id),fingerprint TEXT NOT NULL,
            body TEXT NOT NULL,created REAL NOT NULL)''')
        tx.execute('CREATE INDEX outcome_task_history ON outcome_assessments(task_id,created)')
        tx.execute('''CREATE TABLE outcome_current(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            assessment_id TEXT NOT NULL REFERENCES outcome_assessments(id),revision INTEGER NOT NULL)''')
        tx.execute('''CREATE TABLE outcome_failures(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            attempts INTEGER NOT NULL,error TEXT NOT NULL,next_retry REAL NOT NULL)''')
        tx.execute('CREATE TABLE outcome_consumers(name TEXT PRIMARY KEY,last_seq INTEGER NOT NULL)')
        tx.execute("INSERT INTO outcome_consumers VALUES('deterministic-v1',0)")
        tx.execute("INSERT INTO meta VALUES('outcome_schema','1')")

