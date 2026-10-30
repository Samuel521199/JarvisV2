import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from host.studio3d_high_finish import asset_source
from modules.skills.studio3d.surface_material import validate

class SurfaceMaterial(unittest.TestCase):
 def config(self):
  return {'schema':'jarvis.studio3d.surface-material.v1','author':'Codex','goal':'Test bounded material operation','evidence':'Test paired native views','views':[{'id':'whole','center':[0,0,1],'direction':[1,1,1],'ortho_scale':5}],'resolution':[960,640],'samples':8,'settings':{'tile_span':.75,'paint_roughness':.48,'steel_roughness':.34,'edge_wear':.45,'cavity_dirt':.48,'ground_dust':.2,'bump_distance':.00004},'spades':['blade']}

 def test_accepts_bounded_material_and_camera(self):validate(self.config(),['blade'])

 def test_scoped_paint_contract_leaves_other_roles_out_of_scope(self):
  c=self.config();c['schema']='jarvis.studio3d.surface-material.v2';c.pop('spades');c['targets']=['shield'];c['local_wear']={'base_detail':.08,'patch_strength':.35,'edge_radius':.002}
  validate(c,['shield','tyre','spade'])
  for patch in [{'targets':['shield','shield']},{'targets':['absent']},{'targets':[]},{'spades':['spade']},{'local_wear':{'base_detail':.08,'patch_strength':.35,'edge_radius':.1}}]:
   bad=copy.deepcopy(c);bad.update(patch)
   with self.assertRaises(ValueError):validate(bad,['shield','tyre','spade'])

 def test_rejects_rock_bump_gloss_unbounded_or_unknown_target(self):
  for key,value in [('bump_distance',.01),('paint_roughness',.02),('edge_wear',1),('tile_span',float('nan')),('ground_dust',True)]:
   c=self.config();c['settings'][key]=value
   with self.assertRaises(ValueError):validate(c,['blade'])

 def test_local_chip_regions_are_scoped_and_bounded(self):
  c=self.config();c['schema']='jarvis.studio3d.surface-material.v2';c.pop('spades');c['targets']=['shield'];c['local_wear']={'base_detail':.1,'patch_strength':.2,'edge_radius':.002}
  region={'center':[.1,.5,1.2],'radii':[.2,.1,.05],'coverage':.6};c['damage_regions']=[region];validate(c,['shield','rubber'])
  for patch in [{'radii':[0,.1,.1]},{'radii':[.2,10,.2]},{'center':[0,float('nan'),0]},{'coverage':True},{'coverage':1},{'script':'code'}]:
   bad=copy.deepcopy(c);bad['damage_regions'][0].update(patch)
   with self.assertRaises(ValueError):validate(bad,['shield','rubber'])
  for regions in ([],[region]*9):
   bad=copy.deepcopy(c);bad['damage_regions']=regions
   with self.assertRaises(ValueError):validate(bad,['shield','rubber'])
  old=self.config();old['damage_regions']=[region]
  with self.assertRaises(ValueError):validate(old,['blade'])

 def test_overlay_contract_cannot_rewrite_coating_controls(self):
  c=self.config();c['schema']='jarvis.studio3d.surface-material.v3';c.pop('spades');c.pop('settings');c['targets']=['shield'];c['damage_regions']=[{'center':[0,.5,1],'radii':[.2,.1,.1],'coverage':.25}]
  validate(c,['shield'])
  for patch in [{'settings':self.config()['settings']},{'local_wear':{'base_detail':.1}},{'damage_regions':[]},{'targets':['rubber']}]:
   bad=copy.deepcopy(c);bad.update(patch)
   with self.assertRaises(ValueError):validate(bad,['shield'])
  for change in [{'spades':['elsewhere']},{'python':'arbitrary code'},{'lods':True},{'resolution':[8192,8192]}]:
   c=self.config();c.update(change)
   with self.assertRaises(ValueError):validate(c,['blade'])

 def test_receipt_source_cannot_change_or_cross_operation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);ident='a'*32;folder=root/'artifacts/studio3d-demonstration'/ident;folder.mkdir(parents=True)
   files={}
   for name in ('model.blend','model.glb'):
    raw=(name*8).encode();(folder/name).write_bytes(raw);files[name]={'sha256':hashlib.sha256(raw).hexdigest()}
   receipt={'id':ident,'operation':'demonstration','status':'BUILT_AWAITING_VISUAL_COMPARISON','official_format_issues':{'numErrors':0},'report':{'after_object_digests':{'blade':'digest'}},'files':files}
   p=folder/'status.json';p.write_text(json.dumps(receipt))
   self.assertEqual(asset_source(root,ident,'demonstration')[0],['blade'])
   for field,bad in [('operation','surface_material'),('status','RUNNING'),('id','b'*32)]:
    modified=copy.deepcopy(receipt);modified[field]=bad;p.write_text(json.dumps(modified))
    with self.assertRaises(ValueError):asset_source(root,ident,'demonstration')
   p.write_text(json.dumps(receipt));(folder/'model.blend').write_bytes(b'different source bytes')
   with self.assertRaises(ValueError):asset_source(root,ident,'demonstration')

 def test_material_stage_is_blend_only_export_stage_still_requires_format_gate(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);ident='b'*32;folder=root/'artifacts/studio3d-surface-material'/ident;folder.mkdir(parents=True)
   raw=b'verified native blend bytes';(folder/'model.blend').write_bytes(raw)
   receipt={'id':ident,'operation':'surface_material','status':'BUILT_AWAITING_VISUAL_COMPARISON','report':{'after_object_digests':{'blade':'digest'},'geometry_and_transform_unchanged':True,'source_unchanged':True},'files':{'model.blend':{'sha256':hashlib.sha256(raw).hexdigest()}}}
   p=folder/'status.json';p.write_text(json.dumps(receipt));names,files=asset_source(root,ident,'surface_material')
   self.assertEqual(names,['blade']);self.assertEqual(set(files),{'model.blend'})
   receipt['report']['geometry_and_transform_unchanged']=False;p.write_text(json.dumps(receipt))
   with self.assertRaises(ValueError):asset_source(root,ident,'surface_material')

if __name__=='__main__':unittest.main()
