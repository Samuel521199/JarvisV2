"""Pure bounded trial checks. They never change task scores, policy or knowledge."""
import json
import re
from sdk.protocol import CoreError, canonical, digest
from modules.task_resource import body_evidence

VERSION='work-trials-2'
DOMAINS=('comparison','documents','learning')
ARMS=('workflow_off','workflow_on')


def verifier(suite):
    return VERSION if suite['schema']=='jarvis.work-trials.v1' else 'work-trials-3/'+body_evidence.VERSION


def validate(suite):
    try:return _validate(suite)
    except (TypeError,KeyError,ValueError,RecursionError) as exc:
        raise CoreError('trial_invalid','Malformed bounded trial data') from exc


def _validate(suite):
    if len(json.dumps(suite,ensure_ascii=False,allow_nan=False))>1000000:raise CoreError('trial_invalid','Suite is too large')
    if (not isinstance(suite,dict) or set(suite)!={'schema','origin','provenance','cases'}
            or suite['schema'] not in {'jarvis.work-trials.v1','jarvis.work-trials.v2'} or suite['origin'] not in {'synthetic','user_supplied'}
            or not isinstance(suite['provenance'],str) or not 1<=len(suite['provenance'])<=1000
            or not isinstance(suite['cases'],list) or not 3<=len(suite['cases'])<=30):
        raise CoreError('trial_invalid','Expected a bounded three-domain suite with declared provenance')
    seen=set();content=set()
    for c in suite['cases']:
        if (not isinstance(c,dict) or set(c)!={'id','domain','skill','turns'} or not isinstance(c['id'],str)
                or not re.fullmatch('[a-z0-9-]{1,60}',c['id']) or c['id'] in seen
                or c['domain'] not in DOMAINS or not isinstance(c['skill'],str)
                or not isinstance(c['turns'],list) or not 1<=len(c['turns'])<=3):
            raise CoreError('trial_invalid','Invalid case identity, domain, skill or turn bound')
        seen.add(c['id'])
        for t in c['turns']:
            fields={'prompt','expected','unordered','text_fields','forbidden'}
            if suite['schema']=='jarvis.work-trials.v2':fields.add('body_evidence')
            if (set(t)!=fields
                    or not isinstance(t['prompt'],str) or not 1<=len(t['prompt'])<=6000
                    or not isinstance(t['expected'],dict) or not 1<=len(t['expected'])<=20
                    or not isinstance(t['unordered'],list) or not set(t['unordered'])<=set(t['expected'])
                    or any(not isinstance(t['expected'][k],list) or any(not isinstance(v,str) for v in t['expected'][k]) for k in t['unordered'])
                    or not isinstance(t['text_fields'],list) or any(not isinstance(k,str) for k in t['text_fields'])
                    or not isinstance(t['forbidden'],dict) or any(not isinstance(v,list) or any(not isinstance(x,str) or not x for x in v) for v in t['forbidden'].values())):
                raise CoreError('trial_invalid','Invalid frozen prompt or explicit checks')
            if 'body_evidence' in t:body_evidence.validate(t['body_evidence'])
        key=digest([t['prompt'] for t in c['turns']])
        if key in content:raise CoreError('trial_invalid','Duplicate task content cannot become independent samples')
        content.add(key)
    if {c['domain'] for c in suite['cases']}!=set(DOMAINS):raise CoreError('trial_invalid','Every domain must be represented')
    return suite


def parse_reply(text):
    if not isinstance(text,str) or len(text)>30000:raise ValueError('reply bound')
    text=text.strip()
    if text.startswith('```json') and text.endswith('```'):text=text[7:-3].strip()
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate key')
            result[k]=v
        return result
    def invalid(value):raise ValueError('non-finite JSON')
    value=json.loads(text,object_pairs_hook=pairs,parse_constant=invalid)
    if not isinstance(value,dict):raise ValueError('object required')
    return value


