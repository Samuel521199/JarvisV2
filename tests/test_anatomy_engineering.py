import copy,json,math,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'modules/skills/anatomy'))
from host.core import Core
from host.anatomy import render,artifact,validate_request
from host.anatomy_engineering import CONTRACT,validate_engineering,assembly_poses,readiness,exported
from sdk.protocol import CoreError
from engineering_physics import motor_pump,otto,channel,shallow_water,pendulum,fourbar,arm_ik
PRESETS=json.loads((ROOT/'modules/skills/anatomy/engineering-presets.json').read_text(encoding='utf-8'))
def defaults(kind):return {k:v['default'] for k,v in CONTRACT['experiments'][kind].items()}

class EngineeringData(unittest.TestCase):
 def test_presets_idempotence_and_constraint_transforms(self):
  for s in PRESETS.values():
   v=validate_engineering(s);self.assertEqual(validate_engineering(v),v);poses=assembly_poses(v)
   if 'bearing-front' in poses:self.assertEqual(poses['bearing-front']['position'],[0,0,24]);self.assertEqual(poses['bearing-back']['position'],[0,0,-24])
  v=validate_engineering(PRESETS['shaft-assembly']);self.assertAlmostEqual(assembly_poses(v)['bolt-0']['position'][0],38)
 def test_reject_code_nan_cycles_ports_order_and_impossible_features(self):
  cases=[]
  for change in [{'code':'bad'},{'units':'m'},{'parts':[]},{'schema':True}]:cases.append({**copy.deepcopy(PRESETS['shaft-assembly']),**change})
  for name,value in [('id','../escape'),('params',{'diameter':float('nan')}),('rotation',[0,0,10000]),('kind',[]),('material','url(x)')]:
   s=copy.deepcopy(PRESETS['shaft-assembly']);s['parts'][0][name]=value;cases.append(s)
  s=copy.deepcopy(PRESETS['shaft-assembly']);s['mates'][0]['parent_port']='unknown';cases.append(s)
  s=copy.deepcopy(PRESETS['shaft-assembly']);s['steps'][0],s['steps'][1]=s['steps'][1],s['steps'][0];cases.append(s)
  s=copy.deepcopy(PRESETS['shaft-assembly']);s['parts'][6]['params']['inner']=100;cases.append(s)
  s=copy.deepcopy(PRESETS['shaft-assembly']);s['mates'].append({**s['mates'][0],'part':'shaft','parent':'bearing-front'});cases.append(s)
  for scene in cases:
   with self.subTest(scene=scene.get('schema')),self.assertRaises(CoreError):validate_engineering(scene)
 def test_scope_rejects_executable_or_ambiguous_request(self):
  for req in [{'mechanism':'engineering','preset':[]},{'mechanism':'engineering','scene':PRESETS['cad-starter'],'preset':'cad-starter'},{'mechanism':'engineering','code':'bad'}]:
   with self.assertRaises(CoreError):validate_request(req)

