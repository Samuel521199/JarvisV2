"""Run inside Blender: verify declared closed surfaces and shader data bindings.

This complements rendered multi-view review. It cannot certify likeness, detect
every self-intersection, or approve a high-poly asset for LOD generation.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh


def audit(profile):
    errors = []
    surfaces = []
    declared = set(profile.get('closed_meshes', []))
    attributes = profile.get('required_nonzero_face_attributes', {})
    expected = declared | set(attributes)
    present = {o.name for o in bpy.context.scene.objects if o.type == 'MESH'}
    forbidden = sorted(set(profile.get('forbidden_meshes', [])))
    forbidden_present = sorted(name for name in present if any(
        name == base or name.startswith(base + '.') for base in forbidden))
    for name in forbidden_present:
        errors.append({'object': name, 'issue': 'user-rejected mesh is still present, including hidden or duplicated objects'})
    for name in sorted(expected - present):
        errors.append({'object': name, 'issue': 'declared mesh is absent'})
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        if not obj.hide_render and (not mesh.vertices or not mesh.polygons):
            errors.append({'object': obj.name, 'issue': 'renderable mesh has no faces; exported part inventory would disagree'})
        if not obj.hide_render:
            missing_material_faces = [f.index for f in mesh.polygons
                                      if f.material_index >= len(mesh.materials) or
                                      mesh.materials[f.material_index] is None]
            if missing_material_faces:
                errors.append({'object': obj.name, 'issue': 'visible faces have no assigned material',
                               'count': len(missing_material_faces), 'indices': missing_material_faces[:20]})
        invalid = [v.index for v in mesh.vertices
                   if not all(math.isfinite(x) for x in obj.matrix_world @ v.co)]
        if invalid:
            errors.append({'object': obj.name, 'issue': 'nonfinite vertices',
                           'indices': invalid[:20], 'count': len(invalid)})
        if obj.name not in expected:
            continue
        row = {'object': obj.name, 'vertices': len(mesh.vertices),
               'faces': len(mesh.polygons), 'attributes': {}}
        if obj.name in declared:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            row['boundary_edges'] = sum(e.is_boundary for e in bm.edges)
            row['nonmanifold_edges'] = sum(not e.is_manifold for e in bm.edges)
            row['wire_edges'] = sum(e.is_wire for e in bm.edges)
            bm.free()
            if not mesh.polygons or row['nonmanifold_edges']:
                errors.append({'object': obj.name, 'issue': 'declared solid is not closed',
                               'nonmanifold_edges': row['nonmanifold_edges']})
        for name in attributes.get(obj.name, []):
            attr = mesh.attributes.get(name)
            valid = attr is not None and attr.domain == 'FACE' and attr.data_type == 'FLOAT'
            values = [a.value for a in attr.data] if valid else []
            nonzero = sum(math.isfinite(v) and v > 1e-6 for v in values)
            used = any(m and m.use_nodes and any(
                n.type == 'ATTRIBUTE' and n.attribute_name == name and
                any(socket.is_linked for socket in n.outputs)
                for n in m.node_tree.nodes) for m in mesh.materials)
            row['attributes'][name] = {'valid_face_float': valid,
                                      'nonzero_faces': nonzero,
                                      'linked_material_attribute_node': used}
            if not valid or not nonzero or not used:
                errors.append({'object': obj.name, 'issue': 'required shader attribute is absent, empty, or unbound',
                               'attribute': name})
        surfaces.append(row)
    return {'passed': not errors, 'errors': errors, 'surfaces': surfaces,
            'forbidden_meshes': {'declared': forbidden, 'present': forbidden_present},
            'blend': bpy.data.filepath,
            'limits': ['No visual likeness score', 'No full self-intersection certification',
                       'Does not prove every shader branch reaches the active output',
                       'Not user approval; no LOD authorization']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    result = audit(json.loads(Path(args.profile).read_text(encoding='utf-8')))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'errors': result['errors'],
                      'checked_surfaces': len(result['surfaces']), 'output': str(output)}))
    if not result['passed']:
        raise RuntimeError('Declared surface or material binding checks failed; inspect the saved report')


if __name__ == '__main__':
    main()
