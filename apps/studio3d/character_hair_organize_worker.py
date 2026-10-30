"""Organize and test an FBX-derived character in a disposable output folder.

This is not an arbitrary BLEND importer. It opens one SHA-verified local source
with scripts disabled and keeps geometry and the user's original file intact.
"""
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from control.studio3d_lane import render_lane

OUT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
SOURCE = ROOT / 'user-data/artifacts/studio3d-character/face-atlas-refine-20261027/narrow-24.blend'
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
if source_hash != '4f591a474d45b104f6a85448d9195c3be40bbf928ae779b0e6466a4ff8ce89e2':
    raise ValueError('Face-refined source identity changed')
OUT.mkdir(parents=True, exist_ok=True)
if (OUT/'replaceable-hair.blend').exists():
    raise ValueError('Will not overwrite an existing candidate')

with render_lane(OUT):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig = bpy.data.objects['Armature']; head = rig.pose.bones['J_Bip_C_Head']
    face = bpy.data.objects['Face']; body = bpy.data.objects['Body']
    source_hair = bpy.data.objects['headend']
    prefixes = ('hair-scalp-refined', 'back-hair-refined-', 'bang-refined-', 'side-hair-refined-')
    added = [o for o in scene.objects if o.name.startswith(prefixes)]
    if len(added) != 29:
        raise ValueError('Unexpected hair object count: '+str(len(added)))
    if any(o.type != 'MESH' or o.parent or any(m.type == 'ARMATURE' for m in o.modifiers) for o in added):
        raise ValueError('Unexpected added-hair binding')
    if source_hair.parent != rig or not any(m.type == 'ARMATURE' and m.object == rig for m in source_hair.modifiers):
        raise ValueError('Original headend binding changed')
    for ob in (face, body):
        if any(m and 'hair' in m.name.casefold() for m in ob.data.materials):
            raise ValueError('Hair material mixed with body or face; manual separation required')

    def points(ob):
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = ev.to_mesh()
        result = [ev.matrix_world @ v.co for v in mesh.vertices]
        ev.to_mesh_clear()
        return result

    def mesh_identity(ob):
        digest = hashlib.sha256()
        for v in ob.data.vertices:
            digest.update(struct.pack('fff',*v.co))
        for poly in ob.data.polygons:
            digest.update(struct.pack('I', len(poly.vertices)))
            for v in poly.vertices:
                digest.update(struct.pack('I',v))
            digest.update(struct.pack('I',poly.material_index))
        for block in (ob.data.shape_keys.key_blocks if ob.data.shape_keys else []):
            digest.update(block.name.encode('utf8'))
            for v in block.data:
                digest.update(struct.pack('fff',*v.co))
        return {'geometry_sha256':digest.hexdigest(),
                'materials':[m.name if m else None for m in ob.data.materials]}

    body_face_before = {o.name: mesh_identity(o) for o in (face,body)}

    before = {o.name: points(o) for o in added}
    original_matrices = {o.name: o.matrix_world.copy() for o in added}
    collection = bpy.data.collections.new('Hair_SilverHair_Replaceable_01')
    scene.collection.children.link(collection)
    for ob in [source_hair] + added:
        collection.objects.link(ob)
        for old in list(ob.users_collection):
            if old != collection:
                old.objects.unlink(ob)
    for ob in added:
        group = ob.vertex_groups.new(name='J_Bip_C_Head')
        group.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
        mod = ob.modifiers.new('Follow head bone', 'ARMATURE'); mod.object = rig
    bpy.context.view_layer.update()
    no_pose = {o.name: points(o) for o in added}
    max_baseline = max((a-b).length for o in added for a,b in zip(before[o.name],no_pose[o.name]))
    if any(len(before[o.name]) != len(no_pose[o.name]) for o in added) or max_baseline > 1e-5:
        raise ValueError('Binding changed the current visible pose: '+str(max_baseline))
    if any(max(abs(a-b) for rowa,rowb in zip(original_matrices[o.name],o.matrix_world) for a,b in zip(rowa,rowb)) > 1e-8 for o in added):
        raise ValueError('Hair world transform changed')

    start_head = rig.matrix_world @ head.matrix.copy()
    old_mode = head.rotation_mode; old_quaternion = head.rotation_quaternion.copy(); old_euler = head.rotation_euler.copy()
    head.rotation_mode = 'XYZ'; head.rotation_euler.rotate_axis('Z', math.radians(15))
    bpy.context.view_layer.update()
    delta = rig.matrix_world @ head.matrix @ start_head.inverted()
    turned = {o.name: points(o) for o in added}
    max_follow = max((a-delta@b).length for o in added for a,b in zip(turned[o.name],no_pose[o.name]))
    movement = max((a-b).length for o in added for a,b in zip(turned[o.name],no_pose[o.name]))
    if max_follow > .0001 or movement < .005:
        raise ValueError('Added hair did not follow the head bone: error '+str(max_follow))

    # Actual before/after visibility and a real posed render, not generated art.
    camera = scene.camera; camera.data.type='ORTHO'; camera.data.ortho_scale=.35
    center=Vector((0,0,1.49)); camera.location=center+Vector((0,-5,0))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.filepath=str(OUT/'head-turned.png');bpy.ops.render.render(write_still=True)
    head.rotation_mode=old_mode;head.rotation_quaternion=old_quaternion;head.rotation_euler=old_euler
    bpy.context.view_layer.update()
    scene.render.filepath=str(OUT/'hair-visible.png');bpy.ops.render.render(write_still=True)
    collection.hide_render=True
    scene.render.filepath=str(OUT/'hair-hidden.png');bpy.ops.render.render(write_still=True)
    collection.hide_render=False
    if not face.visible_get() or not body.visible_get() or face.name in collection.objects or body.name in collection.objects:
        raise ValueError('Face or body included in hair group')
    if body_face_before != {o.name: mesh_identity(o) for o in (face,body)}:
        raise ValueError('Face or body geometry or materials changed')
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Source changed during operation')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'replaceable-hair.blend'),check_existing=False)
    report={'source_sha256':source_hash,'collection':collection.name,'face_object':face.name,'body_object':body.name,
        'hair_objects':[source_hair.name]+[o.name for o in added], 'original_headend_binding_retained':True,
        'added_hair_binding':'Each added mesh 100% weighted to J_Bip_C_Head', 'head_bone':'J_Bip_C_Head',
        'current_pose_max_displacement_m':max_baseline,'head_turn_degrees':15,'head_turn_max_motion_m':movement,
        'head_turn_max_rigid_follow_error_m':max_follow,'hide_render_test':True,'body_face_mesh_identity':body_face_before,'user_approval':False,
        'limitations':['Procedural hair is rigidly weighted to head; no independent hair motion',
                       'Only one static head turn tested; intersections and other poses not verified',
                       'Existing headend uses multiple original bone weights; its deformation was not certified',
                       'Geometry, materials and appearance remain unfinished']}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
