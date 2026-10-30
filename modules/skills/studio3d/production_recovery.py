"""Quarantine a lost read-only comparison without replaying or adopting it."""
import copy

RESERVE_USD=.25  # Planning reserve only, never recorded as a provider charge.


def quarantined(row):
    proof=row.get('recovery_disposition',{})
    comparison=(proof.get('action')=='abandon_comparison_without_replay' and proof.get('remote_error')=='host_interrupted')
    inspection=(proof.get('action')=='abandon_inspection_without_replay' and proof.get('remote_error')=='model_timeout'
                and proof.get('local_transport_finished') is True and proof.get('inspection_accepted') is False)
    teaching=(proof.get('action')=='abandon_teaching_plan_without_replay' and proof.get('remote_error')=='connection_failed'
              and proof.get('local_transport_finished') is True and proof.get('plan_executed') is False)
    analysis=(proof.get('action')=='abandon_reference_analysis_without_replay' and proof.get('remote_error')=='connection_failed'
              and proof.get('local_transport_finished') is True and proof.get('analysis_accepted') is False)
    return (row.get('status')=='UNKNOWN' and (comparison or inspection or teaching or analysis)
            and proof.get('request_id')==row.get('request_id') and proof.get('signature')==row.get('signature')
            and proof.get('remote_status')=='UNKNOWN'
            and proof.get('budget_reserve_usd')==RESERVE_USD)


def new_request_allowed(calls,signature):
    for row in calls.values():
        if row.get('status') in ('UNKNOWN','SUBMITTING','CREATED','READY','RUNNING'):
            if row.get('signature')==signature:raise ValueError('Interrupted request signature cannot be replayed under a new key')
            if not quarantined(row):raise ValueError('Resolve original pending/unknown request before creating a different request')


def abandon_reference_analysis(state,key,remote,transport_evidence,diagnostic_evidence,at):
    """Quarantine an ended read-only reference analysis; never recover its answer."""
    import re
    out=copy.deepcopy(state);row=out['calls'][key]
    if not re.fullmatch(r'[a-z0-9-]+-reference-analysis-v[1-9][0-9]*',key):raise ValueError('Only named reference analysis may be quarantined')
    if (row.get('status')!='UNKNOWN' or row.get('error')!='connection_failed' or remote.get('id')!=row['request_id']
        or remote.get('status')!='UNKNOWN' or remote.get('error')!='connection_failed' or remote.get('reply')):
        raise ValueError('Matching terminal original connection failure required')
    if (transport_evidence.get('request_id')!=row['request_id'] or transport_evidence.get('local_transport_finished') is not True
        or transport_evidence.get('active_native_transports')!=0 or transport_evidence.get('asset_lock_held') is not True
        or not transport_evidence.get('implementation_sha256')):
        raise ValueError('Exclusive asset and ended transport evidence required')
    if (diagnostic_evidence.get('read_only') is not True or diagnostic_evidence.get('analysis_accepted') is not False
        or not re.fullmatch('[a-f0-9]{64}',str(diagnostic_evidence.get('source_sha256','')))):
        raise ValueError('Bound read-only diagnostic evidence required')
    row['recovery_disposition']={'action':'abandon_reference_analysis_without_replay','at':at,'request_id':row['request_id'],
        'signature':row['signature'],'remote_status':'UNKNOWN','remote_error':'connection_failed','local_transport_finished':True,
        'analysis_accepted':False,'budget_reserve_usd':RESERVE_USD,'cost_known':False,'transport_evidence':transport_evidence,
        'diagnostic_evidence':diagnostic_evidence}
    out.setdefault('recovery_events',[]).append({'at':at,'author':'Codex','action':'quarantine_terminal_reference_analysis',
        'request_key':key,'paid_replays':0,'scope':'No recovered opinion, no adoption, provider outcome/cost remain unknown'})
    return out


def abandon_comparison(state,key,remote,at):
    out=copy.deepcopy(state);row=out['calls'][key];pending=out.get('pending_iteration');best=out['best_iteration']
    if not pending or pending==best or not key.startswith(pending+'-compare-'+best+'-') or not key.endswith('-sheet-v1'):
        raise ValueError('Only an unadopted pending paired comparison may be abandoned')
    if row['status']!='UNKNOWN' or remote.get('id')!=row['request_id'] or remote.get('status')!='UNKNOWN' or remote.get('error')!='host_interrupted' or remote.get('reply'):
        raise ValueError('Original remote interruption evidence required')
    it=next(i for i in out['iterations'] if i['id']==pending)
    if it['status']!='REVIEWED' or it.get('adoption',{}).get('accepted'):raise ValueError('Cannot abandon active or adopted native work')
    row['recovery_disposition']={'action':'abandon_comparison_without_replay','at':at,'request_id':row['request_id'],
        'signature':row['signature'],'remote_status':remote['status'],'remote_error':remote['error'],
        'candidate':pending,'retained':best,'budget_reserve_usd':RESERVE_USD,'cost_known':False}
    it['adoption']={'accepted':False,'reason':'interrupted_comparison_not_adopted','user_approval':False,'lod_authorized':False}
    it['recovery']='Candidate retained only as incomplete evidence; no visual success or failure inferred.'
    out.pop('pending_iteration');out['status']='CONTINUING'
    out.setdefault('recovery_events',[]).append({'at':at,'author':'Codex','action':'quarantine_lost_comparison','candidate':pending,'retained':best,'request_key':key,'paid_replays':0})
    return out


