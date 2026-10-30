# SPDX-License-Identifier: GPL-2.0-or-later
"""Preserve evaluated carriage box and append supported shallow art relief."""
import bpy,json,hashlib,time
from mathutils import Vector
from modules.skills.studio3d.saddle_fascia import build
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.exterior_closure_worker import shaped,inside
from adapters.studio3d.attachment_seat_worker import world_tree
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene
from mathutils.bvhtree import BVHTree

def run(folder,req,c,source):
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Source inventory changed')
 before={n:digest_object(o) for n,o in objects.items()};ob=objects[c['target']]
 if before[c['target']]!=c['source_digest']:raise ValueError('Saddle source changed')
 if ob.type!='MESH' or len(ob.data.vertices)!=8 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original static box required')
 if len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL' or abs(ob.modifiers[0].width-.004)>1e-6 or ob.modifiers[0].segments!=5:raise ValueError('Unsupported saddle stack')
 if len(ob.data.materials)!=1 or not ob.data.materials[0].use_nodes or any(n.type in ('UVMAP','TEX_COORD','NORMAL_MAP','TANGENT','ATTRIBUTE','VERTEX_COLOR','GROUP','SCRIPT') or n.type=='TEX_IMAGE' and not n.inputs['Vector'].is_linked for n in ob.data.materials[0].node_tree.nodes):raise ValueError('Supported world-coordinate paint required')
 ps=[ob.matrix_world@v.co for v in ob.data.vertices];bounds=[[min(p[i] for p in ps) for i in range(3)],[max(p[i] for p in ps) for i in range(3)]]
 if any(abs(bounds[k][i]-[[-.235,-.33,.4],[.115,.33,.6]][k][i])>2e-6 for k in range(2) for i in range(3)):raise ValueError('Saddle envelope mismatch')
 deps=bpy.context.evaluated_depsgraph_get();tree=world_tree(ob,deps);contacts=[]
 for x in (-.234,.114):
  for y in (-.04,.04):
   for z in (.455,.545):contacts.append({'point':[x,y,z],'before':inside(tree,[x,y,z])})
 base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);v0=[list(v.co) for v in base.vertices];f0=[list(p.vertices) for p in base.polygons];uv0=[(l.name,[list(d.uv) for d in l.data]) for l in base.uv_layers]
 vs=list(v0);fs=list(f0);smooth=[p.use_smooth for p in base.polygons];actions=[];inverse=ob.matrix_world.inverted()
 for p in build(c):
  vs1,fs1,sm=shaped(p,deps);offset=len(vs);vs.extend([list(inverse@Vector(v)) for v in vs1]);fs.extend([[offset+i for i in f] for f in fs1]);smooth.extend(sm);actions.append({'role':p['role'],'vertices':len(vs1),'faces':len(fs1)})
 if len(vs)>6000:raise ValueError('Fascia vertex budget')
 camera=bpy.context.scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);bpy.context.scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before')
 mesh=bpy.data.meshes.new('saddle-fascia');mesh.from_pydata(vs,[],fs);mesh.materials.append(ob.data.materials[0]);mesh.update();old=ob.data;ob.data=mesh;ob.modifiers.clear()
 for p,s in zip(mesh.polygons,smooth):p.use_smooth=s
 for name,data in uv0:
  layer=mesh.uv_layers.new(name=name)
  for a,b in zip(layer.data,data):a.uv=b
  if [list(a.uv) for a in layer.data[:len(data)]]!=data:raise ValueError('Evaluated original UV changed')
 if [list(v.co) for v in mesh.vertices[:len(v0)]]!=v0 or [list(p.vertices) for p in mesh.polygons[:len(f0)]]!=f0:raise ValueError('Original evaluated saddle changed')
 bpy.context.view_layer.update();added=BVHTree.FromPolygons([ob.matrix_world@v.co for v in mesh.vertices],[list(p.vertices) for p in list(mesh.polygons)[len(f0):]],all_triangles=False)
 for row in contacts:row['after_fascia']=inside(added,row['point'])
 after={n:digest_object(o) for n,o in objects.items()}
 if any(before[n]!=after[n] for n in objects if n!=c['target']):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.data.meshes.remove(old);bpy.data.meshes.remove(base);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':actions,'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'contact_samples':contacts,'evaluated_source_vertices_preserved':len(v0),'evaluated_source_faces_preserved':len(f0),'evaluated_uv_loops_preserved':sum(len(d) for _,d in uv0),'views':{'before':vb,'after':va},'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-start,'user_approval':False,'lod_authorized':False,'scope':'Reference-visible decorative faces only. Original evaluated body retained; shallow relief intentionally overlaps source. Eight paired-volume probes do not prove continuous contact, global clearance, animation, engineering or history.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
