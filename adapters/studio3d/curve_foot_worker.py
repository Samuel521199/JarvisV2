# SPDX-License-Identifier: GPL-2.0-or-later
"""Freeze the original visible arch; extend only its two rim rows to the cover."""
import bpy,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.curve_foot import foot_shift
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene
from adapters.studio3d.high_finish_reuse import tree_signature
from modules.skills.studio3d.high_finish import uv_independent_shader

def rim_loops(faces):
    counts={}
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):k=tuple(sorted((a,b)));counts[k]=counts.get(k,0)+1
    if any(v>2 for v in counts.values()):raise ValueError('Overfull source edges')
    edges=[e for e,v in counts.items() if v==1];adj={}
    for a,b in edges:adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
    if len(edges)!=20 or len(adj)!=20 or any(len(v)!=2 for v in adj.values()):raise ValueError('Expected two regular open rims')
    unseen=set(adj);loops=[]
    while unseen:
        start=min(unseen);loop=[start];prev=None;cur=start
        while True:
            nxt=min(v for v in adj[cur] if v!=prev)
            if nxt==start:break
            if nxt in loop:raise ValueError('Invalid boundary cycle')
            loop.append(nxt);prev,cur=cur,nxt
        if len(loop)!=10:raise ValueError('Expected ten-point original rim')
        unseen.difference_update(loop);loops.append(loop)
    if len(loops)!=2:raise ValueError('Expected two feet')
    return loops

