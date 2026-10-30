import json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path('D:/Jarvis');sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/eye-detail-reference-03/candidate.blend'
out=ROOT/'user-data/artifacts/studio3d-character/eye-detail-reference-03-bald-evaluation'
if out.exists():raise ValueError('Evaluation exists')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 for ob in col.all_objects:ob.hide_render=True
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=20;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,d in [('front',(0,-1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True)
 (out/'report.json').write_text(json.dumps({'source':str(src),'hair_hidden_for_render_only':True,'source_saved':False},indent=2),encoding='utf8')