class PhysicsModels(unittest.TestCase):
 def test_closed_linkage_residual_and_unreachable_arm(self):
  s=fourbar(defaults('fourbar'));self.assertEqual(s['summary']['unreachable_samples'],0);self.assertLess(s['summary']['closure_residual_mm'],1e-10);self.assertEqual(len(s['poses']),181)
  s=arm_ik(defaults('arm-ik'));self.assertEqual(s['summary']['solutions'],2);self.assertLess(s['summary']['target_error_mm'],1e-10)
  s=arm_ik({**defaults('arm-ik'),'target_x':250,'target_y':250});self.assertFalse(s['summary']['reachable']);self.assertEqual(s['poses'],[])
  s=arm_ik({'upper':60,'lower':60,'target_x':0,'target_y':0});self.assertTrue(s['summary']['reachable']);self.assertEqual(s['summary']['solution_family'],'infinite')
 def test_motor_energy_and_real_load_response(self):
  p=defaults('motor-pump');a=motor_pump(p);b=motor_pump({**p,'pump_coefficient':p['pump_coefficient']*3})
  self.assertLess(a['summary']['relative_energy_error'],1e-7);self.assertLess(b['summary']['final_speed_rpm'],a['summary']['final_speed_rpm']);self.assertGreater(b['summary']['final_current_A'],a['summary']['final_current_A'])
  self.assertEqual(motor_pump({**p,'voltage':0})['summary']['final_speed_rpm'],0)
 def test_otto_analytic_efficiency_and_energy(self):
  for r in [3,8,16]:
   p={**defaults('otto'),'compression':r};s=otto(p)['summary'];self.assertAlmostEqual(s['efficiency'],1-r**(-.4));self.assertLess(abs(s['energy_residual_J']),1e-8)
 def test_channel_profile_and_grid_refinement(self):
  p=defaults('channel');a=channel({**p,'cells':16});b=channel({**p,'cells':32});self.assertLess(a['summary']['max_velocity_error_m_s'],1e-12);self.assertLess(b['summary']['relative_flow_error'],a['summary']['relative_flow_error']/3)
 def test_shallow_water_conservation_positive_and_refinement(self):
  p={**defaults('shallow-water'),'amplitude':.005};errors=[]
  for n in [40,80,120]:
   s=shallow_water({**p,'cells':n});self.assertLess(s['summary']['relative_mass_error'],1e-12);self.assertGreater(s['summary']['min_depth_m'],0)
   c=math.sqrt(9.81*p['depth']);L=p['length'];t=p['duration'];exact=lambda x:p['depth']+.5*p['amplitude']*(math.exp(-((x-L/2-c*t)/(L*.08))**2)+math.exp(-((x-L/2+c*t)/(L*.08))**2));errors.append(sum(abs(row[2]-exact(row[0])) for row in s['rows'])/n)
  self.assertLess(errors[2],errors[1]);self.assertLess(errors[1],errors[0])
 def test_pendulum_energy_and_measured_small_angle_period(self):
  p={**defaults('pendulum'),'damping':0,'angle_deg':2};s=pendulum(p);self.assertLess(abs(s['summary']['energy_residual_per_kg_J']),1e-9)
  crossings=[]
  for a,b in zip(s['rows'],s['rows'][1:]):
   if a[1]>=0>b[1]:crossings.append(a[0]+(b[0]-a[0])*a[1]/(a[1]-b[1]))
  self.assertGreaterEqual(len(crossings),2);self.assertAlmostEqual((crossings[1]-crossings[0])/s['summary']['small_angle_period_s'],1,delta=.002)

