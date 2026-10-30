# SPDX-License-Identifier: GPL-2.0-or-later
"""Repair only measured bevel microfaces in a frozen cosmetic art surface."""
import bpy,bmesh,json,hashlib,time
from mathutils import Vector
from mathutils.kdtree import KDTree
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene
from adapters.studio3d.high_finish_reuse import tree_signature
from modules.skills.studio3d.high_finish import uv_independent_shader
from modules.skills.studio3d.evaluated_shading import front_faces
from modules.skills.studio3d.microface_cleanup import coplanar
from modules.skills.studio3d.attachment_seat import VERSION

def face_signature(p,tag,uvs):
 rows=[(l.vert[tag],tuple(l.vert.co),tuple(tuple(l[layer].uv) for layer in uvs)) for l in p.loops];start=min(range(len(rows)),key=lambda i:rows[i][0]);return (tuple(rows[start:]+rows[:start]),p.smooth,p.material_index)
def max_nearest(a,b):
 tree=KDTree(len(b))
 for i,p in enumerate(b):tree.insert(Vector(p),i)
 tree.balance();return max(tree.find(Vector(p))[2] for p in a)
def run(folder,req,c,source):
 start=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256'] or req['source_sha256']!=c['source_sha256']:raise ValueError('Frozen cleanup source changed')
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects[n] for n in req['visible_names']}
 if len(objects)!=79:raise ValueError('Original semantic inventory required')
 for n,sha in c['dependencies'].items():
  if dependency(objects[n])[0]!=sha:raise ValueError('Cleanup target or neighbor dependency changed')
 ob=objects['muzzle-brake'];mesh=ob.data;deps=bpy.context.evaluated_depsgraph_get()
 if ob.type!='MESH' or ob.modifiers or mesh.users!=1 or ob.animation_data or mesh.shape_keys or mesh.has_custom_normals:raise ValueError('Single frozen unanimated surface required')
 if inventory(ob,deps)!={'vertices':5312,'faces':4900,'boundary_edges':0,'wire_edges':0,'overfull_edges':0,'small_faces':94}:raise ValueError('Diagnosed original94microfaces required')
 materials={m.name:tree_signature(m.node_tree) for m in mesh.materials if m and m.use_nodes}
 if len(materials)!=len(mesh.materials) or not all(uv_independent_shader(t) for t in materials.values()):raise ValueError('Only verified UV-independent art coatings supported')
 before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name};source_points=[tuple(v.co) for v in mesh.vertices];original_bounds=[[min(p[i] for p in source_points) for i in range(3)],[max(p[i] for p in source_points) for i in range(3)]]
 bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table();tag=bm.verts.layers.int.new('cleanup_original_vertex');ftag=bm.faces.layers.int.new('cleanup_original_face')
 for v in bm.verts:v[tag]=v.index
 for p in bm.faces:p[ftag]=p.index
 small=[p for p in bm.faces if p.calc_area()<1e-10];affected={v for p in small for v in p.verts}
 if sorted(p.index for p in small)!=c['small_faces'] or sorted(v.index for v in affected)!=c['affected_vertices']:raise ValueError('Actual microface component binding changed')
 patch={p.index for v in affected for p in v.link_faces};uvs=list(bm.loops.layers.uv.values());kept={p.index:face_signature(p,tag,uvs) for p in bm.faces if p.index not in patch};fixed_vertices={v.index:tuple(v.co) for v in bm.verts if v not in affected};fixed_edges={(min(e.verts[0][tag],e.verts[1][tag]),max(e.verts[0][tag],e.verts[1][tag])):(e.smooth,e.seam) for e in bm.edges if all(v not in affected for v in e.verts)}
 if c['strategy'] in ('merge_only','merge_then_dissolve'):bmesh.ops.remove_doubles(bm,verts=sorted(affected,key=lambda v:v[tag]),dist=1e-5);bm.normal_update()
 dissolves=[]
 if c['strategy'] in ('dissolve_only','merge_then_dissolve'):
  for _ in range(128):
   options=[]
   for p in bm.faces:
    if p.calc_area()>=1e-10:continue
    for e in p.edges:
     if len(e.link_faces)!=2:continue
     q=next(x for x in e.link_faces if x!=p)
     if p[ftag] not in patch or q[ftag] not in patch or p.smooth!=q.smooth or p.material_index!=q.material_index or q.calc_area()<1e-10:continue
     points=[tuple(v.co) for v in list(p.verts)+list(q.verts)]
     if coplanar(points,tuple(q.normal),tuple(q.verts[0].co)):options.append((max(abs(q.normal.dot(v.co-q.verts[0].co)) for v in p.verts),-q.calc_area(),e,p,q))
   if not options:break
   distance,_,edge,p,q=min(options,key=lambda x:x[:2]);dissolves.append({'source_faces':[p[ftag],q[ftag]],'small_area':p.calc_area(),'max_plane_distance':distance});bmesh.ops.dissolve_edges(bm,edges=[edge],use_verts=False,use_face_split=False);bm.normal_update()
 quality={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'wire_edges':sum(e.is_wire for e in bm.edges),'overfull_edges':sum(len(e.link_faces)>2 for e in bm.edges),'small_faces':sum(p.calc_area()<1e-10 for p in bm.faces)}
 if any(quality[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Cleanup must leave zero small or open/nonmanifold faces')
 after_faces={p[ftag]:face_signature(p,tag,uvs) for p in bm.faces if p[ftag] in kept};after_fixed={v[tag]:tuple(v.co) for v in bm.verts if v[tag] in fixed_vertices};after_edges={(min(e.verts[0][tag],e.verts[1][tag]),max(e.verts[0][tag],e.verts[1][tag])):(e.smooth,e.seam) for e in bm.edges if (min(e.verts[0][tag],e.verts[1][tag]),max(e.verts[0][tag],e.verts[1][tag])) in fixed_edges}
 if after_faces!=kept or after_fixed!=fixed_vertices or after_edges!=fixed_edges:raise ValueError('Geometry/UV/shading outside original local patch changed')
 points=[tuple(v.co) for v in bm.verts];distance=[max_nearest(source_points,points),max_nearest(points,source_points)]
 if max(distance)>1e-5:raise ValueError('Cleanup exceeds existing local displacement cap')
 bounds=[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]
 if bounds!=original_bounds:raise ValueError('Original exterior bounds changed')
 # Only remove temporary audit attributes. Preserve actual surviving face UVs;
 # modified patch topology/UV are explicitly not claimed equal to the source.
 bm.verts.layers.int.remove(tag);bm.faces.layers.int.remove(ftag);new=bpy.data.meshes.new('muzzle-local-microface-cleanup');bm.to_mesh(new);bm.free()
 for mat in mesh.materials:new.materials.append(mat)
 new.update();new.calc_loop_triangles();triangle_issues=[]
 for tri in new.loop_triangles:
  a,b,c0=[new.vertices[i].co for i in tri.vertices];area=(b-a).cross(c0-a).length*.5
  if area<1e-10:triangle_issues.append({'polygon':tri.polygon_index,'vertices':list(tri.vertices),'area':area})
 if triangle_issues:
  (folder/'rejected-triangulation.json').write_text(json.dumps({'known_before_source_small_triangles':264,'remaining_small_triangles':len(triangle_issues),'remaining_zero_triangles':sum(x['area']==0 for x in triangle_issues),'issues':triangle_issues,'polygon_inventory':quality,'saved_model':False,'scope':'Zero polygon microfaces is insufficient; actual render/export tessellation still fails the same1e-10area gate.'},indent=2)+'\n')
  raise ValueError('Actual triangulation retains small or zero-area triangles; no candidate output')
 world=[list(ob.matrix_world@v.co) for v in new.vertices];front=front_faces(world,[[*p.vertices] for p in new.polygons])
 if len(front)!=96 or any(new.polygons[i].use_smooth for i in front):raise ValueError('Retained96flat end faces changed')
 scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before');ob.data=new;bpy.context.view_layer.update()
 if inventory(ob,deps)!=quality or any(dependency(objects[n])[0]!=sha for n,sha in protected.items()):raise ValueError('Saved target inventory or non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after')
 if not all(all(a[k]==b[k] for k in ('direction','camera_position','ortho_scale','lighting')) for a,b in zip(vb['views'],va['views'])):raise ValueError('Fixed comparison changed')
 camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam
 if hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Source changed')
 report={'version':VERSION,'author':c['author'],'strategy':c['strategy'],'actions':[{'object':ob.name,'original_small_faces':94,'original_patch_faces':len(patch),'preserved_faces_and_UV':len(kept),'preserved_vertex_coordinates':len(fixed_vertices),'preserved_edge_flags':len(fixed_edges),'dissolves':dissolves,'quality':quality,'bidirectional_nearest_vertex_distance':distance,'bounds_equal':True,'flat_front_faces':len(front)}],'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'protected_objects':78,'unchanged_non_targets':True,'source_unchanged':True,'contacts_checked':True,'contact_scope':'Tiny local visual patch only, unchanged bounds and finite vertex distance. Not complete contact/collision/animation proof.','views':{'before':vb,'after':va},'elapsed_seconds':time.monotonic()-start,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Cosmetic source-bevel microface cleanup, not decimation, LOD or functional design. Target topology and local UV change; protected outside-patch faces/UV/edge flags retained exactly. No arbitrary empty-face deletion or global merge.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
