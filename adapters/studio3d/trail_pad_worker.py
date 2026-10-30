# SPDX-License-Identifier: GPL-2.0-or-later
"""Append shallow exterior pads to existing strap objects over actual tubes."""
import bpy,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.trail_pad import footprint
from modules.skills.studio3d.attachment_seat import VERSION,components
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene

def patch(center,direction,length,width,radius,base,top,tree,nx=16,ny=12):
    points,faces,boundary=footprint(length,width,radius,nx,ny);cross=Vector((-direction.y,direction.x,0));heights=[];vs=[]
    for s,t in points:
        p=center+direction*s+cross*t;hit,normal,_,_=tree.ray_cast(Vector((p.x,p.y,1.5)),Vector((0,0,-1)),2)
        if hit is None or normal.z<.65:raise ValueError('Pad footprint lacks upward tube support')
        heights.append(list(hit));vs.append([p.x,p.y,hit.z+base])
    count=len(points);vs.extend([[x,y,z+top-base] for x,y,z in vs]);fs=[list(reversed(f)) for f in faces]+[[i+count for i in f] for f in faces]
    fs.extend([[a,b,b+count,a+count] for a,b in zip(boundary,boundary[1:]+boundary[:1])])
    return vs,fs,{'footprint_samples':len(points),'tube_heights':heights,'base_offset':base,'top_offset':top,'boundary_samples':len(boundary)}

