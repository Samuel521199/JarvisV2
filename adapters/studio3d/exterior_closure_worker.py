# SPDX-License-Identifier: GPL-2.0-or-later
"""Add only bounded external art surfaces to a receipt-bound static group."""
import hashlib,json,time
import bpy,bmesh
from mathutils import Vector
from modules.skills.studio3d.exterior_closure import build,check_source,notch_from_surface
from modules.skills.studio3d.attachment_seat import components,VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def inside(tree,p):
 p=Vector(p);loc,normal,_,_=tree.find_nearest(p)
 if loc is None or (p-loc).dot(normal)>-1e-5:raise ValueError('Declared exterior overlap anchor is not inside support')
 return {'point':list(p),'signed_nearest_distance':(p-loc).dot(normal)}

def shaped(part,deps):
 mesh=bpy.data.meshes.new('bounded-closure-build');mesh.from_pydata(part['vertices'],[],part['faces']);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 for p in mesh.polygons:p.use_smooth=part['smooth_sides'] and len(p.vertices)==4
 ob=bpy.data.objects.new('bounded-closure-build',mesh);bpy.context.collection.objects.link(ob)
 if part['bevel']:
  mod=ob.modifiers.new('local exterior edge highlights','BEVEL');mod.width=part['bevel'];mod.segments=4;mod.limit_method='ANGLE'
 bpy.context.view_layer.update();result=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps)
 points=[list(v.co) for v in result.vertices];faces=[list(p.vertices) for p in result.polygons];smooth=[p.use_smooth for p in result.polygons]
 bm=bmesh.new();bm.from_mesh(result);bad=sum(not e.is_manifold for e in bm.edges);bm.free()
 bpy.data.meshes.remove(result);bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
 if bad or len(points)>10000:raise ValueError('Generated external surface is open or over budget')
 return points,faces,smooth

def run(folder,req,c,source):
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['target']]
 if before[c['target']]!=c['source_digest'] or any(before[n]!=h for n,h in c['support_digests'].items()):raise ValueError('Bound exterior source changed')
 if ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or ob.modifiers or len(ob.data.uv_layers)>4 or len(ob.data.vertices)!=520:raise ValueError('Unsupported existing rail mesh')
 if len(components(len(ob.data.vertices),[list(p.vertices) for p in ob.data.polygons]))!=4:raise ValueError('Original four components required')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Unsupported material coordinates')
 bounds={}
 for n in c['support_digests']:
  ps=[objects[n].matrix_world@v.co for v in objects[n].data.vertices];bounds[n]=[[min(p[i] for p in ps) for i in range(3)],[max(p[i] for p in ps) for i in range(3)]]
 check_source(bounds);deps=bpy.context.evaluated_depsgraph_get();trees={n:world_tree(objects[n],deps) for n in (c['target'],'cradle-trough','barrel')}
 contacts=[];local_radii=[]
 for x in (.665-c['saddle_span']/2,.665,.665+c['saddle_span']/2):
  loc,normal,_,_=trees['barrel'].ray_cast(Vector((x,0,1.4)),Vector((0,0,-1)),.5)
  if loc is None or normal.z<.95:raise ValueError('Unsupported measured barrel exterior')
  local_radii.append(loc.z-1.15)
 notch_radius=notch_from_surface(local_radii)
 for p in ([.79,-.08,.94],[.79,.08,1.0],[.64,-.08,1.023],[.69,.08,1.023]):contacts.append({'support':'cradle-trough',**inside(trees['cradle-trough'],p)})
 for p in ([.768,-.15,1.02],[.768,.15,1.02],[.665,-.15,1.04],[.665,.15,1.04]):contacts.append({'support':c['target'],**inside(trees[c['target']],p)})
 original_uv=[{'name':l.name,'active_render':l.active_render,'uv':[list(d.uv) for d in l.data]} for l in ob.data.uv_layers];active_uv=ob.data.uv_layers.active_index
 original_v=[list(v.co) for v in ob.data.vertices];original_f=[list(p.vertices) for p in ob.data.polygons];original_s=[p.use_smooth for p in ob.data.polygons];original_m=[p.material_index for p in ob.data.polygons];verts=list(original_v);faces=list(original_f);smooth=list(original_s);indices=list(original_m);parts=[];inverse=ob.matrix_world.inverted()
 for part in build(c,notch_radius):
  ps,fs,sm=shaped(part,deps);offset=len(verts);verts.extend([list(inverse@Vector(p)) for p in ps]);faces.extend([[i+offset for i in f] for f in fs]);smooth.extend(sm);indices.extend([0]*len(fs));parts.append({'role':part['role'],'first_vertex':offset,'vertex_count':len(ps),'face_count':len(fs)})
 if len(verts)>12000:raise ValueError('External detail vertex budget')
 scene=bpy.context.scene;camera=scene.camera;old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;views_before=render_scene(folder,c['inspection'],objects,'before')
 mat=ob.data.materials[0];mesh=bpy.data.meshes.new(ob.data.name+'-exterior-closure');mesh.from_pydata(verts,[],faces);mesh.materials.append(mat);mesh.update();oldmesh=ob.data;ob.data=mesh
 for p,s,i in zip(mesh.polygons,smooth,indices):p.use_smooth=s;p.material_index=i
 for layer in original_uv:
  uv=mesh.uv_layers.new(name=layer['name']);uv.active_render=layer['active_render']
  for d,v in zip(uv.data,layer['uv']):d.uv=v
  if [list(d.uv) for d in uv.data[:len(layer['uv'])]]!=layer['uv']:raise ValueError('Original UV coordinates changed')
 if original_uv:mesh.uv_layers.active_index=active_uv
 bpy.context.view_layer.update()
 if [list(v.co) for v in mesh.vertices[:len(original_v)]]!=original_v or [list(p.vertices) for p in mesh.polygons[:len(original_f)]]!=original_f:raise ValueError('Original rails changed')
 final_tree=world_tree(ob,deps)
 # Every sampled original support anchor must also be enclosed by the new body.
 # Exclude the original rail vertices so this cannot pass using the rail itself.
 from mathutils.bvhtree import BVHTree
 added_tree=BVHTree.FromPolygons([ob.matrix_world@v.co for v in mesh.vertices],[list(p.vertices) for p in list(mesh.polygons)[len(original_f):]],all_triangles=False)
 for row in contacts:row['new_shell']=inside(added_tree,row['point'])
 clearance=[]
 for v in list(mesh.vertices)[len(original_v):]:
  p=ob.matrix_world@v.co
  if p.z<1.06:continue
  loc,normal,_,distance=trees['barrel'].find_nearest(p)
  if loc is None or (p-loc).dot(normal)<.002:raise ValueError('Added exterior silhouette intersects declared barrel envelope')
  clearance.append(distance)
 after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=c['target']):raise ValueError('Non-target changed')
 views_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=old;bpy.data.meshes.remove(oldmesh);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':parts,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'original_target_vertices_faces_unchanged':True,'original_vertex_count':len(original_v),'original_face_count':len(original_f),'original_uv_loops_preserved':sum(len(l['uv']) for l in original_uv),'original_uv_equal':True,'contacts_checked':True,'contact_samples':contacts,'local_radius_samples':local_radii,'notch_radius':notch_radius,'minimum_sampled_barrel_clearance':min(clearance),'barrel_clearance_sample_count':len(clearance),'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':views_before,'after':views_after},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Source-bound external game-art surfaces. Separate closed components deliberately overlap at sampled mounting regions; not Boolean welded, continuous collision tested, historical dimensions or functional mechanism.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
