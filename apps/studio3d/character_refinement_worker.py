# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed local user-asset refinement. Input is a hash-frozen derived copy."""
import hashlib
import json
import sys
import time
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    request=json.loads((folder/'request.json').read_text(encoding='utf8'))
    if set(request)!={'schema','source_sha256','asset_id'} or request['schema']!='jarvis.character.refinement.v1' or request['asset_id']!='character-silverhair-01':
        raise ValueError('Invalid character refinement request')
    if sha(folder/'source.blend')!=request['source_sha256']:raise ValueError('Frozen source mismatch')
    with render_lane(folder):
        start=time.monotonic()
        bpy.ops.wm.open_mainfile(filepath=str(folder/'source.blend'),load_ui=False,use_scripts=False)
        sc=bpy.context.scene
        rig=next((o for o in sc.objects if o.type=='ARMATURE'),None)
        if not rig or len(rig.data.bones)!=93 or not {'Body','Face','headend'} <= {o.name for o in sc.objects}:
            raise ValueError('Unexpected source character')
        from modules.skills.studio3d.character_body_refine import apply as body
        from modules.skills.studio3d.character_face_refine import apply as face
        # The independently rendered hair candidate exposed bald gaps and was
        # rejected; retain the previous version rather than adopting regression.
        changes={'body':body(),'face':face(),
                 'hair':{'status':'RETAINED_PREVIOUS','reason':'Candidate inspection showed visible scalp gaps; not adopted'}}
        if any(im.source=='FILE' and im.filepath for im in bpy.data.images):
            raise ValueError('External images must not be embedded')
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'character-refined.blend'),check_existing=False)
        originals=[o for o in sc.objects if o.type in ('MESH','CURVE') and not o.hide_render]
        deps=bpy.context.evaluated_depsgraph_get();parts=[];coords=[]
        for obj in originals:
            evaluated=obj.evaluated_get(deps)
            mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=deps)
            if obj.name=='Face':
                import bmesh
                excluded={i for i,m in enumerate(mesh.materials) if m and any(k in m.name.casefold() for k in ('facebrow','faceeyelash','faceeyeline','eyehighlight'))}
                bm=bmesh.new();bm.from_mesh(mesh)
                bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index in excluded],context='FACES')
                bm.to_mesh(mesh);bm.free();mesh.update()
            temp=bpy.data.objects.new('static-'+obj.name,mesh);sc.collection.objects.link(temp)
            temp.matrix_world=obj.matrix_world.copy();parts.append(temp)
            coords.extend(temp.matrix_world@v.co for v in mesh.vertices)
        if not coords:raise ValueError('Empty character geometry')
        bpy.ops.object.select_all(action='DESELECT')
        for o in parts:o.select_set(True)
        bpy.context.view_layer.objects.active=parts[0]
        glb=folder/'character-refined-static.glb'
        bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_skins=False,export_cameras=False,export_lights=False)
        for o in parts:bpy.data.objects.remove(o,do_unlink=True)
        low=Vector([min(v[i] for v in coords) for i in range(3)]);high=Vector([max(v[i] for v in coords) for i in range(3)])
        center=(low+high)/2;span=max(high-low);cam=sc.camera
        if not cam:raise ValueError('Missing reference camera')
        cam.data.type='ORTHO';cam.data.ortho_scale=max(high.z-low.z,high.x-low.x)*1.18
        sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=12;sc.cycles.use_denoising=True
        sc.render.resolution_x=768;sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
        for name,vec in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
            cam.location=center+Vector(vec)*span*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
            sc.render.filepath=str(folder/('view-'+name+'.png'));bpy.ops.render.render(write_still=True)
        cam.data.ortho_scale=.35;head=Vector((0,0,1.49));cam.location=head+Vector((0,-1,0))*5
        cam.rotation_euler=(head-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(folder/'view-head.png');bpy.ops.render.render(write_still=True)
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(glb),merge_vertices=False)
        verts=[o.matrix_world@v.co for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]
        if not verts:raise ValueError('Empty imported GLB')
        lo=Vector([min(v[i] for v in verts) for i in range(3)]);hi=Vector([max(v[i] for v in verts) for i in range(3)])
        err=max(abs(a-b) for a,b in zip(list(low)+list(high),list(lo)+list(hi)))
        if err>.002:raise ValueError('GLB bounds do not match')
        report={'schema':'jarvis.character.refinement.report.v1','source_sha256':request['source_sha256'],
                'source':'derived from user-provided FBX; first-party manual tools', 'changes':changes,
                'roundtrip':{'passed':True,'max_bound_error_m':err},'blender':bpy.app.version_string,
                'elapsed_seconds':time.monotonic()-start,'rig_bones':93,'user_approval':False,
                'limitations':['Not independent reconstruction','GLB is static','New hair and eye details may be unrigged',
                               'Reference similarity and deformation require review']}
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
