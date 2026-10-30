import copy,hashlib,json,math,tempfile,unittest
from pathlib import Path
from host.studio3d_high_finish import asset_source
from modules.skills.studio3d.tyre_surface import validate,geometry

class TyreSurface(unittest.TestCase):
 def sample(self):return {'schema':'jarvis.studio3d.tyre-surface.v1','author':'Codex','goal':'Local visual tyre correction','evidence':'Repeated shoulder overlays in fixed-light render','pairs':[{'tire':'tire','tread':'tread','center':[0,1,.5],'axis':'Y'}],'circumference_segments':256,'longitudinal_depth':.0015,'cross_depth':.001,'cross_count':64,'rubber_color_scale':.25,'inspection':{'bounds':[[-1,-1,0],[1,1,1]],'resolution':[960,640],'samples':8,'views':[{'id':'left','direction':[0,1,0],'lighting':'neutral'}],'regions':{'wheel':['tire']},'focus_region':'wheel'}}
 def test_closed_continuous_high_surface_with_recesses(self):
  v,f=geometry(.5,.45,.1479,256,.0015,.001,64);edge={}
  for face in f:
   for a,b in zip(face,face[1:]+face[:1]):k=tuple(sorted((a,b)));edge[k]=edge.get(k,0)+1
  self.assertTrue(all(n==2 for n in edge.values()));self.assertGreater(len(v),2176)
  self.assertLessEqual(max(math.hypot(p[0],p[2]) for p in v),.500001)
  self.assertAlmostEqual(max(p[1] for p in v)-min(p[1] for p in v),.1479)
  self.assertGreaterEqual(min(math.hypot(p[0],p[2]) for p in v),.449999)
  # Outer tread is actually recessed at a cut, not extra detached cylinders.
  mid=min(range(len(v)//256),key=lambda j:abs(v[j*256][1]-.1479*.10))
  radii=[math.hypot(*[v[mid*256+i][k] for k in (0,2)]) for i in range(4)]
  self.assertLess(radii[0],radii[2])
  shoulder=min(range(len(v)//256),key=lambda j:abs(v[j*256][1]-.1479*.45))
  cut_r=math.hypot(v[shoulder*256][0],v[shoulder*256][2]);plain_r=math.hypot(v[shoulder*256+2][0],v[shoulder*256+2][2])
  self.assertGreater(plain_r-cut_r,.0005)
 def test_accepts_only_bounded_declared_pairs(self):validate(self.sample(),['tire','tread'])
 def test_rejects_unbounded_and_unrelated_operations(self):
  for k,x in [('circumference_segments',10000),('longitudinal_depth',.03),('rubber_color_scale',float('nan')),('cross_count',65),('python','run'),('lods',True)]:
   v=self.sample();v[k]=x
   with self.assertRaises(ValueError):validate(v,['tire','tread'])
  v=self.sample();v['pairs'][0]['tread']='shield'
  with self.assertRaises(ValueError):validate(v,['tire','tread'])
  v=self.sample();v['inspection']['regions']['wheel'].append('tread')
  with self.assertRaises(ValueError):validate(v,['tire','tread'])
 def test_rejects_wrong_source_scale(self):
  for o,i,w in [(10,9,.1),(.5,.1,.1),(.5,.45,3)]:
   with self.assertRaises(ValueError):geometry(o,i,w,256,.0015,.001,64)
 def test_editable_receipt_requires_source_and_untouched_region_evidence(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);ident='c'*32;p=root/'artifacts/studio3d-tyre-surface'/ident;p.mkdir(parents=True)
   raw=b'native editable tyre test';(p/'model.blend').write_bytes(raw)
   row={'id':ident,'operation':'tyre_surface','status':'BUILT_AWAITING_VISUAL_COMPARISON','report':{'after_object_digests':{'tire':'hash'},'source_unchanged':True,'unchanged_non_targets':True,'actions':[{'tire':'tire'}]},'files':{'model.blend':{'sha256':hashlib.sha256(raw).hexdigest()}}}
   (p/'status.json').write_text(json.dumps(row));names,files=asset_source(root,ident,'tyre_surface');self.assertEqual(names,['tire']);self.assertEqual(set(files),{'model.blend'})
   for field,bad in [('source_unchanged',False),('unchanged_non_targets',False),('actions',[])]:
    altered=copy.deepcopy(row);altered['report'][field]=bad;(p/'status.json').write_text(json.dumps(altered))
    with self.assertRaises(ValueError):asset_source(root,ident,'tyre_surface')

if __name__=='__main__':unittest.main()
