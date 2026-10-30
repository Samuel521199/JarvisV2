import copy,unittest,math
from modules.skills.studio3d.curve_foot import validate,foot_shift,NAMES,SCHEMA

class CurveFootTests(unittest.TestCase):
 def contract(self):
  return {'schema':SCHEMA,'author':'Codex','evidence':'Actual20rim points have positive cover gap','source_sha256':'a'*64,'dependencies':{n:'b'*64 for n in NAMES},'boundary_vertices':list(range(20)),'embed':.0006,'inspection':{'regions':{'upper-grip':['breech-top-grip','breech-top-cover']},'focus_region':'upper-grip','views':[{'id':'front','direction':[1,0,0]},{'id':'rear','direction':[-1,0,.2]}],'resolution':[960,640],'samples':12,'bounds':[[-1,-1,0],[1,1,2]]}}
 def test_bound_contract(self):validate(self.contract(),list(NAMES))
 def test_bad_binding(self):
  for key in ('source_sha256','dependencies','boundary_vertices'):
   c=self.contract();c[key]='x'
   with self.assertRaises(ValueError):validate(c,list(NAMES))
 def test_range_and_types(self):
  for n in (True,.0003,.0009,math.nan):
   c=self.contract();c['embed']=n
   with self.assertRaises(ValueError):validate(c,list(NAMES))
 def test_planar_supported_gap(self):
  self.assertAlmostEqual(foot_shift([.006]*20,.0006),-.0066)
  for gaps in ([.001,.006],[-.001],[],[float('nan')],[.012]):
   with self.assertRaises(ValueError):foot_shift(gaps,.0006)
 def test_no_injected_geometry_or_scope(self):
  c=self.contract();c['delete_faces']=True
  with self.assertRaises(ValueError):validate(c,list(NAMES))
  c=self.contract();c['inspection']['focus_region']='all'
  with self.assertRaises(ValueError):validate(c,list(NAMES))
if __name__=='__main__':unittest.main()
