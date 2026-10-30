# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual fixed-camera supplemental renders; never change the source asset."""
import hashlib,itertools,json,sys,time
from contextlib import contextmanager
from pathlib import Path
import bpy
from mathutils import Vector
from modules.skills.studio3d.render_inspection import validate,VERSION


def probe_socket(mat,channel):
    """Only fixed shader inputs or the uniquely identifiable authored edge chain."""
    nodes=mat.node_tree.nodes
    if channel=='damage_mask':
        node=nodes.get('jarvis_damage_mask')
        if not mat.get('jarvis_damage_regions') or node is None or node.type!='MATH' or node.operation!='MAXIMUM':raise ValueError('Missing authored damage-region mask')
        return node.outputs['Value'],{'node':node.name,'scope':'Fixed authored spatial damage union'}
    if channel in ('base_color','roughness','metallic'):
        ps=[n for n in nodes if n.type=='BSDF_PRINCIPLED']
        if len(ps)!=1:raise ValueError('Probe requires one Principled shader')
        socket=ps[0].inputs[{'base_color':'Base Color','roughness':'Roughness','metallic':'Metallic'}[channel]]
        return (socket.links[0].from_socket if socket.is_linked else socket.default_value),{'input':socket.name,'linked':socket.is_linked}
    distances=[n for n in nodes if n.type=='VECT_MATH' and n.operation=='DISTANCE' and any(l.from_node.type=='BEVEL' for l in n.inputs[1].links)]
    if len(distances)!=1:raise ValueError('Probe requires the verified bevel-normal distance chain')
    socket=distances[0].outputs['Value'];trace=[distances[0].name]
    if channel=='edge_mask':
        for kind in ('MAP_RANGE','MATH','MATH'):
            links=list(socket.links)
            if len(links)!=1 or links[0].to_node.type!=kind:raise ValueError('Authored edge chain is ambiguous')
            node=links[0].to_node
            if kind=='MATH' and node.operation!='MULTIPLY':raise ValueError('Unexpected edge operation')
            socket=node.outputs['Result' if kind=='MAP_RANGE' else 'Value'];trace.append(node.name)
    return socket,{'trace':trace,'scope':'Authored local-wear chain only; not arbitrary material introspection'}


