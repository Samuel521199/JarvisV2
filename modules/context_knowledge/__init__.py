from __future__ import annotations

import uuid

from sdk.protocol import CoreError, contract


class Facts:
    """Explicit facts only; no inference, cloud, embeddings or implicit sharing."""
    def __init__(self, db):
        self.db = db

    def put(self, fact: dict, expected_revision: int):
        contract("fact", fact)
        with self.db.transaction() as tx:
            ident = self.write(tx, fact, expected_revision)
            # CLI edits withdraw the old chat-use policy. The owner can reselect it in the UI.
            tx.execute('DELETE FROM memory_usage WHERE fact_id=?', (ident,))
            self.bump(tx)
            return ident

    @staticmethod
    def bump(tx):
        tx.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='memory_epoch'")

    @staticmethod
    def write(tx, fact, expected_revision):
        old = tx.execute("SELECT * FROM facts WHERE principal=? AND scope=? AND key=?",
                         (fact["principal_id"], fact["scope_id"], fact["key"])).fetchone()
        if (old["revision"] if old else 0) != expected_revision:
            raise CoreError("conflict", "Fact revision changed")
        if old:
            tx.execute("UPDATE facts SET value=?,source=?,deleted=0,revision=revision+1 WHERE id=?",
                       (fact["value"], fact["source"], old["id"]))
            return old["id"]
        ident = "fact-" + uuid.uuid4().hex
        tx.execute("INSERT INTO facts(id,principal,scope,key,value,source) VALUES(?,?,?,?,?,?)",
                   (ident, fact["principal_id"], fact["scope_id"], fact["key"], fact["value"], fact["source"]))
        return ident

    def view(self, principal: str, scope: str):
        return self.db.all("SELECT id,key,value,source,revision FROM facts WHERE principal=? AND scope=? AND deleted=0",
                           (principal, scope))

    def forget(self, principal: str, scope: str, key: str, expected_revision: int):
        with self.db.transaction() as tx:
            count = tx.execute("UPDATE facts SET deleted=1,value='',source='',revision=revision+1 "
                               "WHERE principal=? AND scope=? AND key=? AND revision=? AND deleted=0",
                               (principal, scope, key, expected_revision)).rowcount
            if count != 1:
                raise CoreError("conflict", "Fact missing, deleted or changed")
            row = tx.execute('SELECT id FROM facts WHERE principal=? AND scope=? AND key=?', (principal, scope, key)).fetchone()
            tx.execute('DELETE FROM memory_usage WHERE fact_id=?', (row['id'],))
            tx.execute("UPDATE memory_candidates SET state='WITHDRAWN',value='',key='',revision=revision+1 WHERE fact_id=?", (row['id'],))
            self.bump(tx)
