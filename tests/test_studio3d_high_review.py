"""High-poly review must support baking appearance without generating LOD."""
import unittest
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.assets import decode_job
from sdk.protocol import CoreError
class HighReviewTests(unittest.TestCase):
 def scene(self):return {'schema':'jarvis.studio3d.v1','units':'m','title':'Review','materials':[{'id':'paint','color':'#555555','detail':'weathered_paint'}],'objects':[{'id':'panel','kind':'box','material':'paint'}],'unfulfilled':[],'asset_pipeline':{'texture_size':512,'method':'surface','generate_lods':False}}
 def test_high_surface_without_lod(self):
  self.assertIs(validate(self.scene())['asset_pipeline']['generate_lods'],False)
  s=self.scene();s['asset_pipeline']['generate_lods']='false'
  with self.assertRaises(CoreError):validate(s)
 def test_geometry_envelope_retains_strict_json(self):
  self.assertEqual(decode_job(b'{"label":"'+b'x'*300000+b'"}')['label'],'x'*300000)
  for raw in [b'{"id":1,"id":2}',b'{"id":NaN}',b'[]',b' '*2097153]:
   with self.assertRaises(CoreError):decode_job(raw)
