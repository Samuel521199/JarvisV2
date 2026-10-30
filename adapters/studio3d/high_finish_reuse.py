# SPDX-License-Identifier: GPL-2.0-or-later
"""Exact source fingerprints for reuse of receipt-verified high surface groups.

This is a conservative cache gate, not a shader-equivalence theorem. Any
changed source property, unsupported shader or unpacked image rejects reuse.
"""
import hashlib,json,math
import bpy
from modules.skills.studio3d.high_finish import uv_independent_shader

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def scalar(value):
 if value is None or isinstance(value,(bool,int,str)):return value
 if isinstance(value,float):
  if not math.isfinite(value):raise ValueError('Nonfinite source property')
  return value
 try:return [scalar(v) for v in value]
 except TypeError:raise ValueError('Unsupported source property type')

def properties(value):
 return {p.identifier:scalar(getattr(value,p.identifier)) for p in value.bl_rna.properties if not p.is_readonly and p.type not in ('POINTER','COLLECTION')}

def tree_signature(tree,depth=0):
 if depth>4:raise ValueError('Shader group depth budget')
 if tree.animation_data:raise ValueError('Animated shader reuse not supported')
 rows=[]
 for n in tree.nodes:
  if not n.bl_idname.startswith('ShaderNode') or n.bl_idname in ('ShaderNodeScript','ShaderNodeAttribute','ShaderNodeVertexColor'):raise ValueError('Unsupported shader node')
  if getattr(n,'object',None):raise ValueError('External shader object coordinates not supported for reuse')
  row={'type':n.bl_idname,'name':n.name,'properties':properties(n),'inputs':[(s.identifier,scalar(s.default_value)) for s in n.inputs if hasattr(s,'default_value')],'outputs':[(s.identifier,scalar(s.default_value)) for s in n.outputs if hasattr(s,'default_value')]}
  if hasattr(n,'color_ramp'):row['color_ramp']={'properties':properties(n.color_ramp),'elements':[properties(e) for e in n.color_ramp.elements]}
  for key in ('texture_mapping','color_mapping'):
   if hasattr(n,key):row[key]=properties(getattr(n,key))
  if getattr(getattr(n,'color_mapping',None),'use_color_ramp',False):raise ValueError('Texture color ramp reuse not supported')
  if hasattr(n,'mapping'):raise ValueError('Curve mapping reuse not implemented')
  if getattr(n,'image',None):
   im=n.image
   if not im.packed_file or im.source!='FILE':raise ValueError('Reuse requires packed static file image content')
   row['image']={'sha256':hashlib.sha256(im.packed_file.data).hexdigest(),'source':im.source,'size':list(im.size),'colorspace':im.colorspace_settings.name,'alpha_mode':im.alpha_mode}
  if getattr(n,'node_tree',None):row['group']=tree_signature(n.node_tree,depth+1)
  rows.append(row)
 return {'nodes':rows,'links':[(l.from_node.name,list(l.from_node.outputs).index(l.from_socket),l.to_node.name,list(l.to_node.inputs).index(l.to_socket)) for l in tree.links]}

