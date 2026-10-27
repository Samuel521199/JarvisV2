from __future__ import annotations

from sdk.protocol import CoreError, ModelProvider, canonical, contract, decode


class ModelGateway:
    """Contract-checked step-proposal port (jarvis.step-proposal.v1).

    Not wired into Core: production model calls go through ``routed.RoutedModels``,
    whose fallback order comes from user settings. Kept as the reference port for
    a future step-proposing agent runtime and covered by tests/test_core.py.
    """
    def __init__(self, providers: dict[str, ModelProvider] | None = None):
        self.providers = dict(providers or {})

    def describe(self):
        return {"providers": sorted(self.providers), "configured": bool(self.providers)}

    def propose(self, context: dict, order: list[str], allowed: set[str]):
        errors = []
        for name in dict.fromkeys(order):
            if name not in allowed:
                continue
            provider = self.providers.get(name)
            if not provider:
                continue
            try:
                # Providers get detached data, never mutable live host objects.
                proposal = provider.propose(decode(canonical(context)))
                contract("step-proposal", proposal)
                return {"provider": name, "proposal": proposal}
            except Exception:
                # Do not log provider errors which may contain prompts or secrets.
                errors.append(name)
        raise CoreError("model_unavailable", "No permitted provider returned a valid proposal")
