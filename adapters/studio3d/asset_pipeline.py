# SPDX-License-Identifier: GPL-2.0-or-later
"""Blender static-asset preparation. No claim of artist-grade retopology."""
import array,json,math,struct,time
import bpy
from mathutils.bvhtree import BVHTree

def topology(obj):
    m=obj.data;m.calc_loop_triangles();uses=[0]*len(m.edges)
    for p in m.polygons:
        for i in p.loop_indices:uses[m.loops[i].edge_index]+=1
    uv=m.uv_layers.active;area=0;outside=0
    if uv:
        for t in m.loop_triangles:
            a,b,c=[uv.data[i].uv for i in t.loops];area+=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))/2
        outside=sum(not (-1e-5<=v.uv.x<=1.00001 and -1e-5<=v.uv.y<=1.00001) for v in uv.data)
    return {'vertices':len(m.vertices),'triangles':len(m.loop_triangles),'polygons':len(m.polygons),'ngons':sum(len(p.vertices)>4 for p in m.polygons),'boundary_edges':sum(x==1 for x in uses),'nonmanifold_edges':sum(x>2 for x in uses),'loose_edges':sum(x==0 for x in uses),'degenerate_faces':sum(p.area<1e-12 for p in m.polygons),'uv_present':bool(uv),'uv_outside_01_loops':outside,'uv_triangle_area_sum':area,'uv_overlap':'not exactly tested','edge_flow_artist_review':'required'}

def pack_occlusion(path, *, associate_orm=True):
    """glTF AO shares the ORM texture; explicit post-export JSON association."""
    raw=path.read_bytes();length=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+length]);changed=False;bin_length=struct.unpack_from('<I',raw,20+length)[0];binary=bytearray(raw[28+length:28+length+bin_length]);repaired=0
    for mat in doc.get('materials',[]) if associate_orm else []:
        texture=mat.get('pbrMetallicRoughness',{}).get('metallicRoughnessTexture')
        if texture:mat['occlusionTexture']={'index':texture['index'],'strength':1};changed=True
    # A collapsed UV triangle has no unique tangent frame. Preserve all valid
    # MikkTSpace frames; at singular vertices use a documented orthogonal basis
    # instead of exporting a zero vector that violates glTF. This is a warning,
    # not a claim that the UV parametrization has been repaired.
    for mesh in doc.get('meshes',[]):
        for primitive in mesh.get('primitives',[]):
            attributes=primitive.get('attributes',{})
            if 'TANGENT' not in attributes or 'NORMAL' not in attributes:continue
            ta=doc['accessors'][attributes['TANGENT']];na=doc['accessors'][attributes['NORMAL']];tv=doc['bufferViews'][ta['bufferView']];nv=doc['bufferViews'][na['bufferView']]
            if ta['componentType']!=5126 or na['componentType']!=5126:raise ValueError('Unexpected exported tangent layout')
            for i in range(ta['count']):
                to=tv.get('byteOffset',0)+ta.get('byteOffset',0)+i*tv.get('byteStride',16);t=struct.unpack_from('<4f',binary,to)
                if all(math.isfinite(x) for x in t) and sum(x*x for x in t[:3])>1e-12:continue
                no=nv.get('byteOffset',0)+na.get('byteOffset',0)+i*nv.get('byteStride',12);n=struct.unpack_from('<3f',binary,no);nl=math.sqrt(sum(x*x for x in n))
                if nl<1e-10:raise ValueError('Cannot construct tangent for invalid normal')
                n=[x/nl for x in n];axis=min(range(3),key=lambda k:abs(n[k]));a=[float(k==axis) for k in range(3)];dot=n[axis];v=[a[k]-n[k]*dot for k in range(3)];vl=math.sqrt(sum(x*x for x in v));struct.pack_into('<4f',binary,to,*[x/vl for x in v],-1 if t[3]<0 else 1);repaired+=1
    if changed or repaired:
        text=json.dumps(doc,separators=(',',':')).encode();text+=b' '*((-len(text))%4);tail=struct.pack('<II',len(binary),0x004e4942)+binary;path.write_bytes(struct.pack('<III',0x46546c67,2,20+len(text)+len(tail))+struct.pack('<II',len(text),0x4e4f534a)+text+tail)
    return {'singular_tangent_frames':repaired,'meaning':'Orthogonal fallback at singular UVs; UV quality still requires review'}

