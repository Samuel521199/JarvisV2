# SPDX-License-Identifier: GPL-2.0-or-later
"""Render a fresh import of a locally verified static candidate GLB."""
import bpy,sys,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
req=json.loads((folder/'request.json').read_text(encoding='utf8'))
path=folder/'source.glb'
if hashlib.sha256(path.read_bytes()).hexdigest()!=req['sha256']:raise ValueError('GLB source changed')
with render_lane(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(path),merge_vertices=False)
    scene=bpy.context.scene;meshes=[o for o in scene.objects if o.type=='MESH']
    if not meshes:raise ValueError('No GLB meshes')
    center=Vector((0,0,1.49));data=bpy.data.cameras.new('compare');cam=bpy.data.objects.new('compare',data);scene.collection.objects.link(cam);scene.camera=cam
    data.type='ORTHO';data.ortho_scale=.35;cam.location=center+Vector((0,-5,0));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.world=bpy.data.worlds.new('probe-world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.35,.35,.35,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
    for i,loc in enumerate([(4,-5,6),(-4,-3,4),(0,4,5)]):
        light=bpy.data.lights.new('probe-light-'+str(i),'AREA');light.energy=400;light.shape='DISK';light.size=5
        obj=bpy.data.objects.new('probe-light-'+str(i),light);scene.collection.objects.link(obj);obj.location=center+Vector(loc)*1.6;obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='Standard';scene.render.filepath=str(folder/'glb-head.png');bpy.ops.render.render(write_still=True)
    result={'source_sha256':req['sha256'],'mesh_count':len(meshes),'image_sha256':hashlib.sha256((folder/'glb-head.png').read_bytes()).hexdigest(),'scope':'visual of fresh GLB import, not image-match or rig validation'}
    (folder/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