@unittest.skipUnless(readiness()['native_runtime'],'Optional pinned native runtime not prepared')
class NativeEngineering(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
 def test_real_assembly_exports_section_and_conservation(self):
  row=render(self.root,{'mechanism':'engineering','preset':'shaft-assembly'});self.assertEqual(row['adapter_version'],'5.2.0');self.assertEqual(row['checks']['collisions'],[])
  self.assertLess(row['checks']['step_roundtrip_relative_volume_error'],1e-10);self.assertLess(row['checks']['step_roundtrip_bounds_error_mm'],1e-6)
  self.assertIn(b'ISO-10303-21',exported(self.root,row['id'],'assembly.step'));self.assertIn(b'.MILLI.',exported(self.root,row['id'],'assembly.step'));self.assertIn(b'$INSUNITS',exported(self.root,row['id'],'flange-profile.dxf'))
  result=json.loads((self.root/'artifacts/anatomy'/(row['id']+'-engineering')/'result.json').read_text(encoding='utf-8'))
  self.assertEqual(len(result['parts']),19);self.assertTrue(all(p['valid'] and p['mass_kg']>0 for p in result['bom']))
  self.assertEqual(result['assembly']['insertion']['hits'],[]);self.assertEqual(row['quality']['status'],'checked_scope_passed');self.assertTrue(all(x['axial_engagement_mm']==5 for x in result['assembly']['fits'] if x['part'].startswith('nut-')))
  housing=next(p for p in result['parts'] if p['id']=='housing');vertices=housing['section']['vertices'];caps=0
  for a,b,c in housing['section']['triangles']:
   if max(abs(vertices[i][1]) for i in [a,b,c])<1e-6:caps+=1
  self.assertGreater(caps,0);self.assertTrue(all(p[1]>=-1e-6 for p in vertices))
  with self.assertRaises(CoreError):exported(self.root,row['id'],'../configuration.json')
  path=self.root/'artifacts/anatomy'/(row['id']+'-engineering')/'assembly.step';path.write_bytes(b'changed')
  with self.assertRaises(CoreError):exported(self.root,row['id'],'assembly.step')
 def test_bad_assembly_order_detected_even_when_static_clear(self):
  s=copy.deepcopy(PRESETS['shaft-assembly']);s['steps'][1],s['steps'][4]=s['steps'][4],s['steps'][1];row=render(self.root,{'mechanism':'engineering','scene':s});self.assertEqual(row['checks']['collisions'],[]);self.assertTrue(row['checks']['insertion']['hits']);self.assertEqual(row['quality']['status'],'needs_revision')
  plan=row['checks']['plan_candidate'];self.assertEqual(plan['status'],'candidate_sampled_clear');revised={**s,'steps':plan['steps']};again=render(self.root,{'mechanism':'engineering','scene':revised});self.assertEqual(again['checks']['insertion']['hits'],[]);self.assertEqual(again['quality']['status'],'checked_scope_passed');self.assertEqual(revised['parts'],s['parts']);self.assertEqual(revised['mates'],s['mates'])
 def test_true_intersection_volume_and_safe_text(self):
  s=copy.deepcopy(PRESETS['cad-starter']);s['title']='</script><img src=x onerror=alert(1)>';p=s['parts'][0];p.update(kind='box',params={'width':10,'depth':10,'height':10},name='=HYPERLINK("x")');q=copy.deepcopy(p);q.update(id='second',position=[5,0,0]);s['parts']=[p,q];s['mates']=[];s['steps']=s['steps'][:2];s['steps'][1]['part']='second';s['experiments']=[]
  row=render(self.root,{'mechanism':'engineering','scene':s});self.assertAlmostEqual(row['checks']['collisions'][0]['volume_mm3'],500,places=5);self.assertNotIn(b'</script><img',artifact(self.root,row['id']));self.assertIn(b"'=HYPERLINK",exported(self.root,row['id'],'bom.csv'))
 def test_chemistry_conserves_elements_and_enthalpy(self):
  row=render(self.root,{'mechanism':'engineering','preset':'flow-lab'});report=json.loads(exported(self.root,row['id'],'report.json'));s=next(e['summary'] for e in report['experiments'] if e['kind']=='combustion');self.assertGreater(s['temperature_K'],1800);self.assertLess(s['max_element_mass_error'],1e-8);self.assertLess(s['relative_enthalpy_error'],1e-6)
 def test_engineering_generation_reuses_existing_lane(self):
  import uuid
  sys.path.insert(0,str(ROOT/'tests'))
  from test_anatomy_studio import FakeDialogue
  from host import anatomy_composer as c
  from modules.dialogue.store import Dialogues
  body={'id':uuid.uuid4().hex,'prompt':'做轴与滚动轴承装配','provider':'vertex','model':'fixture','mode':'engineering'};fake=FakeDialogue(self.root,text=json.dumps(PRESETS['cad-starter'],ensure_ascii=False));c.submit(self.root,body,fake);c.submit(self.root,body,fake);self.assertEqual(fake.calls,1)
  db=Dialogues(self.root)
  try:self.assertLess(len(json.loads(db.turn('anatomy-'+body['id'])['request'])['text']),12000)
  finally:db.close()
  r=c.finish(self.root,body['id']);self.assertEqual(r['artifact']['mechanism'],'engineering');self.assertEqual(r['status'],'DELIVERED');self.assertEqual(c.finish(self.root,body['id'])['artifact']['id'],r['artifact']['id'])
  newer={**body,'id':uuid.uuid4().hex,'revision_of':body['id'],'prompt':'根据实体检查修订'};c.submit(self.root,newer,fake);revised=c.finish(self.root,newer['id']);self.assertEqual(revised['revision_of'],body['id']);self.assertEqual(revised['artifact']['revision_of'],body['id']);self.assertNotEqual(revised['artifact']['id'],r['artifact']['id']);self.assertEqual(fake.calls,2)

if __name__=='__main__':unittest.main()
