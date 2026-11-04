# SPDX-License-Identifier: GPL-2.0-or-later
"""One receipt-bound exterior front roll preserving the original rear surface."""
from sdk.blender_api import require_blender
import json,hashlib,time,math; bpy = require_blender().bpy; bmesh = require_blender().bmesh
Vector = require_blender().mathutils.Vector
BVHTree = require_blender().bvhtree.BVHTree
from modules.skills.studio3d.attachment_seat import VERSION,components
from modules.skills.studio3d.control_face_roll import front_stations
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.panel_corner_worker import inventory
from adapters.studio3d.inspection_worker import render_scene
from adapters.studio3d.high_finish_reuse import tree_signature
from adapters.studio3d.demonstration_worker import digest_object
from modules.skills.studio3d.high_finish import uv_independent_shader

def run(folder,req,contract,source):
 f=folder;started=time.monotonic()
 if req['source_sha256']!=contract['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=contract['source_sha256']:raise ValueError('Original exterior source changed')
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects[n] for n in req['visible_names']}
 if len(objects)!=79:raise ValueError('Original semantic inventory required')
 for n,h0 in contract['dependencies'].items():
  if dependency(objects[n])[0]!=h0:raise ValueError('Target or neighbour dependency changed')
 deps=bpy.context.evaluated_depsgraph_get();ob=objects['control-seated-castings'];h,record=dependency(ob);protected={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name};digests_before={n:digest_object(o) for n,o in objects.items()}
 if ob.type!='MESH' or ob.data.users!=1 or ob.data.shape_keys or ob.animation_data or len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL' or abs(ob.modifiers[0].width-.003)>1e-7 or ob.modifiers[0].segments!=4:raise ValueError('Original castings configuration required')
 assert len(ob.data.materials)==1 and uv_independent_shader(tree_signature(ob.data.materials[0].node_tree));mat=ob.data.materials[0];ev=ob.evaluated_get(deps);old=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=deps);pts=[ob.matrix_world@v.co for v in old.vertices];faces=[list(p.vertices) for p in old.polygons]
 def match(points,ids):
  lo=[min(points[i][axis] for i in ids) for axis in range(3)];hi=[max(points[i][axis] for i in ids) for axis in range(3)];return max(abs(a-b) for a,b in zip(lo+hi,[-.58,.265,.745,-.40,.385,.875]))<1e-6
 groups=components(len(pts),faces);target=[g for g in groups if match(pts,g)];assert len(target)==1 and len(target[0])==152 and len(groups)==6;ids=set(target[0]);assert sorted(ids)==contract['component_vertices'],'Original component binding changed';selected_faces=[p.index for p in old.polygons if p.vertices[0] in ids];oldtree=BVHTree.FromPolygons(pts,[faces[i] for i in selected_faces]);anchors=[]
 for n in ['connected-control-housing','control-seated-trim','handwheel-left','fasteners-controls','rear-cover-mounts','sight-mounted']:
  o=objects[n];e=o.evaluated_get(deps);me=e.to_mesh()
  for v in me.vertices:
   p=o.matrix_world@v.co;hit=oldtree.find_nearest(p)
   if hit[0] is not None and hit[3]<.025:anchors.append((n,v.index,p.copy(),hit[3]))
  e.to_mesh_clear()
 base=[ob.matrix_world@v.co for v in ob.data.vertices];bf=[list(p.vertices) for p in ob.data.polygons];bg=[g for g in components(len(base),bf) if match(base,g)];assert len(bg)==1 and len(bg[0])==8;bid=sorted(bg[0]);bmap={v:i for i,v in enumerate(bid)};box_faces=[[bmap[i] for i in p] for p in bf if p[0] in bmap];assert len(box_faces)==6
 inspection=contract['inspection'];camera=bpy.context.scene.camera;camera_old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);bpy.context.scene.cycles.seed=4;before=render_scene(f,inspection,objects,'before')
 width=contract['width'];small=.003;segments=16;lo=[min(base[i][a] for i in bid) for a in range(3)];hi=[max(base[i][a] for i in bid) for a in range(3)];cut=lo[0]+width
 bmesh = require_blender().bmesh
 lower=sorted(ids);lm={v:i for i,v in enumerate(lower)};patch=bpy.data.meshes.new('front_patch_preserving_source_rear');patch.from_pydata([pts[i] for i in lower],[],[[lm[i] for i in faces[k]] for k in selected_faces]);patch.materials.append(mat);patch.update()
 for a,b in zip(selected_faces,patch.polygons):b.use_smooth=old.polygons[a].use_smooth
 bm=bmesh.new();bm.from_mesh(patch);bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-7,plane_co=(cut,0,0),plane_no=(1,0,0),clear_inner=True,clear_outer=False)
 border=[e for e in bm.edges if e.is_boundary];boundary=set(v for e in border for v in e.verts);assert len(boundary)==20 and len(border)==20 and all(abs(v.co.x-cut)<1e-6 for v in boundary)
 cy,cz=(lo[1]+hi[1])*.5,(lo[2]+hi[2])*.5;end=sorted(boundary,key=lambda v:math.atan2(v.co.z-cz,v.co.y-cy));rings=[]
 for j in range(segments):
  dx,inset=front_stations(width)[j];x=lo[0]+dx;rings.append([bm.verts.new((x,v.co.y-inset*(1 if v.co.y>cy else -1),v.co.z-inset*(1 if v.co.z>cz else -1))) for v in end])
 rings.append(end)
 for a,b in zip(rings,rings[1:]):
  for j in range(20):k=(j+1)%20;q=bm.faces.new([a[j],a[k],b[k],b[j]]);q.smooth=True
 bm.faces.new(list(reversed(rings[0]))).smooth=False;bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(patch);bm.free();patch.update();patch.calc_loop_triangles();temp=bpy.data.objects.new('temporary_control_box_profile',patch);bpy.context.collection.objects.link(temp);front=[]
 retained_back=[p for p in [pts[i] for i in ids] if p.x>cut+1e-6];positions=set(tuple(v.co) for v in patch.vertices);assert all(tuple(v) in positions for v in retained_back)
 pa=[];pu=[];pd=[]
 for tri in patch.loop_triangles:
  a,b,c=[patch.vertices[i].co for i in tri.vertices];cross=(b-a).cross(c-a);pa.append(cross.length*.5);pd.append(cross.normalized().dot(patch.polygons[tri.polygon_index].normal))
 assert min(pa)>=1e-10 and min(pd)>.99;patchtree=BVHTree.FromPolygons([v.co for v in patch.vertices],[list(p.vertices) for p in patch.polygons]);growth=max(patchtree.find_nearest(p)[3]-d for _,_,p,d in anchors)
 keep=[i for i in range(len(pts)) if i not in ids];remap={old:i for i,old in enumerate(keep)};keepfaces=[p for p in old.polygons if p.index not in selected_faces];offset=len(keep);out=bpy.data.meshes.new('control-case-front-edge');inverse=ob.matrix_world.inverted();out.from_pydata([old.vertices[i].co for i in keep]+[inverse@v.co for v in patch.vertices],[],[[remap[i] for i in p.vertices] for p in keepfaces]+[[offset+i for i in p.vertices] for p in patch.polygons]);out.materials.append(mat)
 for a,b in zip(keepfaces,out.polygons):b.use_smooth=a.use_smooth;b.material_index=a.material_index
 for p,q in zip(patch.polygons,out.polygons[len(keepfaces):]):q.use_smooth=p.use_smooth;q.material_index=0
 for layer in old.uv_layers:
  uv=out.uv_layers.new(name=layer.name)
  for a,b in zip(keepfaces,out.polygons):
   for oi,ni in zip(a.loop_indices,b.loop_indices):uv.data[ni].uv=layer.data[oi].uv
  for p,q in zip(patch.polygons,out.polygons[len(keepfaces):]):
   axis=max(range(3),key=lambda i:abs(p.normal[i]));axes=[i for i in range(3) if i!=axis]
   for li,vi in zip(q.loop_indices,p.vertices):v=patch.vertices[vi].co;uv.data[li].uv=(v[axes[0]],v[axes[1]])
 old_edges={tuple(sorted(remap[i] for i in e.vertices)):bool(e.use_edge_sharp) for e in old.edges if all(i in remap for i in e.vertices)}
 for e in out.edges:
  k=tuple(sorted(e.vertices))
  if k in old_edges:e.use_edge_sharp=old_edges[k]
 out.update();out.calc_loop_triangles()
 for tri in out.loop_triangles:
  if tri.polygon_index>=len(keepfaces):
   for layer in out.uv_layers:
    a,b,c=[layer.data[i].uv for i in tri.loops];pu.append(abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5)
 assert pu and min(pu)>=1e-10
 original_small=[p.index for p in old.polygons if p.area<1e-10];assert not set(original_small)&set(selected_faces)
 assert all(tuple(out.vertices[j].co)==tuple(old.vertices[i].co) for i,j in remap.items());assert all(list(q.vertices)==[remap[i] for i in p.vertices] and q.use_smooth==p.use_smooth and q.material_index==p.material_index for p,q in zip(keepfaces,out.polygons))
 for a,b in zip(old.uv_layers,out.uv_layers):
  assert all(tuple(a.data[oi].uv)==tuple(b.data[ni].uv) for p,q in zip(keepfaces,out.polygons) for oi,ni in zip(p.loop_indices,q.loop_indices))
 bpy.data.objects.remove(temp,do_unlink=True);ob.modifiers.clear();ob.data=out;bpy.context.view_layer.update();quality=inventory(ob,bpy.context.evaluated_depsgraph_get());assert not any(quality[k] for k in ['boundary_edges','wire_edges','overfull_edges']);assert quality['small_faces']==len(original_small)==1
 assert protected=={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name}
 assert growth<=.0005,'Neighbour sampled distance growth exceeds unchanged .0005 gate'
 after=render_scene(f,inspection,objects,'after')
 assert all(all(a[k]==b[k] for k in ['direction','camera_position','ortho_scale','lighting']) for a,b in zip(before['views'],after['views']))
 camera.matrix_world,camera.data.type,camera.data.ortho_scale=camera_old
 report={'version':VERSION,'author':contract['author'],'changed_objects':[ob.name],'unchanged_non_targets':True,'protected_objects':78,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==contract['source_sha256'],'actions':[{'target':ob.name,'original_component_vertices':sorted(ids),'front_roll_width':width,'retained_actual_back_vertices':len(retained_back),'fixed_axial_stations':16,'source_crosssection_vertices':20,'source_modifier_frozen':True}],'quality':quality,'patch_vertices':len(patch.vertices),'patch_faces':len(patch.polygons),'patch_actual_triangles':len(patch.loop_triangles),'minimum_patch_triangle_area':min(pa),'minimum_patch_triangle_normal_dot':min(pd),'minimum_patch_uv_area':min(pu),'preserved_other_component_vertices':len(keep),'preserved_other_component_faces':len(keepfaces),'preserved_other_component_uv_loops':sum(len(p.loop_indices) for p in keepfaces),'preserved_other_component_sharp_edges':len(old_edges),'known_preserved_control_micro_polygons':original_small,'contacts_checked':True,'fixed_neighbour_samples':len(anchors),'maximum_nearest_distance_growth':growth,'contact_scope':'1812 fixed nearby vertices against old/new lower component, including already-separated points; not a continuous-contact, full collision or animation proof.','before_object_digests':digests_before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'views':{'before':before,'after':after},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'known_muzzle_defects':'94small polygons/264small triangles including22zero unchanged; whole asset not topology-approved.','scope':'Cosmetic game exterior front edge roll; actual rear geometry retained, target front topology/UV replaced, other five evaluated components preserved. Original editable bevel stack frozen. No internal function or historical dimensions.','user_approval':False,'lod_authorized':False}
 assert report['source_unchanged'] and report['actions']
 (f/'report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(f/'model.blend'),compress=True)
