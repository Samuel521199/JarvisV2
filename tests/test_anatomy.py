import tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from host.core import Core
from host.anatomy import render,artifact,validate_request
from modules.skills.catalog import Skills
from sdk.protocol import CoreError
class AnatomyCase(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
 def test_receipt_and_tamper(self):
  row=render(self.root,{'mechanism':'slider-crank'});self.assertIn(b'Anatomy',artifact(self.root,row['id']));self.assertEqual(row['model_calls'],0)
  Path(row['path']).write_bytes(b'changed')
  with self.assertRaises(CoreError):artifact(self.root,row['id'])
 def test_scope_and_disabled(self):
  for body in ({'mechanism':'engine'},{'mechanism':'slider-crank','code':'bad'}):
   with self.assertRaises(CoreError):render(self.root,body)
  s=Skills(self.root);s.enable('gears',False);s.close()
  with self.assertRaises(CoreError):render(self.root,{'mechanism':'slider-crank'})
  with self.assertRaises(CoreError):artifact(self.root,'../escape')

 def test_parameterized_planetary_receipt(self):
  row=render(self.root,{'mechanism':'planetary','sun_teeth':20,'planet_teeth':19,'mode':'carrier-fixed'})
  raw=artifact(self.root,row['id'])
  self.assertIn('Willis'.encode(),raw);self.assertIn('carrier-fixed'.encode(),raw)
  self.assertEqual(row['configuration'],{'sun_teeth':20,'planet_teeth':19,'mode':'carrier-fixed'})
  self.assertEqual(row['adapter_version'],'4.0.0');self.assertEqual(len(row['renderer_sha256']),12)
 def test_planetary_bounds_and_assembly_rejected_before_build(self):
  for change in ({'sun_teeth':True},{'planet_teeth':17},{'sun_teeth':49},{'sun_teeth':19,'planet_teeth':18},{'mode':'free'},{'mode':[]},{'output':'../../escape'},{'mechanism':'../planetary'}):
   with self.subTest(change=change),self.assertRaises(CoreError):validate_request({'mechanism':'planetary',**change})
  for value in (None,[],1):
   with self.assertRaises(CoreError):validate_request(value)
 def test_planetary_uses_same_disabled_policy(self):
  s=Skills(self.root);s.enable('gears',False);s.close()
  with self.assertRaises(CoreError):render(self.root,{'mechanism':'planetary'})
 def test_timeout_is_controlled_and_lock_released(self):
  import subprocess
  from unittest.mock import patch
  from host.anatomy import LOCK
  with patch('host.anatomy.subprocess.run',side_effect=subprocess.TimeoutExpired('node',15)):
   with self.assertRaises(CoreError) as e:render(self.root,{'mechanism':'planetary'})
   self.assertEqual(e.exception.code,'anatomy_timeout')
  self.assertFalse(LOCK.locked())
