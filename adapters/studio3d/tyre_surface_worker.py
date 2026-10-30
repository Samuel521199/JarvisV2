# SPDX-License-Identifier: GPL-2.0-or-later
"""Repair only declared exterior tyres, preserving current editable artwork."""
import hashlib,json,math,sys,time
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from modules.skills.studio3d.tyre_surface import validate,geometry,VERSION
from adapters.studio3d.demonstration_worker import digest_object,topology
from adapters.studio3d.inspection_worker import render_scene,region_inventory

def main():
 folder=Path(sys.argv[sys.argv.index('--')+1]);req=json.loads((folder/'request.json').read_text());source=folder/'source.blend';start=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
 c=validate(req['contract'],req['visible_names']);bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None or o.type not in ('MESH','CURVE') for o in objects.values()):raise ValueError('Source inventory changed')
 targets={p[k] for p in c['pairs'] for k in ('tire','tread')};before={n:digest_object(o) for n,o in objects.items()}
 observed=region_inventory({'regions':{'targets':list(targets)}},objects);specs=[]
 for p in c['pairs']:
  tire=objects[p['tire']];tread=objects[p['tread']];center=Vector(p['center'])
  if any(o.type!='MESH' or o.data.users!=1 or o.modifiers or len(o.data.materials)!=1 for o in (tire,tread)):raise ValueError('Unsupported tyre source topology/modifiers')
  if tire.data.materials[0]!=tread.data.materials[0] or tire.data.materials[0].get('jarvis_coating_role')!='rubber':raise ValueError('Targets must share a declared rubber role')
  if observed[p['tread']]['connected_components']<16:raise ValueError('No repeated disconnected overlay evidence')
  ps=[tire.matrix_world@v.co-center for v in tire.data.vertices];radii=[math.hypot(v.x,v.z) for v in ps];width=max(v.y for v in ps)-min(v.y for v in ps)
  if max(abs(max(v[i] for v in ps)+min(v[i] for v in ps)) for i in range(3))>1e-5:raise ValueError('Declared center is not the source wheel center')
  specs.append((p,max(radii),min(radii),width))
 scene=bpy.context.scene;camera=scene.camera;old=camera.matrix_world.copy();oldscale=camera.data.ortho_scale;oldtype=camera.data.type
 native_before=render_scene(folder,c['inspection'],objects,'before');actions=[];rubbers={}
 for p,outer,inner,width in specs:
  obj=objects[p['tire']];original=obj.data.materials[0]
  if original not in rubbers:
   material=original.copy();material.name='tyre-rubber-local';pbr=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
   incoming=list(pbr.inputs['Base Color'].links)
   if len(incoming)!=1:raise ValueError('Expected source coating graph')
   link=incoming[0];output=link.from_socket;material.node_tree.links.remove(link)
   scale=material.node_tree.nodes.new('ShaderNodeMixRGB');scale.name='Bounded tyre albedo correction';scale.blend_type='MULTIPLY';scale.inputs[0].default_value=1;scale.inputs[2].default_value=(c['rubber_color_scale'],)*3+(1,)
   material.node_tree.links.new(output,scale.inputs[1]);material.node_tree.links.new(scale.outputs[0],pbr.inputs['Base Color']);pbr.inputs['Metallic'].default_value=0
   rubbers[original]=material
  vertices,faces=geometry(outer,inner,width,c['circumference_segments'],c['longitudinal_depth'],c['cross_depth'],c['cross_count'])
  mesh=bpy.data.meshes.new(obj.name+'-continuous-grooved');inverse=obj.matrix_world.inverted();center=Vector(p['center'])
  mesh.from_pydata([inverse@(Vector(v)+center) for v in vertices],[],faces);mesh.materials.append(rubbers[original]);mesh.update()
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
  if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
  bm.to_mesh(mesh);bm.free()
  for face in mesh.polygons:face.use_smooth=True
  obj.data=mesh;t=topology(obj)
  if t['boundary_edges'] or t['overfull_edges'] or t['vertices']<=observed[p['tire']]['vertices']:raise ValueError('Invalid replacement high surface')
  actions.append({'tire':p['tire'],'removed_overlay':p['tread'],'actual_source':observed[p['tire']],'actual_overlay':observed[p['tread']],'outer_radius_preserved':outer,'inner_radius_preserved':inner,'width_preserved':width,'after_topology':t,'rubber_color_scale':c['rubber_color_scale'],'mesh_reduction':False})
  bpy.data.objects.remove(objects.pop(p['tread']),do_unlink=True)
 bpy.context.view_layer.update();after={n:digest_object(o) for n,o in objects.items()}
 unchanged=all(before[n]==after[n] for n in before if n not in targets)
 if not unchanged:raise ValueError('Non-target geometry/material slot changed')
 native_after=render_scene(folder,c['inspection'],objects,'after');camera.matrix_world=old;camera.data.type=oldtype;camera.data.ortho_scale=oldscale
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'before_object_digests':before,'after_object_digests':after,'actions':actions,'views':{'before':native_before,'after':native_after},'unchanged_non_targets':unchanged,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'requires_high_surface_texture_export':True,'removed_objects':[p['tread'] for p in c['pairs']],'after_inventory':region_inventory({'regions':{'tires':[p['tire'] for p in c['pairs']]}},objects),'model_calls':0,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-start,'scope':'Authored exterior tyre refinement; not historical proof, physics or independent Jarvis learning'}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
