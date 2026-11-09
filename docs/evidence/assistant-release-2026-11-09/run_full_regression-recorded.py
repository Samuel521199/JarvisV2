from pathlib import Path
import concurrent.futures,hashlib,json,subprocess,sys,time
ROOT=Path('D:/Jarvis-dev');OUT=ROOT/'user-data/full-regression-r2';OUT.mkdir(exist_ok=False)
started=time.monotonic();files=sorted((ROOT/'tests').glob('test_*.py'))
worker="""import sys,unittest,json,time;from pathlib import Path
sys.path[:0]=['D:/Jarvis-dev','D:/Jarvis-dev/tests']
started=time.monotonic();s=unittest.defaultTestLoader.discover('D:/Jarvis-dev/tests',pattern=sys.argv[1]);r=unittest.TextTestRunner(verbosity=1).run(s)
Path(sys.argv[2]).write_text(json.dumps({'file':sys.argv[1],'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':[(x.id(),why) for x,why in r.skipped],'seconds':time.monotonic()-started,'passed':r.wasSuccessful()}),encoding='utf-8');sys.exit(not r.wasSuccessful())
"""
def check(path):
    result=OUT/(path.stem+'.json');log=OUT/(path.stem+'.log')
    with log.open('wb') as stream:
        try:
            p=subprocess.run([sys.executable,'-I','-B','-c',worker,path.name,str(result)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if not result.exists():return {'file':path.name,'passed':False,'error':'worker result missing','returncode':p.returncode}
            value=json.loads(result.read_text(encoding='utf-8'));value['returncode']=p.returncode;value['passed'] &= p.returncode==0;value['log_sha256']=hashlib.sha256(log.read_bytes()).hexdigest();return value
        except subprocess.TimeoutExpired:return {'file':path.name,'passed':False,'error':'600 second file deadline'}
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(check,path) for path in files]
    for future in concurrent.futures.as_completed(futures):
        rows.append(future.result());(OUT/'progress.json').write_text(json.dumps({'files_finished':len(rows),'files_total':len(files),'tests_finished':sum(x.get('tests',0) for x in rows),'failed_files':[x['file'] for x in rows if not x['passed']]}),encoding='utf-8')
report={'scope':'entire test_*.py inventory, unchanged assertions, separate process per file, concurrency 2','tests':sum(x.get('tests',0) for x in rows),'failures':sum(x.get('failures',0) for x in rows),'errors':sum(x.get('errors',0) for x in rows),'skipped':sum(len(x.get('skipped',[])) for x in rows),'seconds':time.monotonic()-started,'files':sorted(rows,key=lambda x:x['file'])}
report['passed']=all(x['passed'] for x in rows) and report['tests']==1531
(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');sys.exit(not report['passed'])
