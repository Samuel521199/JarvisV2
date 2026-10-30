# SPDX-License-Identifier: GPL-2.0-or-later
"""Replace one cosmetic box profile; preserve upper/lower neighboring contacts."""
import hashlib,json,time
import bpy
from mathutils import Vector
from modules.skills.studio3d.pedestal_profile import build,check_original
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.exterior_closure_worker import shaped,inside
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def run(folder,req,c,source):
 started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['target']]
 if before[c['target']]!=c['source_digest']:raise ValueError('Bound pedestal source changed')
 if ob.type!='MESH' or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Unsupported shared or animated source')
 check_original([list(ob.matrix_world@v.co) for v in ob.data.vertices])
 if len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL' or abs(ob.modifiers[0].width-.025)>1e-6 or ob.modifiers[0].segments!=5:raise ValueError('Unsupported pedestal modifier stack')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Topology replacement needs supported world-coordinate coating')
 deps=bpy.context.evaluated_depsgraph_get();oldtree=world_tree(ob,deps);samples=[]
 for name,other in objects.items():
  if name==c['target'] or other.type!='MESH':continue
  ev=other.evaluated_get(deps);mesh=ev.to_mesh()
  for v in mesh.vertices:
   p=other.matrix_world@v.co
   if not (-.25<=p.x<=.19 and -.26<=p.y<=.26 and .52<=p.z<=.86):continue
   loc,normal,_,dist=oldtree.find_nearest(p)
   if loc is not None and dist<.004:samples.append({'object':name,'point':list(p),'distance_before':dist})
  ev.to_mesh_clear()
 if len(samples)>20000:raise ValueError('Excessive neighboring contact samples')
 # Large intersecting faces can have no vertex near the other surface. Preserve
 # explicit overlap probes on both evaluated source solids instead of inventing
 # vertex-contact evidence or increasing the distance tolerance.
 anchors=[]
 for support,points in [('axle-saddle',[(x,y,.575) for x in (-.15,.05) for y in (-.1,.1)]),('cradle-cheeks',[(x,y,z) for x in (-.15,-.10) for y in (-.21,.21) for z in (.76,.79)])]:
  supporttree=world_tree(objects[support],deps)
  for p in points:anchors.append({'support':support,'point':list(p),'source_target':inside(oldtree,p),'source_support':inside(supporttree,p)})
 scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4
 views_before=render_scene(folder,c['inspection'],objects,'before')
 part=build(c);ps,fs,sm=shaped(part,deps);inverse=ob.matrix_world.inverted();oldmesh=ob.data;old_uv_loops=sum(len(l.data) for l in oldmesh.uv_layers)
 new=bpy.data.meshes.new(oldmesh.name+'-layered-profile');new.from_pydata([list(inverse@Vector(p)) for p in ps],[],fs);new.materials.append(oldmesh.materials[0]);new.update();ob.data=new;ob.modifiers.clear()
 for p,s in zip(new.polygons,sm):p.use_smooth=s
 bpy.context.view_layer.update();tree=world_tree(ob,deps)
 for row in samples:
  loc,normal,_,dist=tree.find_nearest(Vector(row['point']));row['distance_after']=dist
  if loc is None or dist-row['distance_before']>.001:raise ValueError('Pedestal profile increased sampled neighboring separation')
 # Top/bottom bands must remain locally solid where the original box joined surroundings.
 band_anchors=[]
 for z in (.575,.76):
  for x,y in [(-.15,-.15),(-.15,.15),(.10,-.15),(.10,.15)]:
   p=Vector((x,y,z));loc,n,_,_=tree.find_nearest(p)
   if loc is None or (p-loc).dot(n)>-.002:raise ValueError('Protected outer bands lost solid interior')
   band_anchors.append(list(p))
 for row in anchors:row['after_target']=inside(tree,row['point'])
 after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=c['target']):raise ValueError('Non-target changed')
 views_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.data.meshes.remove(oldmesh);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':[{'target':c['target'],'role':part['role'],'sections':part['sections'],'old_vertices':8,'new_vertices':len(ps),'old_uv_loops':old_uv_loops,'new_uv_layers':0,'uv_scope':'Source uses checked world coordinates; obsolete box UV explicitly replaced with new topology, original retained in before BLEND. High export generates mapped UV.'}],'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'nearby_vertex_samples':samples,'contact_samples':anchors,'protected_band_anchors':band_anchors,'maximum_sampled_vertex_gap_increase':max((r['distance_after']-r['distance_before'] for r in samples),default=None),'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'views':{'before':views_before,'after':views_after},'elapsed_seconds':time.monotonic()-started,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Cosmetic silhouette only. Twelve evaluated paired-volume probes and eight interior-band probes preserve sampled overlaps. Vertex proximity samples may be empty for large crossing faces; null is not a measured zero gap. Not continuous contact, full collision, animation or functional engineering.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
