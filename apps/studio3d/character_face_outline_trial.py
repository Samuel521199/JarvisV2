"""Bounded facial outline and eye-corner experiment in a separate copy."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-face-study-01';source=srcdir/'candidate.blend'
man=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=man['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/face-outline-study-01'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)
def s(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 if not face.data.shape_keys or face.data.shape_keys.key_blocks.get('EyeAndChinOutlineStudy'):raise ValueError('Unexpected face keys')
 key=face.shape_key_add(name='EyeAndChinOutlineStudy',from_mix=False);m=face.matrix_world;inv=m.inverted();changed=0
 for v in key.data:
  p=m@v.co;x=abs(p.x);sign=1 if p.x>=0 else -1
  eye=s(.015,.027,x)*(1-s(.070,.085,x))*s(1.414,1.430,p.z)*(1-s(1.458,1.480,p.z))*s(.025,.055,-p.y)
  # Extend slightly about each eye centre, with an optional shallow outer lift.
  p.x+=sign*(x-.042)*.055*eye;p.z+=.0006*s(.045,.070,x)*eye
  chin=s(.025,.055,-p.y)*(1-s(.015,.035,x))*s(1.350,1.358,p.z)*(1-s(1.378,1.395,p.z))
  p.z+=.0018*chin
  if eye>1e-7 or chin>1e-7:v.co=inv@p;changed+=1
 key.value=1.;bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,d in [('front',(0,-1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':man['files'][source.name],
  'shape_key':key.name,'vertices_affected':changed,'hair_collection':hair.name,
  'limits':['Visual interpretation is uncertain','No topology, animation or export validation']},indent=2),encoding='utf8')
