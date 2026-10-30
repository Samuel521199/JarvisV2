# SPDX-License-Identifier: GPL-2.0-or-later
"""Preserve actual evaluated geometry/UV, shade only rounded bevel bands smooth."""
import bpy,json,hashlib,time
from modules.skills.studio3d.evaluated_shading import SOURCES,retained_plane
from modules.skills.studio3d.attachment_seat import VERSION
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene
def surface(mesh):
 return {'vertices':[list(v.co) for v in mesh.vertices],'faces':[[*p.vertices] for p in mesh.polygons],'uv':{layer.name:[list(d.uv) for d in layer.data] for layer in mesh.uv_layers},'material_indices':[p.material_index for p in mesh.polygons]}
def run(folder,req,c,source):
 if c['schema']=='jarvis.studio3d.evaluated-shading.v2':return run_planar(folder,req,c,source)
 start=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};smooth_before={n:[p.use_smooth for p in o.data.polygons] for n,o in objects.items() if o.type=='MESH'};deps=bpy.context.evaluated_depsgraph_get();plans=[]
 for t in c['targets']:
  ob=objects[t['object']];nv,width,segments=SOURCES[t['object']]
  if before[t['object']]!=t['source_digest'] or len(ob.data.vertices)!=nv or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys:raise ValueError('Original cover source changed')
  if len(ob.modifiers)!=1 or ob.modifiers[0].type!='BEVEL':raise ValueError('Original bevel only')
  mod=ob.modifiers[0]
  if abs(mod.width-width)>1e-6 or mod.segments!=segments or mod.offset_type!='OFFSET' or abs(mod.profile-.5)>1e-6 or mod.limit_method!='ANGLE' or mod.harden_normals:raise ValueError('Original bevel configuration required')
  base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps)
  if base.has_custom_normals or any(p.use_smooth for p in base.polygons):raise ValueError('Only diagnosed flat bevel surfaces')
  planes=[(list(p.normal),p.normal.dot(p.center)) for p in ob.data.polygons];unchanged=surface(base);smooth=[]
  for p in base.polygons:
   if not retained_plane([list(base.vertices[i].co) for i in p.vertices],list(p.normal),planes):smooth.append(p.index)
  if not smooth or len(smooth)==len(base.polygons):raise ValueError('Must preserve original planes and identify bevel bands')
  plans.append((ob,base,unchanged,smooth))
 scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before');actions=[]
 for ob,base,unchanged,smooth in plans:
  for i in smooth:base.polygons[i].use_smooth=True
  old=ob.data;ob.data=base;ob.modifiers.clear();base.update();bpy.context.view_layer.update()
  if surface(base)!=unchanged:raise ValueError('Evaluated geometry/UV changed')
  actions.append({'target':ob.name,'evaluated_vertices':len(base.vertices),'evaluated_faces':len(base.polygons),'smooth_bevel_faces':len(smooth),'flat_original_plane_faces':len(base.polygons)-len(smooth),'geometry_uv_sha256':hashlib.sha256(json.dumps(unchanged,sort_keys=True).encode()).hexdigest(),'evaluated_surface_unchanged':True});bpy.data.meshes.remove(old)
 after={n:digest_object(o) for n,o in objects.items()};targets={t['object'] for t in c['targets']}
 if any(before[n]!=after[n] or (n in smooth_before and smooth_before[n]!=[p.use_smooth for p in objects[n].data.polygons]) for n in objects if n not in targets):raise ValueError('Non-target changed')
 va=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam;bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'actions':actions,'views':{'before':vb,'after':va},'before_object_digests':before,'after_object_digests':after,'unchanged_non_targets':True,'contacts_checked':True,'contact_scope':'Exact evaluated vertices/faces retained, therefore original geometric contacts unchanged; no claim original assembly was correct.','source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'elapsed_seconds':time.monotonic()-start,'requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'scope':'Only diagnosed flat bevel polygons switched smooth; original planes stay flat. Original evaluated geometry/UV/material references preserved exactly, editable base topology and modifier stack evaluated. No functional, history, animation, full quality or independent learning claim.'};(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

def run_planar(folder,req,c,source):
 from modules.skills.studio3d.evaluated_shading import front_faces
 from adapters.studio3d.spade_frame_worker import dependency
 from adapters.studio3d.panel_corner_worker import inventory
 start=time.monotonic()
 if req['source_sha256']!=c['source_sha256'] or hashlib.sha256(source.read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError('Exact planar shading source changed')
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if len(objects)!=79 or any(o is None for o in objects.values()):raise ValueError('Original visual inventory required')
 for name,sha in c['dependencies'].items():
  ob=bpy.data.objects.get(name)
  if ob is None or dependency(ob)[0]!=sha:raise ValueError('Planar shading operand or neighbor dependency changed')
 ob=objects['muzzle-brake'];deps=bpy.context.evaluated_depsgraph_get()
 if ob.type!='MESH' or len(ob.data.vertices)!=482 or ob.data.users!=1 or ob.animation_data or ob.data.shape_keys or [m.type for m in ob.modifiers]!=['BOOLEAN']*3+['BEVEL']:raise ValueError('Original evaluated surface source required')
 if [m.object.name for m in list(ob.modifiers)[:3]]!=['brake-port-0','brake-port-1','muzzle-opening']:raise ValueError('Original cutter order required')
 base=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),depsgraph=deps);original=surface(base);world=[list(ob.matrix_world@v.co) for v in base.vertices];selected=front_faces(world,original['faces'])
 if base.has_custom_normals or selected!=c['front_face_indices'] or not all(base.polygons[i].use_smooth for i in selected):raise ValueError('Existing smooth planar exterior faces changed')
 expected={'vertices':5312,'faces':4900,'boundary_edges':0,'wire_edges':0,'overfull_edges':0,'small_faces':94};quality=inventory(ob,deps)
 if quality!=expected:raise ValueError('Diagnosed original surface inventory changed')
 # This shading-only operation preserves every existing evaluated point/face/UV.
 # The source's94microfaces remain an explicit unresolved issue; no threshold
 # is enlarged and neither clean topology nor complete asset acceptance is claimed.
 before={n:digest_object(o) for n,o in objects.items()};protected={n:dependency(o)[0] for n,o in objects.items() if n!=ob.name};smooth0=[p.use_smooth for p in base.polygons]
 scene=bpy.context.scene;camera=scene.camera;oldcam=(camera.matrix_world.copy(),camera.data.type,camera.data.ortho_scale);scene.cycles.seed=4;vb=render_scene(folder,c['inspection'],objects,'before')
 ob.data=base;ob.modifiers.clear()
 for i in selected:base.polygons[i].use_smooth=False
 bpy.context.view_layer.update()
 if surface(base)!=original or inventory(ob,deps)!=quality:raise ValueError('Planar shading altered geometry/UV or quality inventory')
 if [i for i,(a,p) in enumerate(zip(smooth0,base.polygons)) if a!=p.use_smooth]!=selected:raise ValueError('Nonselected shading changed')
 if any(dependency(objects[n])[0]!=sha for n,sha in protected.items()):raise ValueError('Non-target dependency changed')
 for name,sha in c['dependencies'].items():
  if name!=ob.name and dependency(bpy.data.objects[name])[0]!=sha:raise ValueError('Cutter/neighbor changed')
 va=render_scene(folder,c['inspection'],objects,'after')
 if not all(all(a[k]==b[k] for k in ('direction','camera_position','ortho_scale','lighting')) for a,b in zip(vb['views'],va['views'])):raise ValueError('Fixed comparison changed')
 camera.matrix_world,camera.data.type,camera.data.ortho_scale=oldcam
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
 report={'version':VERSION,'author':c['author'],'actions':[{'target':ob.name,'flat_planar_faces':selected,'evaluated_surface_unchanged':True,'surface_sha256':hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest(),'quality_before':quality,'quality_after':inventory(ob,deps)}],'before_object_digests':before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'protected_objects':78,'unchanged_non_targets':True,'contacts_checked':True,'contact_scope':'Exact evaluated geometry preserved; no claim existing contact or microface topology was correct.','source_unchanged':True,'views':{'before':vb,'after':va},'requires_high_surface_texture_export':True,'elapsed_seconds':time.monotonic()-start,'known_unresolved_source_issues':['94 existing faces below1e-10area introduced by original bevel stage remain unchanged.'],'clean_topology':False,'user_approval':False,'lod_authorized':False,'scope':'Only96existing visible planar end faces become flat. Geometry/UV/material assignments retained; original base/Boolean/bevel stack evaluated. No bore, functional, dimension or exterior silhouette edit.'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
