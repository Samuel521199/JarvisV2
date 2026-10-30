"""Small, reference-guided eye-corner and brow trial on a draft copy."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/reference-mouth-geometry-study-01/candidate.blend';out=ROOT/'user-data/artifacts/studio3d-character/reference-eye-brow-shape-study-01'
if out.exists():raise ValueError('Existing study')
identity=hashlib.sha256(src.read_bytes()).hexdigest();out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def eye(p):
 a=abs(p.x);w=sm(.036,.065,a)*(1-sm(.078,.095,a))*sm(1.414,1.431,p.z)*(1-sm(1.458,1.479,p.z))*(1-sm(-.055,-.025,p.y))
 return Vector(((1 if p.x>=0 else -1)*.0010*w,0,.0025*w)),w
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];lashes=bpy.data.collections['Face_EyeDetails_Trial'];dg=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(dg);me=ev.to_mesh();pts=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
 if len(pts)!=len(face.data.vertices):raise ValueError('Topology changed')
 eye_key=face.data.shape_keys.key_blocks['Refine_Eyes'];brow_key=face.data.shape_keys.key_blocks['Refine_Brows']
 if eye_key.value!=0 or brow_key.value!=0:raise ValueError('Editing keys already active')
 brow={i for p in face.data.polygons if p.material_index==5 for i in p.vertices};m=face.matrix_world;inv=m.inverted();ne=nb=0
 for i,p in enumerate(pts):
  delta,w=eye(p)
  if w>1e-6:
   v=eye_key.data[i];v.co=inv@(m@v.co+delta);ne+=1
  if i in brow:
   b=.0018*sm(.038,.078,abs(p.x));v=brow_key.data[i];q=m@v.co;q.z+=b;v.co=inv@q;nb+=1
 eye_key.value=1.;brow_key.value=1.;bpy.context.view_layer.update()
 # The standalone eyelash meshes are head-weighted; use evaluated positions
 # to apply the same small eye-corner displacement in their rest data.
 count=0
 for ob in lashes.objects:
  if ob.type!='MESH':continue
  dg=bpy.context.evaluated_depsgraph_get();e=ob.evaluated_get(dg);mesh=e.to_mesh()
  if len(mesh.vertices)!=len(ob.data.vertices):e.to_mesh_clear();raise ValueError('Lash modifier changes topology')
  points=[e.matrix_world@v.co for v in mesh.vertices];e.to_mesh_clear();im=ob.matrix_world.inverted()
  for i,v in enumerate(ob.data.vertices):
   delta,w=eye(points[i])
   if w>1e-6:v.co=im@(ob.matrix_world@v.co+delta);count+=1
  ob.data.update()
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'eye_shape_key':eye_key.name,'brow_shape_key':brow_key.name,'eye_vertices':ne,'brow_vertices':nb,'lash_vertices':count,'limits':['Small heuristic morph, not topology rebuild','Eye corners, eyebrows, seam and expressions require visual review','No blink, rig animation or export validation']},indent=2),encoding='utf8')
