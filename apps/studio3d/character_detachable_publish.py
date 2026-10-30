"""Copy an independently tested editable character candidate and render its views."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane

source=ROOT/'user-data/artifacts/studio3d-character/hair-separation-bound-01'
output=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01'
lane=ROOT/'user-data/artifacts/studio3d-character/detachable-hair-delivery-01'
if output.exists() or lane.exists():raise ValueError('Existing candidate must be inspected')
files=['replaceable-hair.blend','report.json','hair-hidden.png','hair-visible.png','head-turned.png']
source_sha={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in files}
lane.mkdir(parents=True)
with render_lane(lane):
    output.mkdir()
    for n in files:shutil.copyfile(source/n,output/n)
    if any(hashlib.sha256((output/n).read_bytes()).hexdigest()!=h for n,h in source_sha.items()):
        raise ValueError('Candidate copy identity mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(output/'replaceable-hair.blend'),load_ui=False,use_scripts=False)
    if not bpy.data.collections.get('Hair_SilverHair_Replaceable_01'):
        raise ValueError('Hair collection missing')
    sc=bpy.context.scene;cam=sc.camera
    sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=12;sc.cycles.use_denoising=True
    sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=1.94
    center=Vector((0,0,.825))
    for name,vec in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
        cam.location=center+Vector(vec)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=str(output/('view-'+name+'.png'));bpy.ops.render.render(write_still=True)
        print('RENDER_READY '+name,flush=True)
    contents={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output/'manifest.json').write_text(json.dumps({'asset_id':'character-silverhair-01','source_sha256':source_sha,
        'files':contents,'status':'EXPERIMENTAL_NOT_ACCEPTED','user_approval':False,'automatic_promotion':False,
        'limitations':['User-provided FBX derivative; manual edits','Head-follow test only 15-degree pose',
                       'No independent hair motion, animation suite or GLB validation','Face, hair and proportions remain unfinished']},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8')
