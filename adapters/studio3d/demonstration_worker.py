# SPDX-License-Identifier: GPL-2.0-or-later
"""Record and execute one local Blender demonstration with true paired renders."""
import hashlib
import json
import struct
import sys
import time
from pathlib import Path
import bpy
from mathutils import Vector
from modules.skills.studio3d.demonstration import validate, displacement, VERSION
from modules.skills.studio3d.radial_profile import reprofile


def digest_object(obj,*,material_slots=True):
    h = hashlib.sha256()
    for row in obj.matrix_world:
        h.update(struct.pack('<4d', *row))
    if obj.type == 'MESH':
        for vertex in obj.data.vertices:
            h.update(struct.pack('<3d', *vertex.co))
        for polygon in obj.data.polygons:
            h.update(struct.pack('<II', len(polygon.vertices), polygon.material_index))
            for index in polygon.vertices: h.update(struct.pack('<I',index))
    elif obj.type == 'CURVE':
        h.update(str((obj.data.dimensions,obj.data.resolution_u,obj.data.bevel_depth,obj.data.bevel_resolution)).encode())
        for spline in obj.data.splines:
            h.update(str((spline.type,spline.use_cyclic_u)).encode())
            for point in spline.bezier_points:
                for value in (point.co,point.handle_left,point.handle_right): h.update(struct.pack('<3d',*value))
            for point in spline.points: h.update(struct.pack('<4d',*point.co))
    else: raise ValueError('Unsupported source object type: '+obj.type)
    if material_slots:h.update(json.dumps([s.material.name if s.material else None for s in obj.material_slots]).encode())
    return h.hexdigest()


def topology(obj):
    counts = {}
    for p in obj.data.polygons:
        for edge in p.edge_keys: counts[edge] = counts.get(edge,0)+1
    return {'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),
            'boundary_edges':sum(v==1 for v in counts.values()),'overfull_edges':sum(v>2 for v in counts.values())}


def main():
    folder = Path(sys.argv[sys.argv.index('--')+1]); req = json.loads((folder/'request.json').read_text(encoding='utf-8'))
    source = folder/'source.blend'
    if hashlib.sha256(source.read_bytes()).hexdigest() != req['source_sha256']: raise ValueError('Source changed')
    c = validate(req['contract'],req['visible_names']); began = time.monotonic()
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    objects = {name:bpy.data.objects.get(name) for name in req['visible_names']}
    if any(o is None or o.type not in ('MESH','CURVE') for o in objects.values()): raise ValueError('Source inventory changed')
    targets = {a['target'] for a in c['actions']}
    if any(objects[n].type!='MESH' for n in targets): raise ValueError('Relief targets must be meshes')
    before = {n:digest_object(o) for n,o in objects.items()}
    before_topology = {n:topology(objects[n]) for n in targets}
    scene = bpy.context.scene; camera = scene.camera
    if camera is None: raise ValueError('Receipt source must include studio camera')
    old_camera = camera.matrix_world.copy(); old_type=camera.data.type; old_scale=camera.data.ortho_scale
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=c['samples'];scene.cycles.seed=4;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x,scene.render.resolution_y=c['resolution'];scene.render.resolution_percentage=100
    camera.data.type='ORTHO';camera.data.sensor_fit='HORIZONTAL'; images=[]
    def render(stage):
        for v in c['views']:
            center=Vector(v['center']);direction=Vector(v['direction']).normalized()
            camera.location=center+direction*v['ortho_scale']*3
            camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=v['ortho_scale']
            scene.render.filepath=str(folder/(stage+'-'+v['id']+'.png'))
            bpy.context.view_layer.update();bpy.ops.render.render(write_still=True)
            images.append({'stage':stage,'view':v['id'],'file':Path(scene.render.filepath).name,'camera':v,'real_blender_render':True})
    render('before'); actions=[]
    for a in c['actions']:
        obj=objects[a['target']]
        if obj.data.users != 1 or any(m.type!='BEVEL' and m.type!='WEIGHTED_NORMAL' for m in obj.modifiers): raise ValueError('Unsupported shared mesh or deformer')
        changed=0;maximum=0.;inverse=obj.matrix_world.inverted();profile_check=None
        if a['tool']=='radial_reprofile':
            if len(set(p.material_index for p in obj.data.polygons))!=1:raise ValueError('Reprofile needs a single surface material')
            material_index=obj.data.polygons[0].material_index
            vertices,faces,profile_check=reprofile([list(obj.matrix_world@p.co) for p in obj.data.vertices],[list(p.vertices) for p in obj.data.polygons],a)
            materials=list(obj.data.materials);mesh=bpy.data.meshes.new(obj.name+'-pressed-profile')
            mesh.from_pydata([inverse@Vector(p) for p in vertices],[],faces);mesh.update()
            for material in materials:mesh.materials.append(material)
            for p in mesh.polygons:p.use_smooth=True;p.material_index=material_index
            obj.data=mesh;changed=len(vertices);maximum=profile_check['max_axial_change']
        else:
            for vertex in obj.data.vertices:
                world=obj.matrix_world@vertex.co;delta=Vector(displacement(world,a))
                if delta.length>1e-10:
                    vertex.co=inverse@(world+delta);changed+=1;maximum=max(maximum,delta.length)
        if not changed: raise ValueError('Action made no actual change')
        obj.data.update(); row={'action':a,'before_digest':before[obj.name],'after_digest':digest_object(obj),'changed_vertices':changed,'max_world_displacement':maximum,'author':c['author']}
        actions.append(row)
        if profile_check:row['profile_checks']=profile_check
        with (folder/'actions.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(row,ensure_ascii=False)+'\n')
    bpy.context.view_layer.update()
    after={n:digest_object(o) for n,o in objects.items()}
    unexpected=[n for n in objects if n not in targets and before[n]!=after[n]]
    after_topology={n:topology(objects[n]) for n in targets}
    if unexpected: raise ValueError('Out-of-scope geometry changed')
    for a in c['actions']:
        name=a['target'];t=after_topology[name]
        if a['tool']=='radial_relief' and before_topology[name]!=t:raise ValueError('Relief changed topology')
        if a['tool']=='radial_reprofile' and (t['boundary_edges'] or t['overfull_edges'] or t['vertices']<before_topology[name]['vertices']):raise ValueError('Invalid reprofile topology')
    render('after');camera.matrix_world=old_camera;camera.data.type=old_type;camera.data.ortho_scale=old_scale
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects.values():obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(folder/'model.glb'),export_format='GLB',use_selection=True,export_apply=True)
    report={'version':VERSION,'author':c['author'],'goal':c['goal'],'evidence':c['evidence'],'source_sha256':req['source_sha256'],
            'actions':actions,'views':images,'before_object_digests':before,'after_object_digests':after,
            'checks':{'unchanged_non_targets':not unexpected,'topology_preserved':before_topology==after_topology,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],
                      'topology':after_topology,'intentional_profile_retopology':any(a['tool']=='radial_reprofile' for a in c['actions']),'geometry_intersections':'NOT_TESTED','visual_match':'AWAITING_REVIEW','user_approval':False,'lod_authorized':False},
            'blender_version':bpy.app.version_string,'elapsed_seconds':time.monotonic()-began,'scope':'Local mesh relief demonstration; no claim of independent Jarvis execution or historical accuracy.'}
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
