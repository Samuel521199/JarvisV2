"""Render a disposable character hair trial; set PYTHONPATH to project root."""
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from control.studio3d_lane import render_lane
from modules.skills.studio3d.character_hair_layered_trial import apply

folder = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
source = ROOT / '3DModels/SilverHairCharacter/user-fbx-hair-face-candidate-v4/character-rigged-experimental.blend'
manifest = json.loads((source.parent / 'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['files'][source.name]:
    raise ValueError('Candidate identity changed')
with render_lane(folder):
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    report = apply(); scene = bpy.context.scene; cam = scene.camera
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'layered-hair.blend'), check_existing=False)
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 12
    scene.cycles.use_denoising = True; scene.render.resolution_x = 768; scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100; scene.render.image_settings.file_format = 'PNG'
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = .35; head = Vector((0, 0, 1.49))
    for name, axis in [('front',(0,-1,0)),('rear',(0,1,0)),('right',(1,0,0)),('left',(-1,0,0))]:
        cam.location = head + Vector(axis) * 5
        cam.rotation_euler = (head - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(folder / ('hair-' + name + '.png'))
        bpy.ops.render.render(write_still=True)
    (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
