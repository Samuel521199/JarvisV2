"""Retain inspectable final-package outputs from the already real-generated candidates."""
from pathlib import Path
import hashlib,importlib,json,os,sys
ROOT=Path('E:/Jarvis/dev');OUT=Path(__file__).parent/'qualified-r1';DEST=OUT/'actual-artifacts'
def main():
 receipt=json.loads((OUT/'independent-package/result.json').read_text(encoding='utf-8'));assert receipt['passed']
 package=Path(receipt['isolated_data'])/'deployment/packages'/receipt['build']
 manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
 def intact():return all(hashlib.sha256((package/n).read_bytes()).hexdigest()==m['sha256'] for n,m in manifest['files'].items())
 assert intact();DEST.mkdir(exist_ok=False)
 os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
 sys.path[:0]=[str(package),str(ROOT/'tests')]
 namespaces=('adapters','apps','control','host','modules','sdk')
 for name in namespaces:importlib.import_module(name).__path__=[str(package/name)]
 from test_repair_return import RepairReturnTests
 from test_development import Provider,plan
 from sdk.protocol import decode
 from control.paths import child
 rows=[]
 for domain in ('notes','practice','quote'):
  case=RepairReturnTests('test_source_cancel_before_model_preserves_old_tool_and_calls');case.setUp()
  try:
   _,tid,ident,_=case.begin_auto(domain,wrong_original=True)
   candidate=json.loads((OUT.parent/'native-r2'/domain/'result.json').read_text(encoding='utf-8'))['candidate']
   spec=case.core.development.get(ident)['spec'];result=case.execute(ident,Provider([{**plan(),'capability':spec['capability']},candidate]))
   assert result['status']=='CLOSED',result
   actions=case.core.tasks.actions(result['child_task']);delivery=decode(next(a for a in actions if a['step_id']=='deliver')['result'])
   data=child(case.root,delivery['relative_path']).read_bytes();sha=hashlib.sha256(data).hexdigest()
   assert sha==delivery['sha256'];(DEST/(domain+'.txt')).write_bytes(data)
   row={'domain':domain,'condition_score':result['actual']['condition_score'],'original_condition_score':0,
    'acceptance_digest':result['acceptance_digest'],'actual':result['actual'],'delivery_receipt':delivery,'export_sha256':sha,
    'source_input':result['rework_request']['proposal']['input_text'],'same_bytes_as_delivered':True,'new_real_model_calls':0}
   (DEST/(domain+'-receipt.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');rows.append(row)
  finally:case.tearDown()
 imports=all(Path(m.__file__).resolve().is_relative_to(package) for n,m in list(sys.modules.items()) if n.split('.')[0] in namespaces and getattr(m,'__file__',None))
 report={'passed':intact() and imports and len(rows)==3,'build':receipt['build'],'all_runtime_imports_from_package':imports,
  'package_bytes_intact':intact(),'new_real_model_calls':0,'scope':'exported artifacts of final-package replay using previous real model candidates; synthetic business inputs','rows':rows}
 (DEST/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'artifacts':len(rows),'new_real_model_calls':0}),flush=True);assert report['passed']
if __name__=='__main__':main()
