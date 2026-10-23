"""Host composition of admitted capabilities; no second execution registry."""
from sdk.protocol import CoreError


def catalog(core, scope='personal'):
    pure = [{k: r[k] for k in ('capability', 'active', 'revision', 'name', 'description')}
            for r in core.packages.catalog('owner.local', 'personal') if r['available']]
    external = core.connectors.catalog() if scope == 'personal' else []
    return (pure[:6] + external[:6] if pure and external else pure + external)[:12]


def require(core, ref):
    cap = ref['capability']
    slot = core.connectors.reference(cap) if cap.startswith('mcp.') else core.packages.slot(cap)
    if not slot or slot['active'] != ref['active'] or slot['revision'] != ref['revision']:
        raise CoreError('plan_version_changed', 'A selected capability changed; review a new plan')
    core.registry.require(cap, ref['active'])
    core.registry.require_context(cap, ref['active'], {'principal_id': 'owner.local', 'scope_id': 'personal'})
