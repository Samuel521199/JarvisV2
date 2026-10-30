# SPDX-License-Identifier: GPL-2.0-or-later
"""Bound visible spade frame cleanup, with fixed support inventories."""
import bpy, bmesh, json, hashlib, time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from modules.skills.studio3d.spade_frame import TARGETS, SUPPORTS, ANCHORS
from modules.skills.studio3d.attachment_seat import components, VERSION
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene

def mesh_record(m, o):
    return {'vertices':[list(o.matrix_world@v.co) for v in m.vertices],
            'faces':[list(p.vertices) for p in m.polygons],
            'smooth':[p.use_smooth for p in m.polygons],
            'material_indices':[p.material_index for p in m.polygons],
            'uv':[[list(d.uv) for d in layer.data] for layer in m.uv_layers]}

def dependency(ob):
    """Geometry, UV, shading, curve, transform and actual modifier parameters.

    UI state and runtime timings are excluded. Full BLEND SHA binds materials
    and all other dependencies at admission; this digest is not its substitute.
    """
    mods=[]
    ignored={'rna_type','name','type','execution_time','persistent_uid','show_expanded','is_active','is_override_data'}
    for m in ob.modifiers:
        row={'name':m.name,'type':m.type}
        for prop in m.bl_rna.properties:
            if prop.identifier in ignored:continue
            v=getattr(m,prop.identifier,None)
            if isinstance(v,(bool,int,float,str)) or v is None:row[prop.identifier]=v
            elif prop.identifier=='object' and v:row['operand_digest']=digest_object(v)
        mods.append(row)
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    result={'evaluated':mesh_record(mesh,ob),'matrix':[list(r) for r in ob.matrix_world],
            'modifiers':mods,'materials':[m.name if m else None for m in ob.data.materials]}
    ev.to_mesh_clear()
    if ob.type=='MESH':result['base']=mesh_record(ob.data,ob)
    elif ob.type=='CURVE':
        result['curve']={'bevel_depth':ob.data.bevel_depth,'bevel_resolution':ob.data.bevel_resolution,
            'resolution_u':ob.data.resolution_u,'use_fill_caps':ob.data.use_fill_caps,
            'splines':[{'type':s.type,'cyclic':s.use_cyclic_u,'points':[list(p.co) for p in s.points],
              'bezier':[{'co':list(p.co),'left':list(p.handle_left),'right':list(p.handle_right)} for p in s.bezier_points]} for s in ob.data.splines]}
    # Blender's unchanged bevel evaluation was measured to vary derived UVs
    # by < 1.2e-7 across file loads. Bind exact base UVs, full BLEND bytes and
    # modifier parameters instead; keep evaluated UV evidence in the record.
    # This tool accepts only coatings that do not read those derived UVs.
    hashed=dict(result);hashed['evaluated']={k:v for k,v in result['evaluated'].items() if k!='uv'}
    encoded=json.dumps(hashed,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).hexdigest(),result

def support_snapshot(objects):
    """The same four seat solids before/after, never the converted lever."""
    deps=bpy.context.evaluated_depsgraph_get()
    trees=[world_tree(objects[n],deps) for n in SUPPORTS];pieces=[]
    for n in SUPPORTS:
        ob=objects[n];ev=ob.evaluated_get(deps);m=ev.to_mesh()
        points=[ob.matrix_world@v.co for v in m.vertices];faces=[list(p.vertices) for p in m.polygons]
        for ids in components(len(points),faces):
            keep=set(ids);fs=[f for f in faces if f[0] in keep]
            edge_counts={}
            for face in fs:
                for a,b in zip(face,face[1:]+face[:1]):
                    edge=tuple(sorted((a,b)));edge_counts[edge]=edge_counts.get(edge,0)+1
            if set(edge_counts.values())!={2}:raise ValueError('Containment requires closed support components')
            pieces.append(BVHTree.FromPolygons(points,fs))
        ev.to_mesh_clear()
    samples={}
    for n in ANCHORS:
        ob=objects[n];ev=ob.evaluated_get(deps);m=ev.to_mesh()
        points=[ob.matrix_world@v.co for v in m.vertices];ev.to_mesh_clear()
        if len(points)>12000:raise ValueError('Support sample budget')
        samples[n]=[{'point':list(p),'distance':min(t.find_nearest(p)[3] for t in trees)} for p in points]
    return samples,pieces