def run(folder,req,c,source):
    started=time.monotonic()
    if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Exact pad source changed')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
    if len(objects)!=79 or any(v is None for v in objects.values()):raise ValueError('Original inventory required')
    targets={t['object'] for t in c['targets']};before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n not in targets};plans=[]
    for t in c['targets']:
        ob=objects[t['object']];support=objects[t['support']]
        if dependency(ob)[0]!=t['dependency_digest'] or dependency(support)[0]!=t['support_dependency_digest'] or any(dependency(objects[n])[0]!=sha for n,sha in t['grips'].items()):raise ValueError('Pad target/support/grip dependency changed')
        if ob.type!='MESH' or len(ob.data.vertices)!=456 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original strap components required')
        if [len(v) for v in components(len(ob.data.vertices),[list(p.vertices) for p in ob.data.polygons])]!=[64,64,8,8,8]*3:raise ValueError('Original strap component signature required')
        if len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL' or abs(ob.modifiers[0].width-.001)>1e-7 or ob.modifiers[0].segments!=4:raise ValueError('Original strap bevel required')
        if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Supported world-coordinate coating required')
        if support.type!='MESH' or support.modifiers or len(support.data.vertices)!=194:raise ValueError('Original tube required')
        endpoints=[support.matrix_world@support.data.vertices[i].co for i in (192,193)];d=endpoints[1]-endpoints[0];d.z=0;d.normalize();tree=world_tree(support,bpy.context.evaluated_depsgraph_get());patches=[]
        for n in sorted(t['grips']):
            grip=objects[n]
            if grip.type!='MESH' or grip.modifiers or len(grip.data.vertices)!=1220:raise ValueError('Current corrected grip required')
            ps=[grip.matrix_world@v.co for v in grip.data.vertices];center=Vector([(max(p[i] for p in ps)+min(p[i] for p in ps))/2 for i in range(3)]);center.z=0
            patches.append((n,'support-strip',patch(center,d,c['pad_length'],.086,.012,-.001,.006,tree)))
            for sign in (-1,1):patches.append((n,'low-end-pad',patch(center+d*(sign*(c['pad_length']/2-.034)),d,.045,.064,.008,.0055,.019,tree,8,8)))
        plans.append((ob,patches,tree))
    # Explicit bounds must contain the whole representative new pad, not only its unchanged grip.
    lo,hi=c['inspection']['bounds']
    for ob,patches,tree in plans:
        for grip,kind,(pvs,pfs,check) in patches:
            if grip=='trail-handle-left-2' and any(not lo[i]<=p[i]<=hi[i] for p in pvs for i in range(3)):raise ValueError('Representative pad outside fixed frame')
    members={n:objects[n] for n in list(c['inspection']['regions'].values())[0]};cam=bpy.context.scene.camera;oldcam=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);bpy.context.scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],members,'before');actions=[]
    for ob,patches,tree in plans:
        deps=bpy.context.evaluated_depsgraph_get();base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);v0=[list(v.co) for v in base.vertices];f0=[list(p.vertices) for p in base.polygons];uv0=[(l.name,[list(x.uv) for x in l.data]) for l in base.uv_layers];vs=v0.copy();fs=f0.copy();smooth=[p.use_smooth for p in base.polygons];inverse=ob.matrix_world.inverted();records=[]
        for grip,kind,(pvs,pfs,check) in patches:
            offset=len(vs);vs.extend([list(inverse@Vector(p)) for p in pvs]);fs.extend([[offset+i for i in f] for f in pfs]);smooth.extend([True]*(len(pfs)-check['boundary_samples'])+[False]*check['boundary_samples']);records.append({'grip':grip,'kind':kind,**check,'added_vertices':len(pvs),'added_faces':len(pfs)})
        if len(vs)-len(v0)>5000:raise ValueError('Pad geometry budget')
        mesh=bpy.data.meshes.new('trail-supported-exterior-pads');mesh.from_pydata(vs,[],fs);mesh.materials.append(ob.data.materials[0]);mesh.update();ob.data=mesh;ob.modifiers.clear()
        for face,s in zip(mesh.polygons,smooth):face.use_smooth=s
        adjacency={}
        for face in list(mesh.polygons)[len(f0):]:
            for edge in face.edge_keys:adjacency.setdefault(tuple(sorted(edge)),[]).append(face.use_smooth)
        for edge in mesh.edges:
            flags=adjacency.get(tuple(sorted(edge.vertices)),[])
            if flags and any(flags) and not all(flags):edge.use_edge_sharp=True
        for name,values in uv0:
            layer=mesh.uv_layers.new(name=name)
            for x,y in zip(layer.data,values):x.uv=y
            for face in list(mesh.polygons)[len(f0):]:
                coords=[mesh.vertices[i].co for i in face.vertices];origin=coords[0];u=(coords[1]-origin).normalized();normal=(coords[1]-origin).cross(coords[2]-origin).normalized();v=normal.cross(u)
                for idx,p in zip(face.loop_indices,coords):layer.data[idx].uv=((p-origin).dot(u),(p-origin).dot(v))
            if [list(x.uv) for x in layer.data[:len(values)]]!=values:raise ValueError('Original evaluated UV changed')
        if [list(v.co) for v in mesh.vertices[:len(v0)]]!=v0 or [list(p.vertices) for p in mesh.polygons[:len(f0)]]!=f0:raise ValueError('Original evaluated straps changed')
        bpy.context.view_layer.update();quality=inventory(ob,bpy.context.evaluated_depsgraph_get())
        if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Pad topology failed')
        # Check the actual appended bottoms, including end-pad overlap into the strip.
        actual=[];offset=len(v0)
        for row in records:
            count=row['footprint_samples'];gaps=[]
            for vertex,h in zip(list(mesh.vertices)[offset:offset+count],row.pop('tube_heights')):
                p=ob.matrix_world@vertex.co;gaps.append(p.z-h[2])
            expected=row['base_offset']
            if max(abs(x-expected) for x in gaps)>1e-6:raise ValueError('Actual pad foot left its declared support surface')
            if row['kind']=='support-strip' and max(gaps)>0:raise ValueError('Floating strip')
            if row['kind']=='low-end-pad' and max(gaps)>=.006:raise ValueError('End pad no longer overlaps strip')
            actual.append({'kind':row['kind'],'grip':row['grip'],'sampled_bottom_offsets':[min(gaps),max(gaps)],'samples':count});offset+=row['added_vertices']
        actions.append({'object':ob.name,'source_evaluated_vertices':len(v0),'source_evaluated_faces':len(f0),'source_evaluated_uv_loops':sum(len(v) for _,v in uv0),'patches':records,'actual_bottom_checks':actual,'topology':quality,'original_bevel_frozen':True})
    if any(dependency(objects[n])[0]!=sha for n,sha in protected.items()):raise ValueError('Non-target changed')
    va=render_scene(folder,c['inspection'],members,'after')
    for a,b in zip(vb['views'],va['views']):
        if any(a[k]!=b[k] for k in ('direction','camera_position','ortho_scale','lighting')):raise ValueError('Fixed frame changed')
    cam.matrix_world,cam.data.type,cam.data.ortho_scale=oldcam
    if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
    report={'version':VERSION,'author':c['author'],'actions':actions,'source_unchanged':True,'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'protected_objects':len(protected),'unchanged_non_targets':True,'contacts_checked':True,'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Visible shallow pads only, original evaluated strap surfaces/UV kept. 18 overlapping closed components appended to two static objects; source bevel frozen. Finite surface samples do not prove union, full collision, animation or historical function.'}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