def surface_error(a,b):
    def sample(source,target):
        tree=BVHTree.FromPolygons([target.matrix_world@v.co for v in target.data.vertices],[tuple(p.vertices) for p in target.data.polygons],all_triangles=False)
        vertices=source.data.vertices;step=max(1,math.ceil(len(vertices)/2048));distances=[]
        for i in range(0,len(vertices),step):
            hit=tree.find_nearest(source.matrix_world@vertices[i].co)
            if hit[0] is not None:distances.append(hit[3])
        return max(distances,default=0),len(distances)
    x,n=sample(a,b);y,k=sample(b,a);return {'max_distance_m':max(x,y),'samples':n+k,'method':'two-direction sampled vertex-to-triangle nearest distance; not continuous Hausdorff proof'}

def prepare(folder,objects,size,phase,options=None,_lods=True):
    _lods = _lods and (options or {}).get('generate_lods',True)
    started=time.monotonic();s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=8;s.render.threads_mode='FIXED';s.render.threads=4
    s.render.use_persistent_data=True
    options=options or {};project=options.get('method')=='project';high_sources=[];parts=[];projection_report=None
    phase('asset: evaluated static mesh')
    deps=bpy.context.evaluated_depsgraph_get();copies=[]
    if project:
        from adapters.studio3d import projection
        phase('asset: high master to per-part low mesh');copies,high_sources,parts=projection.setup(objects,options)
    else:
        for source in objects:
            mesh=bpy.data.meshes.new_from_object(source.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps);obj=bpy.data.objects.new(source.name+'-static',mesh);bpy.context.collection.objects.link(obj);obj.matrix_world=source.matrix_world.copy();copies.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in copies:obj.select_set(True)
    bpy.context.view_layer.objects.active=copies[0];bpy.ops.object.join();low=bpy.context.object;low.name='Static asset LOD0';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    for source in objects:source.hide_render=True;source.hide_set(True)
    raw_topology=topology(low)
    if any(not all(math.isfinite(x) for x in v.co) for v in low.data.vertices):raise ValueError('Nonfinite geometry')
    phase('asset: cleanup and UV atlas');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=0.000001);bpy.ops.mesh.dissolve_degenerate(threshold=0.00000001);bpy.ops.object.mode_set(mode='OBJECT')
    # A single new atlas, never retain separate overlapping per-part UV sets.
    while low.data.uv_layers:low.data.uv_layers.remove(low.data.uv_layers[-1])
    low.data.uv_layers.new(name='AtlasUV');low.data.uv_layers.active_index=0;low.data.uv_layers.active.active_render=True
    # Dissolve handles collapsed edges; boolean sliver faces can have long,
    # collinear edges. Remove only the same tiny-area faces that fail the gate.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bpy.ops.mesh.select_all(action='DESELECT');bpy.ops.object.mode_set(mode='OBJECT')
    slivers=[p for p in low.data.polygons if p.area<1e-12];removed_area=sum(p.area for p in slivers)
    for p in slivers:p.select=True
    bpy.ops.object.mode_set(mode='EDIT')
    if slivers:bpy.ops.mesh.delete(type='ONLY_FACE')
    bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.delete_loose(use_verts=True,use_edges=True,use_faces=False);bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY',ngon_method='BEAUTY');bpy.ops.object.mode_set(mode='OBJECT')
    for p in low.data.polygons:p.select=p.area<1e-12
    extra_slivers=sum(p.select for p in low.data.polygons)
    bpy.ops.object.mode_set(mode='EDIT')
    if extra_slivers:bpy.ops.mesh.delete(type='ONLY_FACE')
    # A fixed atlas fraction per island can exceed the entire UV tile when a
    # detailed high has thousands of disconnected bolt/bevel islands. Relative
    # margins scale with island size, then the packer fits the atlas to 0..1.
    bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.delete_loose(use_verts=True,use_edges=True,use_faces=False);bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.0001,margin_method='SCALED',scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
    before=topology(low)
    if project:
        audit=projection.ray_audit(low,high_sources,options.get('ray_distance',.03))
        projection_report=projection.report(parts,audit,options)
        (folder/'projection-diagnostic.json').write_text(json.dumps(projection_report,indent=2),encoding='utf-8')
        if audit['miss_fraction']>.05:raise ValueError('Projection ray sample misses exceed 5%; revise low surface or ray distance')
    (folder/'cleanup-diagnostic.json').write_text(json.dumps({'raw':raw_topology,'cleaned':before,'sliver_faces_removed':len(slivers),'removed_face_area_m2':removed_area},indent=2),encoding='utf-8')
    if before['degenerate_faces'] or not before['uv_present'] or before['uv_outside_01_loops'] or not .01<=before['uv_triangle_area_sum']<=1.02:raise ValueError('Degenerate faces, absent/collapsed/outside UV or definite UV overlap prevent baking')
    # Duplicate material nodes so the source objects remain editable.
    for i,m in enumerate(low.data.materials):low.data.materials[i]=m.copy()
    def image(name,noncolor):
        im=bpy.data.images.new(name,width=size,height=size,alpha=False);im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB';return im
    images={k:image(k,k!='basecolor') for k in ('basecolor','normal','roughness','metallic','ao')}
    if project:images['material']=image('roughness-metallic',True)
    targets=[]
    for m in low.data.materials:
        m.use_nodes=True;n=m.node_tree.nodes.new('ShaderNodeTexImage');targets.append((m,n));m.node_tree.nodes.active=n
    s.render.bake.margin=8;s.render.bake.use_clear=True;s.render.bake.use_selected_to_active=project;s.render.bake.normal_space='TANGENT'
    if project:
        s.render.bake.use_cage=True;s.render.bake.cage_extrusion=options.get('ray_distance',.03);s.render.bake.max_ray_distance=2*options.get('ray_distance',.03)
        projection.select(high_sources+[low],low)
    source_materials=list({m for ob in high_sources for m in ob.data.materials}) if project else [m for m,_ in targets]
    def target(im):
        for m,n in targets:n.image=im;m.node_tree.nodes.active=n
    channels=[('basecolor','Base Color'),('material',None)] if project else [('basecolor','Base Color'),('roughness','Roughness'),('metallic','Metallic')]
    for channel,input_name in channels:
        s.cycles.samples=1 # Unlit data passes are deterministic; AO is sampled below.
        phase('asset: baking '+channel);target(images[channel]);restore=[]
        for m in source_materials:
            n=m.node_tree.nodes;links=m.node_tree.links;p=next(x for x in n if x.type=='BSDF_PRINCIPLED');out=next(x for x in n if x.type=='OUTPUT_MATERIAL');surface=out.inputs['Surface'];old=surface.links[0].from_socket if surface.links else None;em=n.new('ShaderNodeEmission');combined=None
            if channel=='material':
                combined=n.new('ShaderNodeCombineColor')
                for target_name,source_name in [('Green','Roughness'),('Blue','Metallic')]:
                    source=p.inputs[source_name]
                    if source.is_linked:links.new(source.links[0].from_socket,combined.inputs[target_name])
                    else:combined.inputs[target_name].default_value=source.default_value
                links.new(combined.outputs[0],em.inputs['Color'])
            else:
                source=p.inputs[input_name]
                if source.is_linked:links.new(source.links[0].from_socket,em.inputs['Color'])
                else:
                    value=source.default_value;em.inputs['Color'].default_value=tuple(value) if input_name=='Base Color' else (value,value,value,1)
            links.new(em.outputs[0],surface);restore.append((m,out,old,em,combined))
        bpy.ops.object.bake(type='EMIT')
        for m,out,old,em,combined in restore:
            m.node_tree.nodes.remove(em)
            if combined:m.node_tree.nodes.remove(combined)
            if old:m.node_tree.links.new(old,out.inputs['Surface'])
    phase('asset: baking tangent normal');target(images['normal']);bpy.ops.object.bake(type='NORMAL')
    phase('asset: baking AO');s.cycles.samples=8;target(images['ao']);bpy.ops.object.bake(type='AO')
    if project:
        for obj in high_sources:obj.hide_render=True;obj.hide_set(True)
        projection.restore(low,parts);before=topology(low)
    packed=image('orm',True);pixels={}
    for k in ('ao','roughness','metallic'):
        a=array.array('f',[0])*(size*size*4);images[k].pixels.foreach_get(a);pixels[k]=a
    material_pixels=None
    if project:
        material_pixels=array.array('f',[0])*(size*size*4);images['material'].pixels.foreach_get(material_pixels)
    out=array.array('f',[0])*(size*size*4)
    for i in range(0,len(out),4):out[i]=pixels['ao'][i];out[i+1]=material_pixels[i+1] if project else pixels['roughness'][i];out[i+2]=material_pixels[i+2] if project else pixels['metallic'][i];out[i+3]=1
    packed.pixels.foreach_set(out);packed.update();images['orm']=packed
    saved={}
    for k in ('basecolor','normal','orm','ao'):
        im=images[k];im.filepath_raw=str(folder/(k+'.png'));im.file_format='PNG';im.save();im.pack();a=array.array('f',[0])*(size*size*4);im.pixels.foreach_get(a);saved[k]={'file':k+'.png','resolution':[size,size],'pixel_min':min(a[0::4]),'pixel_max':max(a[0::4]),'bake':'Cycles high master projected to reduced low mesh' if project else 'Cycles material surface, no high-to-low geometric projection'}
    # One static atlas material. Merging is explicit and is not suitable for an
    # articulated vehicle until material islands are transferred to its parts.
    mat=bpy.data.materials.new('Baked static PBR');mat.use_nodes=True;n=mat.node_tree.nodes;links=mat.node_tree.links;p=n.get('Principled BSDF');p.inputs['Metallic'].default_value=1;p.inputs['Roughness'].default_value=1
    tex={}
    for k in ('basecolor','normal','orm'):
        node=n.new('ShaderNodeTexImage');node.image=images[k];tex[k]=node
    links.new(tex['basecolor'].outputs['Color'],p.inputs['Base Color']);normal=n.new('ShaderNodeNormalMap');links.new(tex['normal'].outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],p.inputs['Normal'])
    sep=n.new('ShaderNodeSeparateColor');links.new(tex['orm'].outputs['Color'],sep.inputs[0]);links.new(sep.outputs['Green'],p.inputs['Roughness']);links.new(sep.outputs['Blue'],p.inputs['Metallic'])
    low.data.materials.clear();low.data.materials.append(mat)
    for face in low.data.polygons:face.material_index=0
    lods=[{'level':0,'file':'model.glb','ratio_requested':1,'topology':topology(low),'distance':{'max_distance_m':0,'samples':0}}]
    diagonal=math.sqrt(sum((max(v.co[i] for v in low.data.vertices)-min(v.co[i] for v in low.data.vertices))**2 for i in range(3)))
    game_parts=projection.split(low,parts) if project else None
    if project and _lods:
        for part in game_parts:part.hide_render=True;part.hide_set(True)
    for level,ratio in ([(1,.5),(2,.25)] if _lods else []):
        phase('asset: LOD'+str(level));name='model-lod'+str(level)+'.glb'
        if project:
            # Every topology gets its own atlas and tangent-space bake directly
            # from the frozen high master. Decimated UVs cannot reuse LOD0 maps.
            lod_folder=folder/('bake-lod'+str(level));lod_folder.mkdir()
            lod_options={**options,'triangle_budget':max(1,int(options.get('triangle_budget',30000)*ratio))}
            lod_parts,lod_report=prepare(lod_folder,objects,size,phase,lod_options,_lods=False)
            stats=lod_report['topology_before'];distances=[];by_name={o['source_part']:o for o in game_parts}
            for part in lod_parts:distances.append(surface_error(by_name[part['source_part']],part))
            error={'max_distance_m':max(d['max_distance_m'] for d in distances),'samples':sum(d['samples'] for d in distances),'method':'two-direction sampled per-part world-space distance from LOD0'}
            # Copy only fixed filenames to the delivery root; the GLB embeds its
            # independent images. Keep internal diagnostics for audit.
            for channel in ('basecolor','normal','orm','ao'):
                filename=f'lod{level}-{channel}.png';(folder/filename).write_bytes((lod_folder/(channel+'.png')).read_bytes());lod_report['baking'][channel]['file']=filename
            projection.select(lod_parts,lod_parts[0])
        else:
            obj=low.copy();obj.data=low.data.copy();obj.name='Static asset LOD'+str(level);bpy.context.collection.objects.link(obj);bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;mod=obj.modifiers.new('Bounded reduction','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
            error=surface_error(low,obj);stats=topology(obj)
        bpy.ops.export_scene.gltf(filepath=str(folder/name),export_format='GLB',use_selection=True,export_apply=True,export_tangents=True);tangents=pack_occlusion(folder/name)
        for part in (lod_parts if project else [obj]):part.hide_render=True;part.hide_set(True)
        lod={'level':level,'file':name,'ratio_requested':ratio,'topology':stats,'distance':error,'tangent_frames':tangents,'max_distance_fraction_of_diameter':error['max_distance_m']/max(diagonal,1e-9)}
        if project:lod.update(baking=lod_report['baking'],projection=lod_report['projection'],checks=lod_report['checks'],texture_strategy='independent UV and high-to-low rebake')
        else:lod['texture_strategy']='inherited atlas; separate visual review required'
        lods.append(lod)
    bpy.ops.object.select_all(action='DESELECT');low.hide_set(False);low.select_set(True);bpy.context.view_layer.objects.active=low
    checks=[{'id':'degenerate-faces','status':'pass' if not before['degenerate_faces'] else 'fail','message':str(before['degenerate_faces'])}, {'id':'mesh-boundary','status':'warn' if before['boundary_edges'] or before['nonmanifold_edges'] else 'pass','message':str(before['boundary_edges'])+' boundary edges; '+str(before['nonmanifold_edges'])+' nonmanifold edges'}, {'id':'uv-atlas','status':'pass' if before['uv_present'] and not before['uv_outside_01_loops'] else 'fail','message':'UV present and in 0..1; exact overlap and density unverified'}, {'id':'lod-reduction','status':'pass' if all(a['topology']['triangles']>b['topology']['triangles'] for a,b in zip(lods,lods[1:])) else 'fail','message':'Actual triangle counts checked'}, {'id':'lod-sampled-distance','status':'warn' if any(x.get('max_distance_fraction_of_diameter',0)>.01 for x in lods) else 'pass','message':'Two-direction sampled distance; silhouette popping requires view check'}]
    singular=sum(x.get('tangent_frames',{}).get('singular_tangent_frames',0) for x in lods)
    for lod in lods:lod['visual_status']='unverified'
    checks.append({'id':'lod-visual-review','status':'warn','message':'Each LOD needs separate visual inspection; format, counts and sampled distance do not certify appearance.'})
    checks.append({'id':'uv-area-utilization','status':'warn' if before['uv_triangle_area_sum']<.2 else 'pass','message':str(round(before['uv_triangle_area_sum']*100,2))+'% summed triangle UV area; not exact union area or density uniformity'})
    checks.append({'id':'singular-uv-tangent','status':'warn' if singular else 'pass','message':str(singular)+' singular UV tangent frames use orthogonal fallback; artist review required'})
    if project:
        checks.extend([{'id':'projection-coverage','status':'warn' if audit['misses'] else 'pass','message':str(audit)}, {'id':'game-budget','status':'pass' if before['triangles']<=options.get('triangle_budget',30000) else 'fail','message':str(before['triangles'])+' / '+str(options.get('triangle_budget',30000))}])
        low.hide_set(True);low.hide_render=True
        for part in game_parts:part.hide_render=False
        projection.select(game_parts,game_parts[0])
    return game_parts or [low],{'schema':'jarvis.studio3d.asset-pipeline.v1','kind':'projected rigid parts' if project else 'static merged review asset','source_part_names':[o.name for o in objects],'part_hierarchy_preserved':False,'part_origins_preserved':project,'projection':projection_report,'topology_raw':raw_topology,'cleanup':{'merge_distance_m':.000001,'degenerate_distance_m':.00000001,'vertices_removed':raw_topology['vertices']-before['vertices']},'topology_before':before,'baking':saved,'lods':lods,'checks':checks,'elapsed_seconds':time.monotonic()-started,'unverified':['artist retopology and deformation edge flow','exact UV overlap/density','per-texel projection and photo fidelity','LOD silhouette popping','material coat/transmission and anisotropy preservation','full target-engine performance'],'AAA_certified':False}
