"""Reversible comparison of lighting on the current character candidate."""
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane

source=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01/replaceable-hair.blend'
out=ROOT/'user-data/artifacts/studio3d-character/reference-lighting-study-01'
if out.exists():raise ValueError('Existing trial must be inspected')
identity=hashlib.sha256(source.read_bytes()).hexdigest();out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 sc=bpy.context.scene;cam=sc.camera
 bg=next(n for n in sc.world.node_tree.nodes if n.type=='BACKGROUND')
 sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=20;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100
 sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=1.94
 target=Vector((0,0,.825));cam.location=target+Vector((0,-5,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
 for tag,strength in [('baseline',.8),('medium',1.15),('bright',1.55)]:
  bg.inputs['Strength'].default_value=strength
  sc.render.filepath=str(out/(tag+'.png'));bpy.ops.render.render(write_still=True)
  print('RENDER_READY '+tag,flush=True)
 (out/'report.json').write_text(json.dumps({'source_sha256':identity,'world_strength':[.8,1.15,1.55],
  'limits':['Lighting only; no geometry changes','Different lighting can hide surface defects','No user acceptance']},indent=2),encoding='utf8')
