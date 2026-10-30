# SPDX-License-Identifier: GPL-2.0-or-later
"""Bake high surface materials per rigid owner, preserving geometric surfaces.

Uses the existing surface atlas backend without decimation, projection or LODs.
Keeps a separate atlas/mesh per movable owner and verifies its surface against
the original evaluated parts. Origins are declared visual animation origins,
not measured physical joints. The editable source blend is never overwritten.
"""
import hashlib,json,sys,time
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from adapters.studio3d.asset_pipeline import prepare,surface_error,pack_occlusion
from modules.skills.studio3d.high_finish import validate,VERSION
from adapters.studio3d.high_finish_reuse import verify_source,load_groups


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]);request=json.loads((folder/'request.json').read_text(encoding='utf-8'));source=folder/'source.blend'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=request['source_sha256']:raise ValueError('Source bytes differ')
    config=validate(request['contract'],request['visible_names']);began=time.monotonic()
    reuse_check=verify_source(folder,request,config)
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    originals={n:bpy.data.objects.get(n) for n in request['visible_names']}
    if any(o is None or o.type not in ('MESH','CURVE') for o in originals.values()):raise ValueError('Frozen source inventory changed')
    if any(m.type=='DECIMATE' for o in originals.values() for m in o.modifiers):raise ValueError('High finish does not accept reduction modifiers')
    # Explicit world-normal triplanar weights survive joining rotated parts.
    # Blender BOX axis selection otherwise changes when mesh owners change.
    from tools.studio3d_blender_material_projection import replace_world_box_projection
    projection_repairs={m.name:replace_world_box_projection(m) for m in {m for o in originals.values() for m in o.data.materials}}
    reused=load_groups(folder,config,originals)
    def phase(text):
        save(folder/'phase.json',{'phase':text});print(text,flush=True)
    scene=bpy.context.scene;camera=scene.camera;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.filepath=str(folder/'before.png')
    phase('high surface before render');bpy.ops.render.render(write_still=True)
    groups={};reports=[];all_source=[]
    for declaration in config['groups']:
        name=declaration['id'];out=folder/name;out.mkdir(exist_ok=True);members=[originals[n] for n in declaration['members']]
        # Independent evaluated source surface used for the geometric check.
        deps=bpy.context.evaluated_depsgraph_get();vertices=[];faces=[]
        for obj in members:
            evaluated=obj.evaluated_get(deps);mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=deps);offset=len(vertices)
            vertices.extend([tuple(obj.matrix_world@v.co) for v in mesh.vertices]);faces.extend([[offset+i for i in p.vertices] for p in mesh.polygons]);bpy.data.meshes.remove(mesh)
        all_source.extend(vertices)
        data=bpy.data.meshes.new('check-'+name);data.from_pydata(vertices,[],faces);data.update();reference=bpy.data.objects.new('check-'+name,data);scene.collection.objects.link(reference);reference.hide_render=True;reference.hide_set(True)
        if name in reused:
            phase(name+': reuse fingerprint-verified mapped group');obj=reused[name];obj.data.transform(obj.matrix_world);obj.matrix_world=Matrix.Identity(4);bpy.context.view_layer.update();parts=[obj];report=request['reuse']['groups'][name]['atlas']
            for member in members:member.hide_render=True;member.hide_set(True)
        else:parts,report=prepare(out,members,config['texture_size'],lambda text:phase(name+': '+text),{'method':'surface','generate_lods':False},_lods=False)
        if len(parts)!=1 or len(report['lods'])!=1:raise ValueError('Unexpected high preparation topology')
        obj=parts[0];check=surface_error(reference,obj)
        if check['max_distance_m']>0.00001:raise ValueError('High surface changed beyond 10 micrometres: '+name)
        bpy.data.objects.remove(reference,do_unlink=True);bpy.data.meshes.remove(data)
        # Free names before naming the game meshes; hidden originals otherwise
        # silently force Blender's .001 suffix and break rigid ownership IDs.
        for member in declaration['members']:originals[member].name='source-'+member
        obj.name=name;origin=Vector(declaration['pivot']);obj.data.transform(Matrix.Translation(-origin));obj.location=origin
        obj['jarvis_motion']=declaration['motion'];obj['source_members']=json.dumps(declaration['members'])
        obj.hide_render=True;obj.hide_set(True);groups[name]=obj
        reports.append({'group':name,'motion':declaration['motion'],'members':declaration['members'],'surface_check':check,'atlas':report,'mesh_reduction_requested':False,'reused_from':request['reuse']['export_id'] if name in reused else None})
    root=bpy.data.objects.new('Game-high',None);scene.collection.objects.link(root)
    bpy.context.view_layer.update()
    for declaration in config['groups']:
        obj=groups[declaration['id']];matrix=obj.matrix_world.copy();obj.parent=groups.get(declaration['parent'],root);obj.matrix_world=matrix;obj.hide_set(False);obj.hide_render=False
    root['jarvis_game_asset']=json.dumps({'schema':'jarvis.game-high.v1','kind':'rigid_high_candidate','version':VERSION,'motion':'separate named groups and declared origins; no animation clip or engine performance certification'})
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [root,*groups.values()]:obj.select_set(True)
    bpy.context.view_layer.objects.active=next(iter(groups.values()));bpy.context.view_layer.update()
    actual_points=[tuple(o.matrix_world@v.co) for o in groups.values() for v in o.data.vertices]
    bounds=lambda ps:[[min(p[i] for p in ps) for i in range(3)],[max(p[i] for p in ps) for i in range(3)]]
    before_bounds=bounds(all_source);after_bounds=bounds(actual_points)
    bound_error=max(abs(before_bounds[j][i]-after_bounds[j][i]) for j in range(2) for i in range(3))
    if bound_error>0.00001:raise ValueError('Rigid origin/parent operation changed posed bounds')
    phase('export grouped textured high')
    bpy.ops.export_scene.gltf(filepath=str(folder/'model.glb'),export_format='GLB',use_selection=True,export_apply=True,export_tangents=True,export_extras=True,export_materials='EXPORT',export_cameras=False,export_lights=False)
    tangents=pack_occlusion(folder/'model.glb')
    scene.cycles.samples=24;scene.render.filepath=str(folder/'after.png');phase('high surface after render');bpy.ops.render.render(write_still=True)
    # Final high blend has packed maps and grouped meshes; editable original stays in source.
    for obj in originals.values():bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True,check_existing=False)
    expected=set(groups);expected_origins={n:list(o.matrix_world.translation) for n,o in groups.items()}
    expected_parents={n:o.parent.name for n,o in groups.items()}
    # Keep the identical stage/camera, replace only the exported asset with its
    # imported GLB. This catches a texture/normal export defect that a BLEND
    # render or a format-only check cannot establish.
    for obj in [*groups.values(),root]:bpy.data.objects.remove(obj,do_unlink=True)
    phase('render imported grouped GLB');bpy.ops.import_scene.gltf(filepath=str(folder/'model.glb'))
    imported={o.name:o for o in bpy.context.selected_objects if o.type=='MESH'}
    actual=set(imported)
    if actual!=expected:raise ValueError('Rigid group roundtrip differs')
    bpy.context.view_layer.update()
    origin_error=max((o.matrix_world.translation-Vector(expected_origins[n])).length for n,o in imported.items())
    if origin_error>0.00001:raise ValueError('Rigid origin roundtrip differs')
    if any(o.parent is None or o.parent.name!=expected_parents[n] for n,o in imported.items()):raise ValueError('Rigid hierarchy roundtrip differs')
    scene.render.filepath=str(folder/'roundtrip.png');bpy.ops.render.render(write_still=True)
    save(folder/'report.json',{'version':VERSION,'source_sha256':request['source_sha256'],'world_projection_repair':projection_repairs,'groups':reports,'rigid_mesh_count':len(groups),
        'material_atlases':len(groups),'roundtrip_group_names':sorted(actual),'roundtrip_origin_error_m':origin_error,'roundtrip_hierarchy_preserved':True,'tangents':tangents,'elapsed_seconds':time.monotonic()-began,'posed_bound_error_m':bound_error,
        'reduction':False,'high_to_low_projection':False,'lods_generated':False,'user_approval':False,'AAA_certified':False,'reuse_verification':reuse_check,
        'unverified':['atlas visual equivalence','exact UV overlap/density','animation collision','target engine draw calls and frame time']})


if __name__=='__main__':main()
