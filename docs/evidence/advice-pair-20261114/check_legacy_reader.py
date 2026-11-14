"""A qualified older runtime resumes a new optional-metrics planning record."""
from pathlib import Path
import os,sys,json,subprocess,hashlib
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114'
if '--controller-runtime' in sys.argv:
    OUT=OUT/'controller-reader-r1';OUT.mkdir(exist_ok=False)
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp');sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
from host.core import Core
import test_goal_advice as fixture

def main():
    prior=json.loads((ROOT/'docs/evidence/advice-budget-20261114/final-r2/independent-package/result.json').read_text())
    if '--controller-runtime' in sys.argv:
        from control.controller_pin import read
        from modules.release_recovery.application import Applications
        daily=Path('E:/Jarvis/runtime/user-data');pin=read(daily);approved=Applications(daily).approved(pin['runtime_source_build'],fresh=False)
        prior={'passed':bool(approved),'build':pin['runtime_source_build'],'isolated_data':str(daily),'source_commit':None}
    legacy=Path(prior['isolated_data'])/'deployment/packages'/prior['build'];manifest=json.loads((legacy/'application.json').read_text())
    assert prior['passed'] and all(hashlib.sha256((legacy/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    case=fixture.GoalAdvice('test_advice_is_automatically_assembled_but_not_promoted_or_authorized');case.setUp()
    try:
        assert case.root.resolve().is_relative_to(Path('E:/Jarvis/validation/temp'))
        case.seed();ident=case.create();case.plan(ident);projection=case.detail(ident)['planning_advice']
        assert projection['message_exposure'] and projection['model_dispatched']
        (OUT/'current-ui-projection.json').write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        before=case.core.db.all('SELECT * FROM model_calls');grants=case.core.db.all('SELECT * FROM grants')
        with case.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
        case.core.close()
        code="import sys,json;from pathlib import Path;sys.path.insert(0,"+repr(str(legacy))+");from control.application_compatibility import require_compatible;require_compatible(Path("+repr(str(case.root))+"),Path("+repr(str(legacy))+"));from host import goals;r=goals.execute(Path("+repr(str(case.root))+"),"+repr(ident)+");print(json.dumps({'status':r['status'],'proposal':r['proposal']},ensure_ascii=False))"
        child=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],capture_output=True,text=True,encoding='utf-8',timeout=60)
        (OUT/'legacy-reader-replay.txt').write_text(child.stdout+child.stderr,encoding='utf-8');assert child.returncode==0,child.stderr
        case.core=Core(case.root);after=case.core.db.all('SELECT * FROM model_calls');now=case.detail(ident)['planning_advice']
        checks={'legacy_resumes_review':json.loads(child.stdout)['status']=='REVIEW','calls_and_usage_unchanged':before==after,'grants_and_spending_unchanged':grants==case.core.db.all('SELECT * FROM grants'),
          'new_reader_retains_existing_dispatch':now['model_dispatched'],'old_reader_may_drop_optional_metric':now['message_exposure'] is None,'sources_still_valid':now['current'],'legacy_bytes_still_intact':all(hashlib.sha256((legacy/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())}
        report={'scope':'actual previous qualified runtime, new optional observation metadata; synthetic provider receipt and restricted fixture only','legacy_build':prior['build'],'legacy_source_commit':prior['source_commit'],'origin':'installed controller runtime source' if '--controller-runtime' in sys.argv else 'previous independently qualified candidate','legacy_inventory_files':len(manifest['files']),
          'checks':checks,'new_real_model_calls':0,'production_data_used':False,'schema_remains':1,'passed':all(checks.values())}
        (OUT/'legacy-reader-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False));assert report['passed']
    finally:case.tearDown()
if __name__=='__main__':main()
