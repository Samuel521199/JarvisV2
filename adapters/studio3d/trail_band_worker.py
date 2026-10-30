# SPDX-License-Identifier: GPL-2.0-or-later
"""Revolve measured original cross sections and retain non-target surfaces."""
import bpy,json,hashlib,time,math
from mathutils import Vector
from modules.skills.studio3d.trail_band import fit,geometry,sub
from modules.skills.studio3d.attachment_seat import components
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene

def rebuild(ob,parts,segments):
    old=ob.data;allids=set(i for ids,p in parts for i in ids);kept=[i for i in range(len(old.vertices)) if i not in allids];remap={i:k for k,i in enumerate(kept)}
    v0=[list(old.vertices[i].co) for i in kept];faces0=[p for p in old.polygons if all(i not in allids for i in p.vertices)]
    if any(any(i in allids for i in p.vertices) and not all(i in allids for i in p.vertices) for p in old.polygons):raise ValueError('Partial original component')
    vs=v0.copy();fs=[[remap[i] for i in p.vertices] for p in faces0];smooth=[p.use_smooth for p in faces0];uv0=[(l.name,[[list(l.data[i].uv) for i in p.loop_indices] for p in faces0],l.active_render) for l in old.uv_layers];added_uv=[];records=[];inverse=ob.matrix_world.inverted()
    for ids,profile in parts:
        ps,pfs,uv,sm=geometry(profile,segments);offset=len(vs);vs.extend([list(inverse@Vector(p)) for p in ps]);fs.extend([[offset+i for i in f] for f in pfs]);smooth.extend(sm);added_uv.extend(uv);records.append({'original_indices':ids,'profile':profile,'first_vertex':offset,'vertices':len(ps),'faces':len(pfs)})
    if len(vs)>26000:raise ValueError('Band refinement vertex budget')
    mesh=bpy.data.meshes.new(ob.name+'-measured-profile');mesh.from_pydata(vs,[],fs);mesh.materials.append(old.materials[0]);mesh.update();ob.data=mesh
    for p,flag in zip(mesh.polygons,smooth):p.use_smooth=flag
    sharp={tuple(sorted((remap[e.vertices[0]],remap[e.vertices[1]]))):e.use_edge_sharp for e in old.edges if all(i in remap for i in e.vertices)}
    for e in mesh.edges:
        key=tuple(sorted(e.vertices))
        if key in sharp:e.use_edge_sharp=sharp[key]
    if not uv0:raise ValueError('Original UV required')
    for name,values,active in uv0:
        layer=mesh.uv_layers.new(name=name);layer.active_render=active
        for p,uv in zip(mesh.polygons,values+added_uv):
            if len(p.loop_indices)!=len(uv):raise ValueError('UV loop mismatch')
            for i,q in zip(p.loop_indices,uv):layer.data[i].uv=q
        if [[list(layer.data[i].uv) for i in p.loop_indices] for p in list(mesh.polygons)[:len(faces0)]]!=values:raise ValueError('Non-target component UV changed')
        for p in list(mesh.polygons)[len(faces0):]:
            points=[layer.data[i].uv for i in p.loop_indices];area=abs(sum(a.x*b.y-a.y*b.x for a,b in zip(points,points[1:]+points[:1])))/2
            if area<=1e-10:raise ValueError('Refined UV degenerate')
    mesh.uv_layers.active_index=old.uv_layers.active_index
    if [list(v.co) for v in mesh.vertices[:len(v0)]]!=v0 or [list(p.vertices) for p in list(mesh.polygons)[:len(faces0)]]!=[[remap[i] for i in p.vertices] for p in faces0]:raise ValueError('Unchanged part geometry altered')
    bpy.context.view_layer.update();quality=inventory(ob,bpy.context.evaluated_depsgraph_get())
    if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Revolved profile topology failed')
    return {'object':ob.name,'kept_vertices':len(kept),'kept_faces':len(faces0),'kept_uv_loops':sum(len(p.loop_indices) for p in faces0),'original_kept_vertex_indices':kept,'parts':records,'quality':quality}

