"""Render the effects of hiding existing hair pieces in a throwaway process."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
source=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01/replaceable-hair.blend'
out=ROOT/'user-data/artifacts/studio3d-character/hair-component-probe-01'
if out.exists():raise ValueError('Probe exists')
out.mkdir(parents=True);identity=hashlib.sha256(source.read_bytes()).hexdigest()
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=12;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));cam.location=center+Vector((0,5,0));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
 modes={'all':[],'without-scalp':['hair-scalp-refined'],'without-headend':['headend'],
        'without-both':['headend','hair-scalp-refined']}
 for name,hidden in modes.items():
  for key in ('headend','hair-scalp-refined'):bpy.data.objects[key].hide_render=key in hidden
  sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print(name,flush=True)
 (out/'report.json').write_text(json.dumps({'source_sha256':identity,'modes':modes,'source_modified':False},indent=2),encoding='utf8')