def assess(reference,reply):
    try:value=parse_reply(reply)
    except (ValueError,TypeError,RecursionError):return {'state':'FAIL','checks':[{'id':'response_format','status':'failed'}],'condition_score':0,'quality_score':None}
    checks=[]
    for key,expected in reference['expected'].items():
        actual=value.get(key);same=key in value and canonical(actual)==canonical(expected)
        if key in reference['unordered']:
            same=isinstance(actual,list) and all(isinstance(v,str) for v in actual) and len(actual)==len(set(actual)) and sorted(actual)==sorted(expected)
        checks.append({'id':key,'status':'passed' if same else 'failed'})
    for key in reference['text_fields']:
        checks.append({'id':key+'_present','status':'passed' if isinstance(value.get(key),str) and value[key].strip() else 'failed'})
    for key,terms in reference['forbidden'].items():
        passed=isinstance(value.get(key),str) and not any(t.casefold() in value[key].casefold() for t in terms)
        checks.append({'id':key+'_withheld','status':'passed' if passed else 'failed'})
    if 'body_evidence' in reference:checks.extend(body_evidence.assess(reference['body_evidence'],value))
    passed=sum(c['status']=='passed' for c in checks)
    return {'state':'PASS' if passed==len(checks) else 'FAIL','checks':checks,'condition_score':100*passed/len(checks),'quality_score':None}


def observation(reference,reply,status,routed,delivered):
    if status!='SUCCEEDED':
        failed=status in {'FAILED','REJECTED','INVALID'}
        return {'state':'FAIL' if failed else 'UNMEASURED','checks':[{'id':'response_delivery','status':'failed' if failed else 'unknown'}],'condition_score':None,'quality_score':None}
    if not routed:return {'state':'FAIL','checks':[{'id':'dialogue_flow','status':'failed'}],'condition_score':None,'quality_score':None}
    if not delivered:return {'state':'FAIL','checks':[{'id':'session_delivery','status':'failed'}],'condition_score':None,'quality_score':None}
    return assess(reference,reply)


def summary(suite,records):
    validate(suite);by={(r['case_id'],r['arm'],r['turn']):r for r in records}
    if len(by)!=len(records):raise CoreError('trial_invalid','Repeated result slot')
    expected={(c['id'],a,i) for c in suite['cases'] for a in ARMS for i in range(len(c['turns']))}
    if not set(by)<=expected:raise CoreError('trial_invalid','Unplanned result slot')
    cases=[]
    for c in suite['cases']:
        row={'id':c['id'],'domain':c['domain'],'arms':{}}
        for arm in ARMS:
            observations=[by.get((c['id'],arm,i)) for i in range(len(c['turns']))]
            states=[r['assessment']['state'] if r else 'UNMEASURED' for r in observations]
            state='FAIL' if 'FAIL' in states else 'PASS' if all(x=='PASS' for x in states) else 'UNMEASURED'
            row['arms'][arm]={'state':state,'turn_states':states}
        cases.append(row)
    domains={d:{a:{s:sum(c['domain']==d and c['arms'][a]['state']==s for c in cases) for s in ('PASS','FAIL','UNMEASURED')} for a in ARMS} for d in DOMAINS}
    pairs=[c for c in cases if all(all(s in {'PASS','FAIL'} for s in c['arms'][a]['turn_states']) for a in ARMS)]
    improved=sum(c['arms']['workflow_off']['state']=='FAIL' and c['arms']['workflow_on']['state']=='PASS' for c in pairs)
    regressed=sum(c['arms']['workflow_off']['state']=='PASS' and c['arms']['workflow_on']['state']=='FAIL' for c in pairs)
    return {'version':verifier(suite),'origin':suite['origin'],'independent_cases':len(cases),'planned_turns':len(expected),
        'recorded_turns':len(records),'complete_pairs':len(pairs),'cases':cases,'domains':domains,
        'descriptive_improved_pairs':improved,'descriptive_regressed_pairs':regressed,
        'all_candidate_conditions_passed':all(c['arms']['workflow_on']['state']=='PASS' for c in cases),
        'comparison_complete':len(pairs)==len(cases),'quality_gain':None,'learning_gain':None,
        'emotion_quality':None,'real_work_gain':None,'all_functional_excellence_verified':False,
        'scope':('Current-runtime workflow guidance ablation on source-excerpt documents; exact current-source and confirmed-plan coverage plus body parity, not free prose semantic certification; no causal or population inference'
                 if suite['schema']=='jarvis.work-trials.v2' else 'Current-runtime workflow guidance ablation on bounded structured replies; no causal or population inference')}
