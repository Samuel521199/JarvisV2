# SPDX-License-Identifier: GPL-2.0-or-later
"""Blender-only trusted operations. JSON data never becomes executable code."""
import json,math,sys,time
from pathlib import Path
import bpy
from mathutils import Vector
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.assets import MAX_GLB_MESHES

def material(row,albedo=None,rotation=0,mapping='cylindrical'):
    m=bpy.data.materials.new(row['id']);m.use_nodes=True;n=m.node_tree.nodes;links=m.node_tree.links
    p=n.get('Principled BSDF');c=tuple(int(row['color'][i:i+2],16)/255 for i in (1,3,5));m.diffuse_color=(*c,1)
    # Blender node input is linear, UI/contract colour is sRGB.
    p.inputs['Base Color'].default_value=(*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c),1)
    for key,target in [('metallic','Metallic'),('roughness','Roughness'),('coat','Coat Weight'),('transmission','Transmission Weight')]:p.inputs[target].default_value=row[key]
    p.inputs['IOR'].default_value=1.45
    p.inputs['Coat Roughness'].default_value=row.get('coat_roughness',.15)
    if row.get('detail')=='weathered_paint':
        from adapters.studio3d.weathering import painted
        painted(m,row)
        return m
    if row.get('detail') in ('fruit_skin','bark'):
        from adapters.studio3d.organic import surface
        surface(m,row,albedo,rotation,mapping)
        return m
    if row.get('detail','none')!='none':
        noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=220 if row['detail']=='rubber' else 130;noise.inputs['Detail'].default_value=2
        bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.06 if row['detail'] in ('painted','steel') else .18;bump.inputs['Distance'].default_value=.00012 if row['detail'] in ('painted','steel') else .0004
        links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
        if row['detail'] in ('painted','steel'):
            # Restrained deterministic finish variation; not simulated wear.
            ramp=n.new('ShaderNodeValToRGB');base=tuple(p.inputs['Base Color'].default_value)
            for stop,factor in zip(ramp.color_ramp.elements,(.55,1.3)):stop.color=tuple(min(1,v*factor) for v in base[:3])+(1,)
            finish=n.new('ShaderNodeTexNoise');finish.inputs['Scale'].default_value=24;finish.inputs['Detail'].default_value=2
            links.new(finish.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],p.inputs['Base Color'])
            rough=n.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=max(.03,row['roughness']-.15);rough.inputs['To Max'].default_value=min(1,row['roughness']+.12);links.new(noise.outputs['Fac'],rough.inputs['Value']);links.new(rough.outputs['Result'],p.inputs['Roughness'])
            if row['detail']=='painted':
                chips=n.new('ShaderNodeTexNoise');chips.inputs['Scale'].default_value=95;chips.inputs['Detail'].default_value=3
                mask=n.new('ShaderNodeMath');mask.operation='GREATER_THAN';mask.inputs[1].default_value=.68;links.new(chips.outputs['Fac'],mask.inputs[0])
                # Convex-edge mask with broken coverage. Paint is dielectric;
                # only exposed substrate receives metal response. This is an
                # authored procedural finish, not measured physical weathering.
                geo=n.new('ShaderNodeNewGeometry');edge=n.new('ShaderNodeMapRange');edge.clamp=True;edge.inputs['From Min'].default_value=.51;edge.inputs['From Max'].default_value=.56;links.new(geo.outputs['Pointiness'],edge.inputs['Value'])
                wear=n.new('ShaderNodeMath');wear.operation='MULTIPLY';links.new(mask.outputs[0],wear.inputs[0]);links.new(edge.outputs['Result'],wear.inputs[1])
                mix=n.new('ShaderNodeMixRGB');links.new(wear.outputs[0],mix.inputs[0]);links.new(ramp.outputs[0],mix.inputs[1]);mix.inputs[2].default_value=(.11,.10,.085,1);links.new(mix.outputs[0],p.inputs['Base Color']);links.new(wear.outputs[0],p.inputs['Metallic'])
    return m

