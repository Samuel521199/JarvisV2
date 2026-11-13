"""Aggregate immutable first scores and measured costs without upgrading scope."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent


def read(path):return json.loads((HERE/path).read_text(encoding='utf-8'))


def main():
    language=[];generation_tokens=0
    for folder in ['unseen-r1-proxy','unseen-r2','unseen-r3','unseen-r4']:
        plan=read(folder+'/plan.json');candidate=read(folder+'/candidate-first.json');baseline=read(folder+'/daily-first.json')
        generation_tokens+=read(folder+'/generator-result.json')['usage']['total_tokens']
        language.append({'round':folder,'baseline':baseline['summary'],'candidate_first_score':candidate['summary'],
            'read_before_score_audit':read(folder+'/audit.json'),'criterion':plan['criteria'],
            'seed_state_unchanged':candidate['seed_state_unchanged'] and baseline['seed_state_unchanged'],
            'source_amendment_before_access':(HERE/folder/'source-amendment-before-access.json').exists()})
    domains=[];tokens=generation_tokens;known_price=0
    for folder in ['project-domains-r1','project-domains-rendered-r1','project-domains-rendered-r2','project-domains-rendered-r3']:
        row=read(folder+'/summary.json');cost=row['costs'];tokens+=cost['total_tokens'] or 0;known_price+=cost['known_api_estimates'].get('USD',0)
        domains.append({'run':folder,'comparison_complete':row['comparison_complete'],'all_conditions_passed':row['all_candidate_conditions_passed'],
            'cases':row['cases'],'costs':cost,'failure_details':row['failure_details'],'source_matches_freeze_at_run_completion':row['source_matches_freeze']})
    old=domains[0]['costs'];first=domains[1]['costs'];last=domains[-1]['costs']
    replay=read('same-reply-render-replay/summary.json');last_language=language[-1]['candidate_first_score']
    actions=read('live-action-regression.json');live_document=read('live-development-document.json')
    extra_tokens=sum(r['usage']['total_tokens'] for r in actions['rows'])+live_document['usage']['total_tokens']
    report={'schema':1,'scope':'Development implementation and bounded project-derived technical acceptance; not independent end-user excellence',
        'language':language,'language_gate_passed':last_language['coverage']>=0.9 and last_language['unsafe_auto']==last_language['wrong_auto_content']==0,
        'domains':domains,'same_reply_replay':{k:replay[k] for k in ['model_calls','before_pass','after_pass','business_fields_unchanged']},
        'cost_comparison':{'optimized_vs_initial_tokens_fraction':last['total_tokens']/old['total_tokens']-1,
            'optimized_vs_first_renderer_tokens_fraction':last['total_tokens']/first['total_tokens']-1,
            'optimized_vs_initial_api_estimate_fraction':last['known_api_estimates']['USD']/old['known_api_estimates']['USD']-1},
        'usage':{'successful_provider_calls':49,'wording_generation_calls':4,'domain_calls':36,'ordinary_action_regression_calls':8,
            'live_development_document_calls':1,'known_provider_tokens':tokens+extra_tokens,
            'api_estimate_usd_for_36_domain_calls':known_price,'generation_price_not_frozen':True,'complete_cost':None,
            'local_unknown_attempts_not_resent':3,'dispatch_resolution':read('dispatch-incident.json')},
        'prior_quantitative_forecasts':{'language_minimum_coverage':0.9,'format_gain':None,'token_reduction':None},
        'quality_score':None,'learning_gain':None,'emotion_quality':None,'production_adopted':False,
        'source_checkpoint':read('source-checkpoint.json'),'related_regressions':read('final-regressions-r2.json'),
        'ordinary_action_regression':{'cases':len(actions['rows']),'passed':actions['passed'],'known_preexisting_cases':True,
            'temporary_bridge_credential_removed':actions['temporary_bridge_credential_removed']},
        'live_development_document':{'passed':live_document['passed'],'review_state':live_document['review_state'],
            'rendering':live_document['rendering'],'synthetic_development_only':True},
        'environment_recovery':read('environment-recovery.json'),'development_restart':read('development-restart.json'),
        'remaining':['Language final holdout below 90 percent','Independent end-user requests and supplier quotation quality',
            'Long-term knowledge benefit and negative transfer','Whole-PC shared resource leases','Multi-Bot ownership and bounded self-healing',
            'Codex offline storage cutover and restart verification','Production controller/source adoption and complete legacy retirement']}
    (HERE/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'language_gate_passed':report['language_gate_passed'],'provider_tokens':report['usage']['known_provider_tokens'],'cost_comparison':report['cost_comparison']}))


if __name__=='__main__':main()
