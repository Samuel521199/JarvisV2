"""Related regressions for optional advice exposure; no cloud requests."""
from pathlib import Path
import sys,os,json,hashlib,unittest,time,re
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114'
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp');sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
files=['host/planning_advice.py','host/goals.py','apps/workbench/planning-advice.js','tests/test_goal_advice_exposure.py']
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
rows=[];ids=[]
for pattern in ['test_goal_advice.py','test_goal_advice_budget.py','test_assistant_goals.py','test_application_compatibility.py','test_workbench.py']:
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern);start=time.monotonic()
    with (OUT/(pattern[:-3]+'-exposure.txt')).open('w',encoding='utf-8') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    row={'pattern':pattern,'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'seconds':time.monotonic()-start,'passed':r.wasSuccessful()};rows.append(row)
    text=(OUT/(pattern[:-3]+'-exposure.txt')).read_text();ids+=re.findall(r'^test_\S+ \(([^)]+)\) \.\.\.',text,re.M)
    (OUT/'exposure-regressions.json').write_text(json.dumps({'source_sha256':hashes,'rows':rows,'unique_tests':len(set(ids)),'test_ids':ids,'source_unchanged':all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items()),'passed':all(row['passed'] for row in rows)},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(row),flush=True)
    if not r.wasSuccessful():raise SystemExit(1)
assert len(ids)==len(set(ids))
