# SPDX-License-Identifier: GPL-2.0-or-later
"""Round only source-bound open surface corners; preserve cutters and shell."""
import bpy,bmesh,sys,json,hashlib,time
from pathlib import Path
from mathutils import Vector
from modules.skills.studio3d.panel_corner import validate,VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def distances(anchors,trees):
 rows={}
 for name,ob in anchors.items():
  ps=[ob.matrix_world@v.co for v in ob.data.vertices]
  if len(ps)>10000:raise ValueError('Anchor vertex budget')
  rows[name]=[min(tree.find_nearest(p)[3] for tree in trees) for p in ps]
 return rows

def inventory(ob,deps):
 mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);bm=bmesh.new();bm.from_mesh(mesh)
 result={'vertices':len(bm.verts),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'wire_edges':sum(e.is_wire for e in bm.edges),'overfull_edges':sum(len(e.link_faces)>2 for e in bm.edges),'small_faces':sum(f.calc_area()<1e-10 for f in bm.faces)}
 bm.free();bpy.data.meshes.remove(mesh);return result

def aperture_main(folder,req,c,source):
 from modules.skills.studio3d.panel_aperture import panel_points,bridge_points
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Source inventory changed')
 targets=[*c['panels'],c['bridge']];before={n:digest_object(o) for n,o in objects.items()};deps=bpy.context.evaluated_depsgraph_get();raw={};old_eval={}
 for name in targets:
  ob=objects[name]
  if before[name]!=c['source_digests'][name] or ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or len(ob.data.materials)!=1:raise ValueError('Unsupported or changed source sheet')
  if any(m.type not in ('BOOLEAN','SOLIDIFY','BEVEL') for m in ob.modifiers) or len([m for m in ob.modifiers if m.type=='SOLIDIFY'])!=1:raise ValueError('Expected original shell modifiers')
  mat=ob.data.materials[0]
  if not mat.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in mat.node_tree.nodes):raise ValueError('Unsupported material coordinates')
  raw[name]={'points':[list(ob.matrix_world@v.co) for v in ob.data.vertices],'faces':[list(p.vertices) for p in ob.data.polygons]};old_eval[name]=inventory(ob,deps)
 prepared={}
 for name in c['panels']:
  row=raw[name];points=panel_points(row['points'],row['faces'],c['half_width'],c['falloff']);prepared[name]=(points,row['faces'])
  if any((Vector(a)-Vector(b)).length>c['max_displacement'] for a,b in zip(row['points'],points)):raise ValueError('Panel movement exceeds local envelope')
 # Front source panels are first positive/negative pair, bound and checked by
 # their original depths; back layers stay separate and retain their offsets.
 front=sorted(c['panels'],key=lambda n:max(p[0] for p in raw[n]['points']),reverse=True)[:2]
 bp,bf=bridge_points(raw[c['bridge']]['points'],[raw[n] for n in front],c['half_width'],c['top_drop'],c['corner_radius'],[{'points':prepared[n][0],'faces':prepared[n][1]} for n in front]);prepared[c['bridge']]=(bp,bf)
 if max(abs(p[1]) for p in bp)>c['half_width']+1e-7:raise ValueError('Bridge overlaps adjacent front sheet area')
 if max(min((Vector(p)-Vector(q)).length for q in raw[c['bridge']]['points']) for p in bp)>c['max_displacement']:raise ValueError('Bridge leaves local source envelope')
 anchors={n:objects[n] for n in c['anchors']};old_dist=distances(anchors,[world_tree(objects[n],deps) for n in targets])
 scene=bpy.context.scene;cam=scene.camera;old=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);scene.cycles.seed=4
 old_views=render_scene(folder,c['inspection'],objects,'before');actions=[]
 for name,(points,faces) in prepared.items():
  ob=objects[name];inverse=ob.matrix_world.inverted()
  if name!=c['bridge']:
   for v,p in zip(ob.data.vertices,points):v.co=inverse@Vector(p)
  else:
   materials=list(ob.data.materials);mesh=bpy.data.meshes.new(name+'-opening-profile');mesh.from_pydata([inverse@Vector(p) for p in points],[],faces)
   for m in materials:mesh.materials.append(m)
   for p in mesh.polygons:p.use_smooth=True
   ob.data=mesh
  ob.data.update();actions.append({'target':name,'tool':'panel_aperture','before_evaluated':old_eval[name],'source_vertices':len(raw[name]['points']),'result_vertices':len(points),'outer_points_preserved':name!=c['bridge'],'modifiers_preserved':True})
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
 for row in actions:
  result=inventory(objects[row['target']],deps);row['after_evaluated']=result
  if any(result[k]>row['before_evaluated'][k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Aperture shell topology regressed')
 new_dist=distances(anchors,[world_tree(objects[n],deps) for n in targets]);anchor_checks={}
 for n,values in old_dist.items():
  delta=max(b-a for a,b in zip(values,new_dist[n]));anchor_checks[n]={'vertices':len(values),'maximum_support_distance_increase':delta,'scope':'Nearest surface samples; not structural support or continuous collision proof'}
  if delta>c['max_anchor_distance_increase']:raise ValueError('Aperture removes declared anchor support')
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n not in targets):raise ValueError('Non-target changed')
 new_views=render_scene(folder,c['inspection'],objects,'after');cam.matrix_world,cam.data.type,cam.data.ortho_scale=old
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'anchor_checks':anchor_checks,'anchors_checked':True,'views':{'before':old_views,'after':new_views},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Bounded exterior opening profile; not historical dimensions, functioning weapon design, collision/animation certification'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

def main():
 folder=Path(sys.argv[sys.argv.index('--')+1]);req=json.loads((folder/'request.json').read_text());source=folder/'source.blend';started=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source receipt changed')
 c=validate(req['contract'],req['visible_names'])
 if c['schema']=='jarvis.studio3d.panel-lower-band.v1':
  from adapters.studio3d.panel_lower_band_worker import main as lower_band
  return lower_band(folder,req,c,source,VERSION)
 if c['schema']=='jarvis.studio3d.panel-aperture.v1':return aperture_main(folder,req,c,source)
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Missing source inventory')
 targets={t['object'] for t in c['targets']};before={n:digest_object(o) for n,o in objects.items()};deps=bpy.context.evaluated_depsgraph_get();prepared=[]
 for target in c['targets']:
  ob=objects[target['object']]
  if ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or not 4<=len(ob.data.vertices)<=10000 or len(ob.data.materials)!=1:raise ValueError('Unsupported panel source')
  if any(m.type not in ('BOOLEAN','SOLIDIFY','BEVEL') for m in ob.modifiers) or len([m for m in ob.modifiers if m.type=='SOLIDIFY'])!=1:raise ValueError('Expected existing thin-shell modifier')
  mat=ob.data.materials[0]
  if not mat.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in mat.node_tree.nodes):raise ValueError('Unsupported coordinate-dependent shader')
  bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();corners=[];indices={v['index'] for v in target['corners']}
  for item in target['corners']:
   if item['index']>=len(bm.verts):raise ValueError('Corner index absent')
   v=bm.verts[item['index']]
   if (ob.matrix_world@v.co-Vector(item['world_position'])).length>2e-6 or not v.is_boundary or len(v.link_edges)!=2 or len(v.link_faces)!=1:raise ValueError('Not a bound isolated open-sheet corner')
   if min(e.calc_length() for e in v.link_edges)<c['offset']*1.3:raise ValueError('Offset consumes adjacent panel span')
   corners.append(v)
  preserved=[v.co.copy() for v in bm.verts if v.index not in indices];original_count=len(bm.verts);original_faces=len(bm.faces);old_eval=inventory(ob,deps)
  bmesh.ops.bevel(bm,geom=corners,offset=c['offset'],segments=c['segments'],affect='VERTICES',clamp_overlap=False,profile=.5)
  if len(bm.verts)<=original_count or len(bm.faces)!=original_faces or any(e.is_wire or len(e.link_faces)>2 for e in bm.edges) or any(face.calc_area()<1e-10 for face in bm.faces):raise ValueError('Corner edit damaged control surface')
  if any(not any((v.co-p).length<1e-7 for v in bm.verts) for p in preserved):raise ValueError('Unselected control vertex changed')
  for v in bm.verts:
   if min((v.co-p).length for p in preserved)<1e-7:continue
   if min((ob.matrix_world@v.co-Vector(i['world_position'])).length for i in target['corners'])>c['offset']*1.8:raise ValueError('New corner leaves local envelope')
  prepared.append((target,ob,bm,old_eval,original_count))
 anchor_objects={n:objects[n] for n in c['anchors']}
 if any(o.type!='MESH' for o in anchor_objects.values()):raise ValueError('Mesh anchor required')
 old_distances=distances(anchor_objects,[world_tree(objects[n],deps) for n in targets])
 scene=bpy.context.scene;camera=scene.camera;old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4
 old_views=render_scene(folder,c['inspection'],objects,'before');actions=[]
 for target,ob,bm,old_eval,original_count in prepared:
  bm.to_mesh(ob.data);bm.free();ob.data.update();actions.append({'target':target,'before_evaluated':old_eval,'control_vertices_before':original_count,'control_vertices_after':len(ob.data.vertices),'offset':c['offset'],'segments':c['segments'],'unselected_control_vertices_preserved':True,'modifiers_preserved':True})
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
 for row in actions:
  actual=inventory(objects[row['target']['object']],deps);row['after_evaluated']=actual
  if any(actual[k]>row['before_evaluated'][k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Evaluated shell topology regressed')
 new_distances=distances(anchor_objects,[world_tree(objects[n],deps) for n in targets]);anchor_checks={}
 for n,old_values in old_distances.items():
  deltas=[b-a for a,b in zip(old_values,new_distances[n])]
  if max(deltas)>c['max_anchor_distance_increase']:raise ValueError('Rounded panel withdrew support from unchanged anchor')
  anchor_checks[n]={'vertices':len(deltas),'maximum_support_distance_increase':max(deltas),'scope':'Nearest evaluated surface at original attachment vertices; not full collision or mechanical support proof'}
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n not in targets):raise ValueError('Non-target changed')
 new_views=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=old
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'anchor_checks':anchor_checks,'anchors_checked':True,'views':{'before':old_views,'after':new_views},'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-started,'scope':'Visible exterior sheet rounding only; no structural or historical engineering validation'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
