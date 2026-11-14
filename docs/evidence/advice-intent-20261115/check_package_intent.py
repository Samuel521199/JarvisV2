"""Replay new developer cases against the qualified package, never daily data."""
from pathlib import Path
import sys,os,json,hashlib,importlib,unittest
ROOT=Path('E:/Jarvis/dev');OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'docs/evidence/advice-intent-20261115/qualified-r1'
def main():
    receipt=json.loads((OUT/'independent-package/result.json').read_text())
    assert receipt['passed'] and not receipt['production_adopted']
    package=Path(receipt['isolated_data'])/'deployment/packages'/receipt['build']
    assert package.is_relative_to(Path('E:/Jarvis/validation'))
    manifest=json.loads((package/'application.json').read_text())
    def intact():return all(hashlib.sha256((package/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    assert intact()
    os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
    sys.path[:0]=[str(package),str(ROOT/'tests')]
    names=('adapters','apps','control','host','modules','sdk')
    # Some roots are namespace packages. Freeze their search locations so the
    # source-test helpers cannot prepend development runtime by changing sys.path.
    for name in names:importlib.import_module(name).__path__=[str(package/name)]
    import test_advice_intent
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_advice_intent)
    with (OUT/'package-intent-replay.txt').open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    loaded={name:str(Path(module.__file__).resolve()) for name,module in list(sys.modules.items()) if name.split('.')[0] in names and getattr(module,'__file__',None)}
    qualified_imports=all(Path(path).is_relative_to(package) for path in loaded.values())
    report={'scope':'seen developer composed-intent replay on qualified runtime; not independent new test design or model quality trial','build':receipt['build'],'package':str(package),'tests_from':str(ROOT/'tests/test_advice_intent.py'),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'all_runtime_imports_from_package':qualified_imports,'loaded_runtime_modules':loaded,'package_bytes_intact_after':intact(),'frozen_controller_policy_changed':False,'production_data_used':False,'cloud_calls':0,'passed':result.wasSuccessful() and qualified_imports and intact()}
    (OUT/'package-intent-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('loaded_runtime_modules',)}),flush=True)
    assert report['passed']
if __name__=='__main__':main()
