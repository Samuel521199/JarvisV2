# SPDX-License-Identifier: GPL-2.0-or-later
"""Read actual cover meshes, replace only their continuous exterior profiles."""
import bpy,bmesh,json,hashlib,time,math
from mathutils import Vector
from modules.skills.studio3d.collar_profile import TARGETS,fit,build,profile,face_uv
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.exterior_closure_worker import inside
from adapters.studio3d.demonstration_worker import digest_object,topology
from adapters.studio3d.inspection_worker import render_scene

def run(folder,req,c,source,version):
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Source inventory changed')
 before={n:digest_object(o) for n,o in objects.items()};deps=bpy.context.evaluated_depsgraph_get();axle=world_tree(objects['axle'],deps);plans=[]
 for name,side in zip(TARGETS,(1,-1)):
  ob=objects[name]
  if before[name]!=c['source_digests'][name] or ob.type!='MESH' or ob.data.users!=1 or ob.modifiers or ob.animation_data or ob.data.shape_keys or len(ob.data.materials)!=1:raise ValueError('Unsupported or changed collar source')
  mat=ob.data.materials[0]
  if not mat.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in mat.node_tree.nodes):raise ValueError('Supported world-coordinate paint required')
  ps=[list(ob.matrix_world@v.co) for v in ob.data.vertices];fs=[list(p.vertices) for p in ob.data.polygons];fitted=fit(ps,fs,side);tree=world_tree(ob,deps);contacts=[]
  for y in (.65,.70,.7475,.80,.845):
   for a in (0,math.pi/2,math.pi,math.pi*1.5):
    p=[.082*math.cos(a),side*y,.5+.082*math.sin(a)];contacts.append({'point':p,'source_cover':inside(tree,p),'original_axle':inside(axle,p)})
  vs,faces=build(c,side)
  nearest=max(tree.find_nearest(Vector(p))[3] for p in vs)
  if nearest>.025:raise ValueError('Replacement leaves local surface envelope')
  plans.append({'target':name,'fit':fitted,'contacts':contacts,'old_tree':tree,'vertices':vs,'faces':faces,'maximum_vertex_to_original_distance':nearest,'source_uv_layers':len(ob.data.uv_layers)})
 scene=bpy.context.scene;cam=scene.camera;old=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);scene.cycles.seed=4
 vb=render_scene(folder,c['inspection'],objects,'before');actions=[]
 for plan in plans:
  ob=objects[plan['target']];inverse=ob.matrix_world.inverted();mesh=bpy.data.meshes.new(ob.name+'-continuous-profile');mesh.from_pydata([inverse@Vector(p) for p in plan['vertices']],[],plan['faces']);mesh.materials.append(ob.data.materials[0]);mesh.update()
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
  if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
  if any(not e.is_manifold for e in bm.edges) or any(f.calc_area()<1e-10 for f in bm.faces):raise ValueError('Rebuilt cover is not a closed nondegenerate surface')
  bm.to_mesh(mesh);bm.free();mesh.update()
  for p in mesh.polygons:p.use_smooth=abs(p.normal.y)<.9999
  # New cylindrical UV belongs only to the new target topology. Existing world-
  # coordinate paint does not read it. Do not claim old target UV was retained.
  uv=mesh.uv_layers.new(name='collar-profile-uv')
  for face in mesh.polygons:
   ps=[ob.matrix_world@mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
   coords=face_uv(ps)
   for index,value in zip(face.loop_indices,coords):uv.data[index].uv=value
  areas=[]
  for face in mesh.polygons:
   coords=[list(uv.data[i].uv) for i in face.loop_indices]
   areas.append(abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(coords,coords[1:]+coords[:1])))/2)
  if min(areas)<1e-12:raise ValueError('New target UV face collapsed')
  oldmesh=ob.data;ob.data=mesh;bpy.data.meshes.remove(oldmesh);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();tree=world_tree(ob,deps)
  for row in plan['contacts']:row['after_cover']=inside(tree,row['point'])
  actual=[ob.matrix_world@v.co for v in mesh.vertices]
  if max((a-Vector(b)).length for a,b in zip(actual,plan['vertices']))>2e-6:raise ValueError('Actual mesh deviates from plan')
  if any(math.hypot(p.x,p.z-.5)>.120002 or not .639998<=abs(p.y)<=.855002 for p in actual):raise ValueError('Actual cover exceeds axial/radial envelope')
  t=topology(ob)
  if t['boundary_edges'] or t['overfull_edges']:raise ValueError('Actual target topology invalid')
  actions.append({k:v for k,v in plan.items() if k not in ('old_tree','vertices','faces')}|{'profile':profile(c),'actual_vertices':len(actual),'actual_faces':len(mesh.polygons),'after_topology':t,'target_uv_replaced':True,'target_uv_minimum_face_area':min(areas),'target_uv_zero_area_faces':0,'world_coordinate_shader_preserved':True,'single_closed_profile':True})
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n not in TARGETS):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');cam.matrix_world,cam.data.type,cam.data.ortho_scale=old;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':version,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':vb,'after':va},'elapsed_seconds':time.monotonic()-start,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Two closed decorative cover profiles, original axis/end positions/maximum radius, forty finite overlap probes with unchanged axle. Not a hollow functional assembly, historic measurements, full collision, animation, exact subset containment or autonomous modeling proof.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
