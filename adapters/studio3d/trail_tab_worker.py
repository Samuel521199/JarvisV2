# SPDX-License-Identifier: GPL-2.0-or-later
"""Append bound, supported exterior silhouettes to existing static straps."""
import bpy,bmesh,json,hashlib,time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from modules.skills.studio3d.trail_tab import shape
from modules.skills.studio3d.attachment_seat import VERSION,components
from adapters.studio3d.spade_frame_worker import dependency,containment
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene

def canonical(extension,deps):
    vs,fs=shape(extension);mesh=bpy.data.meshes.new('bounded-tab');mesh.from_pydata(vs,[],fs);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    ob=bpy.data.objects.new('bounded-tab',mesh);bpy.context.collection.objects.link(ob)
    bevel=ob.modifiers.new('tab edge highlight','BEVEL');bevel.width=.0006;bevel.segments=3;bevel.limit_method='ANGLE'
    bpy.context.view_layer.update();result=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps)
    points=[list(v.co) for v in result.vertices];faces=[list(p.vertices) for p in result.polygons]
    smooth=[abs(p.normal.z)<.999 for p in result.polygons]
    quality=inventory(ob,deps)
    if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Tab prototype topology failed')
    bpy.data.meshes.remove(result);bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
    return points,faces,smooth,quality