def abandon_teaching_plan(state,key,remote,transport_evidence,at,plan_evidence=None):
    """Keep an unsuccessful read-only plan UNKNOWN; permit distinct future work.

    No inference about provider charges or output. A recovered reply must be
    handled separately; this path never authorizes executing that missing plan.
    """
    import re
    out=copy.deepcopy(state);row=out['calls'][key]
    bounded=bool(re.fullmatch(r'[a-z0-9-]+-bounded-plan-v[1-9][0-9]*',key))
    if not bounded and not re.fullmatch(r'teaching-[a-z0-9-]+-redo-plan-v1',key):raise ValueError('Only a read-only teaching plan may be quarantined')
    if bounded and (not isinstance(plan_evidence,dict) or plan_evidence.get('request_id')!=row.get('request_id')
                    or plan_evidence.get('read_only') is not True or plan_evidence.get('plan_executed') is not False
                    or plan_evidence.get('has_reply') is not False
                    or not re.fullmatch('[a-f0-9]{64}',str(plan_evidence.get('source_sha256','')))):
        raise ValueError('Bounded missing-plan source and nonexecution evidence required')
    if (row.get('status')!='UNKNOWN' or row.get('error')!='connection_failed' or remote.get('id')!=row['request_id']
        or remote.get('status')!='UNKNOWN' or remote.get('error')!='connection_failed' or remote.get('reply')):
        raise ValueError('Matching original terminal connection failure required')
    if (transport_evidence.get('request_id')!=row['request_id'] or transport_evidence.get('local_transport_finished') is not True
        or transport_evidence.get('active_native_transports')!=0 or transport_evidence.get('asset_lock_held') is not True
        or not transport_evidence.get('implementation_sha256')):
        raise ValueError('Exclusive asset and ended transport evidence required')
    row['recovery_disposition']={'action':'abandon_teaching_plan_without_replay','at':at,'request_id':row['request_id'],
        'signature':row['signature'],'remote_status':'UNKNOWN','remote_error':'connection_failed','local_transport_finished':True,
        'plan_executed':False,'budget_reserve_usd':RESERVE_USD,'cost_known':False,'transport_evidence':transport_evidence,'plan_evidence':plan_evidence}
    out.setdefault('recovery_events',[]).append({'at':at,'author':'Codex','action':'quarantine_terminal_teaching_plan','request_key':key,
                                               'paid_replays':0,'scope':'No plan result and no execution; unknown cost preserved'})
    return out


def abandon_inspection(state,key,remote,transport_evidence,at):
    """Retire a terminal read-only inspection; cost and missing result stay unknown.

    A distinct teaching request may proceed after checking this evidence. The
    original signature cannot be submitted again or counted as a passed review.
    """
    out=copy.deepcopy(state);row=out['calls'][key];best=out['best_iteration']
    if not key.startswith(best+'-inspection-review-') or not key.endswith(('-left','-right','-front','-rear','-top')):
        raise ValueError('Only the retained asset read-only inspection may be abandoned')
    if (row['status']!='UNKNOWN' or remote.get('id')!=row['request_id'] or remote.get('status')!='UNKNOWN'
        or remote.get('error')!='model_timeout' or remote.get('reply')):
        raise ValueError('Original terminal model-timeout evidence required')
    if (transport_evidence.get('request_id')!=row['request_id'] or transport_evidence.get('local_transport_finished') is not True
        or transport_evidence.get('active_native_transports')!=0 or transport_evidence.get('asset_lock_held') is not True
        or not transport_evidence.get('implementation_sha256')):
        raise ValueError('Verified terminal transport and exclusive asset observation required')
    if out.get('pending_iteration'):raise ValueError('Pending production must be inspected separately')
    row['recovery_disposition']={'action':'abandon_inspection_without_replay','at':at,'request_id':row['request_id'],
        'signature':row['signature'],'remote_status':'UNKNOWN','remote_error':'model_timeout',
        'local_transport_finished':True,'inspection_accepted':False,'retained':best,
        'budget_reserve_usd':RESERVE_USD,'cost_known':False,'transport_evidence':transport_evidence}
    out.setdefault('recovery_events',[]).append({'at':at,'author':'Codex','action':'quarantine_terminal_inspection',
        'request_key':key,'retained':best,'paid_replays':0,'scope':'Local execution ended; provider output and billing remain unknown'})
    # Do not change the existing asset quality gate, adoption, or production state.
    return out
