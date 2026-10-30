"""Attach an approximate reference-derived rear-hair volume in a trial copy."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01';blend=src/'replaceable-hair.blend'
man=json.loads((src/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(blend.read_bytes()).hexdigest()!=man['files'][blend.name]:raise ValueError('Source changed')
hull=ROOT/'user-data/artifacts/studio3d-character/hair-reference-hull-01/rear-hair.obj'
if not hull.is_file():raise FileNotFoundError(hull)
out=ROOT/'user-data/artifacts/studio3d-character/hair-reference-hull-02'
if out.exists():raise ValueError('Existing trial needs inspection')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];arm=bpy.data.objects['Armature'];material=bpy.data.materials['character-hair-procedural']
 bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.obj_import(filepath=str(hull),forward_axis='Y',up_axis='Z')
 ob=bpy.context.selected_objects[0];ob.name='hair-reference-rear-volume'
 for c in list(ob.users_collection):c.objects.unlink(ob)
 col.objects.link(ob)
 # Reduce the inferred scan density before adding head weights.
 bpy.context.view_layer.objects.active=ob;ob.select_set(True)
 dec=ob.modifiers.new('Reduce reference hull density','DECIMATE');dec.ratio=.30
 bpy.ops.object.modifier_apply(modifier=dec.name)
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deformation=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted()
 inv=deformation.inverted()
 for v in ob.data.vertices:v.co=inv@v.co
 ob.data.materials.append(material)
 for face in ob.data.polygons:face.use_smooth=True
 grp=ob.vertex_groups.new(name='J_Bip_C_Head');grp.add(list(range(len(ob.data.vertices))),1.,'REPLACE')
 mod=ob.modifiers.new('Head follow','ARMATURE');mod.object=arm
 # Retain prior strands for rollback, hidden only in this trial.
 hidden=[]
 for obj in col.objects:
  if obj.name.startswith('back-hair-refined-'):obj.hide_render=True;obj.hide_set(True);hidden.append(obj.name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(direction)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':man['files'][blend.name],
  'hull_sha256':hashlib.sha256(hull.read_bytes()).hexdigest(),'vertices':len(ob.data.vertices),'faces':len(ob.data.polygons),
  'hair_collection':col.name,'hidden_original_hair':hidden,'binding':'100% head bone',
  'limitations':['Approximate silhouette volume, not original mesh','Occluded surfaces inferred','No motion, hair collisions, or export validation']},indent=2),encoding='utf8')
