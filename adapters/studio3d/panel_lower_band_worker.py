# SPDX-License-Identifier: GPL-2.0-or-later
"""Source-bound lower shield silhouette and original attachment co-movement."""
import bpy,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.panel_lower_band import PANELS,FLAPS,HARDWARE,TARGETS,shift,displacement,validate_sheet
from modules.skills.studio3d.attachment_seat import components
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def stack(ob):
 rows=[]
 for m in ob.modifiers:
  row={'name':m.name,'type':m.type,'show_viewport':m.show_viewport,'show_render':m.show_render}
  for k in ('width','segments','thickness','offset','use_even_offset','use_quality_normals','solver','operation','use_self','use_hole_tolerant','limit_method','angle_limit'):
   if hasattr(m,k):row[k]=getattr(m,k)
  if m.type=='BOOLEAN':
   if m.object is None or m.object.modifiers or m.object.animation_data:raise ValueError('Unsupported boolean dependency')
   row['cutter']={'name':m.object.name,'digest':digest_object(m.object)}
  rows.append(row)
 return rows

def support_samples(objects,deps):
 trees=[world_tree(objects[n],deps) for n in PANELS+FLAPS]
 result={}
 for name in HARDWARE+('shield-struts',):
  ob=objects[name]
  result[name]=[min(tree.find_nearest(ob.matrix_world@v.co)[3] for tree in trees) for v in ob.data.vertices]
 return result

def occlusion(objects,deps):
 trees={n:world_tree(objects[n],deps) for n in PANELS+FLAPS};rows=[]
 for side in (-1,1):
  for y in (.28,.40,.52,.64,.76):
   for z in (.46,.50,.54):
    hits=[]
    for name,tree in trees.items():
     p,normal,index,d=tree.ray_cast(Vector((2,side*y,z)),Vector((-1,0,0)),4)
     if p is not None:hits.append({'object':name,'x':p.x})
    rows.append({'yz':[side*y,z],'shield_hit':bool(hits),'hits':hits})
 return {'rays':rows,'hit_count':sum(r['shield_hit'] for r in rows),'scope':'Thirty orthographic +X shield-only rays in the axle height band; not full scene visibility or collision proof'}

def main(folder,req,c,source,version):
 from adapters.studio3d.panel_corner_worker import inventory
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Source inventory changed')
 before={n:digest_object(o) for n,o in objects.items()};deps=bpy.context.evaluated_depsgraph_get();raw={};stacks={};old_eval={};uv={};prepared={}
 for name in TARGETS:
  ob=objects[name]
  if before[name]!=c['source_digests'][name] or ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or len(ob.data.materials)!=1:raise ValueError('Unsupported or changed lower band source')
  types=[m.type for m in ob.modifiers]
  if name in PANELS+FLAPS:
   if types not in (['SOLIDIFY','BEVEL'],['BOOLEAN','SOLIDIFY','BEVEL']):raise ValueError('Expected bound thin sheet stack')
   if abs(next(m for m in ob.modifiers if m.type=='SOLIDIFY').thickness)>.025:raise ValueError('Unexpected shell thickness')
  elif types!=['BEVEL'] or ob.modifiers[0].width>.00301 or ob.modifiers[0].segments>4:raise ValueError('Expected small hardware bevel')
  mat=ob.data.materials[0]
  if not mat.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in mat.node_tree.nodes):raise ValueError('Unsupported material coordinates')
  points=[list(ob.matrix_world@v.co) for v in ob.data.vertices];faces=[list(p.vertices) for p in ob.data.polygons]
  raw[name]=(points,faces);stacks[name]=stack(ob);old_eval[name]=inventory(ob,deps);uv[name]=[[list(x.uv) for x in layer.data] for layer in ob.data.uv_layers]
  if name in PANELS+FLAPS:
   validate_sheet(name,points,faces);new=[shift(p,c['raise_height']) for p in points]
  else:
   groups=components(len(points),faces)
   if len(groups)!=(8 if name==HARDWARE[0] else 26):raise ValueError('Expected original rigid attachment components')
   new=[p[:] for p in points]
   for ids in groups:
    center=sum((Vector(points[i]) for i in ids),Vector())/len(ids);delta=Vector(displacement(center.z,c['raise_height']))
    for i in ids:new[i]=list(Vector(points[i])+delta)
  if max((Vector(a)-Vector(b)).length for a,b in zip(points,new))>.157:raise ValueError('Local displacement limit')
  prepared[name]=new
 before_support=support_samples(objects,deps);old_occlusion=occlusion(objects,deps)
 scene=bpy.context.scene;cam=scene.camera;old=(cam.matrix_world.copy(),cam.data.type,cam.data.ortho_scale);scene.cycles.seed=4
 old_views=render_scene(folder,c['inspection'],objects,'before')
 for name,new in prepared.items():
  ob=objects[name];inverse=ob.matrix_world.inverted()
  for v,p in zip(ob.data.vertices,new):v.co=inverse@Vector(p)
  ob.data.update()
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();actions=[]
 for name in TARGETS:
  ob=objects[name];actual=inventory(ob,deps)
  if stack(ob)!=stacks[name] or [[list(x.uv) for x in layer.data] for layer in ob.data.uv_layers]!=uv[name]:raise ValueError('Modifier/dependency/UV changed')
  if [list(p.vertices) for p in ob.data.polygons]!=raw[name][1]:raise ValueError('Original control topology changed')
  if any(actual[k]>old_eval[name][k] for k in ('boundary_edges','wire_edges','overfull_edges','small_faces')):raise ValueError('Evaluated topology regressed')
  actions.append({'target':name,'before_evaluated':old_eval[name],'after_evaluated':actual,'control_topology_and_uv_preserved':True,'modifiers_and_cutter_unchanged':stacks[name],'kind':'rigid_component_translation' if name in HARDWARE else 'lower_outline_plane_preserving_deformation','maximum_displacement':max((Vector(a)-Vector(b)).length for a,b in zip(raw[name][0],prepared[name]))})
 after_support=support_samples(objects,deps);anchor_checks={}
 for name,values in before_support.items():
  delta=max(b-a for a,b in zip(values,after_support[name]));anchor_checks[name]={'vertices':len(values),'maximum_nearest_sheet_distance_increase':delta}
  if delta>.0005:raise ValueError('Declared attachment loses nearby shield surface: '+name+' '+str(delta))
 new_occlusion=occlusion(objects,deps)
 if new_occlusion['hit_count']>=old_occlusion['hit_count']:raise ValueError('No measured axle-band exposure improvement')
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n not in TARGETS):raise ValueError('Non-target changed')
 new_views=render_scene(folder,c['inspection'],objects,'after');cam.matrix_world,cam.data.type,cam.data.ortho_scale=old
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':version,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'anchors_checked':True,'anchor_checks':anchor_checks,'anchor_scope':'Nearest evaluated sheet at attachment base vertices; not continuous contact, mechanism, full collision or animation proof','occlusion':{'before':old_occlusion,'after':new_occlusion},'views':{'before':old_views,'after':new_views},'elapsed_seconds':time.monotonic()-started,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Visible game-art lower shield outline only; not historical dimensions or functional weapon design'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