def containment(p, trees):
    for index,tree in enumerate(trees):
        q=tree.find_nearest(p)
        if q[0] is not None and q[3]<1e-7:return {'inside_or_boundary':True,'component':index,'method':'surface'}
        counts=[]
        for direction in (Vector((1,.317,.189)).normalized(),Vector((-.217,1,.121)).normalized(),Vector((.119,-.237,1)).normalized()):
            point=p+direction*1e-7;count=0
            for _ in range(32):
                hit=tree.ray_cast(point,direction,10)[0]
                if hit is None:break
                count+=1;point=hit+direction*1e-6
            else:raise ValueError('Containment ray budget')
            counts.append(count)
        if all(x%2 for x in counts):return {'inside_or_boundary':True,'component':index,'method':'three-ray parity','counts':counts}
    return {'inside_or_boundary':False}

def verify_support(old, new):
    a,oldtrees=old;b,newtrees=new;overlaps=[];growth={}
    for n in ANCHORS:
        if len(a[n])!=len(b[n]):raise ValueError('Attachment topology changed')
        growth[n]=max(y['distance']-x['distance'] for x,y in zip(a[n],b[n]))
        for i,(x,y) in enumerate(zip(a[n],b[n])):
            if x['point']!=y['point']:raise ValueError('Original attachment moved')
            if y['distance']-x['distance']<=.003:continue
            p=Vector(y['point']);before=containment(p,oldtrees);after=containment(p,newtrees)
            if not(before['inside_or_boundary'] and after['inside_or_boundary']):
                raise ValueError('Unsupported exterior regression: '+n+' sample '+str(i))
            overlaps.append({'object':n,'sample':i,'before_distance':x['distance'],'after_distance':y['distance'],
                             'before':before,'after':after})
    return {'support_inventory':list(SUPPORTS),'attachment_samples':sum(len(x) for x in a.values()),
            'distance_growth':growth,'overlap_probes':overlaps,'outside_growth_threshold':.003,
            'scope':'Finite unchanged attachment points, closed components and three-ray parity. Not continuous contact, full collision or animation.'}

