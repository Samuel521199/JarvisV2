"""Render and package the editable face-only trial as a separate candidate."""
import hashlib,json,shutil,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
source=ROOT/'user-data/artifacts/studio3d-character/face-expression-study-01/candidate.blend'
out=ROOT/'3DModels/SilverHairCharacter/user-fbx-face-study-01'
lane=ROOT/'user-data/artifacts/studio3d-character/face-expression-package-01'
if out.exists() or lane.exists():raise ValueError('Existing package needs inspection')
identity=hashlib.sha256(source.read_bytes()).hexdigest();lane.mkdir(parents=True)
with render_lane(lane):
 out.mkdir();shutil.copyfile(source,out/'candidate.blend')
 if hashlib.sha256((out/'candidate.blend').read_bytes()).hexdigest()!=identity:raise ValueError('Candidate copy mismatch')
 bpy.ops.wm.open_mainfile(filepath=str(out/'candidate.blend'),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];body=bpy.data.objects['Body'];col=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 if not face.data.shape_keys or face.data.shape_keys.key_blocks['EyeExpressionStudy'].value!=1.:raise ValueError('Expected eye study not present')
 if not body.data.shape_keys or body.data.shape_keys.key_blocks['ReferenceWidthCorrection'].value!=1.:raise ValueError('Expected body correction missing')
 if len(col.objects)!=30:raise ValueError('Unexpected hair collection size')
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=1.94;center=Vector((0,0,.825))
 for name,d in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('view-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 for name in ('head-front.png','head-left.png','head-right.png','report.json'):
  shutil.copyfile(source.parent/name,out/name)
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
 (out/'manifest.json').write_text(json.dumps({'asset_id':'character-silverhair-01','status':'EXPERIMENTAL_NOT_ACCEPTED',
  'source_sha256':identity,'files':files,'automatic_promotion':False,'user_approval':False,
  'limits':['Face and hair still differ from reference','No animation or GLB export validation','Original source FBX plus manually authored edits']},
  indent=2)+'\n',encoding='utf8')
