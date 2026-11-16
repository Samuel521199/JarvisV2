"""Adopt the final byte-normalized source after unchanged frozen qualification."""
from deploy import *

def main():
    report=json.loads((OUT/'production.json').read_text());assert report['passed'] and report['after_state']==ws.state(DAILY)
    assert not (OUT/'source-format-adoption.json').exists()
    ready=json.loads((DEV/'state/workstation-update.json').read_text());ws.require_prepared(DAILY,ready)
    before=helpers.fingerprint(DAILY);old=completions();helpers.write(PRIVATE/'before-source-format.json',before)
    before_pin=read(DAILY)
    old_state=ws.state(DAILY);ws.require_live_daily(DAILY);ws.preflight(DAILY,ready['build'])
    ws.conditional_stop(DAILY,old_state['epoch'],old_state['active']['build'])
    backed=ws.backup(DAILY,PRIVATE/'source-format-stopped-backup')
    adopted=ws.release(DAILY,'adopt','--build',ready['build'],'--expected-epoch',old_state['epoch'])
    ws.release(DAILY,'install-launcher');ws.require_live_daily(DAILY)
    receipt={'passed':True,'before':old_state,'after':adopted,'backup':backed,'scope':'Explicit pre-existing upgrade functions only; unrelated workstation automation not enabled or adopted'}
    check=preserve(before,helpers.fingerprint(DAILY),old,completions());assert check['passed'],check
    assert read(DAILY)==before_pin
    result={'passed':True,'reason':'Only redundant final CRLF blank lines removed from host/learning_sources.py; no semantic change','validation':ready['validation'],'build':ready['build'],'controller':read(DAILY),'preservation':check,'after_state':ws.state(DAILY),'application_receipt':receipt}
    (OUT/'source-format-adoption.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    report['steps'].append({'name':'source-whitespace-closeout-adopted','result':result});report.update(after_state=ws.state(DAILY),after_instance=ws.require_live_daily(DAILY),after_controller=read(DAILY))
    (OUT/'production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Final byte-normalized build adopted; original data retained')

if __name__=='__main__':main()
