"""Experiment with the original continuous rear-hair surface, not extra sheets."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
from modules.skills.studio3d.character_hair_shell_trial import apply as reshape_shell
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01'
source=srcdir/'replaceable-hair.blend';manifest=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/hair-continuous-study-01'
if out.exists():raise ValueError('Existing study must be inspected')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];shell=bpy.data.objects['headend']
 reshape_shell(tails=False)
 inv=shell.matrix_world.inverted()
 for vert in shell.data.vertices:
  p=shell.matrix_world@vert.co
  t=max(0.,min(1.,(1.465-p.z)/.080));t=t*t*(3-2*t)
  rear=max(0.,min(1.,(p.y+.005)/.05))
  wave=(math.sin(117*p.x+.25)+.38*math.sin(201*p.x-1.3))/1.38
  p.z-=t*rear*(.006+.006*wave)
  p.y+=t*rear*(.003+.002*wave)
  vert.co=inv@p
 shell.data.update()
 # Keep existing strands independent and change only their lower curvature.
 changed=[]
 for ob in col.objects:
  if not ob.name.startswith('back-hair-refined-'):continue
  num=int(ob.name.rsplit('-',1)[-1]);ob.data=ob.data.copy()
  for v in ob.data.vertices:
   p=v.co;t=max(0.,min(1.,(1.47-p.z)/.13));t=t*t*(3-2*t)
   p.y+=.004*math.sin(num*1.83)*t;p.z+=.004*math.sin(num*2.46)*t
  ob.data.update();changed.append(ob.name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=20;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(direction)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'collection':col.name,'modified':['headend']+changed,'new_objects':[],
  'limitations':['Static previews only','No animation and export check','Shape and resemblance require visual review']},indent=2),encoding='utf8')
