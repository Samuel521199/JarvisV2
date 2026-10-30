# SPDX-License-Identifier: GPL-2.0-or-later
"""Material-only authored weathering, with unchanged geometry and paired renders."""
import hashlib,json,sys,time
from pathlib import Path
import bpy
from mathutils import Vector
from adapters.studio3d.demonstration_worker import digest_object
from modules.skills.studio3d.surface_material import validate,VERSION,TEXTURES

def overlay_damage(mat,regions):
 """Add sparse bounded wear without reconstructing the source paint graph."""
 if mat.get('jarvis_damage_regions'):raise ValueError('Do not stack damage overlays on an already modified material')
 nodes=mat.node_tree.nodes;links=mat.node_tree.links
 shaders=[n for n in nodes if n.type=='BSDF_PRINCIPLED']
 if len(shaders)!=1:raise ValueError('Overlay needs one known paint shader')
 p=shaders[0];before_nodes=set(nodes)
 def node(kind):return nodes.new('ShaderNode'+kind)
 def op(kind,a,b):
  n=node('Math');n.operation=kind
  for i,v in enumerate((a,b)):
   if isinstance(v,(float,int)):n.inputs[i].default_value=v
   else:links.new(v,n.inputs[i])
  return n.outputs[0]
 def ramp(v,a,b):
  n=node('MapRange');n.clamp=True;n.inputs['From Min'].default_value=a;n.inputs['From Max'].default_value=b;links.new(v,n.inputs['Value']);return n.outputs['Result']
 def mix(f,a,b):
  n=node('MixRGB');links.new(f,n.inputs[0])
  for i,v in enumerate((a,b),1):
   if isinstance(v,(int,float)):n.inputs[i].default_value=(v,v,v,1)
   elif isinstance(v,tuple):n.inputs[i].default_value=v
   else:links.new(v,n.inputs[i])
  return n.outputs[0]
 geo=node('NewGeometry')
 def noise(scale):
  n=node('TexNoise');n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=2;links.new(geo.outputs['Position'],n.inputs['Vector']);return n.outputs['Fac']
 mask=0;pattern=op('ADD',op('MULTIPLY',noise(96),.65),op('MULTIPLY',noise(29),.35))
 for region in regions:
  d=node('VectorMath');d.operation='SUBTRACT';links.new(geo.outputs['Position'],d.inputs[0]);d.inputs[1].default_value=region['center']
  scale=node('VectorMath');scale.operation='DIVIDE';links.new(d.outputs['Vector'],scale.inputs[0]);scale.inputs[1].default_value=region['radii']
  length=node('VectorMath');length.operation='LENGTH';links.new(scale.outputs['Vector'],length.inputs[0])
  support=op('SUBTRACT',1,ramp(length.outputs['Value'],.1,1))
  chip=ramp(op('ADD',pattern,op('MULTIPLY',support,.40*region['coverage'])),.674,.686)
  chip=op('MULTIPLY',chip,op('SUBTRACT',1,ramp(length.outputs['Value'],.94,1)))
  mask=op('MAXIMUM',mask,chip)
 mask.node.name='jarvis_damage_mask'
 oxidation=ramp(noise(24),.42,.65);oxide=mix(noise(110),(.042,.030,.022,1),(.075,.055,.035,1))
 replacements={'Base Color':mix(oxidation,(.10,.115,.13,1),oxide),'Metallic':op('MULTIPLY',.82,op('SUBTRACT',1,oxidation)),'Roughness':mix(oxidation,(.34,.34,.34,1),(.79,.79,.79,1))}
 for key,replacement in replacements.items():
  inp=p.inputs[key];original=inp.links[0].from_socket if inp.is_linked else tuple(inp.default_value) if key=='Base Color' else inp.default_value
  links.new(mix(mask,original,replacement),inp)
 bump=node('Bump');bump.inputs['Distance'].default_value=.000015;bump.inputs['Strength'].default_value=.4;links.new(op('SUBTRACT',1,mask),bump.inputs['Height'])
 if p.inputs['Normal'].is_linked:links.new(p.inputs['Normal'].links[0].from_socket,bump.inputs['Normal'])
 links.new(bump.outputs['Normal'],p.inputs['Normal'])
 if not before_nodes<=set(nodes):raise ValueError('Overlay removed source shader nodes')
 mat['jarvis_damage_regions']=json.dumps(regions);mat['jarvis_source_coating_preserved']=True

