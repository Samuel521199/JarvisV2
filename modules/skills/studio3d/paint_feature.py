"""Asset-scoped cosmetic feature attenuation, not a physical wear classifier.

The mask is an authored, source-hash-bound analytic data asset. Selection of
features is not delegated to the model; only a bounded restoration scalar is.
"""
import math,re

SCHEMA='jarvis.studio3d.surface-material.v4'
MASK=('3DModels/PaK38/metadata/demonstrations/paint-feature-scale-evidence-02/broad-feature-mask.png',
      '1df610768eb172edb99278e1c752320dbfa77811ae93ab5fc7f996e77b45d3e7')
TARGETS=('shield-left-0','shield-right-0')
DEPENDENCIES=TARGETS+('shield-left-1','shield-right-1','shield-upper-bridge','fasteners-shield')

def validate(value,names):
 from modules.skills.studio3d.demonstration import validate as validate_demo
 fields={'schema','author','goal','evidence','views','resolution','samples','targets','binding','frame_bounds','restore_strength'}
 if set(value)!=fields or value['schema']!=SCHEMA:raise ValueError('Unexpected feature coating fields')
 if value['targets']!=list(TARGETS) or not set(DEPENDENCIES)<=set(names):raise ValueError('Feature coating target scope')
 binding=value['binding']
 if not isinstance(binding,dict) or set(binding)!={'source_sha256','material_sha256','dependencies'}:raise ValueError('Feature coating source binding')
 if not isinstance(binding['dependencies'],dict) or set(binding['dependencies'])!=set(DEPENDENCIES):raise ValueError('Feature coating dependency scope')
 for digest in [binding['source_sha256'],binding['material_sha256'],*binding['dependencies'].values()]:
  if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Feature coating digest required')
 strength=value['restore_strength']
 if type(strength) not in (int,float) or not math.isfinite(strength) or not .90<=strength<=.98:raise ValueError('Feature restoration envelope')
 bounds=value['frame_bounds']
 if not isinstance(bounds,list) or len(bounds)!=2 or any(not isinstance(p,list) or len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>5 for x in p) for p in bounds):raise ValueError('Feature frame bounds')
 if any(bounds[0][i]>=bounds[1][i] for i in range(3)):raise ValueError('Feature frame extents')
 probe={k:value[k] for k in ('author','goal','evidence','views','resolution','samples')}
 probe.update(schema='jarvis.studio3d.demonstration.v1',actions=[{'tool':'radial_relief','target':names[0],'center':[0,0,0],'axis':[0,1,0],'radial_u':[1,0,0],'inner':.2,'outer':.44,'lobes':8,'phase':0,'amplitude':.01,'reason':'Shared camera contract only; never executed'}])
 validate_demo(probe,names)
 return value
