from __future__ import annotations

import uuid

from sdk.protocol import CoreError, canonical, decode


class Continuity:
    def __init__(self, db):
        self.db = db

    def initialize(self):
        with self.db.transaction() as tx:
            current = tx.execute("SELECT value FROM meta WHERE key='identity'").fetchone()
            if not current:
                identity = {"assistant_id": "jarvis-" + uuid.uuid4().hex, "owner_id": "owner.local",
                            "schema": "jarvis.identity.v1", "generation": 1}
                tx.execute("INSERT INTO meta(key,value) VALUES('identity',?)", (canonical(identity),))

    def describe(self):
        row = self.db.one("SELECT value FROM meta WHERE key='identity'")
        if not row:
            raise CoreError("identity_missing", "Identity missing; never regenerate on ordinary startup")
        return decode(row["value"])
