# SPDX-License-Identifier: GPL-2.0-or-later
"""One-off visual check; launch Blender with the project root in PYTHONPATH."""
import sys,json,hashlib
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
from modules.skills.studio3d.character_hair_refine import apply
from control.studio3d_lane import render_lane
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
source=ROOT/'3DModels/SilverHairCharacter/user-fbx-hair-face-candidate-v4/character-rigged-experimental.blend'
manifest=json.loads((source.parent/'manifest.json').read_text(encoding='utf-8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Candidate identity changed')
with render_lane(folder):
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    report=apply();scene=bpy.context.scene;cam=scene.camera
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';cam.data.type='ORTHO'
    head=Vector((0,0,1.49));cam.data.ortho_scale=.35
    for name,axis in [('front',(0,-1,0)),('rear',(0,1,0)),('right',(1,0,0)),('left',(-1,0,0))]:
        cam.location=head+Vector(axis)*5;cam.rotation_euler=(head-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(folder/('hair-'+name+'.png'));bpy.ops.render.render(write_still=True)
    (folder/'hair-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