def admit(objects,c,source,req):
    if c['source_sha256']!=req['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:
        raise ValueError('Full source binding changed')
    data={}
    for n in TARGETS+ANCHORS:
        ob=objects[n];sha,row=dependency(ob);data[n]=row
        if digest_object(ob)!=c['bindings'][n]['base'] or sha!=c['bindings'][n]['dependency']:
            raise ValueError('Source/dependency binding changed: '+n)
        if ob.animation_data or ob.data.shape_keys or ob.data.users!=1:raise ValueError('Original single-user static source required')
    for n in TARGETS:
        ob=objects[n]
        if n.startswith('spade-lever'):
            if ob.type!='CURVE' or ob.modifiers or len(ob.data.splines)!=1 or len(ob.data.splines[0].bezier_points)!=4 or ob.data.use_fill_caps:
                raise ValueError('Original uncapped four-point curve required')
        elif ob.type!='MESH' or [m.type for m in ob.modifiers]!=['BEVEL']:
            raise ValueError('Original bounded seat and bevel required')
        if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes:raise ValueError('Single world-coordinate coat required')
        if any(x.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or x.type=='TEX_IMAGE' and not x.inputs['Vector'].is_linked for x in ob.data.materials[0].node_tree.nodes):
            raise ValueError('Unsupported material dependency')
    for side,row in c['components'].items():
        for prefix,keys in (('spade-seat',('seat',)),('spade-pivot-seat',('pivot_plate','pivot_cylinder'))):
            ob=objects[prefix+'-'+side];groups=components(len(ob.data.vertices),[list(p.vertices) for p in ob.data.polygons])
            expected=1 if prefix=='spade-seat' else 4
            if len(groups)!=expected:raise ValueError('Original component count changed')
            for key in keys:
                if sorted(row[key]) not in [sorted(g) for g in groups]:raise ValueError('Complete component binding changed')
        if row['seat']!=list(range(8)) or row['pivot_plate']!=list(range(194,202)) or row['pivot_cylinder']!=list(range(194)):
            raise ValueError('Original component identity changed')
    return data

def reshape(objects,c,data):
    actions=[]
    for side in ('left','right'):
     for prefix in ('spade-seat','spade-pivot-seat'):
      n=prefix+'-'+side;o=objects[n];assert digest_object(o)==c['bindings'][n]['base']
      ids=c['components'][side]['seat' if prefix=='spade-seat' else 'pivot_plate']
      bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();selected={bm.verts[i] for i in ids}
      edges=[e for e in bm.edges if set(e.verts)<=selected and abs(e.verts[0].co.z-e.verts[1].co.z)>.035]
      assert len(edges)==4 and len(o.modifiers)==1 and o.modifiers[0].type=='BEVEL'
      preserved=[tuple(v.co) for i,v in enumerate(bm.verts) if i not in ids]
      result=bmesh.ops.bevel(bm,geom=edges,offset=c['corner_offset'],offset_type='OFFSET',segments=8,affect='EDGES',profile=.5,clamp_overlap=True)
      # Shape the horizontal silhouette; retain original finite top/bottom edge bevel.
      for face in result['faces']:face.smooth=True
      bm.normal_update();bm.to_mesh(o.data);bm.free();o.data.update()
      actual={tuple(v.co) for v in o.data.vertices};assert all(v in actual for v in preserved)
      actions.append({'object':n,'tool':'Blender bmesh bevel selected vertical edges','offset':c['corner_offset'],'segments':8,'selected_original_component':ids,'other_component_base_vertices_preserved':len(preserved),'modifiers_retained':True})
      if prefix=='spade-pivot-seat':
       groups=components(len(o.data.vertices),[list(p.vertices) for p in o.data.polygons])
       cylinder=next(g for g in groups if len(g)==194)
       plate=next(g for g in groups if min(o.data.vertices[i].co.z for i in g)>.234 and max(o.data.vertices[i].co.z for i in g)<.276)
       assert len(groups)==4 and set(cylinder).isdisjoint(plate)
       kept={i for g in groups if g not in (cylinder,plate) for i in g};assert len(kept)==132
       kept_positions={tuple(o.data.vertices[i].co) for i in kept}
       def part(indices,label):
        m=bpy.data.meshes.new(label);b=bmesh.new();b.from_mesh(o.data);b.verts.ensure_lookup_table()
        bmesh.ops.delete(b,geom=[v for i,v in enumerate(b.verts) if i not in indices],context='VERTS');b.to_mesh(m);b.free()
        for mat in o.data.materials:m.materials.append(mat)
        ob=bpy.data.objects.new(label,m);bpy.context.scene.collection.objects.link(ob);ob.matrix_world=o.matrix_world.copy();ob.hide_render=True;return ob
       a=part(set(cylinder),'trial-cylinder');b=part(set(plate),'trial-top-plate')
       union=a.modifiers.new('Local exterior coplanar overlap union','BOOLEAN');union.operation='UNION';union.solver='EXACT';union.object=b
       bpy.context.view_layer.update();merged=bpy.data.meshes.new_from_object(a.evaluated_get(bpy.context.evaluated_depsgraph_get()),depsgraph=bpy.context.evaluated_depsgraph_get())
       clean=bmesh.new();clean.from_mesh(merged);old_union_points=[v.co.copy() for v in clean.verts]
       bmesh.ops.remove_doubles(clean,verts=list(clean.verts),dist=1e-6)
       bmesh.ops.dissolve_degenerate(clean,dist=1e-6,edges=list(clean.edges));clean.normal_update()
       assert max(min((v.co-p).length for v in clean.verts) for p in old_union_points)<1.1e-6
       clean.to_mesh(merged);clean.free()
       remaining=bmesh.new();remaining.from_mesh(o.data);remaining.verts.ensure_lookup_table()
       bmesh.ops.delete(remaining,geom=[v for i,v in enumerate(remaining.verts) if i not in kept],context='VERTS')
       remaining.from_mesh(merged);remaining.normal_update();result_mesh=bpy.data.meshes.new(n+'-closed-exterior');remaining.to_mesh(result_mesh);remaining.free()
       for mat in o.data.materials:result_mesh.materials.append(mat)
       assert kept_positions<={tuple(v.co) for v in result_mesh.vertices}
       o.data=result_mesh
       for temp in (a,b):bpy.data.objects.remove(temp,do_unlink=True)
       actions.append({'object':n,'tool':'Exact union of two original overlapping exterior components','original_cylinder_and_rounded_plate_only':True,'other_side_component_base_vertices_preserved':132,'reason':'Sampled dark patch hits coplanar outer faces of existing cylinder and plate, not empty space','new_separate_scene_objects':0})
     n='spade-lever-'+side;o=objects[n];assert digest_object(o)==c['bindings'][n]['base'] and o.type=='CURVE'
     oldcurve=data[n]['curve'];assert len(o.data.splines)==1 and not o.data.splines[0].use_cyclic_u and not o.data.use_fill_caps
     o.data.use_fill_caps=True;o.data.bevel_resolution=8;bpy.context.view_layer.update()
     # Blender creates coincident but disconnected cap loops for this curve.
     # Merge only generated boundary vertices at identical positions, then verify closure.
     mesh=bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()),depsgraph=bpy.context.evaluated_depsgraph_get())
     original_points=[tuple(v.co) for v in mesh.vertices];bm=bmesh.new();bm.from_mesh(mesh)
     boundary=[v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
     assert len(boundary)==80
     bmesh.ops.remove_doubles(bm,verts=boundary,dist=1e-7);bm.normal_update();bm.to_mesh(mesh);bm.free()
     assert all(min((v.co-Vector(p)).length for v in mesh.vertices)<1e-7 for p in original_points)
     bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
     bpy.ops.object.convert(target='MESH');o=bpy.context.view_layer.objects.active;objects[n]=o;o.data=mesh
     cap_count=0
     endpoints=[(Vector(oldcurve['splines'][0]['bezier'][i]['co']),Vector(oldcurve['splines'][0]['bezier'][i]['right'])-Vector(oldcurve['splines'][0]['bezier'][i]['left'])) for i in (0,-1)]
     for face in mesh.polygons:
      if any(all(abs((mesh.vertices[j].co-center).dot(tangent.normalized()))<1e-6 for j in face.vertices) for center,tangent in endpoints):face.use_smooth=False;cap_count+=1
     assert cap_count==36,cap_count
     actions.append({'object':n,'tool':'Curve evaluated sampling and identical-position cap-loop weld','fill_caps':True,'bevel_resolution':8,'original_curve_control_path_and_radius_used':True,'curve_frozen_to_editable_mesh':True,'boundary_vertices_before_weld':80,'merge_distance':1e-7})
     actions.append({'object':n,'tool':'Flat cap faces only','faces':cap_count,'geometry_unchanged_after_weld':True})
    bpy.context.view_layer.update()
    for side in ('left','right'):
     n='spade-pivot-seat-'+side;o=objects[n]
     frozen=bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()),depsgraph=bpy.context.evaluated_depsgraph_get())
     old_points=[v.co.copy() for v in frozen.vertices];repair=bmesh.new();repair.from_mesh(frozen)
     tiny=[face for face in repair.faces if face.calc_area()<1e-10];assert len(tiny)==4
     selected=list({v for face in tiny for v in face.verts});assert len(selected)<=12
     bmesh.ops.remove_doubles(repair,verts=selected,dist=2e-5);repair.normal_update();repair.to_mesh(frozen);repair.free()
     kd=KDTree(len(frozen.vertices))
     for i,v in enumerate(frozen.vertices):kd.insert(v.co,i)
     kd.balance();movement=max(kd.find(p)[2] for p in old_points);assert movement<=2e-5
     o.modifiers.clear();o.data=frozen
     actions.append({'object':n,'tool':'Freeze union bevel and repair four measured microtriangles only','small_faces_before':4,'selected_vertices':len(selected),'merge_distance':2e-5,'max_sampled_coordinate_change':movement,'original_bevel_evaluated_not_retained_as_modifier':True,'gate_area_unchanged':1e-10})

    return actions


