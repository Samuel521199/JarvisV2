"""Reversible head-proportion study from user supplied multiview design."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
source=ROOT/'user-data/artifacts/studio3d-character/eye-detail-reference-03/candidate.blend'
# Identity is taken from the 03 candidate itself and recorded for this study.
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
out=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-01'
if out.exists():raise ValueError('Existing study needs inspection')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];counts={}
 for name in ('Face','Body'):
  ob=bpy.data.objects[name];key=ob.shape_key_add(name='DesignMatureFaceProportion',from_mix=False)
  m=ob.matrix_world;inv=m.inverted();changed=0
  for v in key.data:
   p=m@v.co
   # Smoothly extend the lower front face, fading into temple and neck.
   front=1-sm(.010,.045,p.y)
   head=sm(1.327,1.354,p.z)*(1-sm(1.445,1.462,p.z))
   lower=1-sm(1.355,1.447,p.z)
   jaw=sm(1.351,1.372,p.z)*(1-sm(1.421,1.444,p.z))
   face_width=1-sm(.065,.092,abs(p.x))
   dz=-.012*front*head*lower
   dx=-.085*p.x*front*jaw*face_width
   if abs(dz)+abs(dx)>1e-9:
    p.z+=dz;p.x+=dx;v.co=inv@p;changed+=1
  key.value=1.;counts[name]=changed
 bpy.context.view_layer.update()
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for mode in ('bald','hair'):
  hair.hide_render=mode=='bald'
  for name,d in [('front',(0,-1,0)),('45-left',(-.7071,-.7071,0)),('left',(-1,0,0))]:
   cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
   sc.render.filepath=str(out/(mode+'-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY',mode,name,flush=True)
 hair.hide_render=False
 if hashlib.sha256(source.read_bytes()).hexdigest()!=source_hash:raise ValueError('Source changed')
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':source_hash,'shape_key':'DesignMatureFaceProportion','changed_vertices':counts,'hair_collection':hair.name,'limitations':['Heuristic proportions, no exact fit','Only three static views','Eyelid deformation, animation and export unverified']},indent=2),encoding='utf8')