def run(folder,req,c,source):
    started=time.monotonic()
    if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Original grip source changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects[n] for n in req['visible_names']}
    if len(objects)!=79:raise ValueError('Original semantic inventory required')
    for n,h in c['dependencies'].items():
        if dependency(objects[n])[0]!=h:raise ValueError('Grip or cover dependency changed')
    ob=objects['breech-top-grip'];support=objects['breech-top-cover'];deps=bpy.context.evaluated_depsgraph_get()
    if ob.type!='CURVE' or ob.modifiers or ob.animation_data or ob.data.users!=1 or ob.data.shape_keys:raise ValueError('Original single curve required')
    curve=ob.data
    if len(curve.splines)!=1 or curve.splines[0].type!='BEZIER' or len(curve.splines[0].bezier_points)!=4 or curve.splines[0].use_cyclic_u or curve.use_fill_caps or curve.bevel_resolution!=3 or curve.resolution_u!=12 or abs(curve.bevel_depth-.012)>1e-7:raise ValueError('Original open arch configuration required')
    if len(curve.materials)!=1 or not curve.materials[0] or not uv_independent_shader(tree_signature(curve.materials[0].node_tree)):raise ValueError('Only bound UV-independent coating supported')
    before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name}
    ev=ob.evaluated_get(deps);old=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=deps)
    pts=[v.co.copy() for v in old.vertices];faces=[list(p.vertices) for p in old.polygons]
    if len(pts)!=370 or len(faces)!=360 or old.has_custom_normals:raise ValueError('Original evaluated arch surface required')
    loops=rim_loops(faces);selected=sorted(v for loop in loops for v in loop)
    if selected!=c['boundary_vertices']:raise ValueError('Actual original rim binding changed')
    tree=world_tree(support,deps);inverse=ob.matrix_world.inverted();plans=[]
    for ids in loops:
        world=[ob.matrix_world@pts[i] for i in ids];gaps=[]
        if max(p.z for p in world)-min(p.z for p in world)>1e-7:raise ValueError('Original rim is not horizontal')
        for p in world:
            hit,n,_,_=tree.ray_cast(p+Vector((0,0,.02)),Vector((0,0,-1)),.1)
            if hit is None or n.z<.9999:raise ValueError('Missing planar upward cover support')
            gaps.append(p.z-hit.z)
        shift=foot_shift(gaps,c['embed'])
        for i,p in zip(ids,world):pts[i]=inverse@(p+Vector((0,0,shift)))
        cap=ids.copy();wp=[ob.matrix_world@pts[i] for i in cap]
        normal=sum((wp[i].cross(wp[(i+1)%len(wp)]) for i in range(len(wp))),Vector())
        if normal.z>0:cap.reverse()
        plans.append({'indices':ids,'cap':cap,'vertical_shift':shift,'original_gaps':gaps})
    new=bpy.data.meshes.new('upper-grip-seated-arch');new.from_pydata(pts,[],faces+[p['cap'] for p in plans]);new.materials.append(curve.materials[0])
    for p,q in zip(old.polygons,new.polygons):q.use_smooth=p.use_smooth;q.material_index=p.material_index
    for p in new.polygons[len(faces):]:p.use_smooth=False;p.material_index=0
    for layer in old.uv_layers:
        target=new.uv_layers.new(name=layer.name)
        for i,uv in enumerate(layer.data):target.data[i].uv=uv.uv
        for p in new.polygons[len(faces):]:
            coords=[ob.matrix_world@new.vertices[i].co for i in p.vertices];center=sum(coords,Vector())/len(coords)
            for li,v in zip(p.loop_indices,coords):target.data[li].uv=((v.x-center.x)/.024+.5,(v.y-center.y)/.024+.5)
    new.update();new.calc_loop_triangles()
    for t in new.loop_triangles:
        a,b,c0=[new.vertices[i].co for i in t.vertices]
        if (b-a).cross(c0-a).length*.5<1e-10:raise ValueError('Actual grip triangulation fails area gate')
        if t.polygon_index>=360:
            for layer in new.uv_layers:
                a,b,c0=[layer.data[i].uv for i in t.loops]
                if abs((b.x-a.x)*(c0.y-a.y)-(b.y-a.y)*(c0.x-a.x))*.5<1e-10:raise ValueError('Cap UV triangle degenerate')
    if any(tuple(new.vertices[i].co)!=tuple(old.vertices[i].co) for i in range(370) if i not in selected):raise ValueError('Original arch moved outside two rims')
    if [list(p.vertices) for p in new.polygons[:360]]!=faces or any(tuple(a.uv)!=tuple(b.uv) for la,lb in zip(old.uv_layers,new.uv_layers) for a,b in zip(la.data,lb.data)):raise ValueError('Original faces or UV changed')
    scene=bpy.context.scene;cam=scene.camera;oldcam=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);scene.cycles.seed=4
    vb=render_scene(folder,c['inspection'],objects,'before')
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH')
    ob=bpy.context.view_layer.objects.active;objects['breech-top-grip']=ob;ob.data=new;bpy.context.view_layer.update()
    quality=inventory(ob,deps)
    if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Closed target surface gate failed')
    samples=[]
    for plan in plans:
        coords=[ob.matrix_world@new.vertices[i].co for i in plan['cap']];center=sum(coords,Vector())/len(coords)
        for p in coords+[center]+[(p+center)*.5 for p in coords]:
            hit,n,_,_=tree.ray_cast(p+Vector((0,0,.02)),Vector((0,0,-1)),.1)
            if hit is None or n.z<.9999 or not -.001<p.z-hit.z<0:raise ValueError('Actual closed foot lost support')
            samples.append(p.z-hit.z)
    if any(dependency(objects[n])[0]!=h for n,h in protected.items()):raise ValueError('Non-target dependency changed')
    va=render_scene(folder,c['inspection'],objects,'after')
    if not all(all(a[k]==b[k] for k in ('direction','camera_position','ortho_scale','lighting')) for a,b in zip(vb['views'],va['views'])):raise ValueError('Comparison frame changed')
    cam.matrix_world,cam.data.type,cam.data.ortho_scale=oldcam
    report={'version':VERSION,'author':c['author'],'changed_objects':[ob.name],'protected_objects':78,'unchanged_non_targets':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==c['source_sha256'],'actions':plans,'quality':quality,'actual_triangles':len(new.loop_triangles),'small_triangles':0,'original_vertices_kept':370,'original_unmoved_vertices':350,'original_faces_and_uv_kept':360,'new_flat_caps':2,'foot_samples':len(samples),'actual_cap_gaps':[min(samples),max(samples)],'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'views':{'before':vb,'after':va},'contacts_checked':True,'contact_scope':'42 rim/center/interior samples against fixed cover; not continuous connection, full collision or animation verification.','curve_stack_preserved':False,'source_arch_and_radius_preserved_except_two_extended_rims':True,'known_unchanged_muzzle_defects':'94small polygons and264small loop triangles including22zero remain in a different unchanged object.','requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'scope':'Cosmetic game-grip attachment; original curve frozen to mesh, new caps and local lower ring extension only. Not historical dimensions or an operating mechanism.','user_approval':False,'lod_authorized':False}
    if not report['source_unchanged']:raise ValueError('Source file changed')
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
