"""A reversible face-only eye-shape study on the current character."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-silhouette-02';source=srcdir/'candidate.blend'
manifest=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/face-expression-study-01'
if out.exists():raise ValueError('Existing study needs inspection')
out.mkdir(parents=True)
def smooth(a,b,v):
 t=max(0.,min(1.,(v-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];col=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 if face.data.shape_keys and face.data.shape_keys.key_blocks.get('EyeExpressionStudy'):raise ValueError('Existing expression study')
 if not face.data.shape_keys:face.shape_key_add(name='Basis')
 key=face.shape_key_add(name='EyeExpressionStudy',from_mix=False)
 m=face.matrix_world;inv=m.inverted();changed=0
 for v in key.data:
  p=m@v.co
  if 1.411<p.z<1.480 and abs(p.x)<.085:
   weight=smooth(.005,.025,abs(p.x))*(1-smooth(.055,.085,abs(p.x)))*smooth(1.411,1.430,p.z)*(1-smooth(1.462,1.480,p.z))
   # A smaller follow-up to the prior 24% eye narrowing; retain the FBX UVs.
   p.z=1.446+(p.z-1.446)*(1-.12*weight)
   p.z+=.0013*smooth(.032,.065,abs(p.x))*weight
   if weight>1e-8:v.co=inv@p;changed+=1
 key.value=1.;bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(direction)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'face_shape_key':key.name,'vertices_changed':changed,'hair_collection':col.name,
  'limitations':['Eye shape based on approximate image comparison','Head pose and lighting differ from reference','No motion or export validation']},indent=2),encoding='utf8')
