# SPDX-License-Identifier: GPL-2.0-or-later
"""Append a supported exterior bead, preserving the evaluated perforated plate."""
import bpy,bmesh,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.exterior_border import geometry
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def dependencies(ob,deps):
 mods=[]
 for m in ob.modifiers:
  row={'name':m.name,'type':m.type,'show_render':m.show_render,'show_viewport':m.show_viewport}
  for k in ('width','segments','limit_method','operation','solver','thickness','offset'):
   if hasattr(m,k):row[k]=getattr(m,k)
  if m.type=='BOOLEAN':
   p=m.object
   if p is None:raise ValueError('Missing cutter')
   row['operand']={'name':p.name,'digest':digest_object(p),'matrix':[list(r) for r in p.matrix_world],'vertices':len(p.data.vertices),'faces':len(p.data.polygons),'modifiers':[x.type for x in p.modifiers]}
  mods.append(row)
 ev=ob.evaluated_get(deps);mesh=ev.to_mesh();raw={'vertices':[list(ob.matrix_world@v.co) for v in mesh.vertices],'faces':[list(p.vertices) for p in mesh.polygons]};ev.to_mesh_clear()
 data={'modifiers':mods,'evaluated_geometry_sha256':hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()}
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),data

def run(folder,req,c,source):
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['target']];deps=bpy.context.evaluated_depsgraph_get()
 if before[c['target']]!=c['source_digest']:raise ValueError('Source changed')
 if ob.type!='MESH' or len(ob.data.vertices)!=30 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original static plate required')
 if [m.type for m in ob.modifiers]!=['BOOLEAN']*3+['BEVEL']:raise ValueError('Original cutter/bevel stack required')
 binding,detail=dependencies(ob,deps)
 if binding!=c['dependency_digest']:raise ValueError('Boolean/evaluated dependency changed')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('World-coordinate coating required')
 source_tree=world_tree(ob,deps);base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);v0=[list(v.co) for v in base.vertices];f0=[list(p.vertices) for p in base.polygons]
 vs,fs,uv,path=geometry(c['radius']);inv=ob.matrix_world.inverted();n=len(v0);oldcam=(bpy.context.scene.camera.matrix_world.copy(),bpy.context.scene.camera.data.type,bpy.context.scene.camera.data.ortho_scale)
 bpy.context.scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before')
 # Orient only the appended closed component; original evaluated polygons stay identical.
 bead=bpy.data.meshes.new('bead-check');bead.from_pydata(vs,[],fs);bead.update();bm=bmesh.new();bm.from_mesh(bead);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(bead)
 if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=0:raise ValueError('Border must be closed positive component')
 bm.free();oriented=[list(p.vertices) for p in bead.polygons]
 # UV correspondence follows vertex identity if orientation reversed.
 oriented_uv=[[uv[i][fs[i].index(v)] for v in face] for i,face in enumerate(oriented)]
 mesh=bpy.data.meshes.new('plate-with-exterior-border');mesh.from_pydata(v0+[list(inv@Vector(p)) for p in vs],[],f0+[[n+i for i in face] for face in oriented]);mesh.materials.append(ob.data.materials[0]);mesh.update()
 for oldlayer in base.uv_layers:
  layer=mesh.uv_layers.new(name=oldlayer.name)
  for new,old in zip(mesh.polygons,base.polygons):
   for ni,oi in zip(new.loop_indices,old.loop_indices):layer.data[ni].uv=oldlayer.data[oi].uv
  for face,coords in zip(list(mesh.polygons)[len(f0):],oriented_uv):
   for li,p in zip(face.loop_indices,coords):layer.data[li].uv=p
  mesh.calc_loop_triangles()
  for tri in mesh.loop_triangles:
   if tri.polygon_index<len(f0):continue
   a,b,d=[layer.data[i].uv for i in tri.loops]
   if abs((b.x-a.x)*(d.y-a.y)-(b.y-a.y)*(d.x-a.x))<1e-12:raise ValueError('Degenerate border UV')
 for i,p in enumerate(mesh.polygons):p.use_smooth=base.polygons[i].use_smooth if i<len(f0) else i-len(f0)<(len(path)-1)*16
 if any((mesh.vertices[i].co-Vector(p)).length>1e-7 for i,p in enumerate(v0)) or [list(p.vertices) for p in mesh.polygons[:len(f0)]]!=f0:raise ValueError('Original evaluated surface changed')
 old=ob.data;ob.data=mesh;ob.modifiers.clear();bpy.context.view_layer.update();newtree=world_tree(ob,bpy.context.evaluated_depsgraph_get());contacts=[]
 for i in (1,5,13,21,29,37,45,53,61,len(path)-2):
  x,z=path[i];origin=Vector((x,.3,z));direction=Vector((0,-1,0));front=source_tree.ray_cast(origin,direction,.3)[0]
  if front is None:raise ValueError('Border unsupported')
  back=source_tree.ray_cast(front+direction*.00001,direction,.15)[0];p=Vector((x,.164,z))
  if back is None or not back.y<p.y<front.y or (p-Vector((x,.1665,z))).length>=c['radius']:raise ValueError('No sampled solid overlap')
  contacts.append({'index':i,'witness':list(p),'source_front_y':front.y,'source_back_y':back.y})
 holes=[]
 for x in (-.67,-.765,-.86):
  for dx,dz in ((0,0),(.012,0),(-.012,0),(0,.012),(0,-.012)):
   p=Vector((x+dx,.3,1.11+dz));direction=Vector((0,-1,0))
   if source_tree.ray_cast(p,direction,.3)[0] is not None or newtree.ray_cast(p,direction,.3)[0] is not None:raise ValueError('Declared opening ray blocked')
   holes.append(list(p))
 after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=c['target']):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');camera=bpy.context.scene.camera;camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam
 bpy.data.meshes.remove(old);bpy.data.meshes.remove(base);bpy.data.meshes.remove(bead);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':[{'kind':'visible_perimeter_bead','radius':c['radius'],'retained_evaluated_vertices':len(v0),'retained_evaluated_faces':len(f0),'added_vertices':len(vs),'added_faces':len(fs)}],'views':{'before':vb,'after':va},'source_dependencies':detail,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'overlap_witnesses':contacts,'unblocked_opening_rays':holes,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'elapsed_seconds':time.monotonic()-start,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Visible art border, separate overlapping closed component in existing semantic object. Original evaluated mesh/UV preserved; original editable topology and Boolean/bevel stack evaluated. Ten witnesses and15opening rays are not continuous contact, full collision, animation, historic or functional proof.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
