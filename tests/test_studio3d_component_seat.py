import copy,unittest
from modules.skills.studio3d.component_seat import SCHEMA,supported_modifiers
from modules.skills.studio3d.attachment_seat import validate,axial_translation

def contract():
 names=['heads','support'];c={'schema':SCHEMA,'author':'Codex','evidence':'Read-only measurement of a disconnected cosmetic head','object':'heads','source_digest':'a'*64,'targets':[{'indices':list(range(14)),'center':[.1,.134,.94],'support':'support','axis':[0,1,0]}],'max_move':.03,'embed':.0006,'inspection':{'views':[{'id':'left','direction':[0,1,0]}],'bounds':[[-1,-1,0],[1,1,2]],'resolution':[960,640],'samples':16,'regions':{'heads':names},'focus_region':'heads'}};return c,names

class ComponentSeat(unittest.TestCase):
 def test_existing_bevel_only(self):
  self.assertTrue(supported_modifiers([{'type':'BEVEL','width':.001,'segments':4}]))
  for rows in ([{'type':'BOOLEAN','width':.001,'segments':4}],[{'type':'BEVEL','width':.01,'segments':4}],[{'type':'BEVEL','width':.001,'segments':7}]):
   with self.assertRaises(ValueError):supported_modifiers(rows)
 def test_dispatch_and_source_guards(self):
  c,n=contract();self.assertEqual(validate(c,n),c)
  for k,v in [('source_digest','bad'),('max_move',.031),('embed',float('nan')),('python','bad')]:
   with self.subTest(key=k),self.assertRaises(ValueError):validate({**c,k:v},n)
 def test_target_identity_and_duplicate_guard(self):
  c,n=contract();c['targets']*=2
  with self.assertRaises(ValueError):validate(c,n)
  for k,v in [('support','heads'),('center',[0,0,float('nan')]),('indices',[0]*14),('axis',[0,.8,.6]),('yz',[0,1])]:
   c,n=contract();c['targets'][0][k]=v
   with self.subTest(key=k),self.assertRaises(ValueError):validate(c,n)
 def test_all_canonical_axes_only(self):
  for axis in ([1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]):
   c,n=contract();c['targets'][0]['axis']=axis;self.assertEqual(validate(c,n),c)
  for axis in ([True,0,0],[0,0,0],[1,1,0],[1,0,float('nan')]):
   c,n=contract();c['targets'][0]['axis']=axis
   with self.assertRaises(ValueError):validate(c,n)
 def test_gap_closed_without_burying_head(self):
  delta,e=axial_translation(.1265,.1415,[.115]*7,.0006,.03)
  self.assertAlmostEqual(delta,-.0121);self.assertAlmostEqual(e['base_gap_after'][1],-.0006);self.assertAlmostEqual(e['minimum_visible_height'],.0144)
 def test_uneven_and_unreachable_support_rejected(self):
  for hits in ([.115,.14],[.09]*7,[]):
   with self.assertRaises(ValueError):axial_translation(.1265,.1415,hits,.0006,.03)

if __name__=='__main__':unittest.main()
