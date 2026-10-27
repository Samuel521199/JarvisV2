# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed Blender tools; input is bounded data, never generated Python."""
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def world_vertices(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def surface_gap(obj, support):
    # Sampled vertices against actual triangles, not AABB contact certification.
    vertices = world_vertices(support)
    tree = BVHTree.FromPolygons(vertices, [list(p.vertices) for p in support.data.polygons])
    points = world_vertices(obj)
    if not points or not vertices: return None
    distances = [hit[3] for p in points[::max(1, len(points)//4096)] if (hit := tree.find_nearest(p)) and hit[0] is not None]
    return min(distances) if distances else None


def closed_edges(obj):
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        # glTF UV seams split vertices; weld only a disposable audit mesh.
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
        return sum(not edge.is_manifold for edge in bm.edges)
    finally: bm.free()


def rejected_objects(contract):
    roots = [o for o in bpy.context.scene.objects if any(o.name == n or re.fullmatch(re.escape(n)+r'\.\d{3,}', o.name) for n in contract['rejected'])]
    result = set(roots)
    for obj in roots: result.update(obj.children_recursive)
    return sorted(result, key=lambda o: o.name)


def audit(contract):
    bpy.context.view_layer.update()
    issues, inventory = [], []
    by_id = {p['id']: p for p in contract['parts']}
    for p in contract['parts']:
        obj = bpy.context.scene.objects.get(p['node'])
        if obj is None or obj.type != 'MESH':
            issues.append({'code': 'missing_part', 'symptom': 'missing_part', 'part': p['id']}); continue
        obj.data.calc_loop_triangles()
        row = {'id': p['id'], 'node': obj.name, 'motion': p['motion'], 'motion_owner': p['motion_owner'],
               'position': list(obj.matrix_world.translation), 'triangles': len(obj.data.loop_triangles),
               'materials': [m.name if m else None for m in obj.data.materials]}
        if p['closed_surface']:
            row['nonmanifold_edges'] = closed_edges(obj)
            if row['nonmanifold_edges']: issues.append({'code': 'open_surface', 'symptom': 'open_surface', 'part': p['id'], 'count': row['nonmanifold_edges']})
        inventory.append(row)
    for obj in rejected_objects(contract):
        issues.append({'code': 'rejected_part', 'symptom': 'rejected_parts', 'node': obj.name})
    contacts = []
    for a in contract['attachments']:
        obj = bpy.context.scene.objects.get(by_id[a['part']]['node'])
        support = bpy.context.scene.objects.get(by_id[a['support']]['node'])
        if obj is None or support is None or obj.type != 'MESH' or support.type != 'MESH': continue
        gap = surface_gap(obj, support)
        contacts.append({'part': a['part'], 'support': a['support'], 'sampled_surface_gap_m': gap, 'tolerance_m': a['max_gap']})
        if gap is None or gap > a['max_gap'] + 1e-6:
            issues.append({'code': 'floating_attachment', 'symptom': 'floating_attachment', 'part': a['part'], 'gap_m': gap})
    return {'parts': inventory, 'contacts': contacts, 'issues': issues,
            'passed': not issues, 'scope': 'declared objects, welded audit edges and sampled vertex-to-surface distances only',
            'unverified': ['visual reference similarity', 'historical accuracy', 'intersections and support strength', 'material and UV quality', 'animation sweep collision', 'AAA', 'user high approval']}


def issue_keys(report):
    return {(r['code'], r.get('part'), r.get('node')) for r in report['issues']}


def repair(contract, tool, before):
    changed = []
    if tool == 'remove_rejected':
        objects = rejected_objects(contract)
        retained = {p['node'] for p in contract['parts']}
        if any(o.name in retained for o in objects): raise ValueError('Deletion tree includes a retained semantic part')
        changed = [o.name for o in objects]
        for obj in objects: bpy.data.objects.remove(obj, do_unlink=True)
    elif tool == 'seat_attachment':
        parts = {p['id']: p for p in contract['parts']}
        failing = {r.get('part') for r in before['issues'] if r['code'] == 'floating_attachment'}
        for a in contract['attachments']:
            if a['part'] not in failing or 'target_position' not in a: continue
            obj = bpy.context.scene.objects[parts[a['part']]['node']]
            if obj.constraints: raise ValueError('Constrained placement requires an explicit animation adapter')
            before_pos = list(obj.matrix_world.translation)
            matrix = obj.matrix_world.copy(); matrix.translation = Vector(a['target_position']); obj.matrix_world = matrix
            changed.append({'node': obj.name, 'before_position': before_pos, 'after_position': a['target_position']})
    else: raise ValueError('Unknown fixed repair tool')
    bpy.context.view_layer.update()
    return changed


def render_views(folder, prefix, framing):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 12
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    if scene.world is None: scene.world = bpy.data.worlds.new('learning-review-world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.22,.22,.22,1)
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .7
    scene.view_settings.view_transform = 'Standard'
    points = [o.matrix_world @ Vector(c) for o in scene.objects if o.type == 'MESH' for c in o.bound_box]
    if not points: raise ValueError('No renderable geometry')
    if not framing:
        low = Vector([min(p[k] for p in points) for k in range(3)])
        high = Vector([max(p[k] for p in points) for k in range(3)])
        framing = {'center': list((low+high)/2), 'span': max(high-low)*1.7}
    center, span = Vector(framing['center']), framing['span']
    cam_data = bpy.data.cameras.new('learning-review-camera'); cam = bpy.data.objects.new('learning-review-camera', cam_data)
    scene.collection.objects.link(cam); scene.camera = cam
    cam_data.type = 'ORTHO'; cam_data.ortho_scale = span; cam_data.clip_end = span*20
    lights = []
    for i, direction in enumerate(((2,-3,4),(-3,-1,2),(1,3,3))):
        data = bpy.data.lights.new('learning-light-'+str(i), 'AREA'); data.energy = span*span*140; data.shape = 'DISK'; data.size = span*1.7
        obj = bpy.data.objects.new(data.name, data); scene.collection.objects.link(obj); obj.location = center+Vector(direction)*span
        obj.rotation_euler = (center-obj.location).to_track_quat('-Z','Y').to_euler(); lights.append(obj)
    views = {'front':(0,-4,0), 'rear':(0,4,0), 'left':(-4,0,0), 'right':(4,0,0), 'top':(0,0,4)}
    evidence = {}
    for name, direction in views.items():
        cam.location = center+Vector(direction)*span
        cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
        path = folder/(prefix+'-'+name+'.png'); scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        evidence[name] = {'file': path.name, 'sha256': digest(path)}
    bpy.data.objects.remove(cam, do_unlink=True)
    for obj in lights: bpy.data.objects.remove(obj, do_unlink=True)
    return evidence, framing


def main():
    from modules.skills.studio3d.learning_contract import validate, TOOLS
    folder = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    request = json.loads((folder/'request.json').read_text(encoding='utf-8'))
    contract = validate(request['contract'])
    allowed = request['tools']
    if not isinstance(allowed, list) or len(allowed) > 2 or set(allowed)-set(TOOLS): raise ValueError('Invalid fixed tool list')
    if digest(folder/'source.glb') != request['source_sha256']: raise ValueError('Source changed')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(folder/'source.glb'))
    bpy.context.scene.frame_set(0)
    before = audit(contract)
    result = {'schema':'jarvis.studio3d.learning.worker.v1', 'before':before, 'actions':[], 'blender':bpy.app.version_string,
              'source_sha256':request['source_sha256'], 'render_before':{}, 'render_after':{}, 'framing':None}
    if request['render']:
        result['render_before'], result['framing'] = render_views(folder, 'before', None)
    if allowed and (bpy.data.actions or any(o.type == 'ARMATURE' or o.animation_data for o in bpy.context.scene.objects)):
        raise ValueError('Animated sources are inspection-only in learning tools 1.0')
    current = before
    for tool in allowed:
        tick = time.monotonic(); changed = repair(contract, tool, current); after = audit(contract)
        result['actions'].append({'tool':tool,'changed':changed,'elapsed_seconds':time.monotonic()-tick,
                                  'before_issues':len(current['issues']),'after_issues':len(after['issues'])})
        if issue_keys(after)-issue_keys(current):
            result['regression'] = True; break
        current = after
    after = audit(contract)
    result['after'] = after
    if allowed and not result.get('regression') and issue_keys(after) < issue_keys(before):
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'candidate.blend'))
        bpy.ops.export_scene.gltf(filepath=str(folder/'candidate.glb'), export_format='GLB', export_animations=True, export_extras=True, export_yup=True)
        result['candidate_sha256'] = digest(folder/'candidate.glb')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(folder/'candidate.glb')); bpy.context.scene.frame_set(0)
        result['roundtrip'] = audit(contract)
        if issue_keys(result['roundtrip'])-issue_keys(after): result['regression'] = True
    else: result['candidate_sha256'] = None
    if request['render']:
        result['render_after'], _ = render_views(folder, 'after', result['framing'])
    result['status'] = ('REJECTED_REGRESSION' if result.get('regression') else
                        'REPAIRED_DECLARED_CHECKS' if result.get('roundtrip', {}).get('passed') and result['candidate_sha256'] else
                        'PARTIAL_REPAIR' if result['candidate_sha256'] else 'INSPECTED' if not allowed else 'STALLED')
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__': main()