def run(folder,req,c,source):
    started=time.monotonic()
    if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Exact tab source changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
    if len(objects)!=79 or any(o is None for o in objects.values()):raise ValueError('Original inventory required')
    targets={t['object'] for t in c['targets']};before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n not in targets};plans=[];deps=bpy.context.evaluated_depsgraph_get()
    for t in c['targets']:
        ob=objects[t['object']];tube=objects[t['support']];side=ob.name.rsplit('-',1)[1]
        if dependency(ob)[0]!=t['dependency_digest'] or dependency(tube)[0]!=t['support_dependency_digest'] or dependency(objects['trail-collars-'+side])[0]!=t['collar_dependency_digest']:raise ValueError('Tab source/support dependency changed')
        if ob.type!='MESH' or ob.modifiers or len(ob.data.vertices)!=5586 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Current frozen straps and pads required')
        groups=components(len(ob.data.vertices),[list(p.vertices) for p in ob.data.polygons])
        if [len(x) for x in groups]!=[320,320,152,152,152]*3+[442,162,162]*3 or any(ix not in groups for ix in t['components']):raise ValueError('Bound complete components required')
        if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('World coating required')
        if tube.type!='MESH' or tube.modifiers or len(tube.data.vertices)!=194:raise ValueError('Original tube required')
        endpoints=[tube.matrix_world@tube.data.vertices[i].co for i in (192,193)];axis=(endpoints[1]-endpoints[0]).normalized();horizontal=Vector((axis.y,-axis.x,0)).normalized()
        if side=='right':horizontal=-horizontal;axis=-axis
        vertical=horizontal.cross(axis).normalized()
        if vertical.z<.98:raise ValueError('Unsupported tab orientation')
        parts=[]
        for ix in t['components']:
            points=[ob.matrix_world@ob.data.vertices[i].co for i in ix];center=sum(points,Vector())/len(points)
            parts.append((ix,center,axis,vertical,horizontal))
        plans.append((ob,parts))
    ps,fs,sm,canonical_quality=canonical(c['extension'],deps);lo,hi=c['inspection']['bounds']
    # The third left tab, including its lowest edge, must fit this explicit local frame.
    representative=plans[0] if plans[0][0].name.endswith('left') else plans[1]
    _,ctr,u,v,w=representative[1][2]
    if any(not lo[i]<=p[i]<=hi[i] for x,y,z in ps for p in [ctr+u*x+v*y+w*z] for i in range(3)):raise ValueError('Whole representative tab outside fixed frame')
    members={n:objects[n] for n in list(c['inspection']['regions'].values())[0]};cam=bpy.context.scene.camera;oldcam=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);bpy.context.scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],members,'before');actions=[]
    for ob,parts in plans:
        original=ob.data;v0=[list(x.co) for x in original.vertices];f0=[list(x.vertices) for x in original.polygons];uv0=[(l.name,[list(x.uv) for x in l.data]) for l in original.uv_layers];vs=v0.copy();faces=f0.copy();smooth=[p.use_smooth for p in original.polygons];records=[];inv=ob.matrix_world.inverted()
        world=[ob.matrix_world@x.co for x in original.vertices]
        for ix,ctr,u,v,w in parts:
            start=len(vs);pvs=[ctr+u*x+v*y+w*z for x,y,z in ps];vs.extend([list(inv@p) for p in pvs]);faces.extend([[start+i for i in f] for f in fs]);smooth.extend(sm)
            support=BVHTree.FromPolygons(world,[f for f in f0 if set(f).issubset(ix)],all_triangles=False);added=BVHTree.FromPolygons(pvs,fs,all_triangles=False)
            checks=[]
            for a in (-.010,.010):
                for b in (-.003,.003):
                    point=ctr+u*a+v*(-.016)+w*b
                    old=containment(point,[support]);new=containment(point,[added])
                    if not old['inside_or_boundary'] or not new['inside_or_boundary']:raise ValueError('Tab root lacks sampled overlapping support')
                    checks.append({'point':list(point),'original':old,'added':new})
            slots=[]
            for a in (-.006,-.003,0,.003,.006):
                point=ctr+v*(-c['extension']+.026+a)+w*.03
                hit=added.ray_cast(point,-w,.06)[0]
                if hit is not None:raise ValueError('Visible slot blocked by added tab')
                slots.append(list(point))
            records.append({'original_component_indices':ix,'center':list(ctr),'axes':[list(u),list(v),list(w)],'added_vertices':len(ps),'added_faces':len(fs),'root_probes':checks,'slot_rays':slots})
        if len(vs)-len(v0)>15000:raise ValueError('Tab vertex budget')
        mesh=bpy.data.meshes.new('trail-visible-tabs');mesh.from_pydata(vs,[],faces);mesh.materials.append(original.materials[0]);mesh.update();ob.data=mesh
        for p,s in zip(mesh.polygons,smooth):p.use_smooth=s
        old_sharp={tuple(sorted(e.vertices)):e.use_edge_sharp for e in original.edges}
        for edge in mesh.edges:
            if tuple(sorted(edge.vertices)) in old_sharp:edge.use_edge_sharp=old_sharp[tuple(sorted(edge.vertices))]
        for name,values in uv0:
            layer=mesh.uv_layers.new(name=name)
            layer.active_render=original.uv_layers[name].active_render
            for x,y in zip(layer.data,values):x.uv=y
            for face in list(mesh.polygons)[len(f0):]:
                coords=[mesh.vertices[i].co for i in face.vertices];origin=coords[0];u=(coords[1]-origin).normalized();v=face.normal.cross(u).normalized()
                for idx,p in zip(face.loop_indices,coords):layer.data[idx].uv=((p-origin).dot(u),(p-origin).dot(v))
            if [list(x.uv) for x in layer.data[:len(values)]]!=values:raise ValueError('Original UV changed')
            for face in list(mesh.polygons)[len(f0):]:
                pts=[layer.data[i].uv for i in face.loop_indices];area=abs(sum(a.x*b.y-a.y*b.x for a,b in zip(pts,pts[1:]+pts[:1])))/2
                if area<=1e-10:raise ValueError('Degenerate new tab UV')
        if uv0:mesh.uv_layers.active_index=original.uv_layers.active_index
        if [list(x.co) for x in mesh.vertices[:len(v0)]]!=v0 or [list(p.vertices) for p in mesh.polygons[:len(f0)]]!=f0:raise ValueError('Original strap and pad surfaces changed')
        bpy.context.view_layer.update();quality=inventory(ob,deps)
        if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Actual tab topology failed')
        actions.append({'object':ob.name,'original_vertices':len(v0),'original_faces':len(f0),'original_uv_loops':sum(len(v) for _,v in uv0),'parts':records,'quality':quality,'original_geometry_uv_preserved':True})
    if any(dependency(objects[n])[0]!=h for n,h in protected.items()):raise ValueError('Non-target changed')
    va=render_scene(folder,c['inspection'],members,'after')
    for a,b in zip(vb['views'],va['views']):
        if any(a[k]!=b[k] for k in ('direction','camera_position','ortho_scale','lighting')):raise ValueError('Fixed frame changed')
    cam.matrix_world,cam.data.type,cam.data.ortho_scale=oldcam
    if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
    report={'version':VERSION,'author':c['author'],'actions':actions,'canonical_quality':canonical_quality,'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'protected_objects':len(protected),'unchanged_non_targets':True,'source_unchanged':True,'contacts_checked':True,'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Six external game-art tabs overlapping existing side blocks; original strap/pad surfaces retained. Finite overlap and tab-only open-slot rays do not establish continuous union, global clearance, animation or historical function.'}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
