"""Combine reviewed, reversible character experiments into a new Blender file."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from control.studio3d_lane import render_lane
from modules.skills.studio3d.character_atlas_materials import apply

source = ROOT / 'user-data/artifacts/studio3d-character/body-proportion-revision-20261027-r2/character-proportions-trial.blend'
atlas = Path('C:/Users/samuel/Desktop/模型/Atlas_00001/Female_01.png')
out = ROOT / '3DModels/SilverHairCharacter/user-fbx-proportions-atlas-02'
lane = ROOT / 'user-data/artifacts/studio3d-character/proportions-atlas-02'
if out.exists():
    raise ValueError('Candidate already exists; never overwrite it')
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
atlas_hash = hashlib.sha256(atlas.read_bytes()).hexdigest()
lane.mkdir(parents=True, exist_ok=False)
with render_lane(lane):
    out.mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    report = apply(atlas, include_body_texture=False)
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash or hashlib.sha256(atlas.read_bytes()).hexdigest() != atlas_hash:
        raise ValueError('Source changed during candidate creation')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'character.blend'), check_existing=False)
    print('BLEND_READY', flush=True)
    sc = bpy.context.scene; cam = sc.camera
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 12; sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 768; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.94
    center = Vector((0, 0, .825))
    for name, vec in [('front', (0, -1, 0)), ('rear', (0, 1, 0)), ('left', (-1, 0, 0)), ('right', (1, 0, 0))]:
        cam.location = center + Vector(vec) * 5
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = str(out / ('view-' + name + '.png')); bpy.ops.render.render(write_still=True)
        print('RENDER_READY ' + name, flush=True)
    cam.data.ortho_scale = .34; center = Vector((0, 0, 1.43)); cam.location = center + Vector((0, -5, 0))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = str(out / 'view-head.png'); bpy.ops.render.render(write_still=True)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out / 'manifest.json').write_text(json.dumps({'asset_id':'character-silverhair-01','source_sha256':source_hash,
        'atlas_sha256':atlas_hash,'files':files,'status':'EXPERIMENTAL_NOT_ACCEPTED','material_report':report,
        'limitations':['User FBX derivative, manually authored edits', 'No rig animation or GLB export validation',
                       'Hair remains preliminary', 'Original body atlas omitted to match simplified reference']},
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
