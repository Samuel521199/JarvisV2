"""Render an orthographic head baseline for a facial study."""
from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0,str(_BootstrapPath(__file__).resolve().parents[2]))
from adapters.studio3d.learning_worker import install_runtime
install_runtime(__file__)
from sdk.runtime_paths import project_path, reference_path, optional_character_tool
from sdk.blender_api import require_blender
import hashlib,json,sys
from pathlib import Path
bpy = require_blender().bpy
Vector = require_blender().mathutils.Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
source=project_path('3DModels/SilverHairCharacter/user-fbx-silhouette-02/candidate.blend')
out=project_path('user-data/artifacts/studio3d-character/face-expression-baseline-01')
if out.exists():raise ValueError('Existing baseline requires inspection')
out.mkdir(parents=True);identity=hashlib.sha256(source.read_bytes()).hexdigest()
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,d in [('front',(0,-1,0)),('left',(-1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'source_sha256':identity,'method':'same camera and render as face-expression-study-01','source_modified':False},indent=2),encoding='utf8')
