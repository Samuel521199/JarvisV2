import unittest,copy,math
from modules.skills.studio3d.annular_detail import geometry,fit_rings,validate

class AnnularDetailTests(unittest.TestCase):
 def test_recovers_actual_circular_geometry(self):
  c=[0,.975,.5];v,f=geometry(.115,.05365,.008,32,6,c);r=fit_rings(v,f,c,1)[0]
  self.assertAlmostEqual(r['radius'],.115);self.assertAlmostEqual(r['axial_center'],.05365);self.assertAlmostEqual(r['tube'],.008)
  self.assertEqual((r['source_segments'],r['source_tube_segments']),(32,6))
 def test_open_corrupt_and_distorted_sources_rejected(self):
  c=[0,0,0];v,f=geometry(.115,.05365,.008,32,6,c)
  for faces in [f[:-1],f+f[:1],[[9999,*f[0][1:]],*f[1:]]]:
   with self.assertRaises(ValueError):fit_rings(v,faces,c,1)
  v[0][0]+=.001
  with self.assertRaises(ValueError):fit_rings(v,f,c,1)
 def test_wrong_frame_and_component_count(self):
  v,f=geometry(.115,.05365,.008,32,6,[0,0,0])
  for center,count in [([.001,0,0],1),([0,0,0],2)]:
   with self.assertRaises(ValueError):fit_rings(v,f,center,count)
 def test_high_mesh_closed_manifold_and_dimensions(self):
  for h in (-.1044,.1044):
   v,f=geometry(.069,h,.006,192,16,[0,0,0]);edges={}
   for p in f:
    for a,b in zip(p,p[1:]+p[:1]):k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
   self.assertEqual(set(edges.values()),{2});self.assertEqual(len(v)-len(edges)+len(f),0)
   self.assertAlmostEqual(max(math.hypot(p[0],p[2]) for p in v),.075)
   self.assertAlmostEqual(max(p[1] for p in v),h+.006)
 def test_contract_refuses_overreach(self):
  c={'schema':'jarvis.studio3d.annular-detail.v1','author':'Jarvis','evidence':'Local rendered faceting','targets':[{'object':'ring','center':[0,0,0],'supports':['disc'],'expected_components':6}],'segments':128,'tube_segments':16,'embed':.0005,'max_move':.012,'inspection':{'views':[{'id':'left','direction':[0,1,0]}],'bounds':[[-1,-1,-1],[1,1,1]],'resolution':[960,640],'samples':16,'regions':{'ring':['ring']}}}
  self.assertIs(validate(c,['ring','disc']),c)
  for k,value in [('segments',4096),('embed',float('nan')),('max_move',.1),('author','unknown')]:
   d=copy.deepcopy(c);d[k]=value
   with self.assertRaises(ValueError):validate(d,['ring','disc'])
  d=copy.deepcopy(c);d['targets'][0]['supports']=['ring']
  with self.assertRaises(ValueError):validate(d,['ring','disc'])
