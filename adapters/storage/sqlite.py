from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

from sdk.protocol import CoreError, canonical, decode
from adapters.storage.knowledge_schema import ensure as ensure_knowledge
from adapters.storage.memory_schema import ensure as ensure_memory

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE grants (id TEXT PRIMARY KEY, body TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
    spent INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE tasks (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, digest TEXT NOT NULL,
    body TEXT NOT NULL, bindings TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, deadline REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1, next_step INTEGER NOT NULL DEFAULT 0,
    spent INTEGER NOT NULL DEFAULT 0, cancel INTEGER NOT NULL DEFAULT 0, error TEXT);
CREATE TABLE actions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
    step_id TEXT NOT NULL, capability TEXT NOT NULL, arguments TEXT NOT NULL, digest TEXT NOT NULL,
    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, result TEXT, error TEXT,
    UNIQUE(task_id, step_id));
CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, kind TEXT NOT NULL,
    data TEXT NOT NULL, occurred REAL NOT NULL);
CREATE TABLE modules (id TEXT PRIMARY KEY, active TEXT NOT NULL, previous TEXT,
    enabled INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE facts (id TEXT PRIMARY KEY, principal TEXT NOT NULL, scope TEXT NOT NULL,
    key TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
    deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(principal, scope, key));
"""

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS development_runs (
 id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, digest TEXT NOT NULL, spec TEXT NOT NULL,
 status TEXT NOT NULL, phase TEXT NOT NULL DEFAULT 'plan', attempt INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL, deadline REAL NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
 candidate TEXT, release_id TEXT, task_id TEXT, error TEXT, plan TEXT);
CREATE TABLE IF NOT EXISTS model_calls (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, phase TEXT NOT NULL, provider TEXT NOT NULL,
 status TEXT NOT NULL, input_digest TEXT NOT NULL, reservation INTEGER NOT NULL,
 usage TEXT, result TEXT, error TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS packages (
 id TEXT PRIMARY KEY, capability TEXT NOT NULL, status TEXT NOT NULL, spec TEXT NOT NULL,
 report TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS release_slots (
 capability TEXT PRIMARY KEY, active TEXT, previous TEXT, revision INTEGER NOT NULL DEFAULT 0,
 enabled INTEGER NOT NULL DEFAULT 1, observations INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS release_operations (
 id TEXT PRIMARY KEY, capability TEXT NOT NULL, target TEXT NOT NULL, previous TEXT,
 revision INTEGER NOT NULL, status TEXT NOT NULL, operation TEXT NOT NULL);
"""


class Database:
    def __init__(self, path: Path, *, create: bool = False):
        self.path = path
        if not path.exists() and not create:
            raise CoreError("not_initialized", "Run init for this data root first")
        self.connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA synchronous=FULL")
        # Readers keep their snapshot while the bounded knowledge writer builds an index.
        # WAL remains local to this data root; SQLite handles checkpoint/recovery.
        if self.connection.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
            self.connection.execute('PRAGMA journal_mode=WAL')
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and create:
            try:
                self.connection.executescript("BEGIN IMMEDIATE;" + SCHEMA + "PRAGMA user_version=1; COMMIT;")
            except BaseException:
                self.connection.close()
                raise
        elif version not in {1, 2, 3, 4, 5, 6, 7}:
            self.connection.close()
            raise CoreError("schema_version", "Unsupported database; no automatic destructive migration")
        if version in {0, 1}:
            # Additive transaction: no rewrite of identity, grants, facts or task receipts.
            try:
                self.connection.executescript("BEGIN IMMEDIATE;" + SCHEMA_V2 + "PRAGMA user_version=2; COMMIT;")
            except BaseException:
                self.connection.close()
                raise

        if version in {0, 1, 2}:
            try:
                self.connection.executescript("BEGIN IMMEDIATE; ALTER TABLE model_calls ADD COLUMN model TEXT; ALTER TABLE model_calls ADD COLUMN billing_profile TEXT; PRAGMA user_version=3; COMMIT;")
            except BaseException:
                self.connection.close()
                raise

        if version in {0, 1, 2, 3}:
            try:
                self.connection.executescript("""BEGIN IMMEDIATE;
CREATE TABLE memory_usage(fact_id TEXT PRIMARY KEY REFERENCES facts(id),kind TEXT NOT NULL,
 purpose TEXT NOT NULL,providers TEXT NOT NULL,paused INTEGER NOT NULL,expires REAL,updated REAL NOT NULL);
CREATE TABLE memory_candidates(id TEXT PRIMARY KEY,source_id TEXT UNIQUE NOT NULL,source_revision TEXT NOT NULL,
 scope TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,state TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,
 fact_id TEXT,created REAL NOT NULL);
INSERT INTO meta(key,value) VALUES('memory_epoch','0');
CREATE TABLE development_controls(run_id TEXT PRIMARY KEY REFERENCES development_runs(id),routes TEXT NOT NULL,
 approved_package TEXT,created REAL NOT NULL);
PRAGMA user_version=4; COMMIT;""")
            except BaseException:
                self.connection.close()
                raise

        if version in {0, 1, 2, 3, 4}:
            try:
                self.connection.executescript("""BEGIN IMMEDIATE;
CREATE TABLE goal_plans(id TEXT PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,digest TEXT NOT NULL,
 request TEXT NOT NULL,catalog TEXT NOT NULL,routes TEXT NOT NULL,proposal TEXT,
 status TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,cancel INTEGER NOT NULL DEFAULT 0,
 task_id TEXT,created REAL NOT NULL,deadline REAL NOT NULL,error TEXT);
PRAGMA user_version=5; COMMIT;""")
            except BaseException:
                self.connection.close()
                raise

        if version in {0, 1, 2, 3, 4, 5}:
            try:
                self.connection.executescript("""BEGIN IMMEDIATE;
ALTER TABLE goal_plans ADD COLUMN planning_round INTEGER NOT NULL DEFAULT 0;
CREATE TABLE goal_growth(goal_id TEXT PRIMARY KEY REFERENCES goal_plans(id),status TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,draft TEXT,development_id TEXT UNIQUE REFERENCES development_runs(id),
 prior_proposal TEXT,prior_catalog TEXT,created REAL NOT NULL,deadline REAL NOT NULL,error TEXT);
PRAGMA user_version=6; COMMIT;""")
            except BaseException:
                self.connection.close()
                raise

        if version in {0, 1, 2, 3, 4, 5, 6}:
            try:
                self.connection.executescript("""BEGIN IMMEDIATE;
ALTER TABLE goal_plans ADD COLUMN generation INTEGER NOT NULL DEFAULT 0;
CREATE TABLE goal_context(goal_id TEXT PRIMARY KEY REFERENCES goal_plans(id),scope TEXT NOT NULL,
 enabled INTEGER NOT NULL,view TEXT NOT NULL,history TEXT NOT NULL DEFAULT '[]');
CREATE TABLE chat_goals(turn_id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,goal_id TEXT UNIQUE NOT NULL REFERENCES goal_plans(id));
CREATE TABLE assistant_operations(turn_id TEXT PRIMARY KEY,goal_id TEXT NOT NULL,kind TEXT NOT NULL,result TEXT NOT NULL);
PRAGMA user_version=7; COMMIT;""")
            except BaseException:
                self.connection.close()
                raise

        ensure_knowledge(self.connection)
        ensure_memory(self.connection)

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    @contextmanager
    def read_snapshot(self):
        if self.connection.in_transaction:
            yield
            return
        self.connection.execute('BEGIN')
        try:yield
        finally:self.connection.execute('ROLLBACK')

    def one(self, sql: str, args=()):
        row = self.connection.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, args=()):
        return [dict(row) for row in self.connection.execute(sql, args)]

    @staticmethod
    def event(tx, task_id, kind, data):
        # Event bodies are fixed structured metadata, never input text or secrets.
        tx.execute("INSERT INTO events(task_id,kind,data,occurred) VALUES(?,?,?,?)",
                   (task_id, kind, canonical(data), time.time()))

    def integrity(self):
        return self.connection.execute("PRAGMA integrity_check").fetchone()[0]

    def close(self):
        self.connection.close()
