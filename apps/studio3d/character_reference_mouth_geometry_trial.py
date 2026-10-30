"""Bounded lower-lip geometric study on editable face copy."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/reference-iris-study-03/candidate.blend';out=ROOT/'user-data/artifacts/studio3d-character/reference-mouth-geometry-study-01'
if out.exists():raise ValueError('Existing study')
identity=hashlib.sha256(src.read_bytes()).hexdigest();out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];dg=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(dg);me=ev.to_mesh();pts=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
 if len(pts)!=len(face.data.vertices):raise ValueError('Topology altered by modifiers')
 key=face.data.shape_keys.key_blocks.get('Refine_NoseMouth')
 if key is None or key.value!=0:raise ValueError('Expected an unused draft shape key')
 m=face.matrix_world;inv=m.inverted();changed=0
 for i,v in enumerate(key.data):
  p=pts[i];ax=abs(p.x);front=1-sm(-.054,-.028,p.y)
  x=(1-sm(.008,.020,ax));z=sm(1.367,1.373,p.z)*(1-sm(1.378,1.384,p.z));w=x*z*front
  if w>1e-6:
   q=m@v.co;q.y-=.0025*w;q.z+=.0017*w;v.co=inv@q;changed+=1
 key.value=1.;bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'shape_key':key.name,'vertices_changed':changed,'limits':['Approximate geometry, no lip retopology','No deformation or export validation','Visual acceptance required']},indent=2),encoding='utf8')
