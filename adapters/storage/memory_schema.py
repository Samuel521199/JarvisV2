"""Independent additive memory evolution. Derived indexes are never authoritative."""
from sdk.protocol import CoreError


def ensure(connection):
    row=connection.execute("SELECT value FROM meta WHERE key='memory_schema'").fetchone()
    if row:
        if row[0] not in {'1','2','3','4'}:raise CoreError('memory_schema','Unsupported memory schema')
        if row[0]=='1':upgrade_two(connection)
        if row[0] in {'1','2'}:upgrade_three(connection)
        if row[0] in {'1','2','3'}:upgrade_four(connection)
        return
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE memory_history(
 kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,scope TEXT NOT NULL,
 body TEXT NOT NULL,recorded REAL,PRIMARY KEY(kind,id,revision));
CREATE INDEX memory_history_scope ON memory_history(scope,kind,id);
CREATE TABLE memory_origins(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,body TEXT NOT NULL,checksum TEXT NOT NULL);
CREATE TABLE memory_imports(
 id TEXT PRIMARY KEY,scope TEXT NOT NULL,checksum TEXT NOT NULL,created REAL NOT NULL,counts TEXT NOT NULL);
CREATE TABLE memory_conditions(
 fact_id TEXT PRIMARY KEY REFERENCES facts(id),valid_from REAL,conditions TEXT NOT NULL);
CREATE TRIGGER memory_history_fact_forget AFTER UPDATE OF deleted ON facts WHEN NEW.deleted=1 BEGIN
 DELETE FROM memory_history WHERE kind='fact' AND id=NEW.id;
 DELETE FROM memory_conditions WHERE fact_id=NEW.id;
 DELETE FROM memory_origins WHERE id=NEW.id OR id IN (SELECT id FROM memory_candidates WHERE fact_id=NEW.id);
END;
CREATE TRIGGER memory_origin_candidate_forget AFTER UPDATE OF state ON memory_candidates WHEN NEW.state!='PENDING' BEGIN
 DELETE FROM memory_origins WHERE id=NEW.id;
END;
CREATE TRIGGER memory_history_source_forget AFTER UPDATE OF status ON knowledge_sources WHEN NEW.status='deleted' BEGIN
 DELETE FROM memory_history WHERE kind='source' AND id=NEW.id;
END;
INSERT INTO meta VALUES('memory_schema','1');
COMMIT;''')
    upgrade_two(connection)
    upgrade_three(connection)
    upgrade_four(connection)


def upgrade_two(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE memory_domains(
 id TEXT PRIMARY KEY,parent TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,
 revision INTEGER NOT NULL,archived INTEGER NOT NULL,created REAL NOT NULL);
CREATE TABLE memory_snapshots(
 domain_id TEXT NOT NULL REFERENCES memory_domains(id),kind TEXT NOT NULL,id TEXT NOT NULL,
 revision INTEGER NOT NULL,PRIMARY KEY(domain_id,kind,id));
CREATE TABLE memory_chat_scopes(
 chat_id TEXT PRIMARY KEY,scope TEXT NOT NULL,revision INTEGER NOT NULL);
UPDATE meta SET value='2' WHERE key='memory_schema';
COMMIT;''')


def upgrade_three(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE knowledge_extractions(
 id TEXT PRIMARY KEY,digest TEXT NOT NULL,scope TEXT NOT NULL,source_id TEXT NOT NULL,
 source_revision INTEGER NOT NULL,route TEXT NOT NULL,state TEXT NOT NULL,cancel INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL,completed REAL,error TEXT,added INTEGER NOT NULL DEFAULT 0);
UPDATE meta SET value='3' WHERE key='memory_schema';
COMMIT;''')


def upgrade_four(connection):
    connection.executescript('''BEGIN IMMEDIATE;
CREATE TABLE memory_source_branches(
 domain_id TEXT NOT NULL REFERENCES memory_domains(id),
 source_id TEXT PRIMARY KEY REFERENCES knowledge_sources(id),
 parent_id TEXT NOT NULL REFERENCES knowledge_sources(id),
 base_revision INTEGER NOT NULL,UNIQUE(domain_id,parent_id));
UPDATE meta SET value='4' WHERE key='memory_schema';
COMMIT;''')
