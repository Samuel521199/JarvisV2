# SPDX-License-Identifier: GPL-2.0-or-later
"""Create a derivative of one owner-supplied, hash-verified character baseline.

Fixed first-party operations only. Run in background with autoexec disabled;
the input is a local copy of a known diagnostic, never a model-supplied path.
"""
import bpy,sys,json,hashlib,time
from pathlib import Path
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
from modules.skills.studio3d.character_head import head_objects
from modules.skills.studio3d.character_contract import parameters
from modules.skills.studio3d.character_recipe import scene as initial_scene
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.character_fbx_face import apply as apply_face
from adapters.studio3d.worker import geometry

folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
request=json.loads((folder/'request.json').read_text(encoding='utf8'))
if sha(folder/'source.blend')!=request['source_sha256']:raise ValueError('Baseline hash changed')
with render_lane(folder):
    started=time.monotonic()
    bpy.ops.wm.open_mainfile(filepath=str(folder/'source.blend'),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    arm=next((o for o in scene.objects if o.type=='ARMATURE'),None)
    if not arm or len(arm.data.bones)!=93 or not {'Body','Face','headend'} <= {o.name for o in scene.objects}:
        raise ValueError('Unexpected source character identity')
    # Match the visible pale skin of the supplied reference, using a plain
    # neutral surface. Do not read or apply any of the supplied atlas images.
    for material in bpy.data.materials:
        name=material.name.casefold()
        if '_body_00_skin' in name or '_face_00_skin' in name:
            bs=material.node_tree.nodes.get('Principled BSDF') if material.use_nodes else None
            if bs:bs.inputs['Base Color'].default_value=(.82,.72,.69,1)
    hair=bpy.data.materials.new('character-hair-procedural');hair.use_nodes=True
    bs=hair.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.52,.50,.58,1);bs.inputs['Roughness'].default_value=.6
    values=initial_scene(parameters());values['objects']=head_objects(parameters());values=validate(values)
    names=[]
    for row in values['objects']:
        if not row['id'].startswith(('hair-scalp-refined','back-hair-refined','bang-refined','side-hair-refined')):continue
        obj=geometry(row);obj.data.materials.append(hair)
        if row['modifiers'].get('subdivision'):
            mod=obj.modifiers.new('Hair smoothing','SUBSURF');mod.levels=mod.render_levels=row['modifiers']['subdivision']
        obj.matrix_world=Matrix(((0,1.07,0,0),(-1,0,0,0),(0,0,1,-.052),(0,0,0,1)))
        names.append(obj.name)
    face_report=apply_face()
    if any(im.source=='FILE' and im.filepath for im in bpy.data.images):
        raise ValueError('Baseline has external image references; refusing to embed them')
    scene['character_head_note']='Experimental added hair and procedural face accents, not source reference reconstruction. Hair is not rigged.'
    blend=folder/'character-rigged-experimental.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
    # Export a detached evaluated still; original rig and provisional pose stay in BLEND.
    source_objects=[o for o in scene.objects if o.type in ('MESH','CURVE') and not o.hide_render]
    deps=bpy.context.evaluated_depsgraph_get();static=[];coords=[]
    for o in source_objects:
        e=o.evaluated_get(deps);mesh=bpy.data.meshes.new_from_object(e,preserve_all_data_layers=True,depsgraph=deps)
        if o.name=='Face':
            # The original face-overlay rectangles require missing alpha maps.
            # GLB cannot encode a standalone Transparent-BSDF node reliably,
            # so remove those faces only from the detached static export copy.
            import bmesh
            excluded={i for i,m in enumerate(mesh.materials) if m and any(k in m.name.casefold() for k in ('facebrow','faceeyelash','faceeyeline','eyehighlight'))}
            bm=bmesh.new();bm.from_mesh(mesh)
            bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index in excluded],context='FACES')
            bm.to_mesh(mesh);bm.free();mesh.update()
        tmp=bpy.data.objects.new('static-'+o.name,mesh);scene.collection.objects.link(tmp);tmp.matrix_world=o.matrix_world.copy();static.append(tmp)
        coords.extend(tmp.matrix_world@v.co for v in mesh.vertices)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in static:obj.select_set(True)
    bpy.context.view_layer.objects.active=static[0]
    glb=folder/'character-static-experimental.glb'
    bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_animations=False,export_skins=False,export_cameras=False,export_lights=False)
    for obj in static:bpy.data.objects.remove(obj,do_unlink=True)
    low=Vector([min(v[i] for v in coords) for i in range(3)]);high=Vector([max(v[i] for v in coords) for i in range(3)])
    center=(low+high)/2;span=max(high-low);cam=scene.camera;cam.data.type='ORTHO';cam.data.ortho_scale=max(high.z-low.z,high.x-low.x)*1.18
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    for name,vec in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
        cam.location=center+Vector(vec)*span*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(folder/('view-'+name+'.png'));bpy.ops.render.render(write_still=True)
    cam.data.ortho_scale=.35;head=Vector((0,0,1.49));cam.location=head+Vector((0,-1,0))*5;cam.rotation_euler=(head-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(folder/'view-head.png');bpy.ops.render.render(write_still=True)
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(glb),merge_vertices=False)
    loaded=[o for o in bpy.context.scene.objects if o.type=='MESH'];verts=[o.matrix_world@v.co for o in loaded for v in o.data.vertices]
    if not verts:raise ValueError('No meshes in exported GLB')
    lo=Vector([min(v[i] for v in verts) for i in range(3)]);hi=Vector([max(v[i] for v in verts) for i in range(3)])
    error=max(abs(a-b) for a,b in zip(list(low)+list(high),list(lo)+list(hi)))
    if error>.002:raise ValueError('Export reimport bounds differ')
    result={'schema':'jarvis.character-fbx-head-candidate.v1','source_sha256':request['source_sha256'],'source':'User FBX diagnostic BLEND derivative',
            'procedural_hair_objects':names,'face':face_report,'atlas_loaded':False,'rig_bones':93,'hair_bound_to_rig':False,
            'blender':bpy.app.version_string,'elapsed_seconds':time.monotonic()-started,
            'roundtrip':{'passed':True,'max_bound_error_m':error},
            'limits':['Provisional hair and face; no claim of reference match','Source model provenance and rights unknown','BLEND retains rig; added hair and eye accents not rigged','GLB is a static evaluated pose, not animation ready','No user approval']}
    (folder/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
