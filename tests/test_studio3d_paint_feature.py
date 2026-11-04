import copy,unittest
from modules.skills.studio3d.surface_material import validate,textures
from modules.skills.studio3d.paint_feature import TARGETS,DEPENDENCIES,MASK

class PaintFeature(unittest.TestCase):
 def contract(self):
  return {'schema':'jarvis.studio3d.surface-material.v4','author':'Codex','goal':'Test bounded image feature material','evidence':'Recorded local mask and paired native renders','views':[{'id':'front','center':[0,0,1],'direction':[1,0,.08],'ortho_scale':2}],'resolution':[1280,960],'samples':12,'targets':list(TARGETS),'frame_bounds':[[-.2,-.9,.6],[.3,.9,1.5]],'restore_strength':.95,'binding':{'source_sha256':'a'*64,'material_sha256':'b'*64,'dependencies':{n:'c'*64 for n in DEPENDENCIES}}}
 def test_accepts_only_bounded_existing_target_scope(self):
  c=self.contract();validate(c,list(DEPENDENCIES));self.assertEqual(textures(c)['feature-mask'],MASK)
 def test_model_cannot_supply_image_code_geometry_or_new_material_controls(self):
  for patch in [{'mask':'external.png'},{'python':'code'},{'damage_regions':[]},{'settings':{}},{'targets':['shield-left-1']},{'targets':list(TARGETS)*2},{'resolution':[8192,8192]}]:
   c=self.contract();c.update(patch)
   with self.assertRaises(ValueError):validate(c,list(DEPENDENCIES))
 def test_limits_require_finite_numbers_not_boolean(self):
  for strength in (.89,.99,True,float('nan'),float('inf'),'0.95'):
   c=self.contract();c['restore_strength']=strength
   with self.assertRaises(ValueError):validate(c,list(DEPENDENCIES))
 def test_complete_source_shader_and_neighbor_bindings_required(self):
  for patch in [{'source_sha256':'changed'},{'material_sha256':'a'*63},{'dependencies':{TARGETS[0]:'c'*64}},{'extra':'digest'}]:
   c=self.contract();c['binding'].update(patch)
   with self.assertRaises(ValueError):validate(c,list(DEPENDENCIES))
 def test_invalid_frame_or_missing_inventory_rejected(self):
  for bounds in ([],[[0,0,0],[0,1,1]],[[0,0,0],[float('nan'),1,1]],[[0,0,0],[10,1,1]]):
   c=self.contract();c['frame_bounds']=bounds
   with self.assertRaises(ValueError):validate(c,list(DEPENDENCIES))
  with self.assertRaises(ValueError):validate(self.contract(),list(TARGETS))
 def test_existing_schemas_do_not_add_unused_mask_requirement(self):
  self.assertNotIn('feature-mask',textures({'schema':'jarvis.studio3d.surface-material.v3'}))
 def test_scalar_clamp_does_not_admit_implicit_coordinates_or_unknown_ancestors(self):
  from modules.skills.studio3d.high_finish import uv_independent_shader
  s={'nodes':[{'type':'ShaderNodeNewGeometry','name':'world','inputs':[]},{'type':'ShaderNodeTexImage','name':'mask','inputs':[]},{'type':'ShaderNodeClamp','name':'clamp','inputs':[['Min',0],['Max',1]]}],'links':[['world',0,'mask',0],['mask',0,'clamp',0]]}
  self.assertTrue(uv_independent_shader(s))
  bad=copy.deepcopy(s);bad['links']=bad['links'][1:];self.assertFalse(uv_independent_shader(bad))
  for node in ('ShaderNodeAttribute','ShaderNodeTexCoord','ShaderNodeUVMap','ShaderNodeScript','ShaderNodeGroup'):
   bad=copy.deepcopy(s);bad['nodes'].append({'type':node,'name':'bad','inputs':[]});self.assertFalse(uv_independent_shader(bad))

if __name__=='__main__':unittest.main()
