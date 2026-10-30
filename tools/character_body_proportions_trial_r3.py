"""Reversible character body proportion study; use project root in PYTHONPATH."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from control.studio3d_lane import render_lane

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'user-data/artifacts/studio3d-character/body-silhouette-trial-20261027/body-trial-active.blend'
OUT = ROOT / 'user-data/artifacts/studio3d-character/body-proportion-revision-20261027-r3'
EXPECTED = '9684624ab262ad9ddfab1a3915de8081c5ce8d07cf7a3bd4cc24495967a5c9fa'


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Body trial source hash changed')
    OUT.mkdir(parents=True, exist_ok=False)
    with render_lane(OUT):
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE), load_ui=False, use_scripts=False)
        body = bpy.data.objects['Body']
        keys = body.data.shape_keys.key_blocks
        keys['Trial_Silhouette_Width'].value = .45
        key = body.shape_key_add(name='Trial_Shoulder_Breadth', from_mix=False)
        for v in key.data:
            x, y, z = v.co
            # Widen shoulder by moving outer shoulder and the arms together;
            # gradually fall off over the upper chest, keeping neck central.
            vertical = smooth((z - 1.08) / .13) * (1 - smooth((z - 1.31) / .05))
            lateral = smooth((abs(x) - .035) / .14)
            if x:
                v.co.x += math.copysign(.022 * vertical * lateral, x)
        key.value = 1.0
        depth = body.shape_key_add(name='Trial_Rear_Hip_Curve', from_mix=False)
        for v in depth.data:
            x, y, z = v.co
            # Back of pelvis only; fade gradually through waist, thigh and
            # across the body to avoid moving front abdomen and limbs.
            height = smooth((z - .64) / .12) * (1 - smooth((z - .84) / .17))
            rear = smooth((y - .005) / .055)
            lateral = 1 - smooth((abs(x) - .09) / .08)
            v.co.y += .015 * height * rear * lateral
        depth.value = 1.0
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'character-proportions-trial.blend'), check_existing=False)
        print('CANDIDATE_READY', flush=True)
        sc = bpy.context.scene
        cam = sc.camera
        sc.render.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = 12
        sc.cycles.use_denoising = True
        sc.render.resolution_x = sc.render.resolution_y = 768
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = 'PNG'
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = 1.94
        center = Vector((0, 0, .825))
        for name, vec in [('front', (0, -1, 0)), ('rear', (0, 1, 0)), ('left', (-1, 0, 0)), ('right', (1, 0, 0))]:
            cam.location = center + Vector(vec) * 5
            cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = str(OUT / ('view-' + name + '.png'))
            bpy.ops.render.render(write_still=True)
            print('RENDER_READY', name, flush=True)
        report = {'status': 'EXPERIMENTAL_NOT_ACCEPTED', 'source': str(SOURCE), 'source_sha256': EXPECTED,
                  'changes': {'Trial_Silhouette_Width': .45, 'Trial_Shoulder_Breadth': 1.0,
                              'maximum_shoulder_shift_m': .022,
                              'Trial_Rear_Hip_Curve': 1.0,
                              'maximum_rear_hip_shift_m': .015},
                  'blender': bpy.app.version_string,
                  'limitations': ['Manual authored reversible shape keys, not autonomous generation',
                                  'Shoulder is a small preliminary deformation; rig animation not tested',
                                  'Rear-hip shift is preliminary and not anatomy or animation validation',
                                  'Hair unchanged', 'User visual acceptance not obtained']}
        (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
