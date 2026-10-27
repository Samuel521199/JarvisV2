"""Audit final runtime source, documentation, UI report and scoped live evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from tools.accept_frozen import sources, supporting_inputs
from tools.work_trials import summarize

read=lambda p:json.loads(p.read_text('utf-8'))
frozen=read(HERE/'frozen-r2/snapshot.json');current=sources(ROOT)
diff=sorted(p for p in current.keys()|frozen['source_digests'].keys() if current.get(p)!=frozen['source_digests'].get(p))
support=supporting_inputs(ROOT)
support_diff=sorted(p for p in support.keys()|frozen['supporting_input_digests'].keys() if support.get(p)!=frozen['supporting_input_digests'].get(p))
changed=[c['path'] for c in read(HERE/'candidate-audit.json')['changed_sources']]
docs=['README.md','docs/core-bootstrap.md','docs/contracts.md','docs/delivery-validation.md','docs/decisions-review.md','docs/manifest.json']
def run(name,command):
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (HERE/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    return {'command':command,'returncode':r.returncode,'output':(r.stdout+r.stderr).strip()}
(HERE/'delivery-checks.json').write_text(json.dumps({'status':'RUNNING','production_deployed':False})+'\n',encoding='utf-8')
docs_result=run('delivery-docs',[sys.executable,'tools/check_docs.py','--root','.'])
arch_result=run('delivery-architecture',[sys.executable,'tools/check_architecture.py'])
git_result=run('delivery-selected-diff',['git','diff','--check','--',*changed,*docs])
trailing=[]
for name in changed:
    for line,text in enumerate((ROOT/name).read_text('utf-8').splitlines(),1):
        if text.rstrip(' \t')!=text:trailing.append({'path':name,'line':line})
ui=read(HERE/'report-ui.json');scoped=read(HERE/'trial-source-review.json')
trials={name:summarize(HERE/name)==info['current_summary'] for name,info in scoped['runs'].items()}
forecast=hashlib.sha256((HERE.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()
status=hashlib.sha256((ROOT/'host/work_status.py').read_bytes()).hexdigest()
wrapper=read(HERE/'frozen-r2/result.json')
value={'created_at':datetime.now(timezone.utc).isoformat(),'source_matches_frozen_candidate':not diff,'source_differences':diff,
       'supporting_changes_after_acceptance':support_diff,'supporting_change_reason':'README measured result updated after acceptance; runtime source must remain fixed',
       'docs':docs_result,'architecture':arch_result,'selected_diff_check':git_result,'changed_source_trailing_whitespace':trailing,
       'whole_shared_tree_format_check':read(HERE/'shared-format-check.json'),'report_ui':ui,
       'raw_trial_recomputation_matches_scoped_review':trials,'live_whole_source_matches_final_candidate':False,
       'original_forecast_unchanged':forecast=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f',
       'old_work_status_unchanged':status=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10',
       'report_sha256':hashlib.sha256((HERE/'report.html').read_bytes()).hexdigest(),'frozen_result':wrapper,
       'temporary_cleanup':read(HERE/'temporary-cleanup.json'),'production_deployed':False}
(HERE/'delivery-checks.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not diff and set(support_diff)<= {'README.md'} and not trailing
assert docs_result['returncode']==arch_result['returncode']==git_result['returncode']==0
assert ui['passed'] and value['original_forecast_unchanged'] and value['old_work_status_unchanged']
assert all(trials.values()) and wrapper['local_verdict']=='PASS'
print(json.dumps({'delivery_audit':'PASS','source_count':len(current),'support_changes':support_diff,'docs':docs_result['output'],'architecture':arch_result['output']},ensure_ascii=False))
