"""Preserve original live receipts; disclose and scope the later UI-only fix."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from tools.accept_frozen import sources
from tools.work_trials import summarize
from modules.task_resource.delivery_review import review

read=lambda p:json.loads(p.read_text('utf-8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=sources(ROOT)
allowed=set(read(HERE/'plan-amendment-mobile.json')['allowed_changes_after_live_runs'])
guard={'source_matches_freeze','source_status','comparison_complete','all_candidate_conditions_passed'}
runs={}
for name in ['live-prose-r1','live-excerpt-r1']:
    folder=HERE/name
    frozen=read(folder/'frozen.json');before=frozen['source_digests']
    diff=sorted(p for p in now.keys()|before.keys() if now.get(p)!=before.get(p))
    original=read(folder/'summary.json');actual=summarize(folder)
    same={k:v for k,v in original.items() if k not in guard}=={k:v for k,v in actual.items() if k not in guard}
    assert set(diff)==allowed and same
    assert original['source_matches_freeze'] and not actual['source_matches_freeze']
    assert not actual['comparison_complete'] and actual['source_status']=='CHANGED'
    runs[name]={'original_summary_sha256':hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest(),
                'source_differences':diff,'current_full_source_match':False,
                'generation_and_review_sources_unchanged':True,
                'observations_recomputed_without_change':same,'current_summary':actual}
calibration=read(HERE/'calibration.json')
calibration_same=all(review(c['basis'],c['reply'],'SUCCEEDED','chat')==c['review'] for c in calibration['cases'])
assert calibration_same
write(HERE/'trial-source-review.json',{'created_at':datetime.now(timezone.utc).isoformat(),
      'scope':'Live generation/review components match; complete live source revision differs from final UI candidate. Original summaries remain untouched.',
      'guard_was_bypassed':False,'runs':runs,'calibration_recomputed_without_change':calibration_same,
      'additional_model_calls':0,'production_deployed':False})
print(json.dumps({'scoped_source_review':'PASS','differences':sorted(allowed),'calibration_unchanged':calibration_same}))
