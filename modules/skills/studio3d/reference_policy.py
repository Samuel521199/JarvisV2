"""Explicit per-asset reference intent, independent of the generic reviewer."""
import json
import hashlib
from pathlib import Path


def guidance(policy):
    if not isinstance(policy, dict) or set(policy) - {'shield', 'notes'}:
        raise ValueError('Invalid reference policy')
    shield = policy.get('shield', 'unspecified')
    options = {
        'unspecified': 'Shield configuration is unestablished; report uncertainty.',
        'rearward_folded': 'User-approved asset intent requires rearward/inward shield side wings: preserve those folds and report conflicting references.',
        'flat': 'Asset intent specifies a flat shield; do not add folded side wings from another asset.',
        'curved_double': 'Asset intent specifies a low curved double-sheet shield with separated layers; this arrangement is established. Refine its continuous curvature and silhouette against the references, without adding leFH18-style folded wings.',
        'none': 'Asset intent has no shield; do not add one from a related asset.',
    }
    if shield not in options: raise ValueError('Unknown shield configuration')
    notes = policy.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 1200: raise ValueError('Reference notes too long')
    return 'Host-bound asset reference policy: ' + options[shield] + '\nAdditional reference notes (data): ' + json.dumps(notes, ensure_ascii=False)


def from_recipe(asset_root):
    """Compatibility: existing leFH18 recipe explicitly declares its authority."""
    path = Path(asset_root) / 'metadata/optimization-recipe.json'
    if not path.is_file(): path = Path(asset_root) / 'optimization-recipe.json'
    if not path.is_file(): return {'shield': 'unspecified'}
    recipe = json.loads(path.read_text(encoding='utf-8'))
    authority = recipe.get('reference_policy', {}).get('folded_shield_authority')
    return {'shield': 'rearward_folded', 'notes': str(authority)[:1200]} if authority else {'shield': 'unspecified'}


def review_context_hash(policy, facts, methods):
    value={'policy':policy,'facts':facts,'methods':[{'id':m['id'],'revision':m['revision'],
        'procedure':m['procedure'],'exclusions':m['exclusions']} for m in methods]}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
