import unittest,copy
from modules.skills.studio3d.pedestal_profile import SCHEMA,build,validate,check_original
from modules.skills.studio3d.attachment_seat import validate as dispatch

def contract():
 return {'schema':SCHEMA,'author':'Codex','evidence':'Actual original source and multi-view external silhouette','target':'central-pedestal','source_digest':'a'*64,'waist_inset':.03,'foot_height':.035,'inspection':{'views':[{'id':'rear','direction':[-1,0,.1]}],'bounds':[[-1,-1,0],[1,1,1]],'resolution':[960,640],'samples':16,'regions':{'base':['central-pedestal']},'focus_region':'base'}}

class PedestalProfile(unittest.TestCase):
 def test_contract_and_dispatch(self):
  c=contract();self.assertEqual(dispatch(c,['central-pedestal']),c)
  for k,v in [('target','axle'),('source_digest','bad'),('waist_inset',float('nan')),('foot_height',.05),('script','anything')]:
   with self.assertRaises(ValueError):validate({**c,k:v},['central-pedestal'])
 def test_original_box_not_arbitrary_vertices(self):
  vs=[[x,y,z] for x in (-.215,.155) for y in (-.225,.225) for z in (.555,.825)];self.assertTrue(check_original(vs))
  for altered in (vs[:-1],vs+[vs[0]],[[0,0,0]]+vs[1:]):
   with self.assertRaises(ValueError):check_original(altered)
 def test_closed_non_degenerate_surface(self):
  for inset in (.02,.04):
   c=contract();c['waist_inset']=inset;m=build(c);counts={}
   for f in m['faces']:
    self.assertEqual(len(f),len(set(f)))
    for a,b in zip(f,f[1:]+f[:1]):k=tuple(sorted((a,b)));counts[k]=counts.get(k,0)+1
   self.assertTrue(all(n==2 for n in counts.values()))
 def test_preserves_outer_bands_and_limits_to_inner_waist(self):
  a=build(contract());c=contract();c['waist_inset']=.04;b=build(c)
  for v,w in zip(a['vertices'],b['vertices']):
   if v[2]<=.60 or v[2]>=.715:self.assertEqual(v,w)
  self.assertEqual(min(v[2] for v in a['vertices']),.555);self.assertEqual(max(v[2] for v in a['vertices']),.825)
  self.assertLessEqual(max(abs(v[1]) for v in a['vertices']),.2250001)

if __name__=='__main__':unittest.main()
