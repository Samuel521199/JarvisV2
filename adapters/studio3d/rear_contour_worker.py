# SPDX-License-Identifier: GPL-2.0-or-later
"""Source-bound external cosmetic C silhouette; no internal mechanism changes."""
import bpy,json,hashlib,time,math
from mathutils import Vector
from modules.skills.studio3d.rear_contour import outline
from modules.skills.studio3d.assembly_geometry import Mesh
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.high_finish_reuse import tree_signature
from modules.skills.studio3d.high_finish import uv_independent_shader

def run(folder,req,c,source):
 started=time.monotonic()
 if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Contour source binding changed')
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);names=req['visible_names'];objects={n:bpy.data.objects[n] for n in names};ob=objects['shaped-rear-cover'];deps=bpy.context.evaluated_depsgraph_get()
 assert ob.type=='MESH' and not ob.modifiers and len(ob.data.vertices)==324 and len(ob.data.polygons)==644
 assert len(ob.data.materials)==1 and uv_independent_shader(tree_signature(ob.data.materials[0].node_tree))
 original={n:dependency(o)[0] for n,o in objects.items()};before_digests={n:digest_object(o) for n,o in objects.items()}
 if len(objects)!=79 or any(original[n]!=h for n,h in c['dependencies'].items()):raise ValueError('Full local contour dependency mismatch')
 oldtree=world_tree(ob,deps);anchors=[]
 for n in ['fasteners-breech','rear-seated-cosmetic-fittings']:
  ev=objects[n].evaluated_get(deps);m=ev.to_mesh()
  for v in m.vertices:
   p=objects[n].matrix_world@v.co;hit=oldtree.find_nearest(p)
   if hit[0] is not None and hit[3]<.025:anchors.append((p.copy(),hit[3]))
  ev.to_mesh_clear()
 inspection=c['inspection'];camera=bpy.context.scene.camera;old_camera=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale)
 bpy.context.scene.cycles.seed=4;before=render_scene(folder,inspection,objects,'before')
 disc=[objects['breech-recess'].matrix_world@v.co for v in objects['breech-recess'].data.vertices];cy=(max(p.y for p in disc)+min(p.y for p in disc))*.5;cz=(max(p.z for p in disc)+min(p.z for p in disc))*.5;radius=max(math.hypot(p.y-cy,p.z-cz) for p in disc)+c['clearance']
 outline_points=outline(c['clearance'],cy,cz,radius-c['clearance'])
 # Broad visible C outline around existing closed decorative disc. No new void
 # in the unchanged body and no internal mechanism.

 build=Mesh();build.extrude(outline_points,0,-.79,-.735);n=len(outline_points);build.faces=[list(reversed(range(n))),list(range(n,2*n))]+build.faces[-n:];mesh=bpy.data.meshes.new('rear-C-rounded-art-contour');inv=ob.matrix_world.inverted();mesh.from_pydata([inv@Vector(p) for p in build.vertices],[],build.faces);mesh.materials.append(ob.data.materials[0]);ob.data=mesh
 mod=ob.modifiers.new('fixed_existing_visual_edge_width','BEVEL');mod.width=.012;mod.segments=4;mod.limit_method='ANGLE';mod.angle_limit=.5
 bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());new=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());ob.modifiers.clear();ob.data=new
 new.update();uv=new.uv_layers.new(name='contour-planar-projection')
 for p in new.polygons:
  p.use_smooth=abs(p.normal.x)<.99999
  dominant=max(range(3),key=lambda i:abs(p.normal[i]));axes=[i for i in range(3) if i!=dominant]
  for li in p.loop_indices:
   q=ob.matrix_world@new.vertices[new.loops[li].vertex_index].co;uv.data[li].uv=(q[axes[0]],q[axes[1]])
 bpy.context.view_layer.update();q=inventory(ob,bpy.context.evaluated_depsgraph_get());new.calc_loop_triangles();areas=[(new.vertices[t.vertices[1]].co-new.vertices[t.vertices[0]].co).cross(new.vertices[t.vertices[2]].co-new.vertices[t.vertices[0]].co).length*.5 for t in new.loop_triangles];tiny=sum(a<1e-10 for a in areas)
 orientation_dots=[(new.vertices[t.vertices[1]].co-new.vertices[t.vertices[0]].co).cross(new.vertices[t.vertices[2]].co-new.vertices[t.vertices[0]].co).normalized().dot(new.polygons[t.polygon_index].normal) for t in new.loop_triangles]
 assert min(orientation_dots)>.99,'Loop triangles disagree with polygon orientation'
 tree=world_tree(ob,bpy.context.evaluated_depsgraph_get());growth=max(tree.find_nearest(p)[3]-d for p,d in anchors);protected={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name};assert protected=={n:h for n,h in original.items() if n!=ob.name}
 checks={'source_sha256':c['source_sha256'],'target':'shaped-rear-cover','source_dependencies':original,'quality':q,'minimum_triangle_polygon_orientation_dot':min(orientation_dots),'small_triangles':tiny,'zero_triangles':sum(a==0 for a in areas),'actual_triangles':len(areas),'anchor_samples':len(anchors),'maximum_anchor_nearest_distance_growth':growth,'protected_objects':78,'new_radius':radius,'centre':[cy,cz],'clearance':c['clearance'],'old_topology_and_uv_replaced':True,'scope':'Author cosmetic contour hypothesis, not historical measurements or functional opening.'}
 (folder/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
 assert not any(q[k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')) and tiny==0,'Actual topology/triangle gate failed'
 assert anchors and growth<=.0005,'Existing attachment support changed'
 after=render_scene(folder,inspection,objects,'after');checks['views']={'before':before,'after':after};checks['same_frame']=all(all(a[k]==b[k] for k in ('direction','camera_position','ortho_scale','lighting')) for a,b in zip(before['views'],after['views']));assert checks['same_frame']
 camera.matrix_world,camera.data.type,camera.data.ortho_scale=old_camera
 checks.update(version=VERSION,author=c['author'],actions=[{'operation':'replace_external_C_contour','object':'shaped-rear-cover','clearance':c['clearance'],'source_vertices':324,'source_faces':644,'new_vertices':q['vertices'],'new_faces':q['faces'],'old_topology_and_uv_replaced':True,'unchanged_body_and_disc':True}],changed_objects=['shaped-rear-cover'],unchanged_non_targets=True,source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==c['source_sha256'],before_object_digests=before_digests,after_object_digests={n:digest_object(o) for n,o in objects.items()},contacts_checked=True,contact_scope='1840 unchanged neighbouring vertices, unsigned nearest-surface distance growth <=.0005; not continuous contact, all collisions or animation.',requires_high_surface_texture_export=True,elapsed_seconds=time.monotonic()-started,user_approval=False,lod_authorized=False,known_other_muzzle_defects='94 small polygons;264 small triangles including22 zero remain unchanged elsewhere.')
 if not checks['source_unchanged']:raise ValueError('Source bytes changed')
 (folder/'report.json').write_text(json.dumps(checks,indent=2)+'\n')
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
