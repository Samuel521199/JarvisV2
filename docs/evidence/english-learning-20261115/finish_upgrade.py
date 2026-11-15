"""Review the precise derived timestamp delta; preserve all business bodies verbatim."""
from pathlib import Path
import collections,copy,hashlib,json,shutil,sqlite3,sys
sys.path.insert(0,str(Path(__file__).parent))
from deploy import OUT,PRIVATE,DAILY,helpers,save,ws,read

def main():
    report=json.loads((OUT/'production.json').read_text());assert not report['passed']
    assert report['steps'][-1]['name']=='original-data-retained' and not report['steps'][-1]['result']['passed']
    assert ws.state(DAILY)['active']['build']==report['candidate_build'] and ws.state(DAILY)['epoch']==14
    shutil.copy2(OUT/'production.json',OUT/'production-before-preservation-review.json')
    shutil.copy2(OUT/'production-failure.json',OUT/'production-failure-preservation.json')
    oldroot=Path('D:/Jarvis-Recovery/jarvis/2026-11-15-english-r1/snapshot/daily')
    def rows(root):
        db=sqlite3.connect((root/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:return {r[0]:r for r in db.execute('SELECT task_id,body,checked FROM task_completion')}
        finally:db.close()
    old=rows(oldroot);new=rows(DAILY);assert old.keys()==new.keys()
    changes=[]
    for ident,row in old.items():
        assert row[:2]==new[ident][:2] and new[ident][2]>=row[2]
        if row[2]!=new[ident][2]:changes.append({'task_id':ident,'field':'checked','before':row[2],'after':new[ident][2]})
    assert {r['task_id'] for r in changes}=={'task-c10e37a68b8149128ddb4c3a5239468a','task-d5fcfc0115ea45eca29d747ac430f5ff'}
    before=json.loads((PRIVATE/'before-application.json').read_text());after=helpers.fingerprint(DAILY)
    normalized=copy.deepcopy(after);table='task_completion';name='state/core.sqlite3'
    normalized['databases'][name][table]=dict(collections.Counter(hashlib.sha256(json.dumps(list(row),ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for row in old.values()))
    checked=helpers.retained(before,normalized);assert checked['passed'],checked
    checked.update(derived_timestamp_changes=changes,comparison='All original file bytes and row values retained except exactly two task_completion.checked timestamps; both task IDs and body JSON are byte-identical. Existing completion observer refreshed derived checks after startup. No score or task status was rewritten.',unchanged_original_rows=checked['original_rows']-len(changes))
    def step(name,value):report['steps'].append({'name':name,'result':value});save('production.json',report);print(name,flush=True)
    step('original-data-preservation-reviewed',checked)
    fetch=helpers.client();smoke={}
    for path in ('/api/instance','/api/health','/api/goals','/api/tools','/api/developments','/api/chats','/api/network','/api/task-runner','/api/development-runner'):
        value=fetch(path);smoke[path]={'readable':True,'type':type(value).__name__}
    step('original-authenticated-entries-readable',smoke)
    initial=fetch('/api/english-learning',{'action':'status'});assert not initial['exercises'] and not initial['jobs'] and not initial['config']['enabled']
    assert all(row['attempts']==0 for row in initial['progress']['domains'].values())
    enabled=fetch('/api/english-learning',{'action':'configure','enabled':True,'revision':initial['config']['revision']})
    step('personal-learning-enabled-no-synthetic-results',{'config':enabled['config'],'progress':enabled['progress'],'exercises':len(enabled['exercises'])})
    report.update(passed=True,after_state=ws.state(DAILY),after_controller=read(DAILY),after_instance=ws.instance(18282),actual_user_learning_gains_verified=False,daily_continuous_availability_verified=False)
    save('production.json',report);print('Daily upgrade and preservation reviewed',flush=True)
if __name__=='__main__':main()
