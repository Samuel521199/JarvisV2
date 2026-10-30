"""Keep declared base PBR when glTF cannot represent a procedural coating.

This is an explicitly reported approximation, not texture baking. Geometry,
images and the binary chunk remain unchanged; the Blender material is untouched.
"""
import copy
import hashlib
import json
import struct


def base_pbr(row):
    rgb=[int(row['color'][i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return {'baseColorFactor':linear+[1.0], 'metallicFactor':row['metallic'], 'roughnessFactor':row['roughness']}


def preserve_base_pbr(raw, declarations):
    if len(raw)<20 or raw[:4]!=b'glTF' or struct.unpack_from('<II',raw,4)!=(2,len(raw)):
        raise ValueError('Invalid GLB envelope')
    size,kind=struct.unpack_from('<II',raw,12)
    if kind!=0x4e4f534a or 20+size>len(raw):raise ValueError('Missing GLB JSON')
    doc=json.loads(raw[20:20+size]);tail=raw[20+size:];before=copy.deepcopy(doc);changed=[]
    declared={r['id']:r for r in declarations if r.get('detail') in ('weathered_paint','painted','steel')}
    for mat in doc.get('materials',[]):
        row=declared.get(mat.get('name'))
        if row is None:continue
        pbr=mat.get('pbrMetallicRoughness',{})
        # A real exported color/texture wins. Never replace imported/baked PBR.
        if 'baseColorFactor' in pbr or 'baseColorTexture' in pbr:continue
        if any(k.endswith('Texture') for k in pbr):raise ValueError('Partial mapped material needs explicit review')
        replacement=base_pbr(row);mat['pbrMetallicRoughness']={**pbr,**replacement}
        changed.append({'material':mat['name'],'before':pbr,'after':replacement,'scope':'declared_base_only; procedural wear and bump remain in Blender'})
    if not changed:return raw,{'changed':[],'binary_unchanged':True}
    check=copy.deepcopy(doc)
    for a,b in zip(before.get('materials',[]),check.get('materials',[])):
        if any(x['material']==b.get('name') for x in changed):
            b.pop('pbrMetallicRoughness',None)
            if 'pbrMetallicRoughness' in a:b['pbrMetallicRoughness']=a['pbrMetallicRoughness']
    if before!=check:raise ValueError('Unexpected non-PBR mutation')
    encoded=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();encoded+=b' '*((-len(encoded))%4)
    result=struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),kind)+encoded+tail
    return result,{'changed':changed,'binary_unchanged':True,'binary_sha256':hashlib.sha256(tail).hexdigest()}
