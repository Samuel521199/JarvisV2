"""Additive work linkage; task facts and authority remain in their existing stores."""
from contextlib import nullcontext
from sdk.protocol import CoreError


def ensure(db):
    row = db.one("SELECT value FROM meta WHERE key='work_schema'")
    if row:
        if row['value'] not in {'1','2'}: raise CoreError('work_schema', 'Unsupported work schema')
        if row['value']=='2': return
    with (nullcontext(db.connection) if db.connection.in_transaction else db.transaction()) as tx:
        current=tx.execute("SELECT value FROM meta WHERE key='work_schema'").fetchone()
        if current:
            if current[0]=='1':
                budgets(tx);tx.execute("UPDATE meta SET value='2' WHERE key='work_schema'")
            elif current[0]!='2':raise CoreError('work_schema','Unsupported work schema')
            return
        tx.execute('''CREATE TABLE work_owners(root_goal TEXT PRIMARY KEY REFERENCES goal_plans(id),
            current_goal TEXT NOT NULL UNIQUE REFERENCES goal_plans(id), assistant_id TEXT NOT NULL,
            owner_bot_id TEXT NOT NULL, revision INTEGER NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0,
            registration TEXT NOT NULL, created REAL NOT NULL)''')
        tx.execute('''CREATE TABLE work_revisions(goal_id TEXT PRIMARY KEY REFERENCES goal_plans(id),
            root_goal TEXT NOT NULL REFERENCES work_owners(root_goal), ordinal INTEGER NOT NULL,
            parent_goal TEXT, kind TEXT NOT NULL, note TEXT NOT NULL, start_step INTEGER NOT NULL,
            source_digest TEXT, request_id TEXT UNIQUE, request_digest TEXT,
            UNIQUE(root_goal,ordinal))''')
        budgets(tx)
        tx.execute("INSERT INTO meta VALUES('work_schema','2')")


def budgets(tx):
    tx.execute('''CREATE TABLE work_budgets(root_goal TEXT PRIMARY KEY REFERENCES work_owners(root_goal),
        limit_units INTEGER NOT NULL,revision INTEGER NOT NULL,created REAL NOT NULL)''')
    tx.execute('''CREATE TABLE work_allocations(task_id TEXT PRIMARY KEY REFERENCES tasks(id),
        root_goal TEXT NOT NULL REFERENCES work_budgets(root_goal),units INTEGER NOT NULL,admission_limit INTEGER NOT NULL)''')
    tx.execute('''CREATE TABLE work_budget_changes(root_goal TEXT NOT NULL REFERENCES work_budgets(root_goal),
        request_id TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(root_goal,request_id))''')


def ensure_recoveries(db):
    row=db.one("SELECT value FROM meta WHERE key='work_recovery_schema'")
    if row:
        if row['value']!='1':raise CoreError('work_schema','Unsupported recovery schema')
        return
    with (nullcontext(db.connection) if db.connection.in_transaction else db.transaction()) as tx:
        row=tx.execute("SELECT value FROM meta WHERE key='work_recovery_schema'").fetchone()
        if row:
            if row[0]!='1':raise CoreError('work_schema','Unsupported recovery schema')
            return
        tx.execute('''CREATE TABLE work_recoveries(goal_id TEXT PRIMARY KEY REFERENCES goal_plans(id),
            body TEXT NOT NULL,digest TEXT NOT NULL)''')
        tx.execute("INSERT INTO meta VALUES('work_recovery_schema','1')")
