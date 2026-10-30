"""Experimental, hair-only surface union; original hair pieces stay available."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
source=ROOT/'user-data/artifacts/studio3d-character/hair-contour-study-01/candidate.blend'
out=ROOT/'user-data/artifacts/studio3d-character/hair-voxel-merge-01'
if out.exists():raise ValueError('Existing study must be inspected')
out.mkdir(parents=True);identity=hashlib.sha256(source.read_bytes()).hexdigest()
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];arm=bpy.data.objects['Armature']
 names=['headend']+['hair-contour-tip-%02d'%i for i in range(12)]
 originals=[bpy.data.objects[n] for n in names]
 deps=bpy.context.evaluated_depsgraph_get();bpy.ops.object.select_all(action='DESELECT');temps=[]
 for idx,original in enumerate(originals):
  evaluated=original.evaluated_get(deps); mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=deps)
  mesh.transform(evaluated.matrix_world)
  obj=bpy.data.objects.new('temporary-hair-union-%02d'%idx,mesh);col.objects.link(obj);obj.select_set(True);temps.append(obj)
  original.hide_render=True;original.hide_set(True)
 bpy.context.view_layer.objects.active=temps[0];bpy.ops.object.join();merged=bpy.context.object;merged.name='hair-unified-back-trial'
 merged.data.materials.clear();merged.data.materials.append(bpy.data.materials['character-hair-procedural'])
 for p in merged.data.polygons:p.material_index=0
 merged.data.remesh_voxel_size=.0018;bpy.ops.object.voxel_remesh()
 smooth=merged.modifiers.new('Gentle surface smoothing','SMOOTH');smooth.factor=.32;smooth.iterations=3
 bpy.ops.object.modifier_apply(modifier=smooth.name)
 for p in merged.data.polygons:p.use_smooth=True
 # Mesh vertices are presently world coordinates in the visible pose. Convert
 # to the matching bind-space before attaching the whole hair object to head.
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deformation=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted()
 inv=deformation.inverted()
 for v in merged.data.vertices:v.co=inv@v.co
 grp=merged.vertex_groups.new(name='J_Bip_C_Head');grp.add(list(range(len(merged.data.vertices))),1.,'REPLACE')
 mod=merged.modifiers.new('Head follow','ARMATURE');mod.object=arm
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(direction)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,
  'hair_collection':col.name,'hidden_originals':names,'new_hair_object':merged.name,'vertices':len(merged.data.vertices),
  'limitations':['Remesh may erase detail or produce topology defects','Original multi-bone hair replaced in trial with rigid head weight',
  'No motion, collision or GLB validation','Visual quality not accepted']},indent=2),encoding='utf8')
