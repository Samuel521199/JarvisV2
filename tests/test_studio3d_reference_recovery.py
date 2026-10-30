import unittest
from modules.skills.studio3d.production_recovery import abandon_reference_analysis,quarantined,new_request_allowed
class ReferenceRecovery(unittest.TestCase):
 def inputs(self):
  key='asset-exterior-04-reference-analysis-v1';row={'status':'UNKNOWN','error':'connection_failed','request_id':'r','signature':'original'}
  remote={'id':'r','status':'UNKNOWN','error':'connection_failed','reply':None}
  transport={'request_id':'r','local_transport_finished':True,'active_native_transports':0,'asset_lock_held':True,'implementation_sha256':{'adapter':'a'*64}}
  diagnostic={'read_only':True,'analysis_accepted':False,'source_sha256':'b'*64}
  return {'calls':{key:row}},key,remote,transport,diagnostic,'now'
 def test_unknown_preserved_and_same_signature_replay_rejected(self):
  args=self.inputs();out=abandon_reference_analysis(*args);row=out['calls'][args[1]]
  self.assertTrue(quarantined(row));self.assertEqual(row['status'],'UNKNOWN');self.assertFalse(row['recovery_disposition']['cost_known'])
  self.assertNotIn('recovery_disposition',args[0]['calls'][args[1]])
  new_request_allowed(out['calls'],'different')
  with self.assertRaises(ValueError):new_request_allowed(out['calls'],'original')
 def test_live_wrong_request_or_recovered_reply_refused(self):
  for field,value in [('status','RUNNING'),('id','other'),('reply','recovered')]:
   args=list(self.inputs());args[2][field]=value
   with self.assertRaises(ValueError):abandon_reference_analysis(*args)
  args=list(self.inputs());args[3]['active_native_transports']=1
  with self.assertRaises(ValueError):abandon_reference_analysis(*args)
 def test_missing_readonly_proof_and_unrelated_stage_refused(self):
  for patch in ({'read_only':False},{'analysis_accepted':True},{'source_sha256':'bad'}):
   args=list(self.inputs());args[4].update(patch)
   with self.assertRaises(ValueError):abandon_reference_analysis(*args)
  args=list(self.inputs());args[0]['calls']['paid-mutation']=args[0]['calls'][args[1]];args[1]='paid-mutation'
  with self.assertRaises(ValueError):abandon_reference_analysis(*args)
if __name__=='__main__':unittest.main()
