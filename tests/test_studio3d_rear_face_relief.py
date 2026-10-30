import unittest,copy
from collections import Counter
from modules.skills.studio3d.rear_face_relief import patch
class RearRelief(unittest.TestCase):
 def mesh(self):
  return [[-.215,-.2,.58],[-.215,-.2,.8],[-.215,.2,.8],[-.215,.2,.58],[.155,-.225,.555],[.155,-.225,.825],[.155,.225,.825],[.155,.225,.555]],[[0,1,2,3],[7,6,5,4],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]
 def test_preserves_front_and_silhouette_with_closed_blind_recess(self):
  v,f=self.mesh();old=copy.deepcopy((v,f));vs,fs,r=patch(v,f,.045)
  self.assertEqual((v,f),old);self.assertEqual(vs[:8],v);self.assertEqual(fs[:5],f[1:]);self.assertEqual(r['removed_face_index'],0)
  edges=Counter(tuple(sorted((a,b))) for face in fs for a,b in zip(face,face[1:]+face[:1]))
  self.assertEqual(set(edges.values()),{2});self.assertTrue(all(abs(vs[i][0]+.17)<1e-9 for i in fs[-1]));self.assertEqual(len(vs),88)
 def test_rejects_through_deep_and_nonfinite_edits(self):
  for depth in (True,float('nan'),0,.2):
   with self.assertRaises(ValueError):patch(*self.mesh(),depth)
 def test_rejects_changed_source_and_missing_face(self):
  v,f=self.mesh();v[0][0]+=.01
  with self.assertRaises(ValueError):patch(v,f,.045)
  v,f=self.mesh()
  with self.assertRaises(ValueError):patch(v,f[1:],.045)
if __name__=='__main__':unittest.main()
