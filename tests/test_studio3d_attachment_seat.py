import copy,unittest,hashlib,json,tempfile
from pathlib import Path
from host.studio3d_high_finish import asset_source
from modules.skills.studio3d.attachment_seat import validate,components,axial_translation
class AttachmentSeat(unittest.TestCase):
 def sample(self):
  return {'schema':'jarvis.studio3d.attachment-seat.v1','author':'Codex','evidence':'Actual isolated fasteners above the support','targets':[{'object':'bolts','support':'hub','center':[0,1,.5],'axis':[0,1,0],'radial_range':[.06,.11],'axial_range':[.08,.15],'expected_components':6}],'inspection':{'bounds':[[-1,-1,0],[1,1,2]],'resolution':[960,640],'samples':16,'regions':{'hub':['hub']},'views':[{'id':'left','direction':[0,1,0]}]},'radial_inset':.01,'embed':.0008,'max_move':.025}
 def test_contract_scope_and_limits(self):
  c=self.sample();validate(c,['bolts','hub'])
  for patch in [{'radial_inset':.1},{'embed':0},{'max_move':float('nan')},{'code':'anything'},{'targets':[]}]:
   bad=copy.deepcopy(c);bad.update(patch)
   with self.assertRaises(ValueError):validate(bad,['bolts','hub'])
  bad=copy.deepcopy(c);bad['targets'][0]['support']='bolts'
  with self.assertRaises(ValueError):validate(bad,['bolts','hub'])
 def test_components_keep_indices(self):
  self.assertEqual(components(7,[[0,1,2],[2,3,0],[4,5,6]]),[[0,1,2,3],[4,5,6]])
 def test_v2_footprint_and_adjacent_object_scope(self):
  c=self.sample();c['schema']='jarvis.studio3d.attachment-seat.v2';c['footprint_scale']=.72;c['targets'][0]['blockers']=['ring'];validate(c,['bolts','hub','ring'])
  for value in (.5,1.1,True,float('nan')):
   bad=copy.deepcopy(c);bad['footprint_scale']=value
   with self.assertRaises(ValueError):validate(bad,['bolts','hub','ring'])
  for blockers in ([],['missing'],['bolts'],['hub'],['ring','ring']):
   bad=copy.deepcopy(c);bad['targets'][0]['blockers']=blockers
   with self.assertRaises(ValueError):validate(bad,['bolts','hub','ring'])
 def test_contact_closes_gap_with_visible_head(self):
  delta,c=axial_translation(.11,.125,[.098,.099,.1],.0008,.025)
  self.assertAlmostEqual(delta,-.0128);self.assertLessEqual(max(c['base_gap_after']),0);self.assertGreater(c['minimum_visible_height'],.004)
 def test_miss_far_support_or_burial_rejected(self):
  for hits in ([],[.02],[.098,.12],[float('nan')]):
   with self.assertRaises(ValueError):axial_translation(.11,.125,hits,.0008,.025)
 def test_source_requires_contact_receipt_and_unchanged_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);ident='c'*32;f=root/'artifacts/studio3d-attachment-seat'/ident;f.mkdir(parents=True);raw=b'verified native editable source'
   (f/'model.blend').write_bytes(raw)
   r={'id':ident,'operation':'attachment_seat','status':'BUILT_AWAITING_VISUAL_COMPARISON','report':{'unchanged_non_targets':True,'source_unchanged':True,'actions':[{'target':'bolts'}],'contacts_checked':True,'after_object_digests':{'bolts':'digest','hub':'digest'}},'files':{'model.blend':{'sha256':hashlib.sha256(raw).hexdigest()}}}
   (f/'status.json').write_text(json.dumps(r));self.assertEqual(set(asset_source(root,ident,'attachment_seat')[1]),{'model.blend'})
   for key in ('contacts_checked','source_unchanged','unchanged_non_targets'):
    bad=copy.deepcopy(r);bad['report'][key]=False;(f/'status.json').write_text(json.dumps(bad))
    with self.assertRaises(ValueError):asset_source(root,ident,'attachment_seat')
   (f/'status.json').write_text(json.dumps(r));(f/'model.blend').write_bytes(b'changed native editable source')
   with self.assertRaises(ValueError):asset_source(root,ident,'attachment_seat')
if __name__=='__main__':unittest.main()
