"""The comparison assessor must reject plausible but stale or wrong-domain answers."""
import copy
import importlib.util
from pathlib import Path
import unittest
from sdk.protocol import canonical

SCRIPT=Path(__file__).resolve().parents[1]/'docs/evidence/knowledge-advice-20261114/run_ablation.py'
spec=importlib.util.spec_from_file_location('knowledge_ablation',SCRIPT)
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


class KnowledgeTrialAssessment(unittest.TestCase):
    def answer(self,cases):return {'schema':'jarvis.knowledge-trial-answer.v1','answers':[trial.expected(c) for c in cases]}

    def test_wrong_shipping_objective_or_source_never_scores_as_correct(self):
        cases=trial.cases();answer=self.answer(cases)
        self.assertTrue(trial.grade(canonical(answer),cases)['passed'])
        for index,changes in [(1,{'selected_id':'d','total_minor':5000,'source':'current-input:d'}),
                              (2,{'selected_id':'g','total_minor':6000,'source':'current-input:g'}),
                              (0,{'source':'a plausible but unprovided citation'})]:
            bad=copy.deepcopy(answer);bad['answers'][index].update(changes)
            self.assertFalse(trial.grade(canonical(bad),cases)['passed'])

    def test_missing_duplicate_boolean_and_non_json_outputs_are_retained_failures(self):
        cases=trial.cases();answer=self.answer(cases)
        duplicates=copy.deepcopy(answer);duplicates['answers'][0]['eligible_ids']*=2
        boolean=copy.deepcopy(answer);boolean['answers'][0]['total_minor']=True
        missing=copy.deepcopy(answer);missing['answers'].pop()
        for text in [canonical(duplicates),canonical(boolean),canonical(missing),'some helpful prose',
                     '{"schema":"wrong","schema":"jarvis.knowledge-trial-answer.v1","answers":[]}']:
            self.assertFalse(trial.grade(text,cases)['passed'])

    def test_a_new_input_is_recomputed_instead_of_using_a_previous_winner(self):
        cases=trial.cases();old=self.answer(cases);changed=copy.deepcopy(cases)
        changed[0]['offers'][0]['price_minor']=9500
        self.assertFalse(trial.grade(canonical(old),changed)['passed'])
        self.assertTrue(trial.grade(canonical(self.answer(changed)),changed)['passed'])


if __name__=='__main__':unittest.main()
