"""Reversible mouth and eyelash-flow trial on the independent face study."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-03/candidate.blend';h=hashlib.sha256(src.read_bytes()).hexdigest()
out=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-04'
if out.exists():raise ValueError('Candidate exists')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];details=bpy.data.collections['Face_EyeDetails_Trial']
 key=face.shape_key_add(name='DesignSubtleMouthStudy',from_mix=False);m=face.matrix_world;inv=m.inverted();changed=0
 for v in key.data:
  p=m@v.co
  w=(1-sm(.008,.025,abs(p.x)))*sm(1.370,1.378,p.z)*(1-sm(1.393,1.402,p.z))*(1-sm(-.072,-.052,p.y))
  if w>1e-7:
   p.z=1.386+(p.z-1.386)*(1-.35*w);v.co=inv@p;changed+=1
 key.value=1.
 lash_count=0
 for ob in details.objects:
  if '-upper-' not in ob.name or ob.type!='MESH':continue
  zs=[v.co.z for v in ob.data.vertices];lo=min(zs);hi=max(zs)
  if hi-lo<1e-6:continue
  side=-1 if '-r-' in ob.name else 1
  for v in ob.data.vertices:
   t=max(0.,min(1.,(v.co.z-lo)/(hi-lo)));v.co.x+=side*.0014*t*t
  ob.data.update();lash_count+=1
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for mode in ('bald','hair'):
  hair.hide_render=mode=='bald'
  for name,d in [('front',(0,-1,0)),('45-left',(-.7071,-.7071,0)),('left',(-1,0,0))]:
   cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(mode+'-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY',mode,name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':h,'mouth_shape_key':key.name,'mouth_vertices':changed,'upper_lashes_curved':lash_count,'limitations':['Visual trial; mouth and lashes may not match target','Only static renders','Eye closure and animation untested']},indent=2),encoding='utf8')
