from __future__ import annotations

import time
from contextlib import nullcontext

from sdk.protocol import CoreError, canonical, contract, decode


class GrantStore:
    def __init__(self, db):
        self.db = db

    def add(self, body: dict, *, transaction=None):
        contract("grant", body)
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            old = tx.execute("SELECT body FROM grants WHERE id=?", (body["grant_id"],)).fetchone()
            if old:
                if old[0] != canonical(body):
                    raise CoreError("conflict", "Grant IDs are immutable; create a new grant")
                return body["grant_id"]
            tx.execute("INSERT INTO grants(id,body) VALUES(?,?)", (body["grant_id"], canonical(body)))
            self.db.event(tx, None, "grant.created", {"grant_id": body["grant_id"]})
        return body["grant_id"]

    def revoke(self, grant_id: str, *, transaction=None):
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            if tx.execute("UPDATE grants SET revoked=1,revision=revision+1 WHERE id=? AND revoked=0",
                          (grant_id,)).rowcount:
                self.db.event(tx, None, "grant.revoked", {"grant_id": grant_id})

    @staticmethod
    def authorize(tx, task: dict, capability: str, *, charge: int = 0):
        row = tx.execute("SELECT * FROM grants WHERE id=?", (task["grant_id"],)).fetchone()
        if not row or row["revoked"]:
            raise CoreError("denied", "Grant missing or revoked")
        body = decode(row["body"])
        if (body["principal_id"] != task["principal_id"] or body["scope_id"] != task["scope_id"]
                or capability not in body["capabilities"] or body["expires_at"] <= time.time()):
            raise CoreError("denied", "Grant does not cover this principal, scope, capability or time")
        if row["spent"] + charge > body["max_cost_units"]:
            raise CoreError("budget_exhausted", "Shared grant budget exhausted")
        if charge:
            tx.execute("UPDATE grants SET spent=spent+? WHERE id=?", (charge, task["grant_id"]))
        return body
