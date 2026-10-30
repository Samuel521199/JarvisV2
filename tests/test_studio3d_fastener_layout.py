import copy,math,unittest
from modules.skills.studio3d.fastener_layout import validate,rotate_x_to_normal,bound_component,SCHEMA
from modules.skills.studio3d.attachment_seat import validate as dispatch

def contract():
 names=['heads','sheet','tabs'];c={'schema':SCHEMA,'author':'Codex','evidence':'Measured component and visual-reference target','object':'heads','source_digest':'a'*64,'targets':[{'indices':list(range(14)),'center':[0,.4,1.3],'support':'sheet','yz':[.365,1.35]}],'blockers':['tabs'],'max_move':.65,'embed':.0006,'inspection':{'views':[{'id':'front','direction':[1,0,0]}],'bounds':[[-1,-1,0],[1,1,2]],'resolution':[960,640],'samples':16,'regions':{'shield':names},'focus_region':'shield'}};return c,names

class Layout(unittest.TestCase):
 def test_contract_dispatch_and_fixed_envelopes(self):
  c,n=contract();self.assertEqual(dispatch(c,n),c)
  for key,value in [('max_move',2),('embed',0),('source_digest','bad'),('python','bad')]:
   with self.subTest(key=key),self.assertRaises(ValueError):validate({**c,key:value},n)
 def test_unique_complete_component_binding(self):
  self.assertEqual(bound_component([[0,1,2],[3,4]], [4,3]),[4,3])
  for ids in ([1,2],[0,1,2,3],[99]):
   with self.assertRaises(ValueError):bound_component([[0,1,2],[3,4]],ids)
 def test_duplicate_indices_and_overlap_selection_rejected(self):
  c,n=contract();c['targets']*=2
  with self.assertRaises(ValueError):validate(c,n)
  c,n=contract();c['targets'][0]['indices']=[0]*14
  with self.assertRaises(ValueError):validate(c,n)
 def test_cross_side_or_outside_targets_rejected(self):
  for yz in ([-.365,1.35],[.1,1.3],[.4,1.9],[float('nan'),1.2]):
   c,n=contract();c['targets'][0]['yz']=yz
   with self.assertRaises(ValueError):validate(c,n)
 def test_minimal_rotation_preserves_lengths_and_maps_axis(self):
  n=[math.sqrt(.8),.2,.4];r=rotate_x_to_normal([1,0,0],n)
  for a,b in zip(r,n):self.assertAlmostEqual(a,b)
  p=[.015,.012,-.004];r=rotate_x_to_normal(p,n);self.assertAlmostEqual(sum(v*v for v in r),sum(v*v for v in p))
  self.assertAlmostEqual(sum(a*b for a,b in zip(r,n)),p[0])
 def test_reject_backfacing_or_invalid_normal(self):
  for n in ([0,1,0],[-1,0,0],[2,0,0],[float('nan'),0,0]):
   with self.assertRaises(ValueError):rotate_x_to_normal([1,0,0],n)

if __name__=='__main__':unittest.main()
