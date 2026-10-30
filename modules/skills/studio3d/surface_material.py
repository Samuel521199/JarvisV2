"""Bounded game-art coating edit; fixed, receipt-bound texture sources."""
import math
from modules.skills.studio3d.demonstration import validate as validate_demo

VERSION='1.6.0'
TEXTURES={
 'paint':('3DModels/leFH18/textures/source/worn-painted-steel-basecolor.png','3bebaf27d958b40eaec999f20601f0e35e26c497b4602669f80f1169a880da74'),
 'rubber':('3DModels/leFH18/textures/source/aged-rubber-basecolor.png','229dcfc899619a82e54cdced483a124c0f31897a25b5f821f4ccb2a78b364709'),
 'spade':('3DModels/leFH18/textures/source/worn-spade-basecolor-v2.png','b8a99f89687c593363ec709493f8e45a4a6898f53233f70db77233eade8dfcc7')}

def validate(value,names):
 if not isinstance(value,dict):raise ValueError('Unexpected coating fields')
 overlay=value.get('schema')=='jarvis.studio3d.surface-material.v3'
 scoped=value.get('schema') in ('jarvis.studio3d.surface-material.v2','jarvis.studio3d.surface-material.v3')
 fields={'schema','author','goal','evidence','views','resolution','samples'}|({'targets','damage_regions'} if overlay else {'settings'}|({'targets','local_wear'} if scoped else {'spades'}))
 if not fields<=set(value) or set(value)-fields-({'damage_regions'} if scoped else set()):raise ValueError('Unexpected coating fields')
 if value['schema'] not in ('jarvis.studio3d.surface-material.v1','jarvis.studio3d.surface-material.v2','jarvis.studio3d.surface-material.v3') or not names:raise ValueError('Invalid coating schema or inventory')
 # Reuse the already bounded demonstration camera/author contract.
 probe={k:value[k] for k in ('author','goal','evidence','views','resolution','samples')}
 probe.update(schema='jarvis.studio3d.demonstration.v1',actions=[{'tool':'radial_relief','target':names[0],'center':[0,0,0],'axis':[0,1,0],'radial_u':[1,0,0],'inner':.2,'outer':.44,'lobes':8,'phase':0,'amplitude':.01,'reason':'Validation of shared fixed cameras only; never executed'}])
 validate_demo(probe,names)
 limits={'tile_span':(.4,1.5),'paint_roughness':(.36,.68),'steel_roughness':(.24,.52),'edge_wear':(.1,.65),'cavity_dirt':(.1,.65),'ground_dust':(0,.3),'bump_distance':(0,.00009)}
 settings=value.get('settings',{})
 if not isinstance(settings,dict) or (not overlay and set(settings)!=set(limits)):raise ValueError('Invalid coating settings')
 for key,(lo,hi) in (limits.items() if not overlay else []):
  v=settings[key]
  if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Coating envelope exceeded: '+key)
 if scoped:
  targets=value['targets']
  if not isinstance(targets,list) or not 1<=len(targets)<=12 or any(not isinstance(n,str) for n in targets) or len(set(targets))!=len(targets) or any(n not in names for n in targets):raise ValueError('Invalid local paint targets')
  wear=value.get('local_wear',{});limits={'base_detail':(.04,.18),'patch_strength':(.15,.85),'edge_radius':(.0005,.003)}
  if not isinstance(wear,dict) or (not overlay and set(wear)!=set(limits)):raise ValueError('Invalid local wear controls')
  for k,(lo,hi) in (limits.items() if not overlay else []):
   if type(wear[k]) not in (int,float) or not math.isfinite(wear[k]) or not lo<=wear[k]<=hi:raise ValueError('Local wear envelope exceeded')
  if 'damage_regions' in value:
   regions=value['damage_regions']
   if not isinstance(regions,list) or not 1<=len(regions)<=8:raise ValueError('Damage region budget')
   for region in regions:
    if not isinstance(region,dict) or set(region)!={'center','radii','coverage'}:raise ValueError('Invalid damage region')
    for key,lo,hi in [('center',-4,4),('radii',.015,.4)]:
     v=region[key]
     if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi for x in v):raise ValueError('Invalid bounded damage extent')
    if type(region['coverage']) not in (int,float) or not math.isfinite(region['coverage']) or not .15<=region['coverage']<=.85:raise ValueError('Damage coverage envelope exceeded')
 else:
  spades=value['spades']
  if not isinstance(spades,list) or len(spades)>8 or len(set(spades))!=len(spades) or any(n not in names for n in spades):raise ValueError('Invalid spade targets')
 return value
