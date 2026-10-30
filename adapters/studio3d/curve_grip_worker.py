# SPDX-License-Identifier: GPL-2.0-or-later
"""Preserve six original grip locations and paint while correcting visible profiles."""
import bpy,bmesh,json,hashlib,time,math
from mathutils import Vector
from modules.skills.studio3d.curve_grip import grip_path
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene

def support_foot(point,radius,tree):
    gaps=[]
    for i in range(32):
        a=math.tau*i/32;p=point+Vector((radius*math.cos(a),radius*math.sin(a),0))
        hit,normal,_,_=tree.ray_cast(p+Vector((0,0,.2)),Vector((0,0,-1)),.4)
        if hit is None or normal.z<.75:raise ValueError('Grip foot lacks upward tube support')
        gaps.append(p.z-hit.z)
    shift=min(0.,-.0006-max(gaps))
    if -shift>.012:raise ValueError('Grip foot move exceeds envelope')
    return point+Vector((0,0,shift)),{'sampled_original_gaps':[min(gaps),max(gaps)],'vertical_shift':shift,'rays':32}

def run(folder,req,c,source):
    start=time.monotonic()
    if c['source_sha256']!=req['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Full grip source changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
    if len(objects)!=79 or any(o is None for o in objects.values()):raise ValueError('Original inventory required')
    selected={t['object'] for t in c['targets']};before={n:digest_object(o) for n,o in objects.items()}
    protected={n:dependency(o)[0] for n,o in objects.items() if n not in selected};plans=[];trees={}
    for t in c['targets']:
        ob=objects[t['object']];support=objects[t['support']];sha,data=dependency(ob)
        if digest_object(ob)!=t['base_digest'] or sha!=t['dependency_digest'] or dependency(support)[0]!=t['support_dependency_digest']:raise ValueError('Grip or support dependency changed')
        if ob.type!='CURVE' or ob.modifiers or ob.animation_data or ob.data.shape_keys or ob.data.users!=1:raise ValueError('Unmodified single-user curve required')
        curve=ob.data
        if len(curve.splines)!=1 or curve.splines[0].type!='BEZIER' or curve.splines[0].use_cyclic_u or len(curve.splines[0].bezier_points)!=4 or curve.use_fill_caps:raise ValueError('Original open four-point U required')
        if abs(curve.bevel_depth-.011)>1e-7 or curve.bevel_resolution!=3 or curve.resolution_u!=12:raise ValueError('Unsupported source curve sampling/radius')
        if len(curve.materials)!=1 or not curve.materials[0].use_nodes:raise ValueError('Single supported paint required')
        if any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in curve.materials[0].node_tree.nodes):raise ValueError('UV-dependent grip coating unsupported')
        points=[ob.matrix_world@p.co for p in curve.splines[0].bezier_points]
        if max(p.y for p in points)-min(p.y for p in points)>1e-6 or abs(points[1].x-points[0].x)>1e-6 or abs(points[2].x-points[3].x)>1e-6:raise ValueError('Source is not the declared planar grip')
        if max(abs(ob.matrix_world[i][j]-(1 if i==j else 0)) for i in range(3) for j in range(3))>1e-6:raise ValueError('Unscaled axis-aligned grip frame required')
        if support.type!='MESH' or support.modifiers:raise ValueError('Immutable original tube required')
        tree=trees.setdefault(t['support'],world_tree(support,bpy.context.evaluated_depsgraph_get()))
        a,qa=support_foot(points[0],curve.bevel_depth,tree);b,qb=support_foot(points[-1],curve.bevel_depth,tree)
        crown=max(p[2] for p in data['evaluated']['vertices'])-curve.bevel_depth
        path=grip_path(list(a),list(b),crown,c['corner_radius'])
        plans.append({'target':t,'path':path,'feet':[qa,qb],'original_endpoints':[list(points[0]),list(points[-1])], 'crown_center_z':crown,'radius':curve.bevel_depth})
    members=list(c['inspection']['regions'].values())[0];cam=bpy.context.scene.camera;oldcam=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);bpy.context.scene.cycles.seed=4
    vb=render_scene(folder,c['inspection'],{n:objects[n] for n in members},'before')
    actions=[]
    for plan in plans:
        n=plan['target']['object'];ob=objects[n];curve=ob.data;inverse=ob.matrix_world.inverted();curve.splines.clear();spline=curve.splines.new('BEZIER');spline.bezier_points.add(5)
        for point,row in zip(spline.bezier_points,plan['path']):
            point.handle_left_type='FREE';point.handle_right_type='FREE';point.co=inverse@Vector(row['co']);point.handle_left=inverse@Vector(row['left']);point.handle_right=inverse@Vector(row['right'])
        curve.bevel_resolution=8;curve.use_fill_caps=True;bpy.context.view_layer.update()
        mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()),depsgraph=bpy.context.evaluated_depsgraph_get());bm=bmesh.new();bm.from_mesh(mesh)
        boundary=[v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
        if len(boundary)!=80:raise ValueError('Unexpected generated cap loop layout')
        bmesh.ops.remove_doubles(bm,verts=boundary,dist=1e-7);bm.normal_update();bm.to_mesh(mesh);bm.free()
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');ob=bpy.context.view_layer.objects.active;objects[n]=ob;ob.data=mesh
        feet=[Vector(plan['path'][i]['co']) for i in (0,5)];cap_vertices=set();cap_count=0
        for face in mesh.polygons:
            if any(all(abs((ob.matrix_world@mesh.vertices[i].co).z-foot.z)<1e-6 for i in face.vertices) for foot in feet):
                face.use_smooth=False;cap_vertices.update(face.vertices);cap_count+=1
        if cap_count!=36:raise ValueError('Unexpected actual grip caps')
        tree=trees[plan['target']['support']];actual_gaps=[]
        for i in cap_vertices:
            p=ob.matrix_world@mesh.vertices[i].co;hit,normal,_,_=tree.ray_cast(p+Vector((0,0,.2)),Vector((0,0,-1)),.4)
            if hit is None or normal.z<.75:raise ValueError('Actual cap lost support')
            actual_gaps.append(p.z-hit.z)
        if max(actual_gaps)>1e-5 or min(actual_gaps)<-.025:raise ValueError('Actual cap is unsupported or excessively embedded')
        topology=inventory(ob,bpy.context.evaluated_depsgraph_get())
        if any(topology[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Grip topology failed')
        actions.append({'object':n,'corner_radius':c['corner_radius'],'original_endpoints':plan['original_endpoints'],'new_endpoints':[list(p) for p in feet],'foot_planning':plan['feet'],
            'actual_cap_gaps':[min(actual_gaps),max(actual_gaps)],'actual_cap_vertices':len(cap_vertices),'cap_faces':cap_count,'topology':topology,'original_radius_preserved':True,'curve_frozen_to_mesh':True,'crown_center_z':plan['crown_center_z']})
    bpy.context.view_layer.update()
    if any(dependency(objects[n])[0]!=sha for n,sha in protected.items()):raise ValueError('Non-target dependency changed')
    va=render_scene(folder,c['inspection'],{n:objects[n] for n in members},'after')
    for a,b in zip(vb['views'],va['views']):
        if any(a[k]!=b[k] for k in ('direction','camera_position','ortho_scale','lighting')):raise ValueError('Fixed frame changed')
    cam.matrix_world,cam.data.type,cam.data.ortho_scale=oldcam
    if hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Input mutated')
    report={'version':VERSION,'author':c['author'],'actions':actions,'source_sha256':c['source_sha256'],'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},
            'unchanged_non_targets':True,'protected_objects':len(protected),'contacts_checked':True,'source_unchanged':True,'views':{'before':vb,'after':va},'elapsed_seconds':time.monotonic()-start,
            'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,
            'scope':'Existing visible U-grips only; original footprint x/y, radius and crown height preserved, bounded downward foot adjustment. Closed capped meshes replace curves. Finite cap/tube rays, not continuous contact, global collision, animation or historical reconstruction.'}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
