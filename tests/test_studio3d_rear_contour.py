import copy,math,unittest
from modules.skills.studio3d.rear_contour import validate,outline,NAMES,SCHEMA

class RearContourTests(unittest.TestCase):
 def contract(self):
  return {'schema':SCHEMA,'author':'Codex','evidence':'Actual source and paired external contour views','source_sha256':'a'*64,'dependencies':{n:'b'*64 for n in NAMES},'clearance':.01,'inspection':{'regions':{'rear-contour':['shaped-rear-cover','rear-cover-body','breech-recess']},'focus_region':'rear-contour','views':[{'id':'rear','direction':[-1,0,.16]},{'id':'left','direction':[-1,.8,.35]}],'bounds':[[-1.3,-.55,.6],[-.2,.55,1.6]],'resolution':[960,640],'samples':12}}
 def test_contract(self):validate(self.contract(),NAMES)
 def test_invalid_binding(self):
  for k in ('source_sha256','dependencies'):
   c=self.contract();c[k]='broken'
   with self.assertRaises(ValueError):validate(c,NAMES)
 def test_scope_injection(self):
  c=self.contract();c['change_body']=True
  with self.assertRaises(ValueError):validate(c,NAMES)
  c=self.contract();c['inspection']['bounds'][0][0]=-9
  with self.assertRaises(ValueError):validate(c,NAMES)
 def test_bounds_and_types(self):
  for x in (True,.0079,.0101,float('nan'),float('inf')):
   with self.assertRaises(ValueError):outline(x,0,1.135,.061)
 def test_disc_binding(self):
  for args in ((.01,.01,1.135,.061),(.01,0,1.14,.061),(.01,0,1.135,.065)):
   with self.assertRaises(ValueError):outline(*args)
 def test_envelope_and_no_duplicate_points(self):
  for x in (.008,.009,.01):
   p=outline(x,0,1.135,.061)
   self.assertEqual(len(p),39);self.assertEqual(len(set(map(tuple,p))),39)
   self.assertEqual((min(y for y,z in p),max(y for y,z in p)),(-.125,.125))
   self.assertEqual((min(z for y,z in p),max(z for y,z in p)),(.99,1.31))
 def test_missing_neighbour(self):
  with self.assertRaises(ValueError):validate(self.contract(),NAMES-{'rear-cover-body'})

if __name__=='__main__':unittest.main()
