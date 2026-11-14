"""Audit all recorded domain pairs; aggregate is bookkeeping, not generalization."""
from pathlib import Path
import json,importlib.util
ROOT=Path('E:/Jarvis/dev');BASE=ROOT/'docs/evidence/advice-pair-20261114'
spec=importlib.util.spec_from_file_location('pair_audit',BASE/'analyze_pair.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
rows=[]
for domain,folder,work,harness in [('comparison','native-r1','advice-pair-native-20261114-r1','run_pair.py'),('documents','documents-native-r1','advice-documents-pair-native-20261115-r1','run_remaining_pairs.py'),('learning','learning-native-r1','advice-learning-pair-native-20261115-r1','run_remaining_pairs.py')]:
    a.OUT=BASE/folder;a.DATA=Path('E:/Jarvis/validation')/work/'data';a.HARNESS=BASE/harness;a.main()
    report=json.loads((a.OUT/'analysis.json').read_text());freeze=json.loads((a.OUT/'freeze.json').read_text());raw=[json.loads((a.OUT/(label+'.json')).read_text()) for label in ['without-advice','with-advice']]
    rows.append({'domain':domain,'source_commit':freeze['source_commit'],'order':freeze['order'],'pairs':1,'strict_task_passed':[r['passed'] for r in raw],
      'without_advice':report['metrics']['without-advice'],'with_advice':report['metrics']['with-advice'],'observed_deltas':report['observed_deltas'],'audit_passed':report['passed_audit'],
      'temporary_credential_removed':json.loads((a.OUT/'cleanup.json').read_text())['temporary_bridge_credential_removed']})
base=sum(r['without_advice']['total_tokens'] for r in rows);treatment=sum(r['with_advice']['total_tokens'] for r in rows)
summary={'scope':'three operator-authored cases, one pair per domain; six calls are not six independent questions; no longitudinal or population effect claim','rows':rows,
 'real_model_calls':sum(r[k]['model_calls'] for r in rows for k in ['without_advice','with_advice']),'unique_question_cases':3,'per_domain_pairs':1,
 'bookkeeping_totals':{'without_advice_tokens':base,'with_advice_tokens':treatment,'delta_tokens':treatment-base,'delta_percent':(treatment/base-1)*100},
 'all_six_declared_artifacts_passed':all(all(r['strict_task_passed']) for r in rows),'all_audits_passed':all(r['audit_passed'] for r in rows),'all_temporary_credentials_removed':all(r['temporary_credential_removed'] for r in rows),
 'quality_gain_claimed':False,'statistical_non_inferiority_claimed':False,'long_term_learning_claimed':False,'production_application_adopted':False}
(BASE/'all-domain-pairs.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'total_calls':summary['real_model_calls'],'totals':summary['bookkeeping_totals'],'all_declared_artifacts_passed':summary['all_six_declared_artifacts_passed'],'all_audits_passed':summary['all_audits_passed']},ensure_ascii=False))
