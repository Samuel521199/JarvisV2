"""Additive, independently versioned source ledger. FTS is a rebuildable projection."""
from sdk.protocol import CoreError


def ensure(connection):
    row = connection.execute("SELECT value FROM meta WHERE key='knowledge_schema'").fetchone()
    if row:
        if row[0] not in {'1','2','3','4'}: raise CoreError('knowledge_schema', 'Unsupported knowledge schema')
        if row[0] == '1': upgrade(connection)
        if row[0] in {'1','2'}: upgrade_three(connection)
        if row[0] != '4': upgrade_four(connection)
        return
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS knowledge_sources(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,title TEXT NOT NULL,text TEXT NOT NULL,
 revision INTEGER NOT NULL,status TEXT NOT NULL,bytes INTEGER NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_destinations(
 source_id TEXT NOT NULL REFERENCES knowledge_sources(id),provider TEXT NOT NULL,PRIMARY KEY(source_id,provider));
CREATE TABLE IF NOT EXISTS knowledge_chunks(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,source_id TEXT NOT NULL REFERENCES knowledge_sources(id),
 revision INTEGER NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,line_start INTEGER NOT NULL,line_end INTEGER NOT NULL,
 text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS knowledge_chunk_source ON knowledge_chunks(source_id);
CREATE TABLE IF NOT EXISTS knowledge_changes(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,source_id TEXT NOT NULL,revision INTEGER NOT NULL,operation TEXT NOT NULL,
 chunks INTEGER NOT NULL,occurred REAL NOT NULL);
INSERT OR IGNORE INTO meta VALUES('knowledge_schema','1');
INSERT OR IGNORE INTO meta VALUES('knowledge_epoch','0');
INSERT OR IGNORE INTO meta VALUES('knowledge_index','');
COMMIT;''')
    upgrade(connection)
    upgrade_three(connection)
    upgrade_four(connection)


def upgrade(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS knowledge_cleanups(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,state TEXT NOT NULL,goals INTEGER NOT NULL,
 turns INTEGER NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,error TEXT);
UPDATE meta SET value='2' WHERE key='knowledge_schema';
COMMIT;''')


def upgrade_three(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS knowledge_vectors(
 space TEXT NOT NULL,source_id TEXT NOT NULL,revision INTEGER NOT NULL,start INTEGER NOT NULL,
 end INTEGER NOT NULL,vector BLOB NOT NULL,PRIMARY KEY(space,source_id,revision,start));
CREATE TABLE IF NOT EXISTS knowledge_vector_spaces(
 space TEXT PRIMARY KEY,model_space TEXT NOT NULL,dimension INTEGER NOT NULL,epoch INTEGER NOT NULL,
 state TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_claims(
 id TEXT PRIMARY KEY,source_id TEXT NOT NULL,source_revision INTEGER NOT NULL,start INTEGER NOT NULL,
 end INTEGER NOT NULL,key TEXT NOT NULL,quote TEXT NOT NULL,state TEXT NOT NULL,fact_id TEXT,
 revision INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL,
 UNIQUE(source_id,source_revision,start,end));
CREATE INDEX IF NOT EXISTS knowledge_claim_source ON knowledge_claims(source_id);
INSERT OR IGNORE INTO meta VALUES('knowledge_vector_active','');
UPDATE meta SET value='3' WHERE key='knowledge_schema';
COMMIT;''')


def upgrade_four(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS knowledge_file_retractions(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,chat_id TEXT NOT NULL,turn_id TEXT NOT NULL,
 sha256 TEXT NOT NULL,state TEXT NOT NULL,error TEXT,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_artifact_retractions(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,chat_id TEXT,relative TEXT NOT NULL,
 sha256 TEXT NOT NULL,state TEXT NOT NULL,error TEXT,updated REAL NOT NULL);
UPDATE meta SET value='4' WHERE key='knowledge_schema';
COMMIT;''')