def run(folder,req,c,source):
    started=time.monotonic()
    if c['source_sha256']!=req['source_sha256']:raise ValueError('Full source binding changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
    if any(o is None for o in objects.values()) or len(objects)!=79:raise ValueError('Asset inventory changed')
    data=admit(objects,c,source,req)
    before={n:digest_object(o) for n,o in objects.items()}
    protected={n:dependency(o)[0] for n,o in objects.items() if n not in TARGETS}
    old_support=support_snapshot(objects)
    camera=bpy.context.scene.camera;old_camera=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale)
    members=list(c['inspection']['regions'].values())[0]
    render_objects={n:objects[n] for n in members}
    bpy.context.scene.cycles.seed=4
    vb=render_scene(folder,c['inspection'],render_objects,'before')
    actions=reshape(objects,c,data);bpy.context.view_layer.update()
    support=verify_support(old_support,support_snapshot(objects))
    topology={n:inventory(objects[n],bpy.context.evaluated_depsgraph_get()) for n in TARGETS}
    for n,row in topology.items():
        if any(row[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Topology quality failed: '+n)
    if any(dependency(objects[n])[0]!=sha for n,sha in protected.items()):raise ValueError('Non-target geometry, shading or dependencies changed')
    after={n:digest_object(o) for n,o in objects.items()}
    va=render_scene(folder,c['inspection'],{n:objects[n] for n in members},'after')
    for a,b in zip(vb['views'],va['views']):
        if any(a[k]!=b[k] for k in ('direction','camera_position','ortho_scale','lighting')):raise ValueError('Fixed camera/light comparison changed')
    camera.matrix_world,camera.data.type,camera.data.ortho_scale=old_camera
    if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Original source changed')
    report={'version':VERSION,'author':c['author'],'actions':actions,'support_verification':support,
        'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,
        'protected_objects':len(protected),'contacts_checked':True,'source_unchanged':True,
        'source_bindings':c['bindings'],'source_sha256':req['source_sha256'],'topology':topology,
        'views':{'before':vb,'after':va},'elapsed_seconds':time.monotonic()-started,
        'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,
        'scope':'Visible game exterior. Six targets changed; curves and pivot bevels frozen. Fixed four-seat support inventory; finite parity/overlap samples do not prove continuous welding, full collision, animation or historical construction.'}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
