import unittest,math
from modules.skills.studio3d.saddle_fascia import SCHEMA,validate,build
from modules.skills.studio3d.attachment_seat import validate as dispatch
class SaddleFascia(unittest.TestCase):
 def config(self):return {'schema':SCHEMA,'author':'Codex','evidence':'Actual reference-visible cover only','target':'axle-saddle','source_digest':'a'*64,'face_depth':.018,'inspection':{'views':[{'id':'rear','direction':[-1,0,0]}],'bounds':[[-1,-1,0],[1,1,1]],'resolution':[960,640],'samples':12,'regions':{'base':['axle-saddle']},'focus_region':'base'}}
 def test_contract_rejects_unbounded_or_wrong_target(self):
  c=self.config();self.assertEqual(dispatch(c,['axle-saddle']),c)
  for k,v in [('target','central-pedestal'),('face_depth',.03),('face_depth',float('nan')),('source_digest','invalid'),('extra',True)]:
   with self.assertRaises(ValueError):validate({**c,k:v},['axle-saddle'])
 def test_parts_are_closed_and_finite(self):
  for p in build(self.config()):
   edges={}
   for f in p['faces']:
    self.assertGreaterEqual(len(f),3);self.assertEqual(len(f),len(set(f)))
    for a,b in zip(f,f[1:]+f[:1]):k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
   self.assertTrue(all(n==2 for n in edges.values()));self.assertTrue(all(math.isfinite(x) for v in p['vertices'] for x in v))
 def test_front_rear_panels_reach_original_surface(self):
  ps=build(self.config());front=ps[0]['vertices'];rear=ps[2]['vertices']
  self.assertLess(min(v[0] for v in front),.115);self.assertGreater(max(v[0] for v in rear),-.235)
 def test_relief_does_not_spread_to_side_joints(self):
  for depth in (.012,.024):
   c=self.config();c['face_depth']=depth;vs=[v for p in build(c) for v in p['vertices']]
   self.assertLessEqual(max(abs(v[1]) for v in vs),.2250001);self.assertGreater(min(v[2] for v in vs),.38);self.assertLess(max(v[2] for v in vs),.62);self.assertLess(len(vs),5000)
if __name__=='__main__':unittest.main()
