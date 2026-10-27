# SPDX-License-Identifier: GPL-2.0-or-later
"""Developer visual regression probe, run inside installed Blender.

Loads a receipt-hash-verified first-party lighting scene, then imports each
delivered GLB into it. Never part of the model-controlled execution surface.
"""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector

def verified(folder,name):
    receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    path=folder/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['files'][name]['sha256']:raise ValueError('Artifact hash changed')
    return path

def main():
    master,asset,out=map(lambda x:Path(x).resolve(),sys.argv[sys.argv.index('--')+1:]);out.mkdir(exist_ok=False,parents=True);report=[]
    blend=verified(master,'model.blend')
    for level,name in enumerate(('model.glb','model-lod1.glb','model-lod2.glb')):
        path=verified(asset,name);bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
        for obj in list(bpy.context.scene.objects):
            if obj.type not in ('LIGHT','CAMERA') and obj.name!='Studio floor':bpy.data.objects.remove(obj,do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=str(path),merge_vertices=True);parts=[o for o in bpy.context.selected_objects if o.type=='MESH'];coords=[o.matrix_world@v.co for o in parts for v in o.data.vertices]
        center=Vector([(min(v[k] for v in coords)+max(v[k] for v in coords))/2 for k in range(3)]);scene=bpy.context.scene;camera=scene.camera;offset=camera.location-center
        scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4
        for ob in parts:ob.data.calc_loop_triangles()
        row={'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'triangles':sum(len(o.data.loop_triangles) for o in parts),'renders':[]}
        for angle in (0,90,180,270):
            a=math.radians(angle);camera.location=center+Vector((offset.x*math.cos(a)-offset.y*math.sin(a),offset.x*math.sin(a)+offset.y*math.cos(a),offset.z));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
            filename=f'lod{level}-{angle}.png';scene.render.filepath=str(out/filename);bpy.ops.render.render(write_still=True);row['renders'].append(filename)
        report.append(row)
    (out/'review-inputs.json').write_text(json.dumps({'master':master.name,'asset':asset.name,'blender':bpy.app.version_string,'import_merge_vertices':True,'levels':report,'acceptance':'Visual inspection required; renders are evidence, not automatic certification'},indent=2),encoding='utf-8')

if __name__=='__main__':main()
