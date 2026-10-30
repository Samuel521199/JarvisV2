# SPDX-License-Identifier: GPL-2.0-or-later
"""Character trial uses the existing bounded scene worker and shared lane."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from control.studio3d_lane import render_lane
from adapters.studio3d.worker import main
import json
folder=Path(sys.argv[-1])
request=folder/'request.json'
schema=json.loads(request.read_text(encoding='utf8')).get('schema') if request.is_file() else None
if schema=='jarvis.character.refinement.v1':
    from apps.studio3d.character_refinement_worker import main as refine
    refine()
elif schema=='jarvis.character.glb-visual.v1':
    import apps.studio3d.character_glb_visual_probe
else:
    with render_lane(folder):
        main()
