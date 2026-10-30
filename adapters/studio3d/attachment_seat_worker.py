# SPDX-License-Identifier: GPL-2.0-or-later
"""Translate only selected disconnected fasteners; support stays immutable."""
import hashlib,json,sys,time,math
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from modules.skills.studio3d.attachment_seat import validate,components,axial_translation,VERSION
from adapters.studio3d.demonstration_worker import digest_object,topology
from adapters.studio3d.inspection_worker import render_scene

def world_tree(ob,deps):
 evaluated=ob.evaluated_get(deps);mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=deps)
 try:return BVHTree.FromPolygons([ob.matrix_world@v.co for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons],all_triangles=False)
 finally:bpy.data.meshes.remove(mesh)

def blockers_clear(points,center,axis,trees):
 depths=[(p-center).dot(axis) for p in points];base=min(depths);top=max(depths);tested=0
 for point,depth in zip(points,depths):
  if abs(depth-base)>1e-6:continue
  for name,tree in trees.items():
   loc,_,_,_=tree.ray_cast(point+axis*(top-depth+.06),-axis,top-base+.061);tested+=1
   if loc is not None and (loc-center).dot(axis)>base-.0001:raise ValueError('Adjacent object overlaps fastener footprint: '+name)
 return {'rays_tested':tested,'clear':True,'scope':'Axial rays through flat base vertices; not full triangle collision or clearance certification'}

def layout_main(folder,req,c,source):
 from modules.skills.studio3d.fastener_layout import rotate_x_to_normal,bound_component
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['object']]
 if before[c['object']]!=c['source_digest'] or ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or len(ob.data.vertices)>20000 or any(m.type not in ('BEVEL','WEIGHTED_NORMAL') for m in ob.modifiers):raise ValueError('Unsupported or changed layout source')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes:raise ValueError('Expected single supported material')
 if any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Coordinate-dependent material unsupported')
 deps=bpy.context.evaluated_depsgraph_get();world=[ob.matrix_world@v.co for v in ob.data.vertices];faces=[list(p.vertices) for p in ob.data.polygons];groups=components(len(world),faces);plans=[];trees={n:world_tree(objects[n],deps) for n in {t['support'] for t in c['targets']}};blockers={n:world_tree(objects[n],deps) for n in c['blockers']};old_topology=topology(ob)
 for t in c['targets']:
  ids=bound_component(groups,t['indices']);center=sum((world[i] for i in ids),Vector())/len(ids)
  if (center-Vector(t['center'])).length>2e-6:raise ValueError('Component center binding changed')
  base=min(world[i].x for i in ids);height=max(world[i].x for i in ids)-base
  if not .004<=height<=.03:raise ValueError('Unsupported head thickness')
  feet=[i for i in ids if abs(world[i].x-base)<1e-6]
  if len(feet)<4:raise ValueError('No axial flat footprint')
  y,z=t['yz'];tree=trees[t['support']];loc,normal,_,_=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)),4)
  if loc is None or normal.x<.7:raise ValueError('No facing support at declared target')
  foot_center=Vector((base,center.y,center.z));points=[loc+Vector(rotate_x_to_normal(world[i]-foot_center,normal)) for i in ids]
  gaps=[]
  for index in feet:
   point=points[ids.index(index)];hit,hn,_,_=tree.ray_cast(point+normal*.04,-normal,.08)
   if hit is None or hn.dot(normal)<.94:raise ValueError('Target footprint leaves consistent support')
   gaps.append((point-hit).dot(normal))
  shift=-max(gaps)-c['embed'];points=[p+normal*shift for p in points]
  if max((p-world[i]).length for p,i in zip(points,ids))>c['max_move']:raise ValueError('Layout exceeds movement envelope')
  clearance=blockers_clear(points,loc,normal,blockers)
  plans.append({'target':t,'indices':ids,'points':[list(p) for p in points],'normal':list(normal),'support_point':list(loc),'rotation_degrees':math.degrees(math.acos(max(-1,min(1,normal.x)))),'source_height':height,'planned_clearance':clearance})
 # A conservative separation check between head bounding spheres (including
 # unmoved components) rejects a visually obvious duplicate or overlap.
 moved={i:Vector(p) for a in plans for i,p in zip(a['indices'],a['points'])};spheres=[]
 for ids in groups:
  ps=[moved.get(i,world[i]) for i in ids];center=sum(ps,Vector())/len(ps);spheres.append((center,max((p-center).length for p in ps)))
 for i,(p,r) in enumerate(spheres):
  for q,s in spheres[i+1:]:
   if (p-q).length<r+s+.0005:raise ValueError('Head layout components overlap or nearly touch')
 scene=bpy.context.scene;camera=scene.camera;old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;views_before=render_scene(folder,c['inspection'],objects,'before');inverse=ob.matrix_world.inverted()
 for a in plans:
  for i,p in zip(a['indices'],a['points']):ob.data.vertices[i].co=inverse@Vector(p)
 ob.data.update();bpy.context.view_layer.update()
 if topology(ob)!=old_topology:raise ValueError('Relocation changed topology')
 for i,v in enumerate(ob.data.vertices):
  if i not in moved and (ob.matrix_world@v.co-world[i]).length>1e-8:raise ValueError('Unselected head moved')
 for a in plans:
  t=a['target'];tree=trees[t['support']];normal=Vector(a['normal']);loc=Vector(a['support_point']);ps=[ob.matrix_world@ob.data.vertices[i].co for i in a['indices']];depths=[(p-loc).dot(normal) for p in ps];base=min(depths);top=max(depths);gaps=[];heights=[]
  for p,d in zip(ps,depths):
   if abs(d-base)>1e-6:continue
   hit,hn,_,_=tree.ray_cast(p+normal*.04,-normal,.08)
   if hit is None or hn.dot(normal)<.94:raise ValueError('Actual footprint lost support')
   sd=(hit-loc).dot(normal);gaps.append(d-sd);heights.append(top-sd)
  if len(gaps)<4 or max(gaps)>1e-5 or min(heights)<.004 or -min(gaps)>a['source_height']*.65:raise ValueError('Actual moved head contact/visibility failed')
  a['actual_contact']={'base_gap':[min(gaps),max(gaps)],'minimum_visible_height':min(heights),'sample_count':len(gaps),'verified_after_vertex_edit':True};a['actual_clearance']=blockers_clear(ps,loc,normal,blockers);a.pop('points')
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n!=c['object']):raise ValueError('Non-target changed')
 views_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=old;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':plans,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'unselected_components_unchanged':True,'contacts_checked':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':views_before,'after':views_after},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Exterior visual attachment layout, exact component-bound. Footprint rays and sphere separation, not continuous collision, structural or historical validation.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

