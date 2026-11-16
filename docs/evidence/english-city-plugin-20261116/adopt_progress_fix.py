"""Adopt a qualified derived-review correction without changing original learner scores."""
from deploy import *

def main():
    report=json.loads((OUT/'production.json').read_text());assert report['passed'] and report['after_state']==ws.state(DAILY)
    ready=json.loads((DEV/'state/workstation-update.json').read_text());ws.require_prepared(DAILY,ready)
    assert ready['validation']['passed'] and ready['validation']['policy_sha256']==read(DAILY)['policy_sha256']
    fallback=json.loads((OUT/'qualified.json').read_text())['fallback_build'];before_state=ws.state(DAILY)
    ws.require_live_daily(DAILY);ws.preflight(DAILY,ready['build']);ws.preflight(DAILY,fallback)
    before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-progress-fix.json',before)
    db=sqlite3.connect((DAILY/'state/english-learning.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:progress_before=db.execute('SELECT id,body FROM software_sessions ORDER BY id').fetchall()
    finally:db.close()
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build'])
    backed=ws.backup(DAILY,PRIVATE/'progress-stopped-backup')
    fallback_state=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch'])
    adopted=ws.release(DAILY,'adopt','--build',ready['build'],'--expected-epoch',fallback_state['epoch']);ws.release(DAILY,'install-launcher')
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-progress-fix.json',after);check=preserve(before,after,old,completions());assert check['passed'],check
    db=sqlite3.connect((DAILY/'state/english-learning.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:assert db.execute('SELECT id,body FROM software_sessions ORDER BY id').fetchall()==progress_before
    finally:db.close()
    result={'passed':True,'build':ready['build'],'validation':ready['validation'],'stopped_backup':backed,'preservation':check,'game_progress_rows_unchanged':True,'original_assessment_rows_unchanged':True,'after_state':adopted}
    (OUT/'progress-adoption.json').write_text(json.dumps(result,indent=2)+'\n')
    report['steps'].append({'name':'same-fixed-task-review-correction-adopted','result':result});report.update(after_state=adopted,after_instance=ws.require_live_daily(DAILY),after_controller=read(DAILY))
    (OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Review correction adopted; original scores and game progress preserved')
if __name__=='__main__':main()