def geometry(o):
    p=o['params'];kind=o['kind']
    if kind=='box':bpy.ops.mesh.primitive_cube_add(size=1);obj=bpy.context.object;obj.scale=p['size'];bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    elif kind=='sphere':bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=p['radius']);obj=bpy.context.object
    elif kind=='cylinder':bpy.ops.mesh.primitive_cylinder_add(vertices=p.get('segments',128),radius=p['radius'],depth=p['depth']);obj=bpy.context.object
    elif kind=='torus':bpy.ops.mesh.primitive_torus_add(major_segments=96,minor_segments=32,major_radius=p['radius'],minor_radius=p['tube']);obj=bpy.context.object
    elif kind=='curve':
        curve=bpy.data.curves.new(o['id'],'CURVE');curve.dimensions='3D';curve.resolution_u=12;curve.bevel_depth=p['radius'];curve.bevel_resolution=3
        s=curve.splines.new('BEZIER');s.bezier_points.add(len(p['points'])-1)
        for bp,pt in zip(s.bezier_points,p['points']):bp.co=pt;bp.handle_left_type=bp.handle_right_type='AUTO'
        s.use_cyclic_u=p.get('closed',False);obj=bpy.data.objects.new(o['id'],curve);bpy.context.collection.objects.link(obj)
    else:
        if kind=='sweep':
            from adapters.studio3d.organic import sweep
            verts,faces=sweep(p)
        elif kind=='lathe':
            from adapters.studio3d.organic import radial
            verts,faces=radial(p)
        elif kind=='loft':
            rings=p['rings'];count=len(rings[0]);verts=[pt for ring in rings for pt in ring];closed=p.get('closed',True)
            faces=[(j*count+i,j*count+(i+1)%count,(j+1)*count+(i+1)%count,(j+1)*count+i) for j in range(len(rings)-1) for i in range(count if closed else count-1)]
            if closed and p.get('caps',True):faces.extend([tuple(reversed(range(count))),tuple(range((len(rings)-1)*count,len(rings)*count))])
        else:verts=p['vertices'];faces=p['faces']
        mesh=bpy.data.meshes.new(o['id']);mesh.from_pydata(verts,[],faces);mesh.update();obj=bpy.data.objects.new(o['id'],mesh);bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT');obj.select_set(False)
    obj.name=o['id'];obj.data.name=o['id'];obj.location=o['position'];obj.rotation_euler=[math.radians(a) for a in o['rotation']];obj.scale=o['scale']
    if obj.type=='MESH':
        for face in obj.data.polygons:face.use_smooth=o.get('shading','flat' if kind=='box' else 'smooth')=='smooth'
        # Preserve cast/collared silhouettes without smoothing across sharp
        # steps. Continuous lathe and subdivided surfaces remain smooth.
        if o.get('shading','smooth')=='smooth':obj.data.set_sharp_from_angle(angle=math.radians(40))
    return obj

