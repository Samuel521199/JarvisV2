import unittest,copy
from modules.skills.studio3d.production_recovery import abandon_teaching_plan,quarantined,new_request_allowed
class BoundedPlanRecovery(unittest.TestCase):
 def inputs(self):
  key='external-arm-border-02-bounded-plan-v1';row={'status':'UNKNOWN','error':'connection_failed','request_id':'original','signature':'immutable'}
  return {'calls':{key:row}},key,dict(id='original',status='UNKNOWN',error='connection_failed',reply=None),dict(request_id='original',local_transport_finished=True,active_native_transports=0,asset_lock_held=True,implementation_sha256={'transport':'a'*64}),'now',dict(request_id='original',read_only=True,has_reply=False,plan_executed=False,source_sha256='b'*64)
 def test_quarantine_preserves_identity_and_blocks_signature_replay(self):
  args=self.inputs();out=abandon_teaching_plan(*args);r=out['calls'][args[1]];self.assertTrue(quarantined(r));self.assertEqual(r['signature'],'immutable');self.assertNotIn('recovery_disposition',args[0]['calls'][args[1]])
  with self.assertRaises(ValueError):new_request_allowed(out['calls'],'immutable')
 def test_rejects_missing_reply_or_execution_evidence(self):
  for evidence in (None,dict(self.inputs()[-1],plan_executed=True),dict(self.inputs()[-1],has_reply=True),dict(self.inputs()[-1],source_sha256='x')):
   a=list(self.inputs());a[-1]=evidence
   with self.assertRaises(ValueError):abandon_teaching_plan(*a)
 def test_rejects_live_transport_or_recovered_reply(self):
  for index,key,value in ((3,'active_native_transports',1),(2,'reply','actual response'),(2,'status','RUNNING')):
   a=list(self.inputs());a[index][key]=value
   with self.assertRaises(ValueError):abandon_teaching_plan(*a)
