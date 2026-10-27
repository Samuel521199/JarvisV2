import copy,json,math,tempfile,unittest
from pathlib import Path
from host.core import Core
from host.anatomy import render
from host.anatomy_engineering import readiness,exported
from modules.skills.anatomy.engineering_model import validate_engineering,vehicle_kinematics,operation_transforms,mv
from sdk.protocol import CoreError
ROOT=Path(__file__).resolve().parents[1]
PRESETS=json.loads((ROOT/'modules/skills/anatomy/engineering-presets.json').read_text(encoding='utf-8'))
VEHICLE=PRESETS['vehicle-chassis']

class VehicleData(unittest.TestCase):
 def test_partition_and_defaults(self):
  s=validate_engineering(VEHICLE);self.assertEqual(validate_engineering(s),s)
  self.assertEqual(len(s['parts']),32);self.assertEqual(len(s['assembly_plan']),5)
  self.assertEqual(len({p for g in s['assembly_plan'] for p in g['parts']}),32)
  self.assertTrue(any(len(b)>1 for g in s['assembly_plan'] for b in g['batches']))
 def test_reject_invalid_groups_batches_and_vehicle_geometry(self):
  changes=[lambda s:s['assembly_plan'][0]['parts'].append('battery'),lambda s:s['assembly_plan'][0]['parts'].pop(),lambda s:s['assembly_plan'][0]['batches'].append(['rail-left']),lambda s:s['assembly_plan'][0].update(code='x'),lambda s:s['operation'].update(max_steer=90),lambda s:s['operation']['wheels'][0]['center'].__setitem__(2,50),lambda s:s['operation']['wheels'][0]['parts'].append('battery'),lambda s:s['operation'].update(rear_rotating=[{}]),lambda s:s['operation'].update(wheelbase=51,pivot_track=250,max_steer=25)]
  for change in changes:
   s=copy.deepcopy(VEHICLE);change(s)
   with self.assertRaises(CoreError):validate_engineering(s)
 def test_ackermann_ratios_and_mirror(self):
  o=VEHICLE['operation'];straight=vehicle_kinematics(o,0);self.assertEqual(straight['speed_ratios'],[1]*4)
  left=vehicle_kinematics(o,20);right=vehicle_kinematics(o,-20)
  self.assertGreater(left['steer_deg'][2],left['steer_deg'][3]);self.assertLess(left['speed_ratios'][0],left['speed_ratios'][1])
  for i,j in [(0,1),(2,3)]:self.assertAlmostEqual(left['speed_ratios'][i],right['speed_ratios'][j]);self.assertAlmostEqual(left['steer_deg'][i],-right['steer_deg'][j])
  R=left['turn_radius_mm'];a,b=map(math.radians,left['steer_deg'][2:]);self.assertAlmostEqual(o['wheelbase']/math.tan(b)-o['wheelbase']/math.tan(a),o['pivot_track'])
 def test_world_rigid_rotation_preserves_length_and_wheel_centers(self):
  for steer in [-20,0,20]:
   ts=operation_transforms(VEHICLE,[.1,.2,.3,.4],steer)
   for t in ts.values():
    a=[1,2,3];b=[7,8,9];ta=mv(t['rotation'],a);tb=mv(t['rotation'],b);self.assertAlmostEqual(math.dist(ta,tb),math.dist(a,b))
   self.assertNotIn('rail-left',ts);self.assertIn('halfshaft-left',ts)

@unittest.skipUnless(readiness()['native_runtime'],'Pinned optional native runtime required')
class VehicleNative(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
 def test_vehicle_real_native_and_exports(self):
  r=render(self.root,{'mechanism':'engineering','preset':'vehicle-chassis'});self.assertEqual(r['adapter_version'],'5.2.0');self.assertEqual(r['quality']['status'],'checked_scope_passed')
  for check in [r['checks']['insertion'],r['checks']['groups'],r['checks']['groups']['parallel_internal'],r['checks']['operation']]:self.assertEqual(check['hits'],[])
  self.assertEqual(r['checks']['operation']['poses'],9);self.assertLess(r['checks']['step_roundtrip_relative_volume_error'],1e-6)
  self.assertEqual(len(json.loads(exported(self.root,r['id'],'configuration.json'))['parts']),32)
 def test_known_parallel_collision_is_reported_and_quality_rejected(self):
  s=copy.deepcopy(PRESETS['cad-starter']);s['parts']=s['parts'][:2]
  for i,p in enumerate(s['parts']):p.update(kind='box',params={'width':8,'depth':8,'height':8},position=[(-1 if i==0 else 1)*16,0,0],rotation=[0,0,0])
  s['mates']=[];s['steps']=s['steps'][:2];s['experiments']=[]
  for i,step in enumerate(s['steps']):step.update(part=s['parts'][i]['id'],direction=[1 if i==0 else -1,0,0],distance=48)
  ids=[p['id'] for p in s['parts']];s['assembly_plan']=[dict(id='pair',name='交叉路径负例',parts=ids,direction=[0,0,1],distance=80,batches=[ids])]
  r=render(self.root,{'mechanism':'engineering','scene':s});self.assertEqual(r['checks']['collisions'],[]);self.assertTrue(r['checks']['groups']['parallel_internal']['hits']);self.assertEqual(r['quality']['status'],'needs_revision')
 def test_motion_obstacle_at_turn_is_not_mistaken_for_static_success(self):
  s=copy.deepcopy(VEHICLE);p=next(p for p in s['parts'] if p['id']=='battery');p.update(position=[68,50,30],params={'width':6,'depth':6,'height':6})
  r=render(self.root,{'mechanism':'engineering','scene':s});self.assertEqual(r['checks']['collisions'],[]);self.assertTrue(r['checks']['operation']['hits']);self.assertEqual(r['quality']['status'],'needs_revision')
