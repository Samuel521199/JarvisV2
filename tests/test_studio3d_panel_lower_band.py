import unittest
from modules.skills.studio3d.panel_lower_band import SCHEMA,TARGETS,RAKE,shift,displacement,validate,validate_sheet
from modules.skills.studio3d.panel_corner import validate as dispatch

class LowerBand(unittest.TestCase):
 def config(self):return {'schema':SCHEMA,'author':'Codex','evidence':'Bound original lower profile and actual front-reference mismatch','source_digests':{n:'a'*64 for n in TARGETS},'raise_height':.12,'inspection':{'views':[{'id':'front','direction':[1,0,0]}],'bounds':[[-1,-1,0],[1,1,2]],'resolution':[960,640],'samples':12,'regions':{'shield':list(TARGETS)}}}
 def test_fixed_scope_and_finite_envelope(self):
  c=self.config();names=list(TARGETS)+['shield-struts','axle'];self.assertEqual(dispatch(c,names),c)
  for k,v in [('raise_height',.15),('raise_height',float('nan')),('source_digests',{}),('extra',True)]:
   with self.assertRaises(ValueError):validate({**c,k:v},names)
 def test_plane_and_upper_region_preserved(self):
  for h in (.08,.12,.14):
   for z in (.41,.53,.66,.72,.8,.90,1.1,1.43):
    p=[.36-RAKE*(z-.53),.4,z];q=shift(p,h)
    self.assertAlmostEqual(p[0]+RAKE*p[2],q[0]+RAKE*q[2]);self.assertEqual(p[1],q[1])
    if z>=.90:self.assertEqual(p,q)
 def test_no_fold_and_rigid_lower_attachment_translation(self):
  for h in (.08,.14):
   zs=[.4+i*.001 for i in range(1040)];new=[shift([0,0,z],h)[2] for z in zs]
   self.assertTrue(all(b>a for a,b in zip(new,new[1:])))
   self.assertEqual(displacement(.43,h),displacement(.65,h))
 def test_changed_source_is_not_replayable(self):
  ps=[[0,0,.41+i*.01] for i in range(18)];fs=[[0,1,2,3]]*10;validate_sheet('shield-lower-flap-1',ps,fs)
  with self.assertRaises(ValueError):validate_sheet('shield-lower-flap-1',[shift(p,.12) for p in ps],fs)
if __name__=='__main__':unittest.main()
