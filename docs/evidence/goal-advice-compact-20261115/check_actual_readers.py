"""Actual frozen readers on isolated synthetic v1/v2 goals; no production writes."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path('E:/Jarvis/dev');OUT=Path(__file__).parent
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
import test_goal_advice as fixture
from host.core import Core
from host import goal_context
from sdk.protocol import canonical


def main():
    old=json.loads((ROOT/'docs/evidence/advice-pair-20261114/independent-package/result.json').read_text())
    new=json.loads((OUT/'independent-package/result.json').read_text())
    packages={name:Path(value['isolated_data'])/'deployment/packages'/value['build'] for name,value in [('v1',old),('v2',new)]}
    def intact(package):
        manifest=json.loads((package/'application.json').read_text())
        return all(hashlib.sha256((package/name).read_bytes()).hexdigest()==row['sha256'] for name,row in manifest['files'].items())
    assert all(intact(p) for p in packages.values())
    rows=[]
    for version in (1,2):
        case=fixture.GoalAdvice('test_advice_is_automatically_assembled_but_not_promoted_or_authorized');case.setUp()
        try:
            assert case.root.resolve().is_relative_to(Path('E:/Jarvis/validation/temp'))
            case.seed();ident=case.create();context=goal_context.get(case.core,ident);context['view']['conditional_advice']['version']=version
            with case.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ident))
            case.plan(ident)
            for reader,package in packages.items():
                with case.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
                before=case.core.db.all('SELECT * FROM model_calls');grants=case.core.db.all('SELECT * FROM grants');case.core.close()
                code='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from control.application_compatibility import require_compatible
from sdk.protocol import CoreError
root=Path(sys.argv[2])
try:
    required=require_compatible(root,Path(sys.argv[1]))
except CoreError as error:
    print(json.dumps({'blocked':True,'code':error.code}))
else:
    from host import goals
    result=goals.execute(root,sys.argv[3])
    print(json.dumps({'blocked':False,'status':result['status'],'required':required['required']}))
'''
                run=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code,str(package),str(case.root),ident],capture_output=True,text=True,encoding='utf-8',timeout=60)
                case.core=Core(case.root)
                (OUT/f'actual-reader-{reader}-data-{version}.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                assert run.returncode==0,run.stderr
                result=json.loads(run.stdout);blocked=version==2 and reader=='v1'
                assert result['blocked']==blocked
                assert result.get('code')=='application_data_compatibility' if blocked else result.get('status')=='REVIEW'
                assert case.core.db.all('SELECT * FROM model_calls')==before
                assert case.core.db.all('SELECT * FROM grants')==grants
                rows.append({'data_version':version,'reader':reader,'result':result,'model_ledger_and_grants_unchanged':True})
        finally:case.tearDown()
    report={'scope':'actual qualified v1/v2 packages; synthetic cached receipts, no new cloud calls; not live controller promotion',
        'packages':{name:str(p) for name,p in packages.items()},'rows':rows,'packages_intact':all(intact(p) for p in packages.values()),'production_data_used':False,'passed':True}
    assert report['packages_intact']
    (OUT/'actual-readers.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
