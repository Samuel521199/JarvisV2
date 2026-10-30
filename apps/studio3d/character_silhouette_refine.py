"""Reversible, limited body silhouette fit on the owner's existing candidate."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01';source=srcdir/'replaceable-hair.blend'
manifest=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/body-silhouette-refine-01'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 body=bpy.data.objects['Body'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 if body.data.shape_keys is None or body.data.shape_keys.key_blocks.get('ReferenceWidthCorrection'):
  raise ValueError('Unexpected existing shape keys')
 key=body.shape_key_add(name='ReferenceWidthCorrection',from_mix=False)
 # Scale magnitudes are bounded estimates from height-normalized 2-D outlines.
 # Arm intersections, lighting and pose make these approximate, not dimensions.
 stops=[(0.,1.),(.55,1.),(.68,.98),(.80,.945),(.90,.955),(1.00,.985),(1.14,1.),(1.22,1.025),(1.30,1.025),(1.38,1.),(2.,1.)]
 def factor(z):
  for (za,fa),(zb,fb) in zip(stops,stops[1:]):
   if z<=zb:
    u=max(0.,min(1.,(z-za)/(zb-za)));u=u*u*(3-2*u);return fa+(fb-fa)*u
  return 1.
 m=body.matrix_world;inverse=m.inverted()
 for v in key.data:
  p=m@v.co;p.x*=factor(p.z);v.co=inverse@p
 key.value=1.;bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=1.94;center=Vector((0,0,.825))
 for name,d in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('view-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'shape_key':key.name,'profile':stops,'hair_collection_preserved':hair.name,
  'limitations':['2D approximate silhouettes; poses differ','Head hair and face shape unchanged','Rig animation and GLB export not tested']},indent=2),encoding='utf8')
