"""Frozen bounded regression run; no real model or production adoption."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,unittest
from unittest.mock import patch
ROOT=Path('E:/Jarvis/dev');OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'docs/evidence/advice-budget-20261114'
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
import test_goal_advice_budget

def hashes():return {str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'adapters/models/native.py',ROOT/'host/goals.py',ROOT/'host/planning_advice.py',ROOT/'tests/test_goal_advice_budget.py']}
def main():
    frozen={'scope':'technical envelope/call-ledger verification only','source_sha256':hashes(),'route_budget_rule':'If full prompt exceeds the smallest route limit, omit unused advice whenever the original prompt fits at least one original route; reject only when no original route can fit. Never erase existing calls.', 'baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'predictions':['Exact native envelope budget admits the original prompt after unused advice is omitted','A full fitting prompt keeps its advice','No existing or inherited receipt dependencies are discarded','No cloud requests, quota expansion or production application adoption'],'quality_gain':None,'token_savings':None}
    (OUT/'freeze.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    control=unittest.TestSuite([test_goal_advice_budget.GoalAdviceBudget('test_exact_base_budget_omits_unused_advice_and_current_task_still_executes')])
    with (OUT/'disabled-control.txt').open('w',encoding='utf-8') as stream,patch('host.planning_advice.PlanningAdvice.fit',lambda self,plan,context,prompt,base:prompt):
        r=unittest.TextTestRunner(stream=stream,verbosity=2).run(control)
    # Intentional ablation: the current regression must fail if omission is bypassed.
    assert len(r.failures)==1 and not r.errors
    rows=[{'pattern':'disabled-control','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'expected_failure':True}]
    patterns=['test_goal_advice_budget.py','test_goal_advice.py'] if len(sys.argv)>1 else ['test_goal_advice_budget.py','test_goal_advice.py','test_goal_plans.py','test_assistant_goals.py','test_preferences_dialogue.py','test_model_transport.py']
    for pattern in patterns:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern)
        start=time.monotonic()
        with (OUT/(pattern[:-3]+'.txt')).open('w',encoding='utf-8') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        row={'pattern':pattern,'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'seconds':round(time.monotonic()-start,3),'passed':r.wasSuccessful()};rows.append(row)
        (OUT/'regressions.json').write_text(json.dumps({'rows':rows,'source_unchanged':hashes()==frozen['source_sha256'],'all_positive_passed':all(row.get('passed',True) for row in rows)},indent=2)+'\n',encoding='utf-8')
        print(json.dumps(row),flush=True)
        if not r.wasSuccessful():raise SystemExit(1)
    assert hashes()==frozen['source_sha256']
if __name__=='__main__':main()
