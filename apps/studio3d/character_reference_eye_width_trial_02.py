"""Monotonic, bounded eye-width trial based on front-view comparison."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/reference-eye-brow-shape-study-01/candidate.blend';out=ROOT/'user-data/artifacts/studio3d-character/reference-eye-width-study-02'
if out.exists():raise ValueError('Study exists')
identity=hashlib.sha256(src.read_bytes()).hexdigest();out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
knots=[(0.,0.),(.010,.0065),(.020,.0130),(.045,.042),(.070,.074),(.090,.090),(.12,.12)]
def mapped(x):
 if x>=knots[-1][0]:return x
 for (a,b),(c,d) in zip(knots,knots[1:]):
  if x<=c:return b+(d-b)*(x-a)/(c-a)
 return x
def change(p):
 a=abs(p.x);sign=1 if p.x>=0 else -1
 w=sm(1.413,1.431,p.z)*(1-sm(1.462,1.486,p.z))*(1-sm(-.045,.005,p.y))
 return Vector((sign*(mapped(a)-a)*w,0,0)),w
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];lashes=bpy.data.collections['Face_EyeDetails_Trial'];dg=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(dg);me=ev.to_mesh();pts=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
 if len(pts)!=len(face.data.vertices):raise ValueError('Topology changed')
 if face.data.shape_keys.key_blocks.get('ReferenceEyeWidthFine'):raise ValueError('Key exists')
 iris_ids={i for poly in face.data.polygons if poly.material_index in (1,2) for i in poly.vertices}
 key=face.shape_key_add(name='ReferenceEyeWidthFine',from_mix=False);m=face.matrix_world;inv=m.inverted();changed=0
 for i,p in enumerate(pts):
  delta,w=change(p)
  if i in iris_ids:delta=Vector(((-1 if p.x>=0 else 1)*.0025,0,0));w=1.
  if w>1e-6:
   v=key.data[i];v.co=inv@(m@v.co+delta);changed+=1
 key.value=1.;bpy.context.view_layer.update();count=0
 for ob in lashes.objects:
  if ob.type!='MESH':continue
  dg=bpy.context.evaluated_depsgraph_get();e=ob.evaluated_get(dg);mesh=e.to_mesh()
  if len(mesh.vertices)!=len(ob.data.vertices):e.to_mesh_clear();raise ValueError('Lash topology changed')
  pts=[e.matrix_world@v.co for v in mesh.vertices];e.to_mesh_clear();inv=ob.matrix_world.inverted()
  for i,v in enumerate(ob.data.vertices):
   delta,w=change(pts[i])
   if w>1e-6:v.co=inv@(ob.matrix_world@v.co+delta);count+=1
  ob.data.update()
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'shape_key':key.name,'vertices':changed,'lash_vertices':count,'limits':['Monotonic width map blended in 3D; no guarantee against folds or intersections','Heuristic image-derived parameters','No animation or export tests']},indent=2),encoding='utf8')
