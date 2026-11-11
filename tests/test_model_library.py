import base64,json,tempfile,unittest
from pathlib import Path
from modules.skills.model_library.store import Library,digest
from host.model_library import decode_import,upload
from sdk.protocol import CoreError

class ModelLibrary(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'source.blend';self.source.write_bytes(b'original editable content');self.lib=Library(self.root)
  for ident,kind in [('panzer','model'),('wheel','part')]:self.lib.put_asset({'id':ident,'name':'二号坦克' if kind=='model' else '二号坦克轮组','category':'wwii','kind':kind,'tags':['德军','二战'],'status':'reference'})
 def tearDown(self):self.lib.close();self.tmp.cleanup()
 def test_content_addressed_snapshot_preserves_original_and_deduplicates(self):
  first=self.lib.add_file('panzer',self.source,'editable');second=self.lib.add_file('panzer',self.source,'editable');third=self.lib.add_file('wheel',self.source,'editable')
  self.assertEqual(first,second);self.assertNotEqual(first,third);self.assertEqual(len(list(self.lib.objects.rglob('*.blend'))),1)
  self.source.write_bytes(b'changed author file');stored=self.lib.object_path(self.lib.file('panzer',first));self.assertEqual(stored.read_bytes(),b'original editable content')
 def test_digest_mismatch_never_registers_changed_source(self):
  with self.assertRaises(CoreError):self.lib.add_file('panzer',self.source,'editable','0'*64)
  self.assertEqual(self.lib.detail('panzer')['files'],[])
 def test_cross_asset_files_and_traversal_are_rejected(self):
  file=self.lib.add_file('panzer',self.source,'editable')
  for owner,ident in [('wheel',file),('panzer','../source'),('../panzer',file)]:
   with self.subTest(owner=owner,ident=ident),self.assertRaises(CoreError):self.lib.file(owner,ident)
 def test_search_and_future_categories_are_not_limited_to_wwii(self):
  self.lib.put_asset({'id':'person','name':'银发人物','category':'characters','kind':'character','tags':['角色'],'status':'draft'})
  self.assertEqual([a['id'] for a in self.lib.catalogue('轮组',kind='part')['assets']],['wheel']);self.assertEqual([a['id'] for a in self.lib.catalogue(category='characters')['assets']],['person'])
 def test_reference_methods_need_counterexamples_and_cannot_promote(self):
  with self.assertRaises(CoreError):self.lib.add_case('panzer',{'id':'case','title':'方法'})
  self.lib.add_case('panzer',{'id':'case','title':'方法','prerequisites':['已确认单位'],'counterexamples':['独立归一化'],'promoted':True});self.assertFalse(self.lib.detail('panzer')['methods'][0]['promoted'])
 def test_browser_import_contract_keeps_small_protocol_separate(self):
  self.assertEqual(decode_import(b'{"data":"'+b'x'*300000+b'"}')['data'][:2],'xx')
  with self.assertRaises(CoreError):decode_import(b'{"name":"a","name":"b"}')
  for fields in [{'filename':'../a.glb','data':'AA=='},{'filename':'x.py','data':'AA=='},{'filename':'x.blend','data':'AA==','code':'run'}]:
   with self.subTest(fields=fields),self.assertRaises(CoreError):upload(self.root,fields)
 def test_metadata_and_annotations_survive_reopening(self):
  self.lib.metadata('panzer',['已复核','LOD0'],'保留的说明')
  note=self.lib.annotate('panzer',{'title':'炮塔备注','text':'检查安装位置','point':None,'variant_id':None})
  self.lib.close();self.lib=Library(self.root)
  self.assertEqual(self.lib.detail('panzer')['description'],'保留的说明');self.assertEqual(self.lib.detail('panzer')['annotations'][0]['id'],note['id'])
 def test_invalid_glb_import_never_leaves_an_empty_asset(self):
  with self.assertRaises(CoreError):upload(self.root,{'name':'broken','category':'general','kind':'model','filename':'bad.glb','data':base64.b64encode(b'bad glb').decode()})
  self.assertEqual(self.lib.catalogue()['total'],2)
 def test_future_character_source_import_is_stored_without_execution(self):
  result=upload(self.root,{'name':'人物编辑源','category':'characters','kind':'character','tags':['角色'],'filename':'character.blend','data':base64.b64encode(b'editable snapshot').decode()})
  self.assertEqual(result['kind'],'character');self.assertEqual(result['status'],'draft');self.assertEqual(result['variants'],[])
  self.assertEqual(self.lib.object_path(result['files'][0]).read_bytes(),b'editable snapshot')
 def test_annotation_cannot_cross_versions_or_assets(self):
  f=self.lib.add_file('panzer',self.source,'editable');self.lib.db.execute('INSERT INTO variants VALUES(?,?,?,?,?)',('panzer','lod0',f,'LOD0','game'));self.lib.db.commit();sha=self.lib.file('panzer',f)['sha256']
  value={'title':'接口','text':'复核','variant_id':'lod0','sha256':sha,'point':[1,2,3],'object_name':'wheel','point_space':'object'};note=self.lib.annotate('panzer',value)
  with self.assertRaises(CoreError):self.lib.annotate('panzer',{**value,'sha256':'0'*64})
  with self.assertRaises(CoreError):self.lib.annotate('wheel',{**value,'id':note['id'],'variant_id':None,'point':None})
  self.lib.annotate('panzer',{**value,'id':note['id'],'archived':True});self.assertEqual(self.lib.detail('panzer')['annotations'],[])
 def test_annotation_resolution_persists_and_unknown_states_are_rejected(self):
  note=self.lib.annotate('panzer',{'title':'接缝','text':'待检查','variant_id':None,'point':None,'status':'open'})
  self.lib.annotate('panzer',{'id':note['id'],'title':'接缝','text':'已检查','variant_id':None,'point':None,'status':'resolved'})
  self.assertEqual(self.lib.detail('panzer')['annotations'][0]['status'],'resolved')
  with self.assertRaises(CoreError):self.lib.annotate('panzer',{'title':'错误','text':'','status':'automatic-pass'})

if __name__=='__main__':unittest.main()
