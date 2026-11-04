"""Receipt-bound, two-panel cosmetic feature attenuation. No geometry edit."""
from sdk.blender_api import require_blender
import json,hashlib,time; bpy = require_blender().bpy
from pathlib import Path
from modules.skills.studio3d.surface_material import VERSION,textures
from adapters.studio3d.spade_frame_worker import dependency
from adapters.studio3d.high_finish_reuse import tree_signature
from adapters.studio3d.demonstration_worker import digest_object
from adapters.studio3d.inspection_worker import render_scene

def signature(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def apply_feature(mat,maskfile,strength):
 clone=mat.copy();clone.name='paint-feature-local';nodes=clone.node_tree.nodes;links=clone.node_tree.links;source_images=[n for n in nodes if n.type=='TEX_IMAGE'];assert len(source_images)==3
 image=bpy.data.images.load(str(maskfile),check_existing=False);image.colorspace_settings.name='Non-Color';image.pack();image.name='PaK38-thick-source-feature-data'
 # Only copy the existing colour-mixing branch, retaining its exact world
 # coordinate and geometric-normal weight inputs. No UV or attribute added.
 image_names={n.name for n in source_images};has_cache={};copies={}
 def has_image(n):
  if n.name not in has_cache:has_cache[n.name]=n.name in image_names or any(has_image(l.from_node) for s in n.inputs for l in s.links)
  return has_cache[n.name]
 def copy_branch(socket):
  n=socket.node
  if not has_image(n):return socket
  if n.name not in copies:
   assert n.type in ('TEX_IMAGE','VECT_MATH'),n.type
   q=nodes.new(n.bl_idname);copies[n.name]=q;q.label='Analytic feature mask: '+n.name
   if n.type=='TEX_IMAGE':
    q.image=image
    for key in ('projection','projection_blend','interpolation','extension'):setattr(q,key,getattr(n,key))
   else:q.operation=n.operation
   for i,s in enumerate(n.inputs):
    if s.is_linked:links.new(copy_branch(s.links[0].from_socket),q.inputs[i])
    elif hasattr(s,'default_value'):q.inputs[i].default_value=s.default_value
  return copies[n.name].outputs[list(n.outputs).index(socket)]
 original_colour=nodes['Separate Color'].inputs[0].links[0].from_socket
 mapped=copy_branch(original_colour);assert image_names.issubset(copies)
 split=nodes.new('ShaderNodeSeparateColor');links.new(mapped,split.inputs[0])
 bounded=nodes.new('ShaderNodeClamp');bounded.inputs['Min'].default_value=0;bounded.inputs['Max'].default_value=1;links.new(split.outputs['Red'],bounded.inputs['Value'])
 amount=nodes.new('ShaderNodeMath');amount.operation='MULTIPLY';amount.inputs[1].default_value=strength;links.new(bounded.outputs[0],amount.inputs[0]);amount.name='jarvis_thick_feature_restore'
 def find_mix(a,b):
  matches=[n for n in nodes if n.type=='MIX_RGB' and n.blend_type=='MIX' and not n.inputs[1].is_linked and not n.inputs[2].is_linked and all(abs(x-y)<1e-7 for x,y in zip(n.inputs[1].default_value,a)) and all(abs(x-y)<1e-7 for x,y in zip(n.inputs[2].default_value,b))]
  assert len(matches)==1;return matches[0].outputs[0]
 intact=find_mix((.032,.039,.046,1),(.043,.050,.057,1));rough=find_mix((.38,.38,.38,1),(.53,.53,.53,1));p=nodes['Principled BSDF'];normal=p.inputs['Normal'].links[0].from_socket
 for key,value in [('Base Color',intact),('Metallic',(0,0,0,1)),('Roughness',rough)]:
  socket=p.inputs[key];old=socket.links[0].from_socket;mix=nodes.new('ShaderNodeMixRGB');links.new(amount.outputs[0],mix.inputs[0]);links.new(old,mix.inputs[1])
  if isinstance(value,bpy.types.NodeSocket):links.new(value,mix.inputs[2])
  else:mix.inputs[2].default_value=value
  links.new(mix.outputs[0],socket)
 assert p.inputs['Normal'].links[0].from_socket==normal
 return clone,sorted(copies)

def run(folder,req,c,objects,source,began):
 binding=c['binding']
 if req['source_sha256']!=binding['source_sha256']:raise ValueError('Feature source byte binding changed')
 before={n:dependency(o)[0] for n,o in objects.items()}
 for n,expected in binding['dependencies'].items():
  if before[n]!=expected:raise ValueError('Feature object dependency changed: '+n)
 targets=c['targets'];mat=objects[targets[0]].data.materials[0]
 if mat is None or mat.get('jarvis_coating_role')!='paint':raise ValueError('Feature edit needs painted source')
 if any(list(objects[n].data.materials)!=[mat] or objects[n].data.users!=1 for n in targets):raise ValueError('Feature target material or shared data mismatch')
 original=tree_signature(mat.node_tree)
 if signature(original)!=binding['material_sha256']:raise ValueError('Feature source shader changed')
 original_materials={m:tree_signature(m.node_tree) for o in objects.values() for m in o.data.materials if m and m.use_nodes}
 geometry={n:digest_object(o,material_slots=False) for n,o in objects.items()};digests_before={n:digest_object(o) for n,o in objects.items()}
 config={'regions':{'panel':targets},'focus_region':'panel','bounds':c['frame_bounds'],'resolution':c['resolution'],'samples':c['samples'],'views':[{'id':v['id'],'direction':v['direction'],'lighting':'neutral'} for v in c['views']]}
 bpy.context.scene.cycles.seed=4;pre=render_scene(folder,config,objects,'before')
 clone,copied=apply_feature(mat,folder/'texture-feature-mask.png',c['restore_strength'])
 for name in targets:objects[name].data.materials[0]=clone
 if any(tree_signature(m.node_tree)!=sig for m,sig in original_materials.items()):raise ValueError('Original material changed')
 if any(digest_object(o,material_slots=False)!=geometry[n] for n,o in objects.items()):raise ValueError('Feature edit changed geometry')
 untouched=[n for n in objects if n not in targets]
 if any(dependency(objects[n])[0]!=before[n] for n in untouched):raise ValueError('Feature edit changed non-target dependency')
 target_signature=tree_signature(clone.node_tree)
 post=render_scene(folder,config,objects,'after')
 for a,b in zip(pre['views'],post['views']):
  for k in ('direction','camera_position','ortho_scale','lighting'):
   if a[k]!=b[k]:raise ValueError('Feature comparison conditions changed')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source file changed')
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 report={'version':VERSION,'author':c['author'],'views':[{'stage':stage,'view':v['view'],'file':v['file'],'camera':v,'real_blender_render':True} for stage,r in [('before',pre),('after',post)] for v in r['views']],
 'before_object_digests':digests_before,'after_object_digests':{n:digest_object(o) for n,o in objects.items()},'geometry_and_transform_unchanged':True,'non_target_object_slots_unchanged':True,'untouched_objects':untouched,'non_target_dependencies_unchanged':len(untouched),'source_unchanged':True,'source_coating_preserved':True,'source_textures':textures(c),'target_signature_sha256':signature(target_signature),'original_materials_unchanged':True,'original_normal_input_preserved':True,'copied_mapping_nodes':copied,'restore_strength':c['restore_strength'],'before':pre,'after':post,'requires_high_surface_texture_export':True,'unbaked_glb_material_fidelity':'NOT_PRESERVED_DO_NOT_PUBLISH','user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-began,
 'limitations':['Author-prepared source-specific image mask; not autonomous feature diagnosis or physical material classification.','Nearby thin marks can also enter the mask. Not a general material recipe.','Static native views do not prove dynamic reflections or exported fidelity.']}
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
