# SPDX-License-Identifier: GPL-2.0-or-later
"""Authored coating wear, oil and fine paint grain; no measured-scan claim."""
def painted(material,row):
 n=material.node_tree.nodes;links=material.node_tree.links;p=n.get('Principled BSDF')
 base=tuple(p.inputs['Base Color'].default_value)
 def node(kind):return n.new('ShaderNode'+kind)
 geo=node('NewGeometry')
 def noise(scale,detail):
  t=node('TexNoise');t.inputs['Scale'].default_value=scale;t.inputs['Detail'].default_value=detail
  # Position survives evaluation and static merging; Generated coordinates
  # otherwise stretch each part's coating when the parts share one bake mesh.
  links.new(geo.outputs['Position'],t.inputs['Vector']);return t
 def mathop(op,a,b):
  m=node('Math');m.operation=op
  for i,v in enumerate((a,b)):
   if isinstance(v,(float,int)):m.inputs[i].default_value=v
   else:links.new(v,m.inputs[i])
  return m.outputs[0]
 broad=noise(6,3);grain=noise(row.get('micro_scale',185),3);chips=noise(84,2)
 pigment=node('ValToRGB')
 for e,f,pos in zip(pigment.color_ramp.elements,(.55,1.35),(.25,.75)):
  e.position=pos;e.color=tuple(min(1,c*f) for c in base[:3])+(1,)
 links.new(broad.outputs['Fac'],pigment.inputs[0])
 edge=node('MapRange');edge.clamp=True;edge.inputs['From Min'].default_value=.515;edge.inputs['From Max'].default_value=.570
 links.new(geo.outputs['Pointiness'],edge.inputs['Value'])
 broken=mathop('GREATER_THAN',chips.outputs['Fac'],.52);wear=mathop('MULTIPLY',edge.outputs['Result'],broken)
 if row.get('streak_strength',0):
  scratches=node('TexVoronoi');scratches.feature='DISTANCE_TO_EDGE';scratches.inputs['Scale'].default_value=12;links.new(geo.outputs['Position'],scratches.inputs['Vector'])
  thin=mathop('LESS_THAN',scratches.outputs['Distance'],.018);sparse=mathop('GREATER_THAN',chips.outputs['Fac'],.53)
  wear=mathop('MAXIMUM',wear,mathop('MULTIPLY',mathop('MULTIPLY',thin,sparse),row['streak_strength']))
 # Broken fine scratches supplement curvature wear on broad shield surfaces.
 edgecolor=node('MixRGB');links.new(wear,edgecolor.inputs[0]);links.new(pigment.outputs[0],edgecolor.inputs[1]);edgecolor.inputs[2].default_value=(.16,.135,.10,1)
 links.new(edgecolor.outputs[0],p.inputs['Base Color']);links.new(wear,p.inputs['Metallic'])
 rough=node('MapRange');rough.inputs['To Min'].default_value=max(.05,row.get('roughness',.60)-row.get('roughness_variation',.17));rough.inputs['To Max'].default_value=min(.95,row.get('roughness',.60)+row.get('roughness_variation',.16));links.new(grain.outputs['Fac'],rough.inputs['Value']);links.new(rough.outputs['Result'],p.inputs['Roughness'])
 bump=node('Bump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.00022;links.new(grain.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
 p.inputs['Coat Weight'].default_value=.06;p.inputs['Coat Roughness'].default_value=.38