def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]).resolve();start=time.monotonic();scene=validate(json.loads((folder/'scene.json').read_text(encoding='utf-8')))
    bpy.ops.wm.read_factory_settings(use_empty=True);mats={};objects={};visible=[]
    if 'master' in scene:
        # Only a host-copied, receipt-hash-verified first-party master is allowed.
        # The host never accepts arbitrary BLEND uploads or file paths.
        bpy.ops.wm.open_mainfile(filepath=str(folder/'source.blend'),load_ui=False,use_scripts=False)
        names=json.loads((folder/'master-parts.json').read_text(encoding='utf-8'))
        if not 1<=len(names)<=MAX_GLB_MESHES or len(set(names))!=len(names):raise ValueError('Invalid frozen master part inventory')
        for obj in list(bpy.context.scene.objects):
            if obj.name in names and obj.type in ('MESH','CURVE'):obj.hide_render=False;obj.hide_set(False);visible.append(obj)
            else:bpy.data.objects.remove(obj,do_unlink=True)
        if {o.name for o in visible}!=set(names):raise ValueError('Frozen master inventory differs')
    else:
        binding=scene.get('surface_texture',{});albedo=None
        if binding:
            albedo=bpy.data.images.load(str(folder/'surface-albedo.png'),check_existing=False);albedo.colorspace_settings.name='sRGB';albedo.pack()
        mats={r['id']:material(r,albedo if r['id']==binding.get('material') else None,binding.get('rotation',0),binding.get('mapping','cylindrical')) for r in scene['materials']}
    if 'asset' in scene and 'master' not in scene:
        # Preserve supplied high-poly topology and UV/normal seams during import.
        # Optimization belongs to an explicit preparation/LOD operation.
        bpy.ops.import_scene.gltf(filepath=str(folder/'source.glb'),merge_vertices=False)
        visible=[o for o in bpy.context.scene.objects if o.type=='MESH']
        if not 1<=len(visible)<=MAX_GLB_MESHES:raise ValueError('Imported object budget exceeded')
        for o in list(bpy.context.scene.objects):
            if o.type in ('LIGHT','CAMERA'):bpy.data.objects.remove(o,do_unlink=True)
    phase_times=[];last_phase={'name':'initialization','started':start}
    def phase(s):
        now=time.monotonic();phase_times.append({'phase':last_phase['name'],'elapsed_seconds':now-last_phase['started'],'model_calls':0,'api_tokens':0,'api_cost_usd':0})
        # Preserve completed phase durations even if a later phase fails or the
        # host interrupts the worker. An unfinished phase has no fabricated time.
        (folder/'phase-timings.json').write_text(json.dumps({'completed':phase_times,'active':s}),encoding='utf-8')
        last_phase.update(name=s,started=now);print('STUDIO3D '+s,flush=True)
    phase('modelling')
    for row in ([] if 'master' in scene else scene['objects']):
        bpy.ops.object.select_all(action='DESELECT');obj=geometry(row);obj.data.materials.append(mats[row['material']]);objects[row['id']]=obj
        if row.get('cap_material'):
            obj.data.materials.append(mats[row['cap_material']])
            for face in list(obj.data.polygons)[-2:]:face.material_index=1;face.use_smooth=False
        if row.get('bake_target'):obj['bake_target']=row['bake_target']
        mod=row['modifiers']
        if mod.get('subdivision'):
            m=obj.modifiers.new('Surface subdivision','SUBSURF');m.levels=m.render_levels=mod['subdivision']
        for key in mod.get('difference',[]):
            m=obj.modifiers.new('Cut '+key,'BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=objects[key]
        if mod.get('thickness'):
            m=obj.modifiers.new('Shell thickness','SOLIDIFY');m.thickness=mod['thickness']
        if mod.get('bevel'):
            m=obj.modifiers.new('Edge highlights','BEVEL');m.width=mod['bevel'];m.segments=mod.get('bevel_segments',3)
        obj.hide_render=not row.get('visible',True);obj.hide_viewport=False
        if obj.hide_render:obj.display_type='WIRE';continue
        visible.append(obj)
        if obj.type=='MESH':
            bpy.context.view_layer.objects.active=obj;obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT');obj.select_set(False)
            if scene.get('surface_texture',{}).get('mapping')=='lathe' and row['material']==scene['surface_texture']['material']:
                from adapters.studio3d.organic import lathe_uv
                uv=obj.data.uv_layers.new(name='SurfaceUV')
                for face,coords in zip(obj.data.polygons,lathe_uv(row['params'],[tuple(p.vertices) for p in obj.data.polygons])):
                    for index,xy in zip(face.loop_indices,coords):uv.data[index].uv=xy
    asset_report=None
    if scene.get('asset_pipeline'):
        from adapters.studio3d.asset_pipeline import prepare
        visible,asset_report=prepare(folder,visible,scene['asset_pipeline']['texture_size'],phase,{**scene['asset_pipeline'],'_declarations':scene['objects']})
    deps=bpy.context.evaluated_depsgraph_get();rows=[];coords=[];triangles=0
    for obj in visible:
        if len(visible)>(MAX_GLB_MESHES if 'asset' in scene or 'master' in scene else 128):raise ValueError('Visible object budget exceeded')
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles();n=len(mesh.loop_triangles);triangles+=n
        if triangles>1500000:raise ValueError('Evaluated triangle budget exceeded')
        rows.append({'id':obj.name,'vertices':len(mesh.vertices),'triangles':n,'uv':bool(mesh.uv_layers),'zero_area_faces':sum(p.area<1e-12 for p in mesh.polygons)})
        # Compare exported surface to the evaluated modifier result, never the
        # control cage: subdivision legitimately shrinks its original bounds.
        coords.extend(obj.matrix_world@v.co for v in mesh.vertices);evaluated.to_mesh_clear()
    if not coords:raise ValueError('No visible geometry')
    low=Vector([min(c[i] for c in coords) for i in range(3)]);high=Vector([max(c[i] for c in coords) for i in range(3)]);center=(low+high)*.5;span=max(high-low)
    if span>30:raise ValueError('Scene bounds exceeded')
    phase('studio lighting')
    organic=any(r.get('detail')=='fruit_skin' for r in scene['materials']);photo=scene['render']
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,low.z-min(.008,span*.012)));floor=bpy.context.object;floor.name='Studio floor';floor.data.materials.append(material({'id':'floor','color':photo.get('floor_color','#40454e'),'metallic':0 if organic else .15,'roughness':.75 if organic else .28,'coat':0 if organic else .1,'transmission':0}))
    world=bpy.data.worlds.new('Studio world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.25,.32,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45;bpy.context.scene.world=world
    def area(name,location,power,size,color):
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
        ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=center+Vector(location)*span;ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
    world.node_tree.nodes['Background'].inputs[1].default_value=photo.get('world_strength',.45)
    if 'world_color' in photo:world.node_tree.nodes['Background'].inputs[0].default_value=tuple((int(photo['world_color'][j:j+2],16)/255)**2.2 for j in (1,3,5))+(1,)
    if 'lights' in photo:
        for i,light in enumerate(photo['lights']):area('Review light '+str(i),light['position'],light['power']*span*span,light['size']*span,tuple(int(light['color'][j:j+2],16)/255 for j in (1,3,5)))
    else:area('Key softbox',(.3,-.8,1.5),(110 if organic else 220)*span*span,span*.9,(.94,.97,1));area('Warm rim',(-.7,.9,.9),(60 if organic else 280)*span*span,span*.7,(1,.94,.85));area('Front fill',(1,.5,.6),(55 if organic else 140)*span*span,span*.8,(.94,.97,1))
    cam=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',cam);bpy.context.collection.objects.link(camera);cam.lens=50
    direction={'front':(1,-1.32,.7),'rear':(-1,-1.3,.65),'side':(.08,-1.8,.55)}[scene['render']['view']];camera.location=center+Vector(direction)*span*.92;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    direction=photo.get('camera_direction',direction);cam.lens=photo.get('lens',50)
    camera.location=center+Vector(direction)*span;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    s=bpy.context.scene;s.camera=camera;engine=scene['render']['engine'];available={x.identifier for x in s.render.bl_rna.properties['engine'].enum_items}
    # Blender 4.x called this EEVEE_NEXT; 5.2 restored the EEVEE identifier.
    if engine=='BLENDER_EEVEE_NEXT' and engine not in available and 'BLENDER_EEVEE' in available:engine='BLENDER_EEVEE'
    s.render.engine=engine;s.render.threads_mode='FIXED';s.render.threads=4
    final=scene['render']['quality']=='final'
    # The baked atlas and source meshes already occupy substantial memory.
    # Keep its denoising frame bounded; the editable master gets the 2K hero.
    s.render.resolution_x=(1280 if asset_report else 1920) if final else 960
    s.render.resolution_y=(854 if asset_report else 1280) if final else 640;s.render.resolution_percentage=100
    if photo.get('format')=='square':s.render.resolution_y=s.render.resolution_x
    hero_resolution=[s.render.resolution_x,s.render.resolution_y]
    # Fit actual evaluated geometry. A fixed 10cm near plane clips small props.
    from adapters.studio3d.framing import distance
    cam.sensor_fit='HORIZONTAL';rotation=camera.rotation_euler.to_quaternion()
    aligned=[tuple(rotation.inverted()@(point-center)) for point in coords]
    camera.location=center+Vector(direction).normalized()*distance(aligned,cam.sensor_width,cam.lens,s.render.resolution_x/s.render.resolution_y)
    cam.clip_start=max(.00001,span*.005);cam.clip_end=max(100,span*100)
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.filepath=str(folder/'preview.png');s.view_settings.view_transform='AgX'
    s.view_settings.exposure=scene['render'].get('exposure',0)
    if s.render.engine=='CYCLES':s.cycles.device='CPU';s.cycles.samples=64 if final else 24;s.cycles.use_denoising=True;s.cycles.max_bounces=6
    s['jarvis_schema']=scene['schema'];s['jarvis_title']=scene['title'];s['jarvis_limitations']=' | '.join(scene['unfulfilled'])
    phase('saving blend');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),check_existing=False,compress=True)
    phase('exporting glb');bpy.ops.object.select_all(action='DESELECT')
    for obj in visible:obj.select_set(True)
    # Rigid animation commonly lives on an EMPTY parent rather than a mesh.
    # Selection-only export includes its hierarchy but otherwise skips the
    # parent's action. Preserve imported ancestors explicitly; do not select
    # unrelated objects, review lights or cameras.
    animation_ancestors=set()
    if 'asset' in scene and not asset_report:
        for obj in visible:
            parent=obj.parent
            while parent is not None:
                if parent.type=='EMPTY':animation_ancestors.add(parent)
                parent=parent.parent
        for parent in animation_ancestors:parent.select_set(True)
    # Imported PBR assets also need their UV tangent frames re-exported for
    # normal maps; retaining only the textures leaves each viewer to rebuild
    # a potentially different frame at mirrored UVs and seams.
    preserve_game_high=False
    if 'asset' in scene and not asset_report:
        for obj in animation_ancestors:
            raw=obj.get('jarvis_game_asset')
            if isinstance(raw,str) and len(raw)<=24000:
                try:meta=json.loads(raw)
                except (ValueError,TypeError):continue
                if isinstance(meta,dict) and meta.get('schema')=='jarvis.game-high.v1':preserve_game_high=True
    if preserve_game_high:
        # This is an unchanged imported game high, not a preparation operation.
        # Keep original custom normals, tangents, clips and metadata byte-for-byte.
        # Consume the job's staging copy; the managed original asset is retained.
        # Existing geometry, resource, roundtrip and official format checks still run.
        (folder/'source.glb').replace(folder/'model.glb')
    else:
        bpy.ops.export_scene.gltf(filepath=str(folder/'model.glb'),export_format='GLB',use_selection=True,export_apply=True,export_materials='EXPORT',export_cameras=False,export_lights=False,export_tangents=bool(asset_report or 'asset' in scene),**({'export_extras':True,'export_animation_mode':'NLA_TRACKS'} if 'asset' in scene and not asset_report else {}))
    imported_tangent_frames=None
    if 'asset' in scene and not asset_report and not preserve_game_high:
        from adapters.studio3d.asset_pipeline import pack_occlusion
        # The importer/exporter may recalculate zero tangents at collapsed UV
        # vertices. Use the same recorded orthogonal fallback as the native
        # pipeline, while preserving the imported AO channel and strength.
        imported_tangent_frames=pack_occlusion(folder/'model.glb',associate_orm=False)
    if asset_report:
        from adapters.studio3d.asset_pipeline import pack_occlusion
        asset_report['lods'][0]['tangent_frames']=pack_occlusion(folder/'model.glb')
        count=sum(l.get('tangent_frames',{}).get('singular_tangent_frames',0) for l in asset_report['lods'])
        for row in asset_report['checks']:
            if row['id']=='singular-uv-tangent':row.update(status='warn' if count else 'pass',message=str(count)+' singular UV tangent frames use orthogonal fallback; artist review required')
    phase('rendering');bpy.ops.render.render(write_still=True)
    views=[]
    if scene['render'].get('five_views',False):
        # Documented axes and aspect-aware framing. Five actual camera renders,
        # never copies/crops of the hero frame or claims of image reconstruction.
        cam.type='ORTHO';cam.ortho_scale=span*1.18
        s.render.resolution_x=960;s.render.resolution_y=640
        if engine=='CYCLES':s.cycles.samples=16
        for name,direction in [('front',(1,0,0)),('rear',(-1,0,0)),('left',(0,1,0)),('right',(0,-1,0)),('top',(0,0,1))]:
            cam.ortho_scale=max((high.y-low.y) if name in ('front','rear','top') else (high.x-low.x),((high.x-low.x) if name=='top' else (high.z-low.z))*1.5)*1.18
            phase('orthographic '+name);camera.location=center+Vector(direction)*span*2
            camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
            if name=='top':camera.rotation_euler=(0,0,-math.pi/2)
            bpy.context.view_layer.update();view=camera.matrix_world.inverted();projected=[view@p for p in coords];half_w=cam.ortho_scale/2;half_h=half_w/1.5
            extent=[max(abs(p.x)/half_w for p in projected),max(abs(p.y)/half_h for p in projected)]
            if max(extent)>1.001:raise ValueError('Orthographic camera clips visible geometry: '+name)
            s.render.filepath=str(folder/('view-'+name+'.png'));bpy.ops.render.render(write_still=True)
            views.append({'view':name,'file':'view-'+name+'.png','projection':'ORTHOGRAPHIC','resolution':[960,640],'ortho_scale_m':cam.ortho_scale,'look_from':list(camera.location),'axis_convention':'X forward, Y left, Z up','frame_extent_ndc':extent,'frame_check_passed':True})
    # Import exported GLB in a clean scene; counts and bounds evidence only.
    phase('checking glb roundtrip');bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(folder/'model.glb'),merge_vertices=True)
    imported=[o for o in bpy.context.scene.objects if o.type=='MESH'];ic=[o.matrix_world@v.co for o in imported for v in o.data.vertices]
    ibounds=[[min(c[i] for c in ic) for i in range(3)],[max(c[i] for c in ic) for i in range(3)]] if ic else None
    delta=max(abs(ibounds[j][i]-[low,high][j][i]) for j in range(2) for i in range(3)) if ibounds else None
    report={'schema':'jarvis.studio3d.report.v1','blender':bpy.app.version_string,'visible_objects':len(visible),'triangles':triangles,'objects':rows,'bounds_m':[list(low),list(high)],'render':{'engine':engine,'requested_engine':scene['render']['engine'],'device':'CPU' if engine=='CYCLES' else 'AUTO','resolution':hero_resolution,'samples':(64 if final else 24) if engine=='CYCLES' else None},'glb_roundtrip':{'mesh_objects':len(imported),'bounds_m':ibounds,'max_bound_error_m':delta,'passed':bool(ic and delta<.001)},'elapsed_seconds':time.monotonic()-start,'unverified':['OEM mechanical accuracy','manufacturing','production topology','UV quality','baked PBR textures','LODs','engine performance'],'warnings':['GLB contains base PBR; procedural bump detail stays in Blender/render.','Automatic UV presence is not UV quality certification.']}
    report['orthographic_views']=views
    report['game_high_source_preserved']=preserve_game_high
    if imported_tangent_frames is not None:
        report['imported_tangent_frames']=imported_tangent_frames
        if imported_tangent_frames['singular_tangent_frames']:
            report['warnings'].append('Singular UV tangents use recorded orthogonal fallback; UV quality still requires artist review.')
    if asset_report:
        report['asset_pipeline']=asset_report;report['warnings']=['Static atlas preparation merges object hierarchy; no articulated motion or AAA certification.','Baked base color, normal and ORM are embedded. Coat/transmission and anisotropy are not preserved.'];report['unverified']=['artist topology','UV quality','high-to-low projection','LOD silhouettes','target engine performance','manufacturing']
        if asset_report.get('projection'):
            report['warnings']=['High master projected to reduced rigid parts; original part origins retained, no rig/animation preservation.','Photo fidelity, per-texel projection and target-engine performance require review.'];report['unverified']=['artist topology','exact UV quality','per-texel projection','photo fidelity','LOD silhouettes','target engine performance']
    phase('complete');report['phase_timings']=phase_times
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