def run(folder,req,c,source,version):
    started=time.monotonic()
    if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Exact band source changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
    if len(objects)!=79 or any(o is None for o in objects.values()):raise ValueError('Original inventory required')
    targets={'trail-'+prefix+'-'+s for prefix in ('collars','strap-details') for s in ('left','right')};before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n not in targets};deps=bpy.context.evaluated_depsgraph_get();plans=[];neighbors=[]
    for t in c['targets']:
        side=t['side'];tube=objects['trail-tube-'+side];strap=objects['trail-strap-details-'+side];collar=objects['trail-collars-'+side]
        if any(dependency(ob)[0]!=t[key] for ob,key in ((strap,'strap_digest'),(collar,'collar_digest'),(tube,'tube_digest'))):raise ValueError('Measured band dependency changed')
        for ob,count in ((strap,8658),(collar,520),(tube,194)):
            if ob.type!='MESH' or ob.modifiers or len(ob.data.vertices)!=count or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original band source topology required')
        for ob in (strap,collar):
            if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('World coating required')
        axis=sub(list(tube.matrix_world@tube.data.vertices[193].co),list(tube.matrix_world@tube.data.vertices[192].co));parts=[]
        groups=components(len(strap.data.vertices),[list(p.vertices) for p in strap.data.polygons])
        if [len(x) for x in groups]!=[320,320,152,152,152]*3+[442,162,162]*3+[1024]*3 or any(ix not in groups for ix in t['bead_components']):raise ValueError('Current twenty-seven complete components required')
        for ix in t['bead_components']:parts.append((ix,fit([list(strap.matrix_world@strap.data.vertices[i].co) for i in ix],axis,'bead')))
        collar_groups=components(len(collar.data.vertices),[list(p.vertices) for p in collar.data.polygons])
        if [len(g) for g in collar_groups]!=[130]*4:raise ValueError('Original four sleeve components required')
        sleeves=[(ix,fit([list(collar.matrix_world@collar.data.vertices[i].co) for i in ix],axis,'collar')) for ix in collar_groups]
        plans.extend([(collar,sleeves),(strap,parts)])
        oldtree=world_tree(collar,deps);excluded=set(i for ix,p in parts for i in ix)
        for ob in (strap,objects['fasteners-trail-'+side]):
            for index,vert in enumerate(ob.data.vertices):
                if ob==strap and index in excluded:continue
                point=ob.matrix_world@vert.co;nearest=oldtree.find_nearest(point)
                if nearest[0] is not None and nearest[3]<.03:neighbors.append({'object':ob.name,'index':index,'point':list(point),'old_distance':nearest[3],'support':collar.name})
    lo,hi=c['inspection']['bounds']
    # Full third left band must fit, not just an unchanged framing marker.
    for ob,parts in plans:
        if ob.name=='trail-strap-details-left':
            for ix,p in parts[-2:]:
                vs,_,_,_=geometry(p,c['segments'])
                if any(not lo[k]<=q[k]<=hi[k] for q in vs for k in range(3)):raise ValueError('Full representative band outside fixed frame')
    members={n:objects[n] for n in list(c['inspection']['regions'].values())[0]};cam=bpy.context.scene.camera;oldcam=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);bpy.context.scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],members,'before');actions=[rebuild(ob,parts,c['segments']) for ob,parts in plans];trees={s:world_tree(objects[s],deps) for s in ('trail-collars-left','trail-collars-right')}
    growth=[]
    for sample in neighbors:
        point=Vector(sample['point']);hit=trees[sample['support']].find_nearest(point)
        if hit[0] is None or hit[3]-sample['old_distance']>.003:raise ValueError('Adjacent attachment support regressed')
        growth.append(hit[3]-sample['old_distance'])
    contacts=[]
    for action in actions:
        if not action['object'].startswith('trail-strap-details'):continue
        ob=objects[action['object']];side=ob.name.rsplit('-',1)[1];tree=trees['trail-collars-'+side]
        for part in action['parts']:
            profile=part['profile'];j=min(range(20),key=lambda k:profile['profile'][k][1]);gaps=[]
            for i in range(c['segments']):
                point=ob.matrix_world@ob.data.vertices[part['first_vertex']+j*c['segments']+i].co;loc,normal,_,_=tree.find_nearest(point)
                if loc is None:raise ValueError('Refined bead support missing')
                gap=(point-loc).dot(normal)
                if gap>1e-6 or gap<-.005:raise ValueError('Actual refined bead foot detached or buried')
                gaps.append(gap)
            contacts.append({'object':ob.name,'component_first':part['original_indices'][0],'actual_vertices':len(gaps),'signed_nearest_support':[min(gaps),max(gaps)]})
    if any(dependency(objects[n])[0]!=h for n,h in protected.items()):raise ValueError('Non-target changed')
    va=render_scene(folder,c['inspection'],members,'after')
    for a,b in zip(vb['views'],va['views']):
        if any(a[k]!=b[k] for k in ('direction','camera_position','ortho_scale','lighting')):raise ValueError('Fixed frame changed')
    cam.matrix_world,cam.data.type,cam.data.ortho_scale=oldcam
    if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
    report={'version':version,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'unchanged_non_targets':True,'protected_objects':len(protected),'contacts_checked':True,'actual_bead_foot_checks':contacts,'unchanged_attachment_samples':len(neighbors),'attachment_distance_growth':[min(growth),max(growth)],'source_unchanged':True,'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Original measured radial/axial profiles revolved with more circumference samples. Four objects edited; all other strap components retain geometry/UV. Target ring/sleeve topology and UV replaced. Finite contact samples, not continuous union, full collision, animation or historical dimensions.'}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
