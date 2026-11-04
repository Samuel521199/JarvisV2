# SPDX-License-Identifier: GPL-2.0-or-later
"""One independently UV'd and projected rigid LOD; reuses Jarvis bake backend."""
from sdk.blender_api import require_blender
import hashlib,json,sys,time
from pathlib import Path
bpy = require_blender().bpy
Vector = require_blender().mathutils.Vector
from adapters.studio3d.asset_pipeline import prepare,topology,pack_occlusion,surface_error
from modules.skills.studio3d.game_lod import validate

def main():
    folder=Path(sys.argv[-1]);req=json.loads((folder/'request.json').read_text());cfg=validate(req['contract']);source=folder/'source.blend'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Changed high source')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    names=req['visible_names'];objects=[bpy.data.objects.get(n) for n in names]
    if any(o is None or o.type!='MESH' for o in objects):raise ValueError('Source inventory changed')
    for o in objects:o.hide_render=False;o.hide_set(False)
    scene=bpy.context.scene;scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.cycles.samples=8;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=4
    began=time.monotonic()
    def save(name,data):(folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    def phase(text):save('phase.json',{'phase':text,'elapsed_seconds':time.monotonic()-began});print(text,flush=True)
    parents={o.name:o.parent.name if o.parent else None for o in objects};origins={o.name:list(o.matrix_world.translation) for o in objects}
    backgrounds=[o for o in scene.objects if o.type=='MESH' and o not in objects and not o.hide_render]
    if any(o.animation_data for o in objects):raise ValueError('Animated high requires an explicit animation-preserving adapter')
    phase('source reference render');scene.render.filepath=str(folder/'before.png');bpy.ops.render.render(write_still=True)
    mode=cfg.get('geometry_mode','reduce')
    if mode in ('silhouette','structured'):
        from adapters.studio3d.game_silhouette_worker import build
        from adapters.studio3d.projection import split
        proxies,owners=build(folder,req,dict(zip(names,objects)))
        for ob in objects:ob.hide_render=True;ob.hide_set(True)
        merged,report=prepare(folder,proxies,cfg['texture_size'],phase,{'method':'surface','generate_lods':False,'_retain_rigid_groups':True},_lods=False)
        game=split(merged[0],owners);target_names=[p['name'] for p in owners]
        report['geometry_mode']='coarse semantic exterior silhouette' if mode=='silhouette' else 'component-budgeted semantic exterior and rebuilt tyre';report['high_to_low_projection']=False
    else:
        game,report=prepare(folder,objects,cfg['texture_size'],phase,{'method':'project','category':'machine','triangle_budget':cfg['triangle_budget'],'ray_distance':cfg['ray_distance'],'generate_lods':False},_lods=False);target_names=names
    bad=[r for r in report['checks'] if r['status']=='fail']
    if bad:raise ValueError('Low mesh checks failed: '+str(bad))
    by_name={o['source_part']:o for o in game}
    if set(by_name)!=set(target_names):raise ValueError('Rigid part lost')
    distances=[]
    for original in objects:
        # Source is mapped high, no geometry reduction or old recipe rebuild.
        if original.name in by_name:distances.append({'name':original.name,**surface_error(original,by_name[original.name])})
    # Remove temporary high proxies, coordinate anchors and hidden combined low;
    # retain only the delivered rigid objects and the existing review stage.
    keep=set(game+backgrounds+[o for o in scene.objects if o.type in ('LIGHT','CAMERA')])
    for o in list(scene.objects):
        if o not in keep:bpy.data.objects.remove(o,do_unlink=True)
    root=bpy.data.objects.new('PaK38_LOD'+str(cfg['level']),None);scene.collection.objects.link(root)
    for name,obj in by_name.items():obj.name=name
    for name,obj in by_name.items():
        world=obj.matrix_world.copy();obj.parent=by_name.get(parents[name],root);obj.matrix_world=world;obj.hide_render=False;obj.hide_set(False)
    actual_triangles=sum(topology(o)['triangles'] for o in game)
    if actual_triangles>cfg['triangle_budget']:raise ValueError('Actual budget exceeded')
    if any(len(p.vertices)!=3 for o in game for p in o.data.polygons):raise ValueError('Only triangle polygons are allowed')
    micro=sum(sum(t.area<1e-10 for t in o.data.loop_triangles) for o in game)
    if micro:raise ValueError('Output has triangles below 1e-10: '+str(micro))
    bpy.ops.object.select_all(action='DESELECT')
    for o in game+[root]:o.select_set(True)
    bpy.context.view_layer.objects.active=game[0]
    phase('export projected game LOD');bpy.ops.export_scene.gltf(filepath=str(folder/'model.glb'),export_format='GLB',use_selection=True,export_apply=True,export_tangents=True,export_extras=True,export_cameras=False,export_lights=False)
    tangent=pack_occlusion(folder/'model.glb')
    scene.render.filepath=str(folder/'preview.png');scene.cycles.samples=8;phase('render game LOD');bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True,check_existing=False)
    expected={n:list(o.matrix_world.translation) for n,o in by_name.items()};expected_parent={n:o.parent.name for n,o in by_name.items()}
    for o in game+[root]:bpy.data.objects.remove(o,do_unlink=True)
    phase('actual GLB readback');bpy.ops.import_scene.gltf(filepath=str(folder/'model.glb'));loaded={o.name:o for o in bpy.context.selected_objects if o.type=='MESH'}
    if set(loaded)!=set(target_names):raise ValueError('Readback part mismatch')
    if any(o.parent is None or o.parent.name!=expected_parent[n] for n,o in loaded.items()):raise ValueError('Readback hierarchy mismatch')
    error=max((o.matrix_world.translation-Vector(expected[n])).length for n,o in loaded.items())
    if error>1e-5:raise ValueError('Readback pivot drift')
    count=sum(topology(o)['triangles'] for o in loaded.values())
    save('readback-count-check.json',{'expected':actual_triangles,'actual':count,'by_part':{n:topology(o)['triangles'] for n,o in loaded.items()}})
    if count!=actual_triangles:raise ValueError('Readback triangle mismatch')
    phase('render readback');scene.render.filepath=str(folder/'roundtrip.png');bpy.ops.render.render(write_still=True)
    save('report.json',{'version':'1.1.0','source_sha256':req['source_sha256'],'level':cfg['level'],'geometry_mode':mode,'triangles':actual_triangles,'triangle_polygons_only':True,'parts':target_names,'omitted_source_groups':sorted(set(names)-set(target_names)),'original_pivots':origins,'roundtrip_pivot_error':error,'roundtrip_hierarchy_preserved':True,'roundtrip_triangles':count,'pipeline':report,'surface_distances':distances,'micro_triangles':micro,'tangent_frames':tangent,'authoring':'Fixed first-party worker and existing projection backend; not Jarvis-generated code or autonomous retopology','elapsed_seconds':time.monotonic()-began,'unverified':['target game engine performance','continuous surface collision','continuous LOD switching','exact UV overlap/texel density']})

if __name__=='__main__':main()