@contextmanager
def probe_surface(scene,objects,members,channel):
    """Emission-only source-channel view; black occluders, no saved scene edits."""
    if not channel:
        yield None
        return
    slots=[];copies=[];oldworld=scene.world;settings=scene.view_settings
    oldview=(settings.view_transform,settings.look,settings.exposure,settings.gamma)
    world=bpy.data.worlds.new('inspection-channel-world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
    black=bpy.data.materials.new('inspection-occluder');black.use_nodes=True;copies.append(black)
    black.node_tree.nodes.clear();bo=black.node_tree.nodes.new('ShaderNodeOutputMaterial');be=black.node_tree.nodes.new('ShaderNodeEmission');be.inputs['Color'].default_value=(0,0,0,1);black.node_tree.links.new(be.outputs[0],bo.inputs['Surface'])
    descriptions=[]
    try:
        scene.world=world;settings.view_transform='Standard';settings.look='None';settings.exposure=0;settings.gamma=1
        seen=set();target_data={objects[n].data for n in members}
        for ob in scene.objects:
            if ob.type not in ('MESH','CURVE') or ob.data in seen:continue
            seen.add(ob.data);data=ob.data;original=list(data.materials);slots.append((data,original))
            if data in target_data:
                if not original or any(m is None or not m.use_nodes for m in original):raise ValueError('Missing source shader')
                replacements=[]
                for mat in original:
                    clone=mat.copy();copies.append(clone);socket,description=probe_socket(clone,channel)
                    outs=[n for n in clone.node_tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
                    if len(outs)!=1:raise ValueError('Ambiguous material output')
                    emit=clone.node_tree.nodes.new('ShaderNodeEmission')
                    if hasattr(socket,'node'):clone.node_tree.links.new(socket,emit.inputs['Color'])
                    else:emit.inputs['Color'].default_value=tuple(socket) if hasattr(socket,'__len__') else (socket,socket,socket,1)
                    clone.node_tree.links.new(emit.outputs[0],outs[0].inputs['Surface']);replacements.append(clone)
                    descriptions.append({'object':ob.name,'material':mat.name,**description})
                data.materials.clear()
                for mat in replacements:data.materials.append(mat)
            else:
                data.materials.clear()
                for _ in range(max(1,len(original))):data.materials.append(black)
        yield {'channel':channel,'targets':members,'materials':descriptions,'display':'Emission only, Standard view, zero exposure; PNG display transfer is not a linear scalar measurement','occlusion':'Other surfaces are black occluders','source_saved':False}
    finally:
        for data,original in slots:
            data.materials.clear()
            for mat in original:data.materials.append(mat)
        scene.world=oldworld;settings.view_transform,settings.look,settings.exposure,settings.gamma=oldview
        for mat in copies:bpy.data.materials.remove(mat)
        bpy.data.worlds.remove(world)


@contextmanager
def probe_lighting(scene,camera,center,span,preset):
    """Fixed neutral/grazing studio probes; restore the source stage afterwards."""
    if preset=='source':
        yield {'preset':'source','exposure':scene.view_settings.exposure}
        return
    lights=[(o,o.hide_render) for o in scene.objects if o.type=='LIGHT']
    old_world=scene.world;created=[];world=bpy.data.worlds.new('inspection-probe-world')
    try:
        for obj,_ in lights:obj.hide_render=True
        world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
        world.node_tree.nodes['Background'].inputs['Strength'].default_value=.08;scene.world=world
        basis=camera.rotation_euler.to_matrix();right=basis@Vector((1,0,0));up=basis@Vector((0,1,0));out=basis@Vector((0,0,1))
        direction=(out*.90+right*.35+up*.60).normalized() if preset=='neutral' else (out*.28+right*(1 if preset=='grazing-right' else -1)+up*.25).normalized()
        scale=max(span,.25);descriptions=[]
        for label,vec,power,size in [('key',direction,450.,1.4 if preset=='neutral' else .36),('fill',(out-right*.4+up*.3).normalized(),35.,1.8)]:
            data=bpy.data.lights.new('inspection-'+label,'AREA');obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);created.append(obj)
            obj.location=center+vec*scale*2;obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
            data.energy=power*scale*scale;data.shape='DISK';data.size=size*scale;data.color=(1,1,1)
            descriptions.append({'role':label,'position':list(obj.location),'energy':data.energy,'size':data.size})
        yield {'preset':preset,'lights':descriptions,'world_strength':.08,'exposure':scene.view_settings.exposure,'view_transform':scene.view_settings.view_transform,'scope':'Controlled diagnostic illumination; not reference lighting or proof of physical material correctness.'}
    finally:
        scene.world=old_world
        for obj in created:
            data=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.lights.remove(data)
        bpy.data.worlds.remove(world)
        for obj,hidden in lights:obj.hide_render=hidden


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]);request=json.loads((folder/'request.json').read_text());source=folder/'source.blend'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=request['source_sha256']:raise ValueError('Source changed')
    c=validate(request['contract'],request['visible_names']);start=time.monotonic()
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    objects={n:bpy.data.objects.get(n) for n in request['visible_names']}
    if any(o is None for o in objects.values()):raise ValueError('Source inventory changed')
    result=render_scene(folder,c,objects)
    result['region_inventory']=region_inventory(c,objects)
    result.update(version=VERSION,elapsed_seconds=time.monotonic()-start,source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==request['source_sha256'],scope='Supplemental oblique inspection, not calibrated reference reconstruction or replacement of canonical orthographic views.')
    (folder/'report.json').write_text(json.dumps(result,indent=2)+'\n')


def region_inventory(c,objects):
    """Read the actual source, not the recipe or a visual model's guess."""
    result={}
    for name in sorted({n for members in c['regions'].values() for n in members}):
        obj=objects[name];row={'type':obj.type,'materials':[]}
        for slot in obj.material_slots:
            m=slot.material;info={'name':m.name if m else None}
            if m and m.use_nodes:
                info['principled']=[{'inputs':{k:{'linked':node.inputs[k].is_linked,'default':list(node.inputs[k].default_value) if k=='Base Color' else node.inputs[k].default_value} for k in ('Base Color','Roughness','Metallic')}} for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED']
            row['materials'].append(info)
        if obj.type=='MESH':
            mesh=obj.data;parent=list(range(len(mesh.vertices)))
            def root(i):
                while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
                return i
            edges={}
            for poly in mesh.polygons:
                for a,b in poly.edge_keys:
                    parent[root(a)]=root(b);edges[(a,b)]=edges.get((a,b),0)+1
            points=[obj.matrix_world@v.co for v in mesh.vertices]
            row.update(vertices=len(points),faces=len(mesh.polygons),connected_components=len({root(i) for i in range(len(points))}),boundary_edges=sum(n==1 for n in edges.values()),overfull_edges=sum(n>2 for n in edges.values()),material_indices=sorted({p.material_index for p in mesh.polygons}),world_bounds=[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]])
        result[name]=row
    return result


