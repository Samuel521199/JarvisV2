"""Freeze implementation and experiment rules BEFORE creating the new holdout."""
from datetime import datetime, timezone
import hashlib,json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from sdk.application_policy import TESTS,TEST_SUPPORT

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__=='__main__':
    round_two='--round-two' in sys.argv
    round_three='--round-three' in sys.argv
    round_four='--round-four' in sys.argv
    old=ROOT/'docs/evidence/commitment-shadow-2026-11-08/package-result.json'
    old_report=json.loads(old.read_text(encoding='utf-8'))
    baseline=Path('D:/jarvisTest/commitment-shadow-package-20261108-final/package')
    manifest=json.loads((baseline/'application.json').read_text(encoding='utf-8'))
    assert all(sha(baseline/name)==meta['sha256'] for name,meta in manifest['files'].items())
    names=sorted(manifest['files'])
    plan={'schema':1,'frozen_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'explicit single local commitments; synthetic data; no production adoption',
        'baseline_build':old_report['build'],'baseline_package':str(baseline),
        'baseline_manifest_sha256':sha(baseline/'application.json'),
        'reference_utc':'2032-04-06T16:30:00Z',
        'holdout_method':'approved model generates new wording from product scenarios after code freeze; no implementation or old samples in prompt; operator audits labels before scoring; not independent user or third-party blind data',
        'model_call_limit':1,'holdout_size':40,'holdout_clear_requests':24,
        'gates':{'unsafe_auto':0,'wrong_auto_content':0,'original_supported_min':0.9,'holdout_clear_coverage_min':0.8},
        'utility':'Correct operation, target, literal title and UTC instant, divided by all clear requests. Abstention is not success.',
        'no_post_holdout_tuning':True,
        'controller_cases':['initial adoption','A/B adoption with live data','compatible rollback','failed health restores baseline','controller restart with live pending candidate','unconfirmed exit blocks second writer then recover','STOP during failed startup prevents recovery','revoked session stays revoked','historical incompatible package refused before drain'],
        'runtime_sha256':{name:sha(ROOT/name) for name in names},
        'tests_sha256':{name:sha(ROOT/'tests'/name) for name in TESTS+TEST_SUPPORT+['test_application_release.py']}}
    if round_two:
        plan.update(previous_round='plan.json',previous_holdout_now='development regression set; all 40 retained',
            reason='First independent holdout failed 80% utility gate (3/24); widen explicit literal request grammar and validate on a newly generated set.',
            model_call_limit=1,holdout_method='Second fresh wording generation with new task titles/times after revised code freeze; no old examples or code disclosed. No tuning after this round is scored.')
    if round_three:
        plan.update(previous_round='plan-r2.json',previous_holdouts_now='development regression sets; all 80 retained',
            reason='Second independent holdout failed 80% utility gate (16/24); widen title/clock ordering and reference wrappers, add multi-clock rejection; validate on another new set.',
            model_call_limit=1,holdout_method='Third fresh wording generation after new code freeze, different titles and dates, no old examples or code disclosed; no tuning after scoring.')
    if round_four:
        plan.update(previous_round='plan-r3.json',previous_holdouts_now='development regression sets; all 120 retained',
            reason='Third independent holdout failed utility gate (14/24). Replace phrase-only expansion with literal anchors and full known request-frame validation; no unknown tokens may be ignored.',
            model_call_limit=1,holdout_method='Fourth fresh wording generation after final code freeze, different titles/dates; no old cases, rules or scores disclosed. No further product tuning on these results.')
    with (HERE/('plan-r4.json' if round_four else 'plan-r3.json' if round_three else 'plan-r2.json' if round_two else 'plan.json')).open('x',encoding='utf-8') as stream:json.dump(plan,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'frozen':True,'files':len(names),'holdout_created':False}))
