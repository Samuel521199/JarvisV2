import copy,math,unittest
from modules.skills.studio3d.panel_aperture import validate,panel_points,bridge_points,sample_x,SCHEMA
from modules.skills.studio3d.panel_corner import validate as dispatch

def panel(sign=1):
 ys=[sign*y for y in (.105,.2,.3,.42,.8)];ps=[[.4-.5*z-.1*abs(y),y,z] for z in (.5,1,1.43) for y in ys];fs=[]
 for k in range(2):
  for j in range(4):a=k*5+j;fs.append([a,a+1,a+6,a+5])
 return {'points':ps,'faces':fs}

def bridge():
 ps=[]
 for k in range(3):
  for j in range(17):
   y=(j/16-.5)*.24;lo=1.21+math.sqrt(max(0,.12**2-y*y));z=lo+(1.43-lo)*k/2;ps.append([.4-.5*z-.1*abs(y),y,z])
 return ps

def contract():
 names=['bridge','p0','p1','p2','p3','anchors']
 return {'schema':SCHEMA,'author':'Codex','evidence':'Bound actual source and generated visual reference only','bridge':'bridge','panels':names[1:5],'anchors':['anchors'],'source_digests':{n:'a'*64 for n in names[:5]},'half_width':.18,'top_drop':.17,'corner_radius':.045,'falloff':.42,'max_displacement':.15,'max_anchor_distance_increase':.0005,'inspection':{'views':[{'id':'front','direction':[1,0,0]}],'bounds':[[-1,-1,0],[1,1,2]],'resolution':[960,640],'samples':16,'regions':{'shield':names[:5]},'focus_region':'shield'}},names

class Aperture(unittest.TestCase):
 def test_dispatch_and_bounds(self):
  c,names=contract();self.assertEqual(dispatch(c,names),c)
  for patch in ({'half_width':.4},{'top_drop':float('nan')},{'max_displacement':1},{'panels':['p0']*4},{'python':'bad'}):
   with self.subTest(patch=patch),self.assertRaises(ValueError):validate({**c,**patch},names)
 def test_source_identity_binding(self):
  c,names=contract();c['source_digests'].pop('bridge')
  with self.assertRaises(ValueError):validate(c,names)
 def test_depth_interpolates_original_surface_and_rejects_outside(self):
  p=panel();self.assertAlmostEqual(sample_x(p['points'],p['faces'],.24,.7),.4-.5*.7-.1*.24)
  with self.assertRaises(ValueError):sample_x(p['points'],p['faces'],.9,.7)
 def test_only_inner_domain_changes_and_does_not_fold(self):
  for sign in (1,-1):
   p=panel(sign);result=panel_points(p['points'],p['faces'],.18,.42)
   for old,new in zip(p['points'],result):
    if abs(old[1])>=.42:self.assertEqual(old,new)
    self.assertAlmostEqual(new[0],.4-.5*new[2]-.1*abs(new[1]))
   self.assertAlmostEqual(abs(result[0][1]),.18)
   self.assertTrue(all(abs(result[i][1])<abs(result[i+1][1]) for i in range(4)))
 def test_opening_has_flat_crest_with_rounded_shoulders(self):
  ps,fs=bridge_points(bridge(),[panel(1),panel(-1)],.18,.17,.045)
  self.assertEqual((len(ps),len(fs)),(195,128));lower=ps[:65]
  self.assertAlmostEqual(lower[32][2],1.26)
  self.assertAlmostEqual(lower[28][2],1.26)
  self.assertAlmostEqual(lower[0][2],1.215)
  self.assertAlmostEqual(max(abs(p[1]) for p in ps),.18)
  self.assertTrue(all(abs(p[2]-1.43)<1e-6 for p in ps[130:]))
 def test_rejects_already_changed_or_unsupported_source(self):
  p=panel();altered=panel_points(p['points'],p['faces'],.18,.42)
  with self.assertRaises(ValueError):panel_points(altered,p['faces'],.2,.42)
  with self.assertRaises(ValueError):bridge_points(bridge()[:-1],[p,panel(-1)],.18,.17,.045)
 def test_bridge_ends_match_changed_sheets_without_face_overlap(self):
  original=[panel(1),panel(-1)];changed=[{'points':panel_points(p['points'],p['faces'],.18,.42),'faces':p['faces']} for p in original]
  for p in changed:
   for v in p['points']:v[0]+=.0002
  ps,_=bridge_points(bridge(),original,.18,.17,.045,changed)
  for index in (0,64,65,129,130,194):
   x,y,z=ps[index];p=changed[0 if y>0 else 1];self.assertAlmostEqual(x,sample_x(p['points'],p['faces'],y,z))

if __name__=='__main__':unittest.main()