def render_scene(folder,c,objects,prefix='inspection'):
    """Shared camera/framing for native scene and actual GLB reimport checks."""
    scene=bpy.context.scene;camera=scene.camera;cam=camera.data;cam.type='ORTHO';cam.sensor_fit='HORIZONTAL'
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=c['samples'];scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=4
    width,height=c['resolution'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100
    lo,hi=c['bounds'];aspect=width/height
    # Evaluated geometry used solely for the view/crop projection. Hidden
    # cutters and studio objects never inflate object regions.
    deps=bpy.context.evaluated_depsgraph_get();points={}
    for name,obj in objects.items():
        evaluated=obj.evaluated_get(deps);mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=deps)
        points[name]=[obj.matrix_world@v.co for v in mesh.vertices];bpy.data.meshes.remove(mesh)
    focus=c.get('focus_region');frame_points=[p for n in (c['regions'][focus] if focus else points) for p in points[n]]
    if focus:
        lo=[min(p[i] for p in frame_points) for i in range(3)];hi=[max(p[i] for p in frame_points) for i in range(3)]
    center=(Vector(lo)+Vector(hi))/2;span=max(b-a for a,b in zip(lo,hi));frame=[Vector(v) for v in itertools.product(*zip(lo,hi))]
    rows=[]
    for view in c['views']:
        direction=Vector(view['direction']).normalized();camera.location=center+direction*span*3
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        if abs(direction.z)>.999:camera.rotation_euler=(0,0,-1.5707963267948966)
        bpy.context.view_layer.update();inverse=camera.matrix_world.inverted();projected=[inverse@p for p in frame]
        cam.ortho_scale=max(max(abs(v.x) for v in projected)*2,max(abs(v.y) for v in projected)*2*aspect)*1.12
        sx=cam.ortho_scale/2;sy=sx/aspect
        all_points=[inverse@p for p in frame_points]
        extent=[max(abs(p.x)/sx for p in all_points),max(abs(p.y)/sy for p in all_points)]
        if max(extent)>1.001:raise ValueError('Fixed frame clips candidate geometry')
        name=view['id'];scene.render.filepath=str(folder/(prefix+'-'+name+'.png'))
        with probe_lighting(scene,camera,center,span,view.get('lighting','source')) as lighting:
            with probe_surface(scene,objects,c['regions'][focus] if focus else [],view.get('surface_probe')) as surface:
                print('inspection '+name+' '+lighting['preset']+' '+str(view.get('surface_probe')),flush=True);bpy.ops.render.render(write_still=True)
        regions={}
        for region,members in c['regions'].items():
            ps=[inverse@p for member in members for p in points[member]]
            xy=[((p.x/sx+1)*width/2,(1-p.y/sy)*height/2) for p in ps]
            x0=min(p[0] for p in xy);x1=max(p[0] for p in xy);y0=min(p[1] for p in xy);y1=max(p[1] for p in xy)
            pad=max(8,.06*max(x1-x0,y1-y0))
            rect=[max(0,int(x0-pad)),max(0,int(y0-pad)),min(width,int(x1+pad)+1),min(height,int(y1+pad)+1)]
            if rect[2]>rect[0] and rect[3]>rect[1]:regions[region]={'rect':rect,'members':members,'visibility':'projected bounds; may include occlusion, not proof all members are visible'}
        rows.append({'view':name,'file':prefix+'-'+name+'.png','projection':'ORTHOGRAPHIC','direction':list(direction),'camera_position':list(camera.location),'ortho_scale':cam.ortho_scale,'frame_extent':extent,'regions':regions,'lighting':lighting,'surface_probe':surface})
    return {'views':rows,'resolution':[width,height],'focus_region':focus,'frame_bounds':[list(lo),list(hi)],'framing_scope':'Declared region only; other geometry may be outside the frame' if focus else 'Full declared asset'}


if __name__=='__main__':main()