def group_fingerprints(config,objects,diagnostic_path):
 deps=bpy.context.evaluated_depsgraph_get();materials={};material_records={};object_hashes={};object_records={}
 for name,ob in objects.items():
  mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
  try:
   if len(mesh.color_attributes):raise ValueError('Vertex color reuse not supported')
   geometry={'vertices':[list(ob.matrix_world@v.co) for v in mesh.vertices],'faces':[(list(p.vertices),p.material_index,p.use_smooth) for p in mesh.polygons],'uvs':{uv.name:[list(x.uv) for x in uv.data] for uv in mesh.uv_layers},'normals':[list(n.vector) for n in mesh.corner_normals]}
   slots=[]
   for m in mesh.materials:
    if m is None:raise ValueError('Missing source material')
    if m.animation_data:raise ValueError('Animated material reuse not supported')
    if m.name not in materials:
     material_records[m.name]={'properties':properties(m),'nodes':tree_signature(m.node_tree) if m.use_nodes else None};materials[m.name]=digest(material_records[m.name])
     if not m.use_nodes or not uv_independent_shader(material_records[m.name]['nodes']):raise ValueError('Reuse supports only proven UV-independent world-space coatings')
     for node in m.node_tree.nodes:
      if node.type=='BSDF_PRINCIPLED' and any('anisotropic' in s.name.lower() and s.is_linked for s in node.inputs):raise ValueError('UV-dependent anisotropic coating reuse not supported')
    slots.append(materials[m.name])
   object_records[name]={'geometry':{k:digest(v) for k,v in geometry.items()},'matrix_world':[list(row) for row in ob.matrix_world],'object_name':ob.name,'slots':slots}
   comparable={**object_records[name],'geometry':{k:v for k,v in object_records[name]['geometry'].items() if k!='uvs'}};object_hashes[name]=digest(comparable)
  finally:bpy.data.meshes.remove(mesh)
 groups={g['id']:digest({n:object_hashes[n] for n in g['members']}) for g in config['groups']}
 diagnostic_path.write_text(json.dumps({'groups':groups,'objects':object_records,'materials':material_records},indent=2)+'\n')
 return groups

def verify_source(folder,request,config):
 names=request['visible_names'];reuse=config.get('reuse');evidence={}
 if not reuse:return evidence
 for name,key in [('reuse-source.blend','source_sha256'),('reuse-high.blend','high_sha256')]:
  if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=request['reuse'][key]:raise ValueError('Reuse file changed')
 bpy.ops.wm.open_mainfile(filepath=str(folder/'reuse-source.blend'),load_ui=False,use_scripts=False)
 old={n:bpy.data.objects.get(n) for n in names}
 if any(o is None for o in old.values()):raise ValueError('Reuse source inventory mismatch')
 before=group_fingerprints(config,old,folder/'reuse-source-fingerprints.json')
 bpy.ops.wm.open_mainfile(filepath=str(folder/'source.blend'),load_ui=False,use_scripts=False)
 new={n:bpy.data.objects.get(n) for n in names}
 if any(o is None for o in new.values()):raise ValueError('Current source inventory mismatch')
 after=group_fingerprints(config,new,folder/'current-source-fingerprints.json')
 if any(before[g]!=after[g] for g in reuse['groups']):raise ValueError('Reused group source geometry/material changed')
 return {'export_id':reuse['export_id'],'source_before':before,'source_after':after,'reused_groups':reuse['groups'],'verified':True,'scope':'Exact evaluated geometry/normals/transforms and whitelisted UV-independent world-coating nodes/images/properties. Source UV digest is diagnostic only; mapped groups retain their separately verified atlases. Output is checked and rendered after import.'}

def load_groups(folder,config,originals):
 names=config.get('reuse',{}).get('groups',[])
 if not names:return {}
 for g in config['groups']:
  if g['id'] in names:
   for n in g['members']:originals[n].name='source-'+n
 with bpy.data.libraries.load(str(folder/'reuse-high.blend'),link=False) as (available,loaded):
  if any(n not in available.objects for n in names):raise ValueError('Reused mapped group missing')
  loaded.objects=list(names)
 result={}
 for ob in loaded.objects:
  if ob is None or ob.type!='MESH':raise ValueError('Invalid reused mapped group')
  bpy.context.scene.collection.objects.link(ob)
 bpy.context.view_layer.update()
 for name,ob in zip(names,loaded.objects):
  matrix=ob.matrix_world.copy();ob.parent=None;ob.matrix_world=matrix;ob.name=name;ob.hide_render=True;ob.hide_set(True);result[name]=ob
 bpy.context.view_layer.update()
 for g in config['groups']:
  if g['id'] in result and max(abs(result[g['id']].matrix_world.translation[i]-g['pivot'][i]) for i in range(3))>1e-5:raise ValueError('Reused object origin differs from verified declaration')
 return result
