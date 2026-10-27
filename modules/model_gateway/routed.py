"""Durable, budgeted model calls. Unknown remote outcomes do not auto-retry."""
import time
import uuid

from control.policy.grants import GrantStore
from sdk.protocol import CoreError, canonical, contract, decode, digest


class RoutedModels:
    def __init__(self, db, providers, order):
        self.db, self.providers, self.order = db, providers, list(order)
        self.network_check = lambda: None
        self.phase_order = lambda _: self.order
        if len(self.order) > 8 or len(set(self.order)) != len(self.order) or any(n not in providers for n in self.order):
            raise CoreError("model_config", "Invalid bounded route order")

    def request(self, run_id, phase, prompt, schema, authority, max_calls, checkpoint, network_enabled):
        signature = digest({"prompt": prompt, "schema": schema})
        old = self.db.all("SELECT * FROM model_calls WHERE run_id=? AND phase=? ORDER BY created", (run_id, phase))
        for row in old:
            if row["input_digest"] != signature:
                raise CoreError("model_context_changed", "An existing call has different context")
            if row["status"] in {"DISPATCHING", "UNKNOWN"}:
                raise CoreError("model_unknown", "Remote outcome/cost unknown; explicit retry acknowledgement required")
            if row["status"] == "SUCCEEDED": return decode(row["result"])
        if not network_enabled:
            raise CoreError("network_disabled", "Model network use is not enabled for this invocation")
        self.network_check()
        for name in self.phase_order(phase):
            provider = self.providers[name]
            if not provider.available(): continue
            # One attempt per route per phase. A rejected model may use an allowed backup.
            if any(row["provider"] == name and row["status"] != "ACKNOWLEDGED" for row in old): continue
            checkpoint()
            ident = "call-" + uuid.uuid4().hex
            reservation = len(prompt.encode("utf-8")) + 1024 + provider.config["max_output_tokens"]
            with self.db.transaction() as tx:
                used = tx.execute("SELECT COUNT(*) FROM model_calls WHERE run_id=?", (run_id,)).fetchone()[0]
                if used >= max_calls:
                    raise CoreError("model_budget", "Model-call budget exhausted; restart does not reset it")
                GrantStore.authorize(tx, authority, "model.generate.v1", charge=1)
                tx.execute("INSERT INTO model_calls(id,run_id,phase,provider,status,input_digest,reservation,created,model,billing_profile) VALUES(?,?,?,?,'DISPATCHING',?,?,?,?,?)",
                           (ident, run_id, phase, name, signature, reservation, time.time(), provider.config.get('model'), canonical(provider.config.get('billing_profile'))))
            try:
                result = provider.generate(prompt, lambda: (checkpoint(), self.network_check()))
                state = result["status"]
                if state == "SUCCEEDED":
                    try: contract(schema, result["value"])
                    except CoreError:
                        result = {"status": "INVALID", "code": "model_contract", "usage": result.get("usage", {})}
                        state = "INVALID"
                if state not in {"SUCCEEDED", "REJECTED", "INVALID", "UNKNOWN"}:
                    raise CoreError("model_reply", "Unknown provider response state")
            except BaseException:
                with self.db.transaction() as tx:
                    tx.execute("UPDATE model_calls SET status='UNKNOWN',error='interrupted' WHERE id=?", (ident,))
                raise
            with self.db.transaction() as tx:
                tx.execute("UPDATE model_calls SET status=?,usage=?,result=?,error=? WHERE id=?",
                    (state, canonical(result.get("usage", {})), canonical(result["value"]) if state == "SUCCEEDED" else None,
                     result.get("code"), ident))
                self.db.event(tx, None, "model.receipt", {"call_id": ident, "status": state, "provider": name})
            if state == "SUCCEEDED": return result["value"]
            if state == "UNKNOWN":
                raise CoreError("model_unknown", "Remote result/cost unknown; no automatic fallback")
        raise CoreError("model_unavailable", "No permitted route returned a valid result")

    def recover(self, run_id=None):
        with self.db.transaction() as tx:
            query = "UPDATE model_calls SET status='UNKNOWN',error='host_interrupted' WHERE status='DISPATCHING'"
            return tx.execute(query + (' AND run_id=?' if run_id else ''), (run_id,) if run_id else ()).rowcount

    def cached(self, run_id, phase):
        row = self.db.one("SELECT result FROM model_calls WHERE run_id=? AND phase=? AND status='SUCCEEDED' ORDER BY created DESC LIMIT 1", (run_id, phase))
        return decode(row["result"]) if row else None

    def acknowledge_unknown(self, run_id):
        with self.db.transaction() as tx:
            count = tx.execute("UPDATE model_calls SET status='ACKNOWLEDGED' WHERE run_id=? AND status='UNKNOWN'", (run_id,)).rowcount
            self.db.event(tx, None, "model.unknown_acknowledged", {"run_id": run_id, "calls": count})
        return count
