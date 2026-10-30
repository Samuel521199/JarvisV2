# SPDX-License-Identifier: GPL-2.0-or-later
"""Appearance-only blind recess; no functional chamber or internal mechanism."""
import bpy,json,hashlib,time,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from modules.skills.studio3d.facade_pocket import placement
from modules.skills.studio3d.attachment_seat import VERSION,components
from adapters.studio3d.demonstration_worker import digest_object,topology
from adapters.studio3d.inspection_worker import render_scene

def tree(o):
 o.data.calc_loop_triangles()
 return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.loop_triangles],all_triangles=True)

def replace_subset(o,keep,mirror=False,mirror_indices=None,triangulate=False):
 old=o.data;remap={i:j for j,i in enumerate(keep)};faces=[p for p in old.polygons if all(i in remap for i in p.vertices)];coords=[list(old.vertices[i].co) for i in keep]
 selection=set(keep) if mirror else set(mirror_indices or [])
 for i,p in zip(keep,coords):
  if i in selection:p[1]*=-1
 if any(any(i in selection for i in p.vertices) and not all(i in selection for i in p.vertices) for p in faces):raise ValueError('Mirror must cover whole components')
 if triangulate:
  old.calc_loop_triangles();triangles=[t for t in old.loop_triangles if all(i in remap for i in t.vertices)];faces=[old.polygons[t.polygon_index] for t in triangles];orders=[list(t.loops) for t in triangles]
 else:orders=[list(p.loop_indices) for p in faces]
 orders=[[order[0],*reversed(order[1:])] if all(old.loops[i].vertex_index in selection for i in order) else order for order in orders]
 mesh=bpy.data.meshes.new(old.name+' facade correction');mesh.from_pydata(coords,[],[[remap[old.loops[i].vertex_index] for i in order] for order in orders]);mesh.update()
 for m in old.materials:mesh.materials.append(m)
 for a,b in zip(faces,mesh.polygons):b.material_index=a.material_index;b.use_smooth=a.use_smooth
 for layer in old.uv_layers:
  uv=mesh.uv_layers.new(name=layer.name)
  for order,p in zip(orders,mesh.polygons):
   for i,j in zip(order,p.loop_indices):uv.data[j].uv=layer.data[i].uv
 o.data=mesh;bpy.data.meshes.remove(old)