def component_main(folder,req,c,source):
 from modules.skills.studio3d.fastener_layout import bound_component
 from modules.skills.studio3d.component_seat import supported_modifiers
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['object']]
 if before[c['object']]!=c['source_digest'] or ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or len(ob.data.vertices)>20000:raise ValueError('Unsupported or changed component source')
 supported_modifiers([{'type':m.type,'width':getattr(m,'width',0),'segments':getattr(m,'segments',0)} for m in ob.modifiers])
 if any(m is None or not m.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in m.node_tree.nodes) for m in ob.data.materials):raise ValueError('Coordinate-dependent material unsupported')
 deps=bpy.context.evaluated_depsgraph_get();world=[ob.matrix_world@v.co for v in ob.data.vertices];groups=components(len(world),[list(p.vertices) for p in ob.data.polygons]);old_topology=topology(ob)
 trees={n:world_tree(objects[n],deps) for n in {t['support'] for t in c['targets']}};plans=[];selected=set()
 for t in c['targets']:
  ids=bound_component(groups,t['indices']);center=sum((world[i] for i in ids),Vector())/len(ids);axis=Vector(t['axis']);tree=trees[t['support']]
  if (center-Vector(t['center'])).length>2e-6:raise ValueError('Component center binding changed')
  depths=[(world[i]-center).dot(axis) for i in ids];base=min(depths);top=max(depths);feet=[world[i] for i,d in zip(ids,depths) if abs(d-base)<1e-6]
  if len(feet)<4:raise ValueError('No planar support footprint')
  hits=[]
  for p in feet:
   loc,normal,_,_=tree.ray_cast(p+axis*.04,-axis,.08)
   if loc is None or normal.dot(axis)<.95:raise ValueError('No matching planar facing support')
   hits.append((loc-center).dot(axis))
  delta,contact=axial_translation(base,top,hits,c['embed'],c['max_move'])
  plans.append({'target':t,'delta':list(axis*delta),'contact':contact});selected.update(ids)
 (folder/'contact-plan.json').write_text(json.dumps(plans,indent=2)+'\n')
 scene=bpy.context.scene;camera=scene.camera;old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;views_before=render_scene(folder,c['inspection'],objects,'before');inverse=ob.matrix_world.inverted()
 for p in plans:
  for i in p['target']['indices']:ob.data.vertices[i].co=inverse@(world[i]+Vector(p['delta']))
 ob.data.update();bpy.context.view_layer.update()
 if topology(ob)!=old_topology:raise ValueError('Seating changed topology')
 if any((ob.matrix_world@v.co-world[i]).length>1e-8 for i,v in enumerate(ob.data.vertices) if i not in selected):raise ValueError('Unselected component moved')
 for p in plans:
  t=p['target'];axis=Vector(t['axis']);center=Vector(t['center']);ps=[ob.matrix_world@ob.data.vertices[i].co for i in t['indices']];depths=[(v-center).dot(axis) for v in ps];base=min(depths);top=max(depths);gaps=[];heights=[]
  for v,d in zip(ps,depths):
   if abs(d-base)>1e-6:continue
   loc,normal,_,_=trees[t['support']].ray_cast(v+axis*.04,-axis,.08)
   if loc is None or normal.dot(axis)<.95:raise ValueError('Actual moved footprint lost support')
   sd=(loc-center).dot(axis);gaps.append(d-sd);heights.append(top-sd)
  if len(gaps)<4 or max(gaps)>1e-5 or min(heights)<.004 or -min(gaps)>(top-base)*.65:raise ValueError('Actual moved contact/visibility failed')
  p['actual_contact']={'base_gap':[min(gaps),max(gaps)],'minimum_visible_height':min(heights),'sample_count':len(gaps),'verified_after_vertex_edit':True}
 after={n:digest_object(o) for n,o in objects.items()}
 if any(after[n]!=before[n] for n in objects if n!=c['object']):raise ValueError('Non-target changed')
 views_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=old;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':plans,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'unselected_components_unchanged':True,'contacts_checked':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':views_before,'after':views_after},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-started,'user_approval':False,'lod_authorized':False,'scope':'Cosmetic flat-foot component seating on evaluated immutable support; footprint vertex rays, not full collision, structural or historical validation.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

