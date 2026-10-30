"""Bounded rigid high-asset finish contract. No reduction or generated code."""
import math
import re

VERSION='1.2.2'

def uv_independent_shader(signature):
    """Conservative whitelist for the existing explicit world-space coating.

    UV-dependent nodes, nested groups and implicit image coordinates fail closed.
    Actual Principled anisotropy is checked by the Blender adapter as well.
    """
    allowed={'ShaderNodeAmbientOcclusion','ShaderNodeBsdfPrincipled','ShaderNodeBump','ShaderNodeCombineXYZ','ShaderNodeMapRange','ShaderNodeMath','ShaderNodeMixRGB','ShaderNodeNewGeometry','ShaderNodeOutputMaterial','ShaderNodeRGBToBW','ShaderNodeSeparateColor','ShaderNodeSeparateXYZ','ShaderNodeTexImage','ShaderNodeTexNoise','ShaderNodeVectorMath','ShaderNodeValue','ShaderNodeRGB','ShaderNodeValToRGB','ShaderNodeBevel'}
    for n in signature['nodes']:
        if n['type'] not in allowed or 'group' in n:return False
        if n['type']=='ShaderNodeTexImage' and not any(l[2]==n['name'] and l[3]==0 for l in signature['links']):return False
        if n['type']=='ShaderNodeBsdfPrincipled' and any('anisotropic' in name.lower() and value!=0 for name,value in n['inputs']):return False
    return True


def validate(value,visible_names):
    if not isinstance(value,dict) or set(value) not in ({'groups','texture_size'},{'groups','texture_size','reuse'}):raise ValueError('Unexpected high finish fields')
    if type(value['texture_size']) is not int or value['texture_size'] not in (512,1024):raise ValueError('High material atlas budget')
    groups=value['groups']
    if not isinstance(groups,list) or not 1<=len(groups)<=16:raise ValueError('Rigid group budget')
    ids=set();members=set()
    for g in groups:
        if not isinstance(g,dict) or set(g)!={'id','members','parent','pivot','motion'}:raise ValueError('Invalid rigid group')
        if not isinstance(g['id'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,39}',g['id']) or g['id'] in ids:raise ValueError('Invalid group name')
        ids.add(g['id'])
        if g['motion'] not in ('fixed','visual_rotation','visual_slide'):raise ValueError('Unknown visual movement')
        if not isinstance(g['members'],list) or not g['members'] or len(g['members'])>128:raise ValueError('Empty or oversized membership')
        for name in g['members']:
            if not isinstance(name,str) or name not in visible_names or name in members:raise ValueError('Missing or duplicate source member')
            members.add(name)
        if not isinstance(g['pivot'],list) or len(g['pivot'])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>20 for v in g['pivot']):raise ValueError('Invalid visual origin')
    if members!=set(visible_names):raise ValueError('All visible parts must have exactly one owner')
    by={g['id']:g for g in groups}
    for g in groups:
        seen={g['id']};parent=g['parent']
        while parent is not None:
            if not isinstance(parent,str) or parent not in ids or parent in seen:raise ValueError('Cyclic or missing parent')
            seen.add(parent);parent=by[parent]['parent']
    if 'reuse' in value:
        r=value['reuse']
        if not isinstance(r,dict) or set(r)!={'export_id','groups'} or not isinstance(r['export_id'],str) or not re.fullmatch('[a-f0-9]{32}',r['export_id']):raise ValueError('Receipt-bound reuse required')
        if not isinstance(r['groups'],list) or not 1<=len(r['groups'])<len(groups) or any(not isinstance(n,str) or n not in ids for n in r['groups']) or len(set(r['groups']))!=len(r['groups']):raise ValueError('Invalid explicit reused groups')
    return value