def run(folder,req,c,source):
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()}
 if c['schema']=='jarvis.studio3d.facade-slot-repair.v1':return repair_slots(folder,req,c,source,objects,before,start)
 v2=c['schema'].endswith('.v2')
 for n,d in c['bindings'].items():
  o=objects[n]
  if before[n]!=d or o.type!='MESH' or (o.modifiers and n not in ('rear-seated-cosmetic-fittings','fasteners-breech')) or o.animation_data or o.data.shape_keys or o.data.users!=1:raise ValueError('Original facade source changed')
  if n in ('rear-seated-cosmetic-fittings','fasteners-breech') and (len(o.modifiers)!=1 or o.modifiers[0].type!='BEVEL' or abs(o.modifiers[0].width-(.002 if n=='rear-seated-cosmetic-fittings' else .001))>1e-6 or o.modifiers[0].segments!=4):raise ValueError('Original attachment bevel required')
 body=objects['rear-cover-body'];disc=objects['breech-recess'];facade=objects['shaped-rear-cover']
 if (len(body.data.vertices),len(facade.data.vertices),len(disc.data.vertices))!=(216,324,194):raise ValueError('Only original three meshes')
 oldverts=[body.matrix_world@v.co for v in body.data.vertices];dv=[disc.matrix_world@v.co for v in disc.data.vertices];rear=min(p.x for p in oldverts);front=max(p.x for p in oldverts)
 if abs(rear+.7405)>1e-6 or abs(front+.3855)>1e-6 or any(abs(p.y)>.125001 or not .989999<=p.z<=1.310001 for p in oldverts):raise ValueError('Original facade envelope changed')
 cy=0.;cz=1.135;radius=.068
 if max(math.hypot(p.y-cy,p.z-cz) for p in dv)>.061001:raise ValueError('Existing badge radius changed')
 floor,delta=placement(rear,c['depth'],min(p.x for p in dv),max(p.x for p in dv),front)
 scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before');extra=[]
 if v2:
  trim=objects['rear-seated-cosmetic-fittings'];groups=components(len(trim.data.vertices),[list(p.vertices) for p in trim.data.polygons])
  if [len(g) for g in groups]!=[192,66,98,8,98,8,98] or groups[3][0]!=356:raise ValueError('Original trim components changed')
  if any((trim.matrix_world@trim.data.vertices[i].co).x>-.7839 for g in groups[:3] for i in g):raise ValueError('Only three original front trim components')
  before_facade_tree=tree(facade);fasteners=objects['fasteners-breech'];deps=bpy.context.evaluated_depsgraph_get();ev=fasteners.evaluated_get(deps);fm=ev.to_mesh();near=[]
  for v in fm.vertices:
   p=fasteners.matrix_world@v.co;hit=before_facade_tree.find_nearest(p)
   if hit[0] is not None and hit[3]<.025 and p.x<-.78:near.append((Vector((p.x,-p.y,p.z)),hit[3]))
  ev.to_mesh_clear();fg=components(len(fasteners.data.vertices),[list(p.vertices) for p in fasteners.data.polygons])
  if len(fg)!=12 or any(len(g)!=14 for g in fg) or fg[4][0]!=56:raise ValueError('Original front fastener components required')
  if any(fasteners.data.vertices[i].co.x>-.78 for g in fg[4:] for i in g):raise ValueError('Only original eight front head components')
  # Freeze the actual bevel result before reflecting. Re-evaluation of mirrored
  # base polygons produced a measured 0.0001073 deviation in the rejected trial.
  baked=bpy.data.meshes.new_from_object(fasteners.evaluated_get(deps),depsgraph=deps);old=fasteners.data;fasteners.modifiers.clear();fasteners.data=baked;bpy.data.meshes.remove(old)
  eg=components(len(baked.vertices),[list(p.vertices) for p in baked.polygons]);frontgroups=[g for g in eg if all(baked.vertices[i].co.x<-.78 for i in g)]
  if len(eg)!=12 or len(frontgroups)!=8:raise ValueError('Evaluated front components differ')
  replace_subset(facade,list(range(len(facade.data.vertices))),mirror=True,triangulate=True);replace_subset(trim,[i for g in groups[3:] for i in g]);replace_subset(fasteners,list(range(len(fasteners.data.vertices))),mirror_indices=[i for g in frontgroups for i in g],triangulate=True);bpy.context.view_layer.update()
  ev=fasteners.evaluated_get(bpy.context.evaluated_depsgraph_get());fm=ev.to_mesh();fk=KDTree(len(fm.vertices))
  for v in fm.vertices:fk.insert(fasteners.matrix_world@v.co,v.index)
  fk.balance();actual_error=max((fk.find(p)[2] for p,d in near),default=1);ev.to_mesh_clear()
  if actual_error>1e-7:raise ValueError('Actual mirrored head geometry differs from sampled positions')
  ft=tree(facade);growth=max((ft.find_nearest(p)[3]-d for p,d in near),default=0)
  if not near or growth>1e-6:raise ValueError('Mirrored facade lost sampled fixed fastener support')
  if topology(facade)['boundary_edges'] or topology(facade)['overfull_edges']:raise ValueError('Mirrored facade topology')
  extra=[{'target':'shaped-rear-cover','operation':'mirror_visible_C_outline_y_with_correct_winding_and_UV','sampled_fastener_vertices':len(near),'max_nearest_distance_growth':growth,'actual_mirrored_fastener_nearest_error':actual_error},{'target':'fasteners-breech','operation':'mirror_eight_evaluated_front_head_components_with_support','four_side_evaluated_heads_unchanged':True,'original_bevel_evaluated':True},{'target':'rear-seated-cosmetic-fittings','operation':'remove_three_unreferenced_front_trim_components','removed_vertices':356,'remaining_components':4,'remaining_base_vertices':len(trim.data.vertices),'side_fittings_kept':True}]
 # Subtract only a shallow closed cylinder on the rear face of this source box.
 startx=rear-.06
 bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=radius,depth=floor-startx,location=((floor+startx)/2,cy,cz),rotation=(0,math.pi/2,0));cutter=bpy.context.object
 for material in body.data.materials:
  if material is None:raise ValueError('Original paint material missing')
  cutter.data.materials.append(material)
 for p in cutter.data.polygons:p.use_smooth=len(p.vertices)==4
 bpy.context.view_layer.update();mod=body.modifiers.new('Bounded cosmetic blind pocket','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();mesh=bpy.data.meshes.new_from_object(body.evaluated_get(deps),depsgraph=deps);old=body.data;body.modifiers.clear();body.data=mesh;bpy.data.objects.remove(cutter,do_unlink=True);bpy.data.meshes.remove(old);mesh.update()
 # Boolean-added walls receive nondegenerate face-local UVs; outside source UVs stay.
 inv=body.matrix_world.inverted();newfaces=0
 for p in mesh.polygons:
  center=body.matrix_world@p.center;radial=math.hypot(center.y-cy,center.z-cz)
  if radial<radius+.001 and rear-1e-6<=center.x<=floor+1e-6:
   newfaces+=1;normal=p.normal;u=normal.cross(Vector((0,0,1)))
   if u.length<.1:u=normal.cross(Vector((0,1,0)))
   u.normalize();v=normal.cross(u).normalized()
   for layer in mesh.uv_layers:
    for li in p.loop_indices:
     pos=mesh.vertices[mesh.loops[li].vertex_index].co;layer.data[li].uv=(pos.dot(u),pos.dot(v))
   p.use_smooth=abs(normal.x)<.1
 disc.location.x+=delta;mesh.update();bpy.context.view_layer.update()
 topo=topology(body)
 if topo['boundary_edges'] or topo['overfull_edges'] or len(mesh.vertices)>1500:raise ValueError('Blind cosmetic shell topology failed')
 kd=KDTree(len(mesh.vertices))
 for v in mesh.vertices:kd.insert(body.matrix_world@v.co,v.index)
 kd.balance();error=max(kd.find(p)[2] for p in oldverts)
 if error>1e-7:raise ValueError('Original outer vertices changed')
 bt=tree(body);probes=[]
 for y,z in [(0,0),(.02,0),(-.02,0),(0,.02),(0,-.02),(.035,.02),(-.035,.02),(.035,-.02),(-.035,-.02)]:
  hit,normal,_,_=bt.ray_cast(Vector((rear-.065,cy+y,cz+z)),Vector((1,0,0)),.15)
  if hit is None or abs(hit.x-floor)>1e-6 or normal.x>-.9:raise ValueError('Pocket must have visible solid floor')
  probes.append(list(hit))
 actual=[disc.matrix_world@v.co for v in disc.data.vertices];back=max(p.x for p in actual);feet=[p for p in actual if abs(p.x-back)<1e-6];embed=[]
 for p in feet:
  hit,normal,_,_=bt.ray_cast(Vector((rear-.06,p.y,p.z)),Vector((1,0,0)),.15)
  if hit is None or not .0009<=p.x-hit.x<=.0011:raise ValueError('Cosmetic badge lost blind-floor overlap')
  embed.append(p.x-hit.x)
 if len(embed)<8:raise ValueError('Insufficient floor witnesses')
 after={n:digest_object(o) for n,o in objects.items()};targets={'rear-cover-body','breech-recess'}|({'shaped-rear-cover','rear-seated-cosmetic-fittings','fasteners-breech'} if v2 else set())
 if any(m is None for m in body.data.materials):raise ValueError('Cosmetic boolean introduced empty material slot')
 if any(before[n]!=after[n] for n in objects if n not in targets):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':extra+[{'target':'rear-cover-body','operation':'shallow_blind_cosmetic_pocket','depth':c['depth'],'radius':radius,'original_vertex_nearest_error':error,'topology':topo,'floor_probe_count':len(probes),'floor_probes':probes,'new_face_uv_count':newfaces},{'target':'breech-recess','operation':'move_existing_decorative_disc_behind_facade','translation':[delta,0,0],'back_overlap_samples':len(embed),'back_overlap_range':[min(embed),max(embed)],'front_x_before':min(p.x for p in dv),'front_x_after':min(p.x for p in actual)}],'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'contact_scope':'Finite disc-back overlap rays, nine blind floor rays and optional nearby fastener distance samples; no full collision or functional mechanism claim','source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-start,'scope':'Appearance-only closed recess; no barrel connection, loading geometry or functional internal structure. Body outer vertices preserved, rear topology/UV replaced. Optional source-bound C outline mirrored and three unsupported front trim components removed, side fittings kept. Unselected objects unchanged. History/dimensions unverified.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

def repair_slots(folder,req,c,source,objects,before,start):
 from adapters.studio3d.evaluated_shading_worker import surface
 o=objects['rear-cover-body'];mesh=o.data
 if before[o.name]!=c['source_digest'] or o.modifiers or len(mesh.vertices)!=409 or len(mesh.polygons)!=316 or len(mesh.materials)!=2 or mesh.materials[0] is None or mesh.materials[1] is not None:raise ValueError('Only measured cosmetic Boolean slot failure')
 affected=[p.index for p in mesh.polygons if p.material_index==1]
 if affected:raise ValueError('Only measured unused empty slot may be removed')
 for i in affected:
  p=mesh.polygons[i];v=o.matrix_world@p.center
  if not -.741<=v.x<=-.695 or math.hypot(v.y,v.z-1.135)>.069:raise ValueError('Missing material outside declared pocket')
 prior=surface(mesh);prior.pop('material_indices');scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before')
 for i in affected:mesh.polygons[i].material_index=0
 mesh.materials.pop(index=1);mesh.update();actual=surface(mesh);actual.pop('material_indices')
 if prior!=actual:raise ValueError('Slot repair changed geometry or UV')
 after={n:digest_object(v) for n,v in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=o.name):raise ValueError('Slot repair changed other object')
 va=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':'Codex','actions':[{'target':o.name,'operation':'remove_measured_unused_empty_boolean_material_slot','affected_faces':len(affected),'removed_empty_slots':1,'geometry_uv_unchanged':True}],'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'contact_scope':'Geometry unchanged; previous limited geometric evidence still applies, not global contact proof','source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-start,'scope':'Author material-slot repair of retained Jarvis executed candidate. No plan replay or geometry regeneration.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
