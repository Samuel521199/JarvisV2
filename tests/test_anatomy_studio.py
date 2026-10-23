import copy,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from host.core import Core
from host.anatomy import render,artifact,validate_request
from host.anatomy_scene import validate_scene,PRESETS,SCHEMA
from host import anatomy_composer as composer
from modules.dialogue.store import Dialogues
from modules.skills.catalog import Skills
from sdk.protocol import CoreError,canonical

class FakeDialogue:
 def __init__(self,root,status='SUCCEEDED',text=None):self.root=root;self.status=status;self.text=text;self.calls=0
 def submit(self,c):
  self.calls+=1;s=Dialogues(self.root)
  try:
   s.begin(c,[]);s.start_attempt(c['request_id'],{'id':'fixture','model':'fake','billing_profile':None})
   s.finish(c['request_id'],{'status':self.status,'text':self.text if self.text is not None else canonical(PRESETS['electric-water'])})
  finally:s.close()

class StudioCase(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
 def body(self):return {'id':uuid.uuid4().hex,'prompt':'电机带动水泵和水波','provider':'vertex','model':'fixture'}
 def test_all_presets_and_safe_literal_render(self):
  for name,preset in PRESETS.items():
   with self.subTest(name=name):
    normalized=validate_scene(preset);self.assertEqual(validate_scene(normalized),normalized)
    row=render(self.root,{'mechanism':'studio','preset':name});raw=artifact(self.root,row['id']);self.assertIn(b'Anatomy',raw);self.assertEqual(row['adapter_version'],'4.0.0');self.assertEqual(row['model_calls'],0)
  scene=copy.deepcopy(PRESETS['engine']);scene['title']='</script><img src=x onerror=alert(1)>'
  raw=artifact(self.root,render(self.root,{'mechanism':'studio','scene':scene})['id'])
  self.assertNotIn(b'</script><img',raw);self.assertIn(b'\\u003c/script>',raw)
 def test_scene_unknown_and_invalid_values(self):
  cases=[]
  for k,v in [('code','alert(1)'),('url','https://x.invalid')]:
   s=copy.deepcopy(PRESETS['engine']);s[k]=v;cases.append(s)
  for k,v in [('type','arbitrary-engine'),('id','../bad'),('effects',['flame','flame']),('effects',['html']),('params',{'rpm':True}),('params',{'rpm':float('nan')}),('params',{'cylinders':3}),('params',{'rpm':3601}),('params',{'script':'code'})]:
   s=copy.deepcopy(PRESETS['engine']);s['modules'][0][k]=v;cases.append(s)
  for value in cases:
   with self.subTest(value=value),self.assertRaises(CoreError):validate_scene(value)
 def test_links_and_overflow(self):
  base=PRESETS['electric-water']
  cases=[]
  for change in ({'from':'missing'},{'to':'motor'},{'ratio':0},{'ratio':True},{'ratio':5},{'kind':'electricity'}):
   s=copy.deepcopy(base);s['links'][0].update(change);cases.append(s)
  s=copy.deepcopy(base);s['links'].append(dict(s['links'][0]));cases.append(s)
  s=copy.deepcopy(base);s['modules'][2]=copy.deepcopy(s['modules'][1]);s['modules'][2]['id']='pump';s['links']= [{'from':'gear','to':'pump','kind':'shaft','ratio':1},{'from':'pump','to':'gear','kind':'shaft','ratio':1}];cases.append(s)
  s=copy.deepcopy(base);s['modules'][0]['params']={'voltage':24,'constant':.02,'resistance':1};s['modules'][1]['params']={'teeth_a':60,'teeth_b':12};s['links'][0]['ratio']=4;cases.append(s)
  for scene in cases:
   with self.assertRaises(CoreError):validate_scene(scene)
 def test_scope_and_disable(self):
  for value in ({'mechanism':'studio','preset':'bad'},{'mechanism':'studio','scene':PRESETS['engine'],'preset':'engine'},{'mechanism':'studio','code':'bad'}):
   with self.assertRaises(CoreError):validate_request(value)
  s=Skills(self.root);s.enable('gears',False);s.close()
  with self.assertRaises(CoreError):render(self.root,{'mechanism':'studio'})
  with self.assertRaises(CoreError):composer.submit(self.root,self.body(),FakeDialogue(self.root))
 def test_composition_idempotence_delivery_and_receipt(self):
  fake=FakeDialogue(self.root);body=self.body();first=composer.submit(self.root,body,fake);second=composer.submit(self.root,body,fake)
  self.assertEqual(fake.calls,1);self.assertTrue(second['existing']);self.assertEqual(composer.state(self.root,first['id'])['status'],'CANDIDATE')
  done=composer.finish(self.root,first['id']);self.assertEqual(done['status'],'DELIVERED');self.assertEqual(done['artifact']['model_calls'],1)
  self.assertEqual(composer.finish(self.root,first['id'])['artifact']['id'],done['artifact']['id']);self.assertEqual(len(composer.listing(self.root)),1)
  s=Dialogues(self.root);r=s.turn('anatomy-'+body['id']);self.assertFalse(json.loads(r['request'])['memory_enabled']);self.assertEqual(json.loads(r['request'])['skill'],'none');s.close()
  with self.assertRaises(CoreError):composer.submit(self.root,{**body,'prompt':'changed'},fake)
 def test_unknown_invalid_and_cancel_never_render_or_retry(self):
  for status,text in [('UNKNOWN',None),('SUCCEEDED','not JSON'),('SUCCEEDED',canonical({**PRESETS['engine'],'code':'bad'}))]:
   fake=FakeDialogue(self.root,status,text);body=self.body();composer.submit(self.root,body,fake);composer.submit(self.root,body,fake)
   self.assertEqual(fake.calls,1)
   with self.assertRaises(CoreError):composer.finish(self.root,body['id'])
  fake=FakeDialogue(self.root);body=self.body();composer.submit(self.root,body,fake);composer.cancel(self.root,body['id']);self.assertEqual(composer.state(self.root,body['id'])['status'],'CANCELLED')
  with self.assertRaises(CoreError):composer.finish(self.root,body['id'])
 def test_generation_scope(self):
  for change in ({'provider':'auto'},{'prompt':''},{'id':'../bad'},{'code':'bad'}):
   with self.assertRaises(CoreError):composer.submit(self.root,{**self.body(),**change},FakeDialogue(self.root))
 def test_custom_parts_reject_cycles_and_executable_fields(self):
  for change in ({'parent':'elbow'},{'shape':'html'},{'color':'url(x)'},{'position':[0,0,151]},{'amplitude':181},{'rotation':[0,float('inf'),0]},{'code':'bad'}):
   scene=copy.deepcopy(PRESETS['robot']);scene['modules'][0]['params']['parts'][0].update(change)
   with self.subTest(change=change),self.assertRaises(CoreError):validate_scene(scene)
  scene=copy.deepcopy(PRESETS['robot']);scene['modules'][0]['params']['parts']*=5
  with self.assertRaises(CoreError):validate_scene(scene)
 def test_candidate_identifier_repair_is_recorded_and_revalidated(self):
  scene=copy.deepcopy(PRESETS['electric-water']);scene['modules'][0]['id']='electric_motor';scene['links'][0]['from']='electric_motor'
  valid,changes=composer.candidate(canonical(scene));self.assertEqual(valid['modules'][0]['id'],'electric-motor');self.assertEqual(valid['links'][0]['from'],'electric-motor');self.assertEqual(changes[0]['from'],'electric_motor')
  scene['modules'][1]['id']='electric-motor'
  with self.assertRaises(CoreError):composer.candidate(canonical(scene))
  scene=copy.deepcopy(PRESETS['robot']);parts=scene['modules'][0]['params']['parts'];parts[0]['id']='main_base';parts[1]['parent']='main_base';valid,changes=composer.candidate(canonical(scene));self.assertEqual(valid['modules'][0]['params']['parts'][1]['parent'],'main-base')
  parts[0]['code']='bad'
  with self.assertRaises(CoreError):composer.candidate(canonical(scene))
  scene=copy.deepcopy(PRESETS['robot']);scene['modules'][0]['params']['parts'][1]['parent']='missing'
  with self.assertRaises(CoreError):validate_scene(scene)

if __name__=='__main__':unittest.main()
