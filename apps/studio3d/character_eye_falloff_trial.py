"""Eye-shape trial against stylized face design; isolated head study."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-04/candidate.blend'
source_hash=hashlib.sha256(src.read_bytes()).hexdigest();out=ROOT/'user-data/artifacts/studio3d-character/face-eye-proportion-study-03'
if out.exists():raise ValueError('Existing trial needs inspection')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def transform(p):
 ax=abs(p.x);sx=1 if p.x>=0 else -1
 # Broad continuous falloff prevents sharp transitions in the adjacent face skin.
 wx=sm(0.,.035,ax)*(1-sm(.075,.115,ax))
 wz=sm(1.392,1.425,p.z)*(1-sm(1.466,1.505,p.z))
 wy=1-sm(-.01,.045,p.y)
 w=wx*wz*wy
 dx=sx*((ax-.045)*.22-.0005)*w
 dz=(p.z-1.446)*.08*w + .0008*sm(.044,.070,ax)*w
 return Vector((dx,0,dz)),w
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];details=bpy.data.collections['Face_EyeDetails_Trial']
 key=face.shape_key_add(name='ReferenceEyeProportionStudy',from_mix=False);m=face.matrix_world;inv=m.inverted();changed=0
 for v in key.data:
  p=m@v.co;delta,w=transform(p)
  if w>1e-7:v.co=inv@(p+delta);changed+=1
 key.value=1.
 lash_vertices=0
 for ob in details.objects:
  if ob.type!='MESH':continue
  m=ob.matrix_world.copy();inv=m.inverted()
  for v in ob.data.vertices:
   p=m@v.co;delta,w=transform(p)
   if w>1e-7:v.co=inv@(p+delta);lash_vertices+=1
  ob.data.update()
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=28;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':source_hash,'shape_key':key.name,'face_vertices_changed':changed,'lash_vertices_changed':lash_vertices,'hair_hidden_for_renders_only':True,'limitations':['Approximate shape trial, not facial retopology','Fitted points and transitions require visual evaluation','Blinks, expressions and export not tested']},indent=2),encoding='utf8')
