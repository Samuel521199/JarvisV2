# SPDX-License-Identifier: GPL-2.0-or-later
"""High master -> bounded per-part reduction -> isolated projection helpers.

This is mechanical static retopology assistance, not an artist or rigging system.
"""
import math
import bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree


def evaluated_copy(source, name):
    deps=bpy.context.evaluated_depsgraph_get()
    mesh=bpy.data.meshes.new_from_object(source.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.matrix_world=source.matrix_world.copy()
    return obj


def select(objects,active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=active


def setup(objects,options):
    from adapters.studio3d.asset_pipeline import topology
    budget=options.get('triangle_budget',30000);parts=[];high=[];low=[]
    # Each source is already the high master. Never subdivide to hit a quota.
    bases=[o for o in objects if not o.get('bake_target')]
    for i,source in enumerate(bases):
        hi=evaluated_copy(source,'HIGH '+source.name);stats=topology(hi)
        if not stats['triangles']:raise ValueError('Empty high source')
        if any(not math.isfinite(x) for v in hi.data.vertices for x in v.co):raise ValueError('Nonfinite high source')
        high.append(hi)
        # Complexity weights are visible in the receipt, not a global ratio.
        name=source.name.lower()
        category='tracks' if 'track-' in name else 'wheels' if any(k in name for k in ('wheel','road-','return-','hub','rim','spokes')) else 'small_round' if any(k in name for k in ('lamp','handle','barrel')) else 'body'
        weight=math.sqrt(stats['triangles'])
        parts.append({'name':source.name,'high_triangles':stats['triangles'],'weight':weight,'budget_group':category,'matrix':source.matrix_world.copy(),'offset':Vector(((i%5)*64,((i//5)%5)*64,(i//25)*64)),'key':'part-'+str(i)})
    total=sum(p['high_triangles'] for p in parts)
    if total>1500000:raise ValueError('High master exceeds 1.5M triangle worker budget')
    reserve=sum(min(24,p['high_triangles']) for p in parts)
    if reserve>budget:raise ValueError('Budget cannot preserve all parts')
    shares={'tracks':.16,'wheels':.32,'small_round':.07,'body':.45}
    present={p['budget_group'] for p in parts};normalizer=sum(shares[k] for k in present)
    weighted={k:sum(p['weight'] for p in parts if p['budget_group']==k) for k in present}
    for hi,p in zip(high,parts):
        obj=hi.copy();obj.data=hi.data.copy();obj.name='LOW '+p['name'];bpy.context.collection.objects.link(obj)
        target=min(p['high_triangles'],min(24,p['high_triangles'])+int((budget-reserve)*shares[p['budget_group']]/normalizer*p['weight']/weighted[p['budget_group']]))
        p['target_triangles']=target;select([obj],obj)
        declaration=next((d for d in options.get('_declarations',[]) if d['id']==p['name']),None)
        if options.get('category')=='organic' and declaration and declaration['kind']=='lathe' and declaration['params'].get('caps') and not any(k in declaration.get('modifiers',{}) for k in ('difference','thickness')) and target>=128:
            from adapters.studio3d.organic import retopo_lathe
            vertices,faces=retopo_lathe(declaration['params'],target)
            tree=BVHTree.FromPolygons([v.co for v in hi.data.vertices],[tuple(f.vertices) for f in hi.data.polygons])
            fitted=[tree.find_nearest(Vector(v))[0] for v in vertices]
            mesh=bpy.data.meshes.new('Organic ring low');mesh.from_pydata(fitted,[],faces);mesh.update()
            for mat in hi.data.materials:mesh.materials.append(mat)
            obj.data=mesh
            for face in mesh.polygons:face.use_smooth=True
            bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
            p['reduction_method']='arc-length rings projected onto evaluated high surface'
        elif target<p['high_triangles']:
            mod=obj.modifiers.new('Per part budget','DECIMATE');mod.ratio=target/p['high_triangles'];mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
            p['reduction_method']='per-part collapse decimation'
        # Independent groups remain separate throughout cleanup and baking.
        obj.vertex_groups.clear();group=obj.vertex_groups.new(name=p['key']);group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
        obj.location+=p['offset'];hi.location+=p['offset'];low.append(obj)
        p['low_triangles']=topology(obj)['triangles']
    # Detail meshes share their parent bake location and cast onto its low mesh.
    # They remain in the high master, but add no separate low draw/object budget.
    by_name={p['name']:p for p in parts}
    for source in objects:
        if source.get('bake_target'):
            if source['bake_target'] not in by_name:raise ValueError('Unknown detail bake target')
            p=by_name[source['bake_target']];hi=evaluated_copy(source,'HIGH DETAIL '+source.name);hi.location+=p['offset'];high.append(hi)
            p.setdefault('attached_details',[]).append({'name':source.name,'triangles':topology(hi)['triangles']})
        source.hide_render=True;source.hide_set(True)
    if sum(topology(o)['triangles'] for o in high)>1500000:raise ValueError('High master detail budget exceeded')
    bpy.context.view_layer.update()
    # Cycles selected-to-active iterates source objects. A single bake proxy
    # avoids repeatedly tracing the entire destination for every part. Preserve
    # Generated coordinates through explicit per-source coordinate anchors.
    for hi in high:
        bounds=[Vector(v) for v in hi.bound_box];lo=Vector([min(v[k] for v in bounds) for k in range(3)]);extent=Vector([max(v[k] for v in bounds)-lo[k] for k in range(3)])
        anchor=bpy.data.objects.new('Bake coordinates '+hi.name,None);bpy.context.collection.objects.link(anchor)
        anchor.matrix_world=hi.matrix_world@Matrix.Translation(lo)@Matrix.Diagonal((*[max(x,1e-9) for x in extent],1))
        for i,mat in enumerate(hi.data.materials):
            mat=mat.copy();hi.data.materials[i]=mat
            if not mat.use_nodes:continue
            coord=mat.node_tree.nodes.new('ShaderNodeTexCoord');coord.object=anchor
            for node in list(mat.node_tree.nodes):
                if node.type=='TEX_COORD' and node!=coord:
                    for link in list(node.outputs['Generated'].links):mat.node_tree.links.new(coord.outputs['Object'],link.to_socket)
                if node.type in ('TEX_NOISE','TEX_VORONOI','TEX_WAVE') and not node.inputs['Vector'].is_linked:mat.node_tree.links.new(coord.outputs['Object'],node.inputs['Vector'])
    select(high,high[0]);bpy.ops.object.join();proxy=bpy.context.object;proxy.name='HIGH isolated bake proxy'
    return low,[proxy],parts


def ray_audit(low,high,distance):
    """Finite sample diagnostic. Not a per-texel cage coverage guarantee."""
    vertices=[];faces=[]
    for obj in high:
        start=len(vertices);vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(start+i for i in p.vertices) for p in obj.data.polygons)
    tree=BVHTree.FromPolygons(vertices,faces);misses=0;count=0
    low.data.calc_loop_triangles();triangles=low.data.loop_triangles
    # Match the smooth cage direction at interior, near-edge and near-vertex
    # samples. Face-centre rays alone miss uncovered patches on coarse LODs.
    weights=[(1/3,1/3,1/3),(.94,.03,.03),(.03,.94,.03),(.03,.03,.94),(.49,.49,.02),(.49,.02,.49),(.02,.49,.49)]
    stride=max(1,math.ceil(len(triangles)*len(weights)/8192))
    for index in range(0,len(triangles),stride):
        t=triangles[index]
        for w in weights:
            center=sum((low.matrix_world@low.data.vertices[i].co*weight for i,weight in zip(t.vertices,w)),Vector())
            n=sum((low.data.vertices[i].normal*weight for i,weight in zip(t.vertices,w)),Vector());n=low.matrix_world.to_3x3().inverted().transposed()@n
            if n.length<.1:misses+=1;count+=1;continue
            hit=tree.ray_cast(center+n*distance,-n.normalized(),distance*2.01)
            misses+=int(hit[0] is None);count+=1
    return {'samples':count,'misses':misses,'miss_fraction':misses/max(count,1),'method':'7 smooth-cage barycentric rays per sampled triangle, max8192 samples; not per-texel proof'}


def restore(low,parts):
    groups={low.vertex_groups[p['key']].index:p for p in parts}
    for v in low.data.vertices:
        match=[groups[g.group] for g in v.groups if g.group in groups and g.weight>.5]
        if len(match)!=1:raise ValueError('Lost or ambiguous part identity')
        v.co-=match[0]['offset']
    low.data.update()


def split(low,parts):
    """Keep source names, object origins and rigid transforms; no rig claim."""
    by_group={low.vertex_groups[p['key']].index:p for p in parts}
    owners={v.index:next(g.group for g in v.groups if g.group in by_group and g.weight>.5) for v in low.data.vertices}
    result=[];mesh=low.data;uv=mesh.uv_layers.active
    for group,p in by_group.items():
        polygons=[f for f in mesh.polygons if owners[f.vertices[0]]==group]
        if not polygons:raise ValueError('Reduction removed a required part')
        indices=sorted({i for f in polygons for i in f.vertices});mapping={v:i for i,v in enumerate(indices)};inverse=p['matrix'].inverted()
        data=bpy.data.meshes.new(p['name']+' game');data.from_pydata([inverse@mesh.vertices[i].co for i in indices],[],[[mapping[i] for i in f.vertices] for f in polygons]);data.update()
        data.materials.append(mesh.materials[0]);layer=data.uv_layers.new(name='AtlasUV');normals=[]
        for dest,src in zip(data.polygons,polygons):
            dest.use_smooth=src.use_smooth
            for di,si in zip(dest.loop_indices,src.loop_indices):
                layer.data[di].uv=uv.data[si].uv
                normals.append((p['matrix'].to_3x3().transposed()@mesh.corner_normals[si].vector).normalized())
        data.normals_split_custom_set(normals)
        obj=bpy.data.objects.new(p['name']+' · game',data);bpy.context.collection.objects.link(obj);obj.matrix_world=p['matrix'];obj['source_part']=p['name'];result.append(obj)
    low.hide_render=True;low.hide_set(True)
    return result


def report(parts,audit,options):
    return {'method':'Cycles selected-to-active, separated part bake positions','high_created_before_low':True,
      'high_triangles':sum(p['high_triangles']+sum(d['triangles'] for d in p.get('attached_details',[])) for p in parts),'requested_low_budget':options.get('triangle_budget',30000),
      'category':options.get('category','prop'),'ray_distance_m':options.get('ray_distance',.03),'normal_convention':'glTF tangent +Y',
      'coverage':audit,'parts':[{k:v for k,v in p.items() if k not in ('matrix','offset','key')} for p in parts],
      'origin_preserved':True,'rig_or_animation_preserved':False,'reference_fidelity':'requires photo review; polygon count is not evidence'}