def coating(mat,role,folder,c,local_wear=None,damage_regions=None):
 if 'jarvis_damage_regions' in mat:del mat['jarvis_damage_regions']
 n=mat.node_tree.nodes;links=mat.node_tree.links;n.clear()
 def node(kind):return n.new('ShaderNode'+kind)
 p=node('BsdfPrincipled');p.name='Principled BSDF';out=node('OutputMaterial');links.new(p.outputs[0],out.inputs['Surface'])
 def mathop(op,a,b):
  m=node('Math');m.operation=op
  for i,v in enumerate((a,b)):
   if isinstance(v,(int,float)):m.inputs[i].default_value=v
   else:links.new(v,m.inputs[i])
  return m.outputs[0]
 def ramp(v,a,b):
  m=node('MapRange');m.clamp=True;m.inputs['From Min'].default_value=a;m.inputs['From Max'].default_value=b;links.new(v,m.inputs['Value']);return m.outputs['Result']
 def mix(f,a,b):
  m=node('MixRGB')
  for i,v in enumerate((f,a,b)):
   if isinstance(v,(int,float)):m.inputs[i].default_value=v
   elif isinstance(v,tuple):m.inputs[i].default_value=v
   else:links.new(v,m.inputs[i])
  return m.outputs[0]
 geo=node('NewGeometry')
 def noise(scale):
  m=node('TexNoise');m.inputs['Scale'].default_value=scale;m.inputs['Detail'].default_value=2;links.new(geo.outputs['Position'],m.inputs['Vector']);return m.outputs['Fac']
 grain=noise(650);broad=noise(9)
 if role=='dark':
  p.inputs['Base Color'].default_value=(.012,.013,.015,1);p.inputs['Roughness'].default_value=.67;return
 image=node('TexImage');image.image=bpy.data.images.load(str(folder/('texture-'+('paint' if role=='steel' else role)+'.png')),check_existing=True);image.image.pack();image.projection='BOX';image.projection_blend=.2
 scale=node('VectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=1/c['tile_span'];links.new(geo.outputs['Position'],scale.inputs[0]);links.new(scale.outputs[0],image.inputs['Vector'])
 color=image.outputs['Color'];sep=node('SeparateColor');links.new(color,sep.inputs[0]);bw=node('RGBToBW');links.new(color,bw.inputs[0])
 rust=ramp(mathop('SUBTRACT',sep.outputs['Red'],sep.outputs['Blue']),.015,.07)
 scratch=mathop('MULTIPLY',ramp(bw.outputs[0],.125,.25),mathop('SUBTRACT',1,rust))
 edge=mathop('MULTIPLY',ramp(geo.outputs['Pointiness'],.52,.59),ramp(noise(95),.48,.73))
 if local_wear:
  bevel=node('Bevel');bevel.samples=4;bevel.inputs['Radius'].default_value=local_wear['edge_radius'];links.new(geo.outputs['Normal'],bevel.inputs['Normal'])
  distance=node('VectorMath');distance.operation='DISTANCE';links.new(geo.outputs['Normal'],distance.inputs[0]);links.new(bevel.outputs['Normal'],distance.inputs[1])
  edge=mathop('MULTIPLY',ramp(distance.outputs['Value'],.035,.25),ramp(noise(95),.40,.70))
 edge=mathop('MULTIPLY',edge,c['edge_wear'])
 exposed=mathop('MAXIMUM',scratch,edge)
 ao=node('AmbientOcclusion');ao.inputs['Distance'].default_value=.045;ao.samples=8;ao.only_local=False
 dirt=mathop('MULTIPLY',mathop('SUBTRACT',1,ao.outputs['AO']),c['cavity_dirt'])
 z=node('SeparateXYZ');links.new(geo.outputs['Position'],z.inputs[0]);low=mathop('SUBTRACT',1,ramp(z.outputs['Z'],.02,.35))
 dust=mathop('MULTIPLY',mathop('MULTIPLY',low,broad),c['ground_dust'])
 if role=='rubber':
  base=mix(.68,color,(.008,.010,.012,1));metal=0;rough=mix(broad,(.72,.72,.72,1),(.87,.87,.87,1))
 elif role=='steel':
  base=mix(mathop('MULTIPLY',rust,.65),(.085,.10,.115,1),color);metal=mathop('MULTIPLY',.88,mathop('SUBTRACT',1,rust));rough=mix(rust,(c['steel_roughness'],)*3+(1,),(.75,.75,.75,1))
 else:
  pigment=node('MixRGB');pigment.blend_type='MULTIPLY';pigment.inputs[0].default_value=1;links.new(color,pigment.inputs[1]);pigment.inputs[2].default_value=(.50,.57,.64,1)
  # Keep most large painted faces intact. Generic tile contrast must not make
  # every flat face look like aggregate stone; reinforce wear at contact and
  # bounded broken edges, plus sparse broad patches rather than uniform flecks.
  intact=mix(broad,(.032,.039,.046,1),(.043,.050,.057,1))
  detail=mathop('ADD',.38,mathop('ADD',mathop('MULTIPLY',ramp(noise(3),.55,.76),.24),mathop('ADD',mathop('MULTIPLY',edge,1.8),mathop('MULTIPLY',dirt,.7))))
  if local_wear:
   detail=mathop('ADD',local_wear['base_detail'],mathop('ADD',mathop('MULTIPLY',ramp(noise(3),.58,.76),local_wear['patch_strength']),mathop('ADD',mathop('MULTIPLY',edge,1.8),mathop('MULTIPLY',dirt,.7))))
  detail=mathop('MINIMUM',.85,detail)
  base=mix(mathop('MULTIPLY',rust,.55),pigment.outputs[0],color)
  if role!='spade':base=mix(detail,intact,base)
  if role!='spade':exposed=mathop('MULTIPLY',exposed,detail)
  base=mix(edge,base,(.12,.14,.16,1));metal=mathop('MULTIPLY',exposed,mathop('SUBTRACT',1,rust));rough=mix(broad,(c['paint_roughness']-.05,)*3+(1,),(c['paint_roughness']+.10,)*3+(1,));rough=mix(exposed,rough,(.31,.31,.31,1));rough=mix(rust,rough,(.78,.78,.78,1))
 if damage_regions:
  # Explicit artist-declared regions control WHERE chips can appear. Noise
  # breaks their contour, rather than making every intact face equally dirty.
  damage=0;pattern=mathop('ADD',mathop('MULTIPLY',noise(96),.65),mathop('MULTIPLY',noise(29),.35))
  for region in damage_regions:
   delta=node('VectorMath');delta.operation='SUBTRACT';links.new(geo.outputs['Position'],delta.inputs[0]);delta.inputs[1].default_value=region['center']
   normalized=node('VectorMath');normalized.operation='DIVIDE';links.new(delta.outputs['Vector'],normalized.inputs[0]);normalized.inputs[1].default_value=region['radii']
   length=node('VectorMath');length.operation='LENGTH';links.new(normalized.outputs['Vector'],length.inputs[0])
   support=mathop('SUBTRACT',1,ramp(length.outputs['Value'],.1,1))
   mask=ramp(mathop('ADD',pattern,mathop('MULTIPLY',support,.40*region['coverage'])),.674,.686)
   mask=mathop('MULTIPLY',mask,mathop('SUBTRACT',1,ramp(length.outputs['Value'],.94,1)))
   damage=mathop('MAXIMUM',damage,mask)
  damage.node.name='jarvis_damage_mask'
  oxidation=ramp(noise(24),.42,.65)
  oxide=mix(noise(110),(.042,.030,.022,1),(.075,.055,.035,1))
  chip=mix(oxidation,(.10,.115,.13,1),oxide)
  base=mix(damage,base,chip)
  metal=mix(damage,(metal,metal,metal,1) if isinstance(metal,(int,float)) else metal,mathop('MULTIPLY',.82,mathop('SUBTRACT',1,oxidation)))
  rough=mix(damage,rough,mix(oxidation,(.34,.34,.34,1),(.79,.79,.79,1)))
  mat['jarvis_damage_regions']=json.dumps(damage_regions)
 base=mix(dirt,base,(.025,.022,.018,1));base=mix(dust,base,(.095,.078,.056,1));links.new(base,p.inputs['Base Color'])
 if isinstance(metal,(int,float)):p.inputs['Metallic'].default_value=metal
 else:links.new(mathop('MULTIPLY',metal,mathop('SUBTRACT',1,mathop('MAXIMUM',dirt,dust))),p.inputs['Metallic'])
 rough=mix(mathop('MAXIMUM',dirt,dust),rough,(.82,.82,.82,1))
 rough=mathop('ADD',rough,mathop('MULTIPLY',mathop('SUBTRACT',noise(220),.5),.24));links.new(rough,p.inputs['Roughness'])
 bump=node('Bump');bump.inputs['Distance'].default_value=c['bump_distance'];bump.inputs['Strength'].default_value=.24;links.new(mathop('SUBTRACT',grain,mathop('MULTIPLY',damage,.75)) if damage_regions else grain,bump.inputs['Height']);links.new(bump.outputs[0],p.inputs['Normal'])
 p.inputs['Coat Weight'].default_value=0
 from tools.studio3d_blender_material_projection import replace_world_box_projection
 replace_world_box_projection(mat)
 mat['jarvis_coating_role']=role;mat['jarvis_finish_scope']='Authored visual wear; not a measured historic surface'

def main():
 folder=Path(sys.argv[sys.argv.index('--')+1]);req=json.loads((folder/'request.json').read_text());source=folder/'source.blend';began=time.monotonic()
 if hashlib.sha256(source.read_bytes()).hexdigest()!=req['source_sha256']:raise ValueError('Source changed')
 c=validate(req['contract'],req['visible_names'])
 for role,(_,expected) in TEXTURES.items():
  if hashlib.sha256((folder/('texture-'+role+'.png')).read_bytes()).hexdigest()!=expected:raise ValueError('Texture source changed')
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 objects={n:bpy.data.objects.get(n) for n in req['visible_names']}
 if any(o is None or o.type not in ('MESH','CURVE') for o in objects.values()):raise ValueError('Inventory mismatch')
 before={n:digest_object(o) for n,o in objects.items()};materials={m for o in objects.values() for m in o.data.materials}
 geometry_before={n:digest_object(o,material_slots=False) for n,o in objects.items()};scoped=c['schema']!='jarvis.studio3d.surface-material.v1';overlay=c['schema']=='jarvis.studio3d.surface-material.v3'
 if not scoped and {m.name for m in materials}!={'paint','steel','dark','rubber'}:raise ValueError('Unsupported source material roles')
 if scoped:
  for name in c['targets']:
   if not objects[name].data.materials or any(m is None or m.get('jarvis_coating_role')!='paint' for m in objects[name].data.materials):raise ValueError('Local operation supports verified painted targets only; rubber/steel/spade excluded')
  for region in c.get('damage_regions',[]):
   def overlaps(ob):
    points=[ob.matrix_world@Vector(v) for v in ob.bound_box]
    return all(region['center'][i]+region['radii'][i]>=min(p[i] for p in points) and region['center'][i]-region['radii'][i]<=max(p[i] for p in points) for i in range(3))
   if not any(overlaps(objects[n]) for n in c['targets']):raise ValueError('Damage region does not overlap any declared target bounds')
 scene=bpy.context.scene;camera=scene.camera;old=camera.matrix_world.copy();oldtype=camera.data.type;oldscale=camera.data.ortho_scale
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=c['samples'];scene.cycles.seed=4;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=4
 scene.render.resolution_x,scene.render.resolution_y=c['resolution'];scene.render.resolution_percentage=100;camera.data.type='ORTHO';camera.data.sensor_fit='HORIZONTAL';views=[]
 def render(stage):
  for v in c['views']:
   center=Vector(v['center']);camera.location=center+Vector(v['direction']).normalized()*v['ortho_scale']*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=v['ortho_scale'];scene.render.filepath=str(folder/(stage+'-'+v['id']+'.png'));bpy.context.view_layer.update();bpy.ops.render.render(write_still=True)
   views.append({'stage':stage,'view':v['id'],'file':Path(scene.render.filepath).name,'camera':v,'real_blender_render':True})
 render('before')
 overrides=[]
 if scoped:
  copies={}
  for name in c['targets']:
   ob=objects[name]
   if ob.data.users!=1:raise ValueError('Shared geometry material slots cannot be edited locally')
   for i,m in enumerate(ob.data.materials):
    if m not in copies:
     clone=m.copy();clone.name='paint-localized'
     if overlay:overlay_damage(clone,c['damage_regions'])
     else:coating(clone,'paint',folder,c['settings'],c['local_wear'],c.get('damage_regions'))
     copies[m]=clone
    ob.data.materials[i]=copies[m];overrides.append({'object':name,'slot':i,'from':m.name,'to':copies[m].name})
 else:
  for mat in materials:coating(mat,mat.name,folder,c['settings'])
  spade=bpy.data.materials['paint'].copy();spade.name='soil-contact-steel';coating(spade,'spade',folder,c['settings'])
  for name in c['spades']:
   ob=objects[name]
   for i,m in enumerate(ob.data.materials):
    if m.name=='paint':ob.data.materials[i]=spade;overrides.append({'object':name,'slot':i,'from':'paint','to':spade.name})
 after={n:digest_object(o) for n,o in objects.items()};geometry_after={n:digest_object(o,material_slots=False) for n,o in objects.items()}
 untouched=[n for n in objects if scoped and n not in c['targets']]
 if geometry_before!=geometry_after or any(before[n]!=after[n] for n in untouched):raise ValueError('Material edit changed geometry or non-target slots')
 render('after');camera.matrix_world=old;camera.data.type=oldtype;camera.data.ortho_scale=oldscale
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model.blend'),compress=True)
 # BOX/world-space coating cannot be exported as UV textures directly. This
 # stage intentionally produces editable BLEND only. The separate high_finish
 # tool makes mapped surfaces and validates/reimports the actual final GLB.
 report={'version':VERSION,'author':c['author'],'views':views,'before_object_digests':before,'after_object_digests':after,'geometry_and_transform_unchanged':geometry_before==geometry_after,'non_target_object_slots_unchanged':all(before[n]==after[n] for n in untouched),'untouched_objects':untouched,'slot_overrides':overrides,'material_settings':c.get('settings'),'local_wear':c.get('local_wear'),'source_coating_preserved':overlay,'source_textures':TEXTURES,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==req['source_sha256'],'unbaked_glb_material_fidelity':'NOT_PRESERVED_DO_NOT_PUBLISH','requires_high_surface_texture_export':True,'user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-began}
 report['damage_regions']=c.get('damage_regions',[])
 (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
