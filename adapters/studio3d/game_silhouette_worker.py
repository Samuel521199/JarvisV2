# SPDX-License-Identifier: GPL-2.0-or-later
"""Coarse exterior proxies derived from the bound editable semantic source.

No hidden mechanisms, manufacturing reconstruction, or detail-preserving claim.
"""
from sdk.blender_api import require_blender
import json,hashlib,math
from sdk.point_cloud import bounds, principal_axes, project, reconstruct
bpy = require_blender().bpy; bmesh = require_blender().bmesh
Vector = require_blender().mathutils.Vector; Matrix = require_blender().mathutils.Matrix

def build(folder,request,originals):
    source=folder/'semantic.blend'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=request['semantic_sha256']:raise ValueError('Semantic source changed')
    names=tuple(request['semantic_names'])
    with bpy.data.libraries.load(str(source),link=False) as (before,after):
        if any(n not in before.objects for n in names):raise ValueError('Missing semantic reference')
        after.objects=list(names)
    semantic=dict(zip(names,after.objects));scene=bpy.context.scene
    for ob in semantic.values():scene.collection.objects.link(ob);ob.hide_render=True;ob.hide_set(True)
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();cache={}
    for name,ob in semantic.items():
        mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps)
        cache[name]=[tuple(ob.matrix_world@v.co) for v in mesh.vertices];bpy.data.meshes.remove(mesh)
    lo,raw_max=bounds(p for cloud in cache.values() for p in cloud)
    hi,high_max=bounds(tuple(o.matrix_world@v.co) for o in originals.values() for v in o.data.vertices)
    if any(raw_max[i]-lo[i]<=1e-12 for i in range(3)):raise ValueError('Degenerate semantic bounds')
    ratios=[(high_max[i]-hi[i])/(raw_max[i]-lo[i]) for i in range(3)]
    if max(ratios)-min(ratios)>.001:raise ValueError('Semantic/high frames require a nonuniform transform; inspect before proxying')
    scale=math.fsum(ratios)/3;points={n:[tuple(hi[i]+(v[i]-lo[i])*scale for i in range(3)) for v in ps] for n,ps in cache.items()}
    detailed=request['contract'].get('geometry_mode')=='structured'
    paint=bpy.data.materials.new('Far paint');paint.use_nodes=True;p=paint.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.035,.042,.048,1);p.inputs['Roughness'].default_value=.78;p.inputs['Metallic'].default_value=.15
    rubber=bpy.data.materials.new('Far rubber');rubber.use_nodes=True;p=rubber.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.006,.007,.008,1);p.inputs['Roughness'].default_value=.94
    if detailed:
        paint=semantic['disc-left'].data.materials[0].copy();rubber=semantic['tire-left'].data.materials[0].copy()
    owners=['barrel','breech','carriage','cradle','shield','trail-left','trail-right','wheel-left','wheel-right']
    if detailed:owners+=['controls','handwheel-left']
    groups={n:[[],[],[],[]] for n in owners};actions=[]
    def append(owner,verts,faces,mat=0,smooth=False):
        vs,fs,ms,ss=groups[owner];start=len(vs);vs.extend([list(v) for v in verts]);fs.extend([[start+i for i in face] for face in faces]);ms.extend([mat]*len(faces));ss.extend(smooth if isinstance(smooth,list) else [smooth]*len(faces))
    def component(owner,name,target):
        source=semantic[name];mesh=bpy.data.meshes.new_from_object(source.evaluated_get(deps),depsgraph=deps);ob=bpy.data.objects.new('Component budget '+name,mesh);scene.collection.objects.link(ob)
        for vertex in mesh.vertices:vertex.co=tuple(hi[i]+((source.matrix_world@vertex.co)[i]-lo[i])*scale for i in range(3))
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;mesh.calc_loop_triangles();before=len(mesh.loop_triangles)
        if before>target:
            mod=ob.modifiers.new('Independent semantic budget','DECIMATE');mod.ratio=target/before;mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
        append(owner,[v.co.copy() for v in ob.data.vertices],[tuple(p.vertices) for p in ob.data.polygons],smooth=False if name.startswith('shield-') else [p.use_smooth for p in ob.data.polygons]);actions.append({'source':name,'owner':owner,'method':'individual semantic component collapse','budget':target,'source_triangles':before})
        bpy.data.objects.remove(ob,do_unlink=True)
    def box(owner,name):
        ps=points[name];center,axes=principal_axes(ps);lower,upper=bounds(project(ps,center,axes))
        verts=[reconstruct(center,axes,[upper[k] if bit&(1<<k) else lower[k] for k in range(3)]) for bit in range(8)]
        append(owner,verts,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)])
        actions.append({'source':name,'owner':owner,'method':'oriented coarse box'})
    def cylinder(owner,a,b,r,segments=8,mat=0):
        a,b=Vector(a),Vector(b);axis=(b-a).normalized();u=axis.cross(Vector((0,0,1)))
        if u.length<.01:u=axis.cross(Vector((0,1,0)))
        u.normalize();v=axis.cross(u);verts=[p+r*(math.cos(t*math.tau/segments)*u+math.sin(t*math.tau/segments)*v) for p in (a,b) for t in range(segments)]
        faces=[tuple(reversed(range(segments))),tuple(range(segments,segments*2))]+[(i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments)]
        append(owner,verts,faces,mat)
    def axial(owner,name,segments=8):
        ps=points[name];center,axes=principal_axes(ps);axis=axes[-1];dist=[p[0] for p in project(ps,center,[axis])];rad=max(math.sqrt(math.fsum((p[i]-center[i]-d*axis[i])**2 for i in range(3))) for p,d in zip(ps,dist));a=reconstruct(center,[axis],[min(dist)]);b=reconstruct(center,[axis],[max(dist)]);cylinder(owner,a,b,rad,segments)
        actions.append({'source':name,'owner':owner,'method':'principal-axis coarse cylinder','segments':segments})
    if detailed:
        specs=[('barrel','barrel',96),('barrel','muzzle-brake',128),('carriage','axle',48),('carriage','axle-saddle',70),('carriage','central-pedestal',48),('breech','rear-cover-body',160),('breech','breech-top-cover',88),('breech','external-arm',160),('cradle','cradle-trough',128),('controls','connected-control-housing',120),('handwheel-left','handwheel-left',80)]
        for owner,name,target in specs:component(owner,name,target)
    else:
        for name in ['barrel','muzzle-brake']:axial('barrel',name,8)
        axial('carriage','axle',8)
        for owner,name in [('carriage','axle-saddle'),('carriage','central-pedestal'),('breech','rear-cover-body'),('breech','breech-top-cover'),('cradle','cradle-trough')]:box(owner,name)
    def hull2(ps):
        ps=sorted(set(map(tuple,ps)))
        def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        rows=[]
        for seq in (ps,ps[::-1]):
            row=[]
            for p in seq:
                while len(row)>1 and cross(row[-2],row[-1],p)<=1e-10:row.pop()
                row.append(p)
            rows+=row[:-1]
        # The far silhouette needs the coarse panel outline, not dozens of
        # bevel/corner samples from the high. Remove least-area corner samples.
        while len(rows)>8:
            index=min(range(len(rows)),key=lambda i:abs(cross(rows[i-1],rows[i],rows[(i+1)%len(rows)])))
            rows.pop(index)
        return rows
    for name in ['shield-left-0','shield-right-0','shield-upper-bridge','shield-lower-flap--1','shield-lower-flap-1']:
        if detailed:
            component('shield',name,128 if name in ('shield-left-0','shield-right-0') else 96 if name=='shield-upper-bridge' else 48);continue
        ps=points[name];center,axes=principal_axes(ps);normal=axes[0];basis=axes[1:];outline=hull2([tuple(round(v,6) for v in p) for p in project(ps,center,basis)]);dist=[p[0] for p in project(ps,center,[normal])];thick=max(.003,max(dist)-min(dist))
        verts=[reconstruct(center,[*basis,normal],[*p,side*thick/2]) for side in (-1,1) for p in outline];n=len(outline);faces=[tuple(reversed(range(n))),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        append('shield',verts,faces);actions.append({'source':name,'method':'convex exterior panel; small opening/detail omitted'})
    for side in ['left','right']:
        ps=points['tire-'+side];lower,upper=bounds(ps);center=[(a+b)/2 for a,b in zip(lower,upper)];r=max(upper[0]-lower[0],upper[2]-lower[2])/2
        if detailed:
            width=upper[1]-lower[1];profile=[(.86*r,lower[1]),(.975*r,lower[1]),(r,lower[1]+.2*width),(r,upper[1]-.2*width),(.975*r,upper[1]),(.86*r,upper[1])];n=24
            verts=[(center[0]+rad*math.cos(i*math.tau/n),y,center[2]+rad*math.sin(i*math.tau/n)) for rad,y in profile for i in range(n)];faces=[(j*n+i,j*n+(i+1)%n,((j+1)%6)*n+(i+1)%n,((j+1)%6)*n+i) for j in range(6) for i in range(n)]
            append('wheel-'+side,verts,faces,1,True);component('wheel-'+side,'disc-'+side,128);component('wheel-'+side,'hub-'+side,48);component('trail-'+side,'trail-tube-'+side,96);component('trail-'+side,'spade-blade-'+side,128);actions.append({'source':'tire-'+side,'method':'closed 24-station,6-row tyre profile; fine grooves omitted'});continue
        a=center.copy();b=center.copy();a[1]=lower[1];b[1]=upper[1];cylinder('wheel-'+side,a,b,float(r),12,1)
        # Flat paint disks on each side leave the dark tyre border visible.
        for y,sign in [(lower[1]-.0003,-1),(upper[1]+.0003,1)]:
            verts=[(center[0]+r*.86*math.cos(i*math.tau/12),y,center[2]+r*.86*math.sin(i*math.tau/12)) for i in range(12)];append('wheel-'+side,verts,[tuple(range(12)) if sign==1 else tuple(reversed(range(12)))])
        actions.append({'source':'tire-'+side,'method':'12-sided tyre cylinder and flat paint disks; hubs/ribs removed'})
        axial('trail-'+side,'trail-tube-'+side,8);box('trail-'+side,'spade-blade-'+side)
    proxies=[];parts=[]
    for owner,(verts,faces,mats,smooth) in groups.items():
        mesh=bpy.data.meshes.new('Silhouette '+owner);mesh.from_pydata(verts,[],faces);mesh.update();mesh.materials.append(paint);mesh.materials.append(rubber)
        for face,mat,flag in zip(mesh.polygons,mats,smooth):face.material_index=mat;face.use_smooth=flag
        bm=bmesh.new();bm.from_mesh(mesh)
        if detailed:bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
        old_faces=len(mesh.polygons);repaired=mesh.validate(verbose=True,clean_customdata=False)
        actions.append({'owner':owner,'validation_repaired':repaired,'removed_invalid_faces':old_faces-len(mesh.polygons),'same_owner_merge_distance':1e-6 if detailed else 0})
        if mesh.validate(clean_customdata=False):raise ValueError('Generated component remains invalid')
        ob=bpy.data.objects.new('Silhouette '+owner,mesh);scene.collection.objects.link(ob)
        for group in owners:ob.vertex_groups.new(name=group)
        ob.vertex_groups[owner].add(list(range(len(mesh.vertices))),1,'REPLACE');proxies.append(ob)
        parts.append({'name':owner,'key':owner,'matrix':originals[owner].matrix_world.copy(),'offset':Vector((0,0,0))})
    (folder/'silhouette-construction.json').write_text(json.dumps({'semantic_sha256':request['semantic_sha256'],'frame_scale':scale,'frame_ratios':list(ratios),'actions':actions,'owners':owners,'omitted':'Small fasteners/handles and fine tyre grooves; individual principal components retained.' if detailed else 'All small fasteners, handles, wheel ribs/hubs/grooves and observation opening. Deliberate distant exterior only.','material_strategy':'Original semantic paint/rubber roles surface-baked after component reduction; no high-to-low projection.' if detailed else 'Flat author-assigned far paint/rubber baked from the proxies; not a high-detail projection.'},indent=2))
    return proxies,parts
