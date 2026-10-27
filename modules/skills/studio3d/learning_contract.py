"""Bounded data contract for reviewed, local hard-surface repairs."""
import copy
import math
import re

SCHEMA = 'jarvis.studio3d.learning.v1'
VERSION = '1.0.0'
TOOLS = ('remove_rejected', 'seat_attachment')


def name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 120 or any(ord(c) < 32 for c in value):
        raise ValueError('Expected a bounded object identity')
    return value


def vector(value):
    if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 100 for x in value):
        raise ValueError('Expected three finite coordinates within 100 metres')
    return value


def validate(raw):
    if not isinstance(raw, dict) or set(raw) - {'schema', 'asset_id', 'family', 'parts', 'attachments', 'rejected', 'symptoms', 'reference_policy'}:
        raise ValueError('Unknown learning contract fields')
    v = copy.deepcopy(raw)
    if v.get('schema') != SCHEMA or v.get('family') not in ('hard_surface', 'towed_artillery'):
        raise ValueError('Unknown learning schema/family')
    if not isinstance(v.get('asset_id'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', v['asset_id']):
        raise ValueError('Invalid asset ID')
    parts = v.get('parts')
    if not isinstance(parts, list) or not 1 <= len(parts) <= 512:
        raise ValueError('Declare 1 to 512 semantic parts')
    ids, nodes = set(), set()
    for p in parts:
        if not isinstance(p, dict) or set(p) - {'id', 'node', 'motion_owner', 'motion', 'closed_surface'}:
            raise ValueError('Invalid part specification')
        for k in ('id', 'node', 'motion_owner'): name(p.get(k))
        if p['id'] in ids or p['node'] in nodes: raise ValueError('Duplicate part identity')
        if p.get('motion') not in ('fixed', 'rotating', 'translating', 'coupled') or type(p.get('closed_surface')) is not bool:
            raise ValueError('Declare motion and intended surface closure')
        ids.add(p['id']); nodes.add(p['node'])
    owners = {p['id']: p['motion_owner'] for p in parts}
    for ident in ids:
        seen = set(); cursor = ident
        while True:
            if cursor not in ids: raise ValueError('Unknown motion owner')
            if owners[cursor] == cursor: break
            if cursor in seen: raise ValueError('Motion ownership cycle')
            seen.add(cursor); cursor = owners[cursor]
    attachments = v.setdefault('attachments', [])
    if not isinstance(attachments, list) or len(attachments) > 512: raise ValueError('Too many attachment checks')
    seen = set()
    for a in attachments:
        if not isinstance(a, dict) or set(a) - {'part', 'support', 'max_gap', 'target_position'}:
            raise ValueError('Invalid attachment')
        if a.get('part') not in ids or a.get('support') not in ids or a['part'] == a['support'] or a['part'] in seen:
            raise ValueError('Invalid or duplicate attachment identity')
        seen.add(a['part'])
        if type(a.get('max_gap')) not in (int, float) or not math.isfinite(a['max_gap']) or not 0 <= a['max_gap'] <= .05:
            raise ValueError('Attachment tolerance outside 0..0.05 m')
        if 'target_position' in a: vector(a['target_position'])
    rejected = v.setdefault('rejected', [])
    if not isinstance(rejected, list) or len(rejected) > 128: raise ValueError('Too many rejected objects')
    for r in rejected: name(r)
    if set(rejected) & nodes: raise ValueError('Cannot reject a retained semantic part')
    symptoms = v.setdefault('symptoms', [])
    if not isinstance(symptoms, list) or len(symptoms) > 16: raise ValueError('Too many symptoms')
    for s in symptoms:
        if not isinstance(s, str) or not re.fullmatch('[a-z_]{1,60}', s): raise ValueError('Invalid symptom tag')
    policy = v.setdefault('reference_policy', {})
    if not isinstance(policy, dict) or set(policy) - {'shield', 'notes'} or policy.get('shield', 'unspecified') not in ('unspecified', 'rearward_folded', 'flat', 'none'):
        raise ValueError('Invalid reference policy')
    if 'notes' in policy and (not isinstance(policy['notes'], str) or len(policy['notes']) > 1200): raise ValueError('Reference notes too long')
    return v


def context(contract, symptoms=None):
    v = validate(contract)
    return {'asset_id': v['asset_id'], 'family': v['family'], 'tool_version': VERSION,
            'symptoms': list(symptoms if symptoms is not None else v['symptoms']),
            'declared_rejections': bool(v['rejected']),
            'declared_target': any('target_position' in a for a in v['attachments']),
            'shield': v['reference_policy'].get('shield', 'unspecified')}
