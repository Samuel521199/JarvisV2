"""Freeze and run bounded three-domain dialogue trials in a disposable data root.

python -m tools.work_trials --output NEW_DIRECTORY --run
No live service is restarted. Existing credentials are read through their vault
port only. There is no automatic retry, fallback, score writeback or promotion.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from unittest.mock import patch

from adapters.models.native import NativeModel
from control.credentials import Credentials
from control.network import NetworkGate
from control.recovery.gate import StopGate
from host.core import Core
from host.dialogue import DialogueHost
from modules.dialogue.store import Dialogues
from modules.preferences.store import resolve
from modules.skills.catalog import Skills
from modules.workspace.sessions import Sessions
from modules.task_resource import trial_checks
from modules.task_resource import delivery_review
from modules.dialogue import delivery_basis
from sdk.pricing import estimate
from sdk.protocol import CoreError, canonical, decode, digest
from tools.accept_completion import source_snapshot

ROOT=Path(__file__).resolve().parents[1]


def exclusive(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def basis_text(text,value):
    if value is None:return text
    return text+'\n\n本次明确更新交付核对依据（资料声明，不是新的外部动作要求）：\n事实：\n'+('\n'.join(value['facts']) or '无')+'\n已确认计划：\n'+('\n'.join(value['plans']) or '无')


def validate_basis_inputs(suite,inputs):
    if inputs is None:return
    if not isinstance(inputs,dict) or set(inputs)!={'schema','cases'} or inputs['schema']!='jarvis.delivery-inputs.v1' or not isinstance(inputs['cases'],dict):
        raise CoreError('trial_invalid','Invalid explicit basis input pack')
    if set(inputs['cases'])!={c['id'] for c in suite['cases']}:raise CoreError('trial_invalid','Basis input case mapping must exactly match suite')
    for case in suite['cases']:
        rows=inputs['cases'][case['id']];current=delivery_basis.empty()
        if not isinstance(rows,list) or len(rows)!=len(case['turns']):raise CoreError('trial_invalid','Basis input turn count differs')
        for i,(value,turn) in enumerate(zip(rows,case['turns'])):
            if value is not None:
                # Explicit user input is separate from hidden assessment references.
                try:text=basis_text(turn['prompt'],value)
                except (KeyError,TypeError):raise CoreError('trial_invalid','Invalid explicit facts/plans') from None
                if len(text)>12000:raise CoreError('trial_invalid','Combined user input is too large')
                current=delivery_basis.update(value,text,'input-'+str(i),current)


def bounded_route(catalog,provider='auto',model=None,reasoning='default',max_output_tokens=1800):
    if type(max_output_tokens) is not int or not 128<=max_output_tokens<=8192:raise CoreError('trial_invalid','Invalid frozen output ceiling')
    route=resolve(catalog,provider,model,reasoning)
    route.update(max_output_tokens=max_output_tokens,max_prompt_bytes=50000,timeout_seconds=60)
    route['parameters']={**route['parameters'],'max_output_tokens':max_output_tokens}
    return route


def cost_summary(records):
    calls=[a for r in records for a in r.get('attempts',[])]
    tokens=[];amounts={};unknown=0
    for c in calls:
        usage=c.get('usage') or {};n=usage.get('total_tokens')
        if type(n) is not int or n<0:
            x,y=usage.get('prompt_tokens'),usage.get('completion_tokens')
            n=x+y if type(x) is int and type(y) is int and x>=0 and y>=0 else None
        tokens.append(n)
        bill=c['estimate']
        if bill['amount'] is None:unknown+=1
        elif bill['currency']:amounts[bill['currency']]=amounts.get(bill['currency'],0)+bill['amount']
    return {'attempts':len(calls),'known_tokens':sum(n for n in tokens if n is not None),
        'tokens_complete':all(n is not None for n in tokens),'total_tokens':sum(tokens) if all(n is not None for n in tokens) else None,
        'known_api_estimates':amounts,'unpriced_attempts':unknown,'full_cost':None,
        'missing':['human effort','local compute','supplier invoice reconciliation'],'quality_cost_efficiency':None}


def summarize(folder):
    frozen=json.loads((folder/'frozen.json').read_text('utf-8'))
    if frozen['verifier']!=trial_checks.verifier(frozen['suite']) or frozen['suite_digest']!=digest(frozen['suite']):
        raise CoreError('trial_changed','Frozen evaluator or suite changed')
    records=[json.loads(p.read_text('utf-8')) for p in sorted((folder/'turns').glob('*.result.json'))]
    for r in records:
        if r['freeze_digest']!=digest(frozen) or r['record_digest']!=digest({k:v for k,v in r.items() if k!='record_digest'}):
            raise CoreError('trial_changed','Result binding or checksum changed')
        case=next(c for c in frozen['suite']['cases'] if c['id']==r['case_id']);ref=case['turns'][r['turn']]
        expected_skill=case['skill'] if r['arm']=='workflow_on' and case['skill']!='none' else None
        flow=r['status']=='SUCCEEDED' and r['skill_id']==expected_skill and r['action_kind']=='chat' and r['task_count']==0
        delivery=any(a['kind']=='original_session_reply' and a['sha256']==hashlib.sha256((r['reply'] or '').encode()).hexdigest() for a in r['artifacts'])
        assessment=trial_checks.observation(ref,r['reply'],r['status'],flow,delivery)
        if r['assessment']!=assessment or r['flow_valid']!=(flow and delivery):raise CoreError('trial_changed','Assessment does not match raw observations and frozen reference')
        if r.get('delivery_review') and r['delivery_review'].get('reason')!='observer_error':
            checked=delivery_review.review(r['delivery_basis'],r['reply'],r['status'],r['action_kind'])
            if checked!=r['delivery_review']:raise CoreError('trial_changed','Shadow observation differs from frozen basis and reply')
        for a in r.get('artifacts',[]):
            path=folder/a['file']
            if path.resolve().parent!=(folder/'artifacts').resolve() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=a['sha256']:
                raise CoreError('trial_changed','Delivered evidence changed')
    result=trial_checks.summary(frozen['suite'],records)
    result.update(execution=frozen['execution'],costs=cost_summary(records),source_matches_freeze=source_snapshot()==frozen['source_digests'],
        production_deployed=False,forecast_delta=None,avoidable_interventions=None,required_decisions=None,
        unmeasured=['independent real requests','free-form semantic coverage','subjective document quality','human retention and transfer','emotional experience','full costs'],
        failure_details=[{'case_id':r['case_id'],'arm':r['arm'],'turn':r['turn'],'stage':r['failure_stage'],
            'failed_checks':[c['id'] for c in r['assessment']['checks'] if c['status']!='passed']} for r in records if r['assessment']['state']!='PASS'])
    if not result['source_matches_freeze']:result.update(comparison_complete=False,all_candidate_conditions_passed=False,source_status='CHANGED')
    if 'explicit_basis_inputs' in frozen:
        from collections import Counter
        result['shadow_states']=dict(Counter((r.get('delivery_review') or {}).get('state','NOT_RECORDED') for r in records))
        result['shadow_is_completion_gate']=False
    return result


def run_suite(suite,out,catalog,route,factory,*,execution='live',owner_checkpoint=lambda:None,basis_inputs=None):
    suite=trial_checks.validate(copy.deepcopy(suite));basis_inputs=copy.deepcopy(basis_inputs);validate_basis_inputs(suite,basis_inputs)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'turns').mkdir();(out/'artifacts').mkdir()
    ordering=[{'case_id':c['id'],'arm':a} for i,c in enumerate(suite['cases']) for a in (trial_checks.ARMS if i%2==0 else tuple(reversed(trial_checks.ARMS)))]
    frozen={'schema':'jarvis.work-trial-freeze.v1','created':time.time(),'suite':suite,'suite_digest':digest(suite),
        'source_digests':source_snapshot(),'verifier':trial_checks.verifier(suite),'execution':execution,
        'route':{k:route.get(k) for k in ('id','adapter','model','parameters','max_output_tokens','max_prompt_bytes','timeout_seconds','billing_profile')},
        'catalog_digest':digest(catalog),'order':ordering,'repetitions':1,'max_calls':2*sum(len(c['turns']) for c in suite['cases']),
        'stop_after_consecutive_response_failures':3,'memory_enabled':False,'fallback':False,
        'comparison':'current runtime, identical model and limits, selected workflow guidance off/on; quotation is same-path control',
        'decision':'descriptive technical screening only; never automatic adoption or all-domain excellence'}
    if basis_inputs is not None:frozen['explicit_basis_inputs']=basis_inputs
    exclusive(out/'frozen.json',frozen);consecutive=0;calls=0
    with tempfile.TemporaryDirectory(prefix='jarvis-work-trials-') as temp:
        root=Path(temp);core=Core.initialize(root);core.preferences.install(catalog,{})
        skills=Skills(root);host=DialogueHost(root);store=Dialogues(root)
        try:
            class Client:
                def __init__(self,config,*ignored):self.inner=factory(config,root/'temp')
                def available(self):owner_checkpoint();return self.inner.available()
                def complete(self,messages,checkpoint,**kwargs):
                    nonlocal calls
                    if calls>=frozen['max_calls']:raise CoreError('trial_limit','Frozen call bound reached')
                    if len(canonical(messages).encode())>route['max_prompt_bytes']:raise CoreError('model_input_limit','Frozen input bound reached')
                    calls+=1
                    def check():owner_checkpoint();checkpoint()
                    check();result=self.inner.complete(messages,check,**kwargs)
                    exclusive(out/'artifacts'/(key+'.native.json'),{k:result.get(k) for k in ('status','code','text','usage')})
                    return result
            with patch('host.dialogue.NativeModel',Client):
                for slot in ordering:
                    c=next(c for c in suite['cases'] if c['id']==slot['case_id']);arm=slot['arm'];chat=store.create()
                    for i,reference in enumerate(c['turns']):
                        owner_checkpoint()
                        if source_snapshot()!=frozen['source_digests']:raise CoreError('trial_changed','Source changed during the frozen experiment')
                        key=c['id']+'-'+arm+'-'+str(i);ident='trial-'+key;skill=c['skill'] if arm=='workflow_on' else 'none'
                        command={'chat_id':chat,'request_id':ident,'text':reference['prompt'],'provider':route['id'],'model':route['model'],
                            'reasoning':'default','skill':skill,'assistant_mode':True,'memory_enabled':False}
                        if basis_inputs is not None:
                            value=basis_inputs['cases'][c['id']][i]
                            if value is not None:command.update(text=basis_text(command['text'],value),delivery_basis=value)
                        guidance=skills.select(skill,reference['prompt']);store.begin(command,[route],guidance)
                        exclusive(out/'turns'/(key+'.started.json'),{'freeze_digest':digest(frozen),'case_id':c['id'],'arm':arm,'turn':i,'request_digest':digest(command),'started':time.time()})
                        start=time.monotonic();host.run(ident);elapsed=time.monotonic()-start;t=store.turn(ident)
                        actual=decode(t['guidance']) if t['guidance'] else None;action=decode(t['assistant_action']) if t.get('assistant_action') else {}
                        expected_skill=None if skill=='none' else skill
                        flow=(t['status']=='SUCCEEDED' and (actual or {}).get('id')==expected_skill and action.get('kind')=='chat'
                            and core.db.one('SELECT COUNT(*) AS n FROM tasks')['n']==0)
                        attempts=[]
                        for a in store.db.execute('SELECT status,usage,error,created,billing_profile FROM attempts WHERE turn_id=? ORDER BY id',(ident,)):
                            usage=decode(a['usage']) if a['usage'] else {};price=decode(a['billing_profile']) if a['billing_profile'] else None
                            attempts.append({'status':a['status'],'usage':usage,'error':a['error'],'estimate':estimate(price,usage,a['created'])})
                        artifacts=[];artifact_ok=False
                        wire=out/'artifacts'/(key+'.native.json')
                        if wire.is_file():artifacts.append({'file':'artifacts/'+wire.name,'sha256':hashlib.sha256(wire.read_bytes()).hexdigest(),'kind':'native_protocol_response'})
                        if t['status']=='SUCCEEDED':
                            sessions=Sessions(root)
                            try:
                                saved=sessions.path(chat)/'replies'/(ident+'.md');raw=saved.read_bytes()
                                artifact_ok=raw==t['reply'].encode();name=key+'.reply.md.txt';(out/'artifacts'/name).write_bytes(raw)
                                artifacts.append({'file':'artifacts/'+name,'sha256':hashlib.sha256(raw).hexdigest(),'kind':'original_session_reply'})
                            except (CoreError,OSError):pass
                            finally:sessions.close()
                            try:
                                document=trial_checks.parse_reply(t['reply']).get('document')
                                if isinstance(document,str):
                                    raw=document.encode();name=key+'.document.md.txt';(out/'artifacts'/name).write_bytes(raw)
                                    artifacts.append({'file':'artifacts/'+name,'sha256':hashlib.sha256(raw).hexdigest(),'kind':'verbatim_document_field_from_reply'})
                            except (ValueError,TypeError):pass
                        assessment=trial_checks.observation(reference,t['reply'],t['status'],flow,artifact_ok)
                        flow=flow and artifact_ok
                        stage=('output_limit_or_incomplete' if t.get('error')=='model_reply_incomplete' else 'assistant_protocol' if t.get('error')=='assistant_invalid' else 'transport_or_availability') if t['status']!='SUCCEEDED' else 'delivery' if not artifact_ok else 'assistant_routing' if not flow else 'content' if assessment['state']=='FAIL' else None
                        r={'case_id':c['id'],'domain':c['domain'],'arm':arm,'turn':i,'freeze_digest':digest(frozen),'status':t['status'],
                            'error':t.get('error'),'reply':t.get('reply'),'skill_id':(actual or {}).get('id'),'skill_version':(actual or {}).get('version'),
                            'action_kind':action.get('kind'),'task_count':core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'],'flow_valid':flow,'elapsed_seconds':round(elapsed,4),'attempts':attempts,
                            'artifacts':artifacts,'assessment':assessment,'failure_stage':stage,'business_quality':None}
                        if basis_inputs is not None:r.update(delivery_basis=decode(t['delivery_basis']) if t.get('delivery_basis') else None,delivery_review=decode(t['delivery_review']) if t.get('delivery_review') else None)
                        exclusive(out/'turns'/(key+'.result.json'),{**r,'record_digest':digest(r)})
                        print(canonical({'case':c['id'],'arm':arm,'turn':i,'status':t['status'],'checks':assessment['state']}),flush=True)
                        consecutive=consecutive+1 if t['status']!='SUCCEEDED' else 0
                        if consecutive>=3:return summarize(out)
                        if t['status']!='SUCCEEDED':break  # Dependent turns cannot pretend the lost context exists.
            return summarize(out)
        finally:store.close();host.close();skills.close();core.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suite',type=Path,default=ROOT/'tests/fixtures/work_trials_v1.json')
    parser.add_argument('--provider',default='auto');parser.add_argument('--model');parser.add_argument('--run',action='store_true')
    parser.add_argument('--basis-inputs',type=Path,help='Explicit user declarations, separate from hidden assessment references')
    parser.add_argument('--reasoning',default='default');parser.add_argument('--max-output-tokens',type=int,default=1800)
    args=parser.parse_args()
    if args.suite.stat().st_size>1000000:raise CoreError('trial_invalid','Suite file is too large')
    suite=trial_checks.validate(json.loads(args.suite.read_text('utf-8')))
    inputs=None
    if args.basis_inputs:
        if args.basis_inputs.stat().st_size>1000000:raise CoreError('trial_invalid','Basis input pack too large')
        inputs=json.loads(args.basis_inputs.read_text('utf-8'));validate_basis_inputs(suite,inputs)
    if not args.run:
        print(canonical({'execution':'NOT_RUN','domains':list(trial_checks.DOMAINS),'cases':len(suite['cases']),'max_calls':2*sum(len(c['turns']) for c in suite['cases']),'suite_digest':digest(suite)}));return
    owner=ROOT/'user-data';StopGate(owner).require_running();NetworkGate(owner).require_online()
    db=sqlite3.connect('file:'+(owner/'config/settings.sqlite3').as_posix()+'?mode=ro',uri=True)
    try:catalog=decode(db.execute('SELECT catalog FROM models WHERE id=1').fetchone()[0])
    finally:db.close()
    route=bounded_route(catalog,args.provider,args.model,args.reasoning,args.max_output_tokens);credential=Credentials(owner).get
    def checkpoint():StopGate(owner).require_running();NetworkGate(owner).require_online()
    result=run_suite(suite,args.output,catalog,route,lambda cfg,temp:NativeModel(cfg,credential,temp),owner_checkpoint=checkpoint,basis_inputs=inputs)
    exclusive(args.output/'summary.json',result)
    print(canonical({'summary':str(args.output/'summary.json'),'complete':result['comparison_complete'],'all_candidate_conditions_passed':result['all_candidate_conditions_passed']}))


if __name__=='__main__':main()
