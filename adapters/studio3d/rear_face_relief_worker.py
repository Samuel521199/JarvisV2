# SPDX-License-Identifier: GPL-2.0-or-later
"""Change one evaluated rear face; retain the rest of the bound art asset."""
import bpy,bmesh,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.rear_face_relief import patch
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene
def run(folder,req,c,source):
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['target']]
 if before[c['target']]!=c['source_digest']:raise ValueError('Source changed')
 if ob.type!='MESH' or len(ob.data.vertices)!=8 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original static block required')
 if len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL' or abs(ob.modifiers[0].width-.025)>1e-6 or ob.modifiers[0].segments!=5:raise ValueError('Original bevel stack required')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Supported world-coordinate coating required')
 deps=bpy.context.evaluated_depsgraph_get();base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);v0=[list(v.co) for v in base.vertices];world=[list(ob.matrix_world@v.co) for v in base.vertices];f0=[list(p.vertices) for p in base.polygons]
 source_tree=world_tree(ob,deps);contact_samples=[]
 for name in ('axle-saddle','cradle-cheeks'):
  neighbor=objects[name];ev=neighbor.evaluated_get(deps);nm=ev.to_mesh()
  for vertex in nm.vertices:
   p=neighbor.matrix_world@vertex.co;distance=source_tree.find_nearest(p)[3]
   if distance<=.005:contact_samples.append({'object':name,'index':vertex.index,'point':list(p),'before_distance':distance})
  ev.to_mesh_clear()
 if len(contact_samples)<8:raise ValueError('Insufficient adjacent near-surface evidence')
 vs,fs,action=patch(world,f0,c['depth']);camera=bpy.context.scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);bpy.context.scene.cycles.seed=4
 vb=render_scene(folder,c['inspection'],objects,'before');mesh=bpy.data.meshes.new('rear-blind-relief');inv=ob.matrix_world.inverted();mesh.from_pydata([list(inv@Vector(p)) for p in vs],[],fs);mesh.materials.append(ob.data.materials[0]);mesh.update()
 # New faces receive explicit per-face planar UV islands; retained faces keep the old UV loops exactly.
 original=[p for i,p in enumerate(base.polygons) if i!=action['removed_face_index']]
 for oldlayer in base.uv_layers:
  layer=mesh.uv_layers.new(name=oldlayer.name)
  for new,old in zip(mesh.polygons,original):
   for ni,oi in zip(new.loop_indices,old.loop_indices):layer.data[ni].uv=oldlayer.data[oi].uv
  for face in list(mesh.polygons)[len(original):]:
   axis=max(range(3),key=lambda j:abs(face.normal[j]));axes=[j for j in range(3) if j!=axis]
   for li in face.loop_indices:
    p=vs[mesh.loops[li].vertex_index];layer.data[li].uv=(p[axes[0]]*1.2+.5,p[axes[1]]*1.2+.1)
  mesh.calc_loop_triangles()
  for tri in mesh.loop_triangles:
   if tri.polygon_index<len(original):continue
   a,b,d=[layer.data[i].uv for i in tri.loops];area=abs((b.x-a.x)*(d.y-a.y)-(b.y-a.y)*(d.x-a.x))*.5
   if area<1e-12:raise ValueError('Degenerate new UV triangle')
 for new,old in zip(mesh.polygons,original):new.use_smooth=old.use_smooth
 old=ob.data;ob.data=mesh;ob.modifiers.clear();bpy.context.view_layer.update()
 if any((mesh.vertices[i].co-Vector(p)).length>1e-7 for i,p in enumerate(v0)):raise ValueError('Existing evaluated vertex changed')
 bm=bmesh.new();bm.from_mesh(mesh)
 if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=0:raise ValueError('Closed positive mesh required')
 bm.free();tree=world_tree(ob,bpy.context.evaluated_depsgraph_get());rays=[]
 for row in contact_samples:
  row['after_distance']=tree.find_nearest(Vector(row['point']))[3]
  if row['after_distance']-row['before_distance']>1e-6:raise ValueError('Existing adjacent near-surface sample separated')
 for y in (-.10,0,.10):
  for z in (.65,.69,.73):
   p,n,_,_=tree.ray_cast(Vector((-.3,y,z)),Vector((1,0,0)),.6)
   if p is None or abs(p.x-(-.215+c['depth']))>2e-6 or n.x>-.95:raise ValueError('Blind floor missing')
   rays.append(list(p))
 after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=c['target']):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.data.meshes.remove(old);bpy.data.meshes.remove(base);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':[action],'views':{'before':vb,'after':va},'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'closed_mesh':True,'blind_floor_samples':rays,'contacts_checked':True,'contact_samples':contact_samples,'contact_scope':'Only original neighbor vertices within .005 of the evaluated pedestal; no increase beyond1e-6. Other neighbors may have zero samples. Not continuous contact, all assembly clearance or animation.','source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-start,'scope':'Author exterior hypothesis: one rear quad replaced by blind relief. Evaluated old vertices and all other faces retained; old editable 8-vertex topology/modifier baked. No functional interior, historical, complete collision or animation claim.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