def main():
 folder=Path(sys.argv[sys.argv.index('--')+1]);req=json.loads((folder/'request.json').read_text());source=folder/'source.blend';began=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
 c=validate(req['contract'],req['visible_names'])
 if c['schema']=='jarvis.studio3d.rear-contour.v1':
  from adapters.studio3d.rear_contour_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.curve-foot.v1':
  from adapters.studio3d.curve_foot_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.trail-tab.v1':
  from adapters.studio3d.trail_tab_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.trail-pad.v1':
  from adapters.studio3d.trail_pad_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.curve-grip.v1':
  from adapters.studio3d.curve_grip_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.spade-frame.v1':
  from adapters.studio3d.spade_frame_worker import run
  return run(folder,req,c,source)
 if c['schema'] in ('jarvis.studio3d.facade-pocket.v1','jarvis.studio3d.facade-pocket.v2','jarvis.studio3d.facade-slot-repair.v1'):
  from adapters.studio3d.facade_pocket_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.surface-cleanup.v1':
  from adapters.studio3d.microface_cleanup_worker import run
  return run(folder,req,c,source)
 if c['schema'] in ('jarvis.studio3d.evaluated-shading.v1','jarvis.studio3d.evaluated-shading.v2'):
  from adapters.studio3d.evaluated_shading_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.exterior-border.v1':
  from adapters.studio3d.exterior_border_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.rear-face-relief.v1':
  from adapters.studio3d.rear_face_relief_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.saddle-fascia.v1':
  from adapters.studio3d.saddle_fascia_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.pedestal-profile.v1':
  from adapters.studio3d.pedestal_profile_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.exterior-closure.v1':
  from adapters.studio3d.exterior_closure_worker import run
  return run(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.component-seat.v1':return component_main(folder,req,c,source)
 if c['schema']=='jarvis.studio3d.fastener-layout.v1':return layout_main(folder,req,c,source)
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 targets={t['object'] for t in c['targets']};before={n:digest_object(o) for n,o in objects.items()};plans=[];support_trees={};blocker_trees={};deps=bpy.context.evaluated_depsgraph_get()
 for t in c['targets']:
  ob=objects[t['object']];support=objects[t['support']];center=Vector(t['center']);axis=Vector(t['axis'])
  if ob.type!='MESH' or support.type!='MESH' or ob.data.users!=1 or len(ob.data.vertices)>20000 or any(m.type not in ('BEVEL','WEIGHTED_NORMAL') for m in ob.modifiers):raise ValueError('Unsupported source mesh')
  tree=world_tree(support,deps)
  support_trees[t['object']]=tree
  blocker_trees[t['object']]={n:world_tree(objects[n],deps) for n in t.get('blockers',[])}
  world=[ob.matrix_world@v.co for v in ob.data.vertices];groups=components(len(world),[list(p.vertices) for p in ob.data.polygons]);chosen=[]
  if len(groups)>64:raise ValueError('Component budget')
  for ids in groups:
   centroid=sum((world[i] for i in ids),Vector())/len(ids);relative=centroid-center;axial=relative.dot(axis);radial=relative-axis*axial;radius=radial.length
   if not(t['radial_range'][0]<=radius<=t['radial_range'][1] and t['axial_range'][0]<=axial<=t['axial_range'][1]):continue
   if len(ids)>256 or radius<c['radial_inset']+.015:raise ValueError('Unexpected selected fastener')
   inset=-radial.normalized()*c['radial_inset'];scale=c.get('footprint_scale',1)
   points=[world[i]+inset+(world[i]-centroid-axis*(world[i]-centroid).dot(axis))*(scale-1) for i in ids];depths=[(p-center).dot(axis) for p in points];base=min(depths);top=max(depths)
   feet=[p for p,d in zip(points,depths) if abs(d-base)<1e-6]
   if len(feet)<4:raise ValueError('No planar support footprint')
   hits=[]
   for foot in feet:
    loc,normal,_,_=tree.ray_cast(foot+axis*.06,-axis,.12)
    if loc is None or normal.dot(axis)<.6:raise ValueError('Declared support not facing fastener footprint')
    hits.append((loc-center).dot(axis))
   delta,check=axial_translation(base,top,hits,c['embed'],c['max_move']);move=inset+axis*delta
   if move.length>c['max_move']:raise ValueError('Combined move exceeds envelope')
   adjusted=[p+axis*delta for p in points]
   if max((p-world[i]).length for p,i in zip(adjusted,ids))>c['max_move']:raise ValueError('Footprint change exceeds movement envelope')
   clearance=blockers_clear(adjusted,center,axis,blocker_trees[t['object']])
   chosen.append({'indices':ids,'delta':list(move),'centroid':list(centroid),'footprint_scale':scale,'source_radius':radius,'target_radius':radius-c['radial_inset'],'contact':check,'planned_adjacent_clearance':clearance})
  if len(chosen)!=t['expected_components']:raise ValueError('Selected component count differs from declared evidence')
  plans.append({'target':t,'components':chosen,'before_topology':topology(ob),'before_vertices':[list(v.co) for v in ob.data.vertices]})
 (folder/'contact-plan.json').write_text(json.dumps(plans,indent=2)+'\n')
 scene=bpy.context.scene;camera=scene.camera;old=camera.matrix_world.copy();oldtype=camera.data.type;oldscale=camera.data.ortho_scale;scene.cycles.seed=4
 views_before=render_scene(folder,c['inspection'],objects,'before')
 for plan in plans:
  ob=objects[plan['target']['object']];inverse=ob.matrix_world.inverted();selected=set()
  for component in plan['components']:
   selected.update(component['indices']);delta=Vector(component['delta']);centroid=Vector(component['centroid']);axis=Vector(plan['target']['axis'])
   for i in component['indices']:
    point=ob.matrix_world@ob.data.vertices[i].co;offset=point-centroid;ob.data.vertices[i].co=inverse@(point+delta+(offset-axis*offset.dot(axis))*(component['footprint_scale']-1))
  ob.data.update()
  if topology(ob)!=plan['before_topology']:raise ValueError('Seating changed topology')
  if any((ob.data.vertices[i].co-Vector(p)).length>1e-8 for i,p in enumerate(plan['before_vertices']) if i not in selected):raise ValueError('Non-selected component moved')
  t=plan['target'];axis=Vector(t['axis']);center=Vector(t['center']);tree=support_trees[t['object']]
  for component in plan['components']:
   points=[ob.matrix_world@ob.data.vertices[i].co for i in component['indices']];depths=[(p-center).dot(axis) for p in points];base=min(depths);top=max(depths);gaps=[];heights=[]
   for point,depth in zip(points,depths):
    if abs(depth-base)>1e-6:continue
    loc,normal,_,_=tree.ray_cast(point+axis*.06,-axis,.12)
    if loc is None or normal.dot(axis)<.6:raise ValueError('Actual modified footprint lost support')
    support_depth=(loc-center).dot(axis);gaps.append(depth-support_depth);heights.append(top-support_depth)
   if len(gaps)<4 or max(gaps)>1e-5 or min(heights)<.004 or -min(gaps)>(top-base)*.65:raise ValueError('Actual modified fastener failed contact/visibility check')
   component['actual_contact']={'sample_count':len(gaps),'base_gap':[min(gaps),max(gaps)],'minimum_visible_height':min(heights),'verified_after_vertex_edit':True}
   component['actual_adjacent_clearance']=blockers_clear(points,center,axis,blocker_trees[t['object']])
  plan.pop('before_vertices');plan['unselected_vertices_unchanged']=True
 bpy.context.view_layer.update();after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n not in targets):raise ValueError('Non-target changed')
 views_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world=old;camera.data.type=oldtype;camera.data.ortho_scale=oldscale
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':plans,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'contact_scope':'Planar mesh footprint samples on evaluated support; not a collision solver or engineering validation','source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':views_before,'after':views_after},'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-began}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
