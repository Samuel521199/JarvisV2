import copy,json,math,tempfile,unittest
from pathlib import Path
from host.core import Core
from host.anatomy import render
from host.anatomy_engineering import readiness,exported
from modules.skills.anatomy.engineering_model import validate_engineering,operation_transforms
from modules.skills.anatomy.engineering_transmission import transmission_ratios,gear_outline
from sdk.protocol import CoreError
ROOT=Path(__file__).resolve().parents[1];PRESETS=json.loads((ROOT/'modules/skills/anatomy/engineering-presets.json').read_text(encoding='utf-8'));RACE=PRESETS['racecar']

def stress_scene(count=96):
 s=copy.deepcopy(PRESETS['cad-starter']);s.update(title='独立简单零件数量压力样例',description='数量/文件/渲染压力例，不代表同数量复杂赛车或啮合系统。',parts=[],mates=[],steps=[],experiments=[])
 for i in range(count):
  id='block-'+str(i);s['parts'].append(dict(id=id,name='压力块 '+str(i),kind='box',params={'width':8,'depth':8,'height':4},material='aluminum',position=[i%12*16,i//12*16,0],rotation=[0,0,0]));s['steps'].append(dict(part=id,instruction='从上方装入独立压力块。',direction=[0,0,1],distance=30))
 return s

class RaceData(unittest.TestCase):
 def test_ratios_and_gear_geometry(self):
  s=validate_engineering(RACE);self.assertEqual(validate_engineering(s),s);self.assertEqual(len(s['parts']),72)
  r=transmission_ratios(s);self.assertEqual(r['pinion'],4);self.assertEqual(r['lay-gear'],-2);self.assertEqual(r['output-gear'],1)
  ps={p['id']:p for p in s['parts']}
  for pair in s['operation']['transmission']['stages']:self.assertAlmostEqual(ps[pair['driver']]['params']['teeth']*r[pair['driver']]+ps[pair['driven']]['params']['teeth']*r[pair['driven']],0)
  for p in ps.values():
   if p['kind']=='gear':
    points=gear_outline(p['params']);self.assertTrue(all(math.isfinite(x) for v in points for x in v));self.assertAlmostEqual(max(math.hypot(*v) for v in points),p['params']['module']*(p['params']['teeth']+2)/2)
 def test_invalid_transmission_and_boundaries(self):
  changes=[lambda s:s['operation']['transmission'].update(output='battery'),lambda s:s['operation']['transmission']['shafts'][0]['parts'].append('battery'),lambda s:next(p for p in s['parts'] if p['id']=='pinion')['position'].__setitem__(0,-20),lambda s:next(p for p in s['parts'] if p['id']=='pinion')['params'].update(teeth=12),lambda s:next(p for p in s['parts'] if p['id']=='cockpit')['params'].update(mount_span=149)]
  for change in changes:
   s=copy.deepcopy(RACE);change(s)
   with self.assertRaises(CoreError):validate_engineering(s)
  validate_engineering(stress_scene(96))
  with self.assertRaises(CoreError):validate_engineering(stress_scene(97))
 def test_transforms_include_transmission_only_when_declared(self):
  s=validate_engineering(RACE);ts=operation_transforms(s,[.3,.1,.2,.1],10);self.assertIn('pinion',ts);self.assertNotIn('cockpit',ts);self.assertNotIn('battery',ts)

@unittest.skipUnless(readiness()['native_runtime'],'Pinned optional native runtime required')
class RaceNative(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
 def test_real_race_geometry_paths_motion_and_export(self):
  r=render(self.root,{'mechanism':'engineering','preset':'racecar'});self.assertEqual(r['quality']['status'],'checked_scope_passed');self.assertEqual(r['adapter_version'],'5.2.0');self.assertEqual(r['checks']['collisions'],[])
  for row in [r['checks']['insertion'],r['checks']['groups'],r['checks']['groups']['parallel_internal'],r['checks']['operation']]:self.assertEqual(row['hits'],[])
  self.assertEqual(r['checks']['operation']['poses'],30);self.assertEqual(r['checks']['transmission']['ratios_to_carrier']['pinion'],4);self.assertLess(r['checks']['step_roundtrip_relative_volume_error'],1e-6);self.assertEqual(len(json.loads(exported(self.root,r['id'],'configuration.json'))['parts']),72);self.assertIn('assembly.step',r['resources']['portable_encoding'])
 def test_simple_96_part_stress_export(self):
  r=render(self.root,{'mechanism':'engineering','scene':stress_scene()});self.assertEqual(r['quality']['status'],'checked_scope_passed');self.assertEqual(len(r['configuration']['parts']),96)
  out=ROOT/'docs/evidence/anatomy-race-2026-10-23';out.mkdir(parents=True,exist_ok=True);(out/'stress-96.json').write_text(json.dumps({'scope':'96 simple disjoint boxes, not 96 drivetrain parts','receipt':r},ensure_ascii=False,indent=2),encoding='utf-8')
