import bpy,math,sys,json
from pathlib import Path
from mathutils import Vector
ROOT=Path('D:/Jarvis');sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-04/candidate.blend';out=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-30deg'
if out.exists():raise ValueError('Study exists')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False);hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];hair.hide_render=True
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 a=math.radians(30);direction=Vector((-math.sin(a),-math.cos(a),0));cam.location=center+direction*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
 sc.render.filepath=str(out/'bald-30-left.png');bpy.ops.render.render(write_still=True)
 (out/'report.json').write_text(json.dumps({'angle_degrees':30,'projection':'ORTHOGRAPHIC','source':str(src),'hair_hidden_render_only':True,'source_modified':False},indent=2),encoding='utf8')
