"""Adopt the restored unknown-commitment guard under the unchanged protocol/policy."""
from deploy import *

def main():
    report=json.loads((OUT/'production.json').read_text());assert report['passed'] and report['after_state']==ws.state(DAILY)
    assert not (OUT/'compat-adoption.json').exists(),'Inspect the existing adoption receipt rather than replaying it'
    ready=json.loads((DEV/'state/workstation-controller-update.json').read_text());ws.require_prepared(DAILY,ready)
    assert ready['validation']['passed'] and ready['validation']['policy_sha256']==read(DAILY)['policy_sha256']
    before_state=ws.state(DAILY);old_boot=ws.require_live_daily(DAILY);old_pin=read(DAILY)
    before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-compat-guard.json',before)
    promoted=ws.apply_controller(DAILY,DEV,reviewed_source=True)
    assert promoted['committed'] and not promoted['registration_pending']
    assert ws.state(DAILY)==before_state and ws.require_live_daily(DAILY)['boot_id']==old_boot['boot_id']
    controller_check=preserve(before,helpers.fingerprint(DAILY),old,completions());assert controller_check['passed']
    assert read(DAILY)['controller_protocol']==old_pin['controller_protocol']==9 and read(DAILY)['policy_sha256']==old_pin['policy_sha256']
    fallback=json.loads((OUT/'qualified.json').read_text())['fallback_build']
    ws.preflight(DAILY,ready['build']);ws.preflight(DAILY,fallback)
    db=sqlite3.connect((DAILY/'state/english-learning.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:progress_before=db.execute('SELECT id,body FROM software_sessions ORDER BY id').fetchall()
    finally:db.close()
    before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-compat-app.json',before)
    ws.conditional_stop(DAILY,before_state['epoch'],before_state['active']['build'])
    backed=ws.backup(DAILY,PRIVATE/'compat-stopped-backup')
    fallback_state=ws.release(DAILY,'adopt','--build',fallback,'--expected-epoch',ws.state(DAILY)['epoch'])
    adopted=ws.release(DAILY,'adopt','--build',ready['build'],'--expected-epoch',fallback_state['epoch']);ws.release(DAILY,'install-launcher')
    after=helpers.fingerprint(DAILY);helpers.write(PRIVATE/'after-compat-app.json',after);check=preserve(before,after,old,completions());assert check['passed'],check
    db=sqlite3.connect((DAILY/'state/english-learning.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:assert db.execute('SELECT id,body FROM software_sessions ORDER BY id').fetchall()==progress_before
    finally:db.close()
    result={'passed':True,'build':ready['build'],'validation':ready['validation'],'controller':read(DAILY),'controller_same_boot':True,'controller_preservation':controller_check,'stopped_backup':backed,'preservation':check,'game_progress_rows_unchanged':True,'original_assessment_rows_unchanged':True,'after_state':adopted}
    (OUT/'compat-adoption.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    report['steps'].append({'name':'unknown-empty-commitment-guard-restored','result':result});report.update(after_state=adopted,after_instance=ws.require_live_daily(DAILY),after_controller=read(DAILY))
    (OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Compatibility guard adopted; original data, scores and game progress preserved')

if __name__=='__main__':main()
