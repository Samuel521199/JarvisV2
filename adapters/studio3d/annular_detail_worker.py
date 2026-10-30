# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual source-derived exterior bead smoothing and sampled support seating."""
import hashlib,json,sys,time,math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from modules.skills.studio3d.annular_detail import validate,fit_rings,geometry,VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object,topology
from adapters.studio3d.inspection_worker import render_scene

def support_samples(r,h,tube,center,trees,count):
 side=1 if h>0 else -1;axis=Vector((0,side,0));gaps=[];visible=[]
 for i in range(count):
  angle=math.tau*i/count
  for offset in (-.5,0,.5):
   radius=r+offset*tube;half=tube*math.sqrt(1-offset*offset)
   foot=Vector(center)+Vector((radius*math.cos(angle),h-side*half,radius*math.sin(angle)));hits=[]
   for tree in trees:
    loc,normal,_,_=tree.ray_cast(foot+axis*.08,-axis,.18)
    if loc is not None and normal.dot(axis)>.5:hits.append((foot-loc).dot(axis))
   if not hits:raise ValueError('No facing support under bead sample')
   gap=min(hits);gaps.append(gap);visible.append(gap+2*half)
 return {'rays':len(gaps),'gap':[min(gaps),max(gaps)],'minimum_visible_height':min(visible),'scope':'Discrete axial footprint samples; not complete triangle collision proof'}

def main():
 folder=Path(sys.argv[sys.argv.index('--')+1]);req=json.loads((folder/'request.json').read_text());source=folder/'source.blend';started=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
 c=validate(req['contract'],req['visible_names'])
 if c['schema']=='jarvis.studio3d.trail-band.v1':
  from adapters.studio3d.trail_band_worker import run
  return run(folder,req,c,source,VERSION)
 if c['schema']=='jarvis.studio3d.collar-profile.v1':
  from adapters.studio3d.collar_profile_worker import run
  return run(folder,req,c,source,VERSION)
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(ob is None for ob in objects.values()):raise ValueError('Missing source inventory')
 before={n:digest_object(o) for n,o in objects.items()};deps=bpy.context.evaluated_depsgraph_get();plans=[]
 for target in c['targets']:
  ob=objects[target['object']]
  if ob.type!='MESH' or ob.data.users!=1 or ob.modifiers or len(ob.data.materials)!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Unsupported ring source')
  mat=ob.data.materials[0]
  if not mat.use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in mat.node_tree.nodes):raise ValueError('Cannot retopologize UV-dependent or unsupported shader')
  rings=fit_rings([list(ob.matrix_world@v.co) for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons],target['center'],target['expected_components'])
  trees=[world_tree(objects[n],deps) for n in target['supports']]
  for ring in rings:
   if c['segments']<ring['source_segments'] or c['tube_segments']<=ring['source_tube_segments']:raise ValueError('High surface refinement only')
   old=support_samples(ring['radius'],ring['axial_center'],ring['tube'],target['center'],trees,c['segments'])
   move=max(0,old['gap'][1]+c['embed'])
   if move>c['max_move']:raise ValueError('Required seating exceeds bounded movement')
   h=ring['axial_center']-math.copysign(move,ring['axial_center']);new=support_samples(ring['radius'],h,ring['tube'],target['center'],trees,c['segments'])
   if new['gap'][1]>1e-6 or new['minimum_visible_height']<.002:raise ValueError('Seat would float or hide the lip')
   ring.update(before_support=old,after_support=new,axial_move=move,new_axial_center=h)
  plans.append({'target':target,'rings':rings})
 (folder/'geometry-plan.json').write_text(json.dumps(plans,indent=2)+'\n')
 scene=bpy.context.scene;camera=scene.camera;old=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4
 images_before=render_scene(folder,c['inspection'],objects,'before')
 for plan in plans:
  ob=objects[plan['target']['object']];vertices=[];faces=[]
  for ring in plan['rings']:
   v,f=geometry(ring['radius'],ring['new_axial_center'],ring['tube'],c['segments'],c['tube_segments'],plan['target']['center']);offset=len(vertices);vertices.extend(v);faces.extend([[i+offset for i in p] for p in f])
  inverse=ob.matrix_world.inverted();mesh=bpy.data.meshes.new(ob.name+'-supported-smooth-beads');mesh.from_pydata([inverse@Vector(v) for v in vertices],[],faces);mesh.materials.append(ob.data.materials[0]);mesh.update()
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
  for face in mesh.polygons:face.use_smooth=True
  ob.data=mesh;t=topology(ob)
  if t['boundary_edges'] or t['overfull_edges']:raise ValueError('Invalid rebuilt ring topology')
  plan['after_topology']=t
  # Read the actual replaced mesh, not merely the analytic plan. The supported
  # sampling counts all include the back-most tube row on each side.
  trees=[world_tree(objects[n],deps) for n in plan['target']['supports']]
  for index,ring in enumerate(plan['rings']):
   side=1 if ring['new_axial_center']>0 else -1;axis=Vector((0,side,0));j=c['tube_segments']*(3 if side>0 else 1)//4;gaps=[]
   for i in range(c['segments']):
    k=index*c['segments']*c['tube_segments']+i*c['tube_segments']+j;point=ob.matrix_world@ob.data.vertices[k].co
    expected=Vector(vertices[k])
    if (point-expected).length>2e-6:raise ValueError('Rebuilt world coordinate differs from plan')
    hits=[]
    for tree in trees:
     loc,normal,_,_=tree.ray_cast(point+axis*.08,-axis,.18)
     if loc is not None and normal.dot(axis)>.5:hits.append((point-loc).dot(axis))
    if not hits:raise ValueError('Actual bottom vertex lost support')
    gaps.append(min(hits))
   if max(gaps)>1e-6 or min(gaps)+2*ring['tube']<.002:raise ValueError('Actual rebuilt bead failed support or visibility')
   ring['actual_bottom_vertex_check']={'count':len(gaps),'gap':[min(gaps),max(gaps)],'minimum_visible_height':min(gaps)+2*ring['tube'],'read_from_rebuilt_mesh':True}
 bpy.context.view_layer.update();after={n:digest_object(o) for n,o in objects.items()};targets={t['object'] for t in c['targets']}
 if any(before[n]!=after[n] for n in before if n not in targets):raise ValueError('Non-target changed')
 images_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world, camera.data.type,camera.data.ortho_scale=old
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':plans,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':images_before,'after':images_after},'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-started,'scope':'Circular exterior bead tessellation and axial support samples; no functional weapon design, historical dimensions, full collision or autonomous learning claim'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
