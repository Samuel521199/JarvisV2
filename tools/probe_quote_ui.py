"""Real browser/HTTP/worker domain checks on disposable synthetic quotes only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from host import goals, assistant
from modules.dialogue.store import Dialogues
from host.core import Core
from host.completion import command as completion_command, refresh
from sdk.protocol import canonical, decode, digest
from tools.probe_concurrency import Fixture

ROOT=Path(__file__).resolve().parents[1]
CODE='''import json
def run(text):
    data=json.loads(text)
    ids=[]
    best=None
    for item in data['offers']:
        if item['price_minor'] > data['max_price_minor'] or item['delivery_days'] > data['max_delivery_days']:
            continue
        ids.append(item['id'])
        if best is None or item['price_minor'] < best['price_minor']:
            best=item
    return json.dumps({'schema':'jarvis.quote-result.v1','eligible_ids':ids,'selected_id':best['id'] if best else None,'selected_source':best['source'] if best else None})
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--requests',action='store_true');modes.add_argument('--sources',action='store_true');modes.add_argument('--changes',action='store_true');modes.add_argument('--inheritance',action='store_true');modes.add_argument('--recovery',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    data=json.loads((ROOT/'tests/fixtures/quote_acceptance_v1.json').read_text('utf-8'))
    dump=lambda value:json.dumps(value,ensure_ascii=False)
    empty={**data['input'],'max_price_minor':0}
    empty_result={'schema':'jarvis.quote-result.v1','eligible_ids':[],'selected_id':None,'selected_source':None}
    with tempfile.TemporaryDirectory(prefix='jarvis-quote-ui-') as tmp:
        root=Path(tmp);fixture=Fixture(root)
        fixture.server.development_runner=SimpleNamespace(state=lambda:{'status':'idle'})
        try:
            shutil.copytree(ROOT/'user-data/worker-runtime',root/'worker-runtime');core=Core(root)
            try:
                for wrong in (False,True):
                    cap='plugin.quote-wrong.v1' if wrong else 'plugin.quote.v1'
                    samples=[{'input':dump(data['input']),'expected':dump(data['wrong_cheapest'] if wrong else data['correct'])},
                             {'input':dump(empty),'expected':dump(data['wrong_cheapest'] if wrong else empty_result)}]
                    spec={'schema':'jarvis.development.v1','request_id':'quote-ui-'+str(wrong),'principal_id':'owner.local','scope_id':'personal',
                          'grant_id':'fixture-unused','goal':'Synthetic quote fixture','capability':cap,'description':'Synthetic quote JSON output',
                          'public_cases':samples[:1],'evaluation_cases':samples[1:],'sample_input':samples[0]['input'],
                          'limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
                    code='def run(text):\n    return '+repr(dump(data['wrong_cheapest']))+'\n' if wrong else CODE
                    package=core.packages.stage({'schema':'jarvis.code-candidate.v1','summary':'First-party offline quote fixture','files':[{'path':'main.py','content':code}]},spec)
                    if not core.packages.verify(package)['passed']:raise RuntimeError('Fixture verification failed')
                    core.packages.activate(package,0)
                cases=[];parent_records={}
                request_goal='预算不超过100元，交期不超过5天，选择最低价报价，保留来源引用，保存结果'
                choices=[('correct',data['input'],'plugin.quote.v1'),('wrong',data['input'],'plugin.quote-wrong.v1'),('empty',empty,'plugin.quote.v1')]
                if args.requests or args.sources or args.changes or args.inheritance or args.recovery:choices=[('correct',data['input'],'plugin.quote.v1'),('uncovered',data['input'],'plugin.quote.v1'),('conflict',data['input'],'plugin.quote.v1')]
                for name,source,cap in choices:
                    goal=(request_goal+'，必须保修三年' if name=='uncovered' else request_goal.replace('100元','90元') if name=='conflict' else request_goal) if args.requests else '按预算和交期选择最低报价并保存来源'
                    if args.sources or args.changes or args.inheritance or args.recovery:
                        goal=request_goal;turn='quote-ui-'+name;store=Dialogues(root)
                        try:
                            raw=goal+'，必须保修三年' if name=='uncovered' else goal.replace('100元','90元') if name=='conflict' else goal
                            if args.changes:raw=goal+'，必须保修三年' if name=='correct' else goal;goal=raw
                            if args.inheritance or args.recovery:raw=request_goal+('，必须保修三年' if name=='uncovered' else '');goal=raw
                            store.begin({'chat_id':store.create(),'request_id':turn,'text':raw,'provider':'openai','model':'fixture','reasoning':'default',
                                'assistant_mode':True,'attachments':[{'name':'合成报价.json','text':dump(source)}]},[])
                            store.context(turn);store.finish(turn,{'status':'SUCCEEDED','text':'拟订目标','provider':'openai','model':'fixture',
                                'assistant_action':{'kind':'goal','target':'','goal':goal,'input_text':dump(source)}})
                        finally:store.close()
                        ident=assistant.goal_from_turn(root,turn)['id']
                        if args.changes:
                            revised=request_goal.replace('100元','90元');input90={**data['input'],'max_price_minor':9000}
                            edits=[('将要求「预算不超过100元」替换为「预算不超过90元」',revised+'，必须保修三年',input90),('撤销要求「必须保修三年」',revised,input90)] if name=='correct' else [('新增要求「必须保修三年」',request_goal+'，必须保修三年',source)] if name=='uncovered' else [('将要求「预算不超过100元」替换为「预算不超过90元」',request_goal,source)]
                            for i,(raw,goal,source) in enumerate(edits):
                                d=goals.command(root,{'action':'detail','id':ident});store=Dialogues(root);amend=turn+'-amend-'+str(i)
                                try:
                                    chat=store.turn(turn)['chat_id']
                                    store.begin({'chat_id':chat,'request_id':amend,'text':raw,'provider':'openai','model':'fixture','reasoning':'default','assistant_mode':True},[])
                                    store.context(amend);store.finish(amend,{'status':'SUCCEEDED','text':'明确修订','provider':'openai','model':'fixture',
                                        'assistant_action':{'kind':'amend','target':ident,'target_revision':d['plan']['revision'],'goal':goal,'input_text':dump(source)}})
                                finally:store.close()
                                assistant.accept(root,{'turn_id':amend})
                    else:
                        ident=goals.command(root,{'action':'create','request':{'request_id':'quote-ui-'+name,'goal':goal,
                            'input_text':dump(source),'provider':'auto','model':'','reasoning':'default'}})['id']
                    revision=goals.command(root,{'action':'detail','id':ident})['plan']['revision']
                    goals.command(root,{'action':'edit','id':ident,'revision':revision,'proposal':{'schema':'jarvis.goal-plan.v1','summary':'独立核对合成报价结果','input_text':dump(source),
                        'steps':[{'title':'选择报价','capability':cap,'source':'input','expected':'符合冻结约束的最低价和来源'}],'questions':[]}})
                    if args.inheritance or args.recovery:
                        d=goals.command(root,{'action':'detail','id':ident})
                        r=goals.command(root,{'action':'review_quote_changes','id':ident,'revision':d['plan']['revision']})
                        tid=goals.command(root,{'action':'approve','id':ident,'revision':r['revision'],'acceptance':{**r['acceptance'],'coverage':'complete'}})['task_id']
                        core.run_task(tid);parent_records[ident]=core.tasks.actions(tid)
                        if args.recovery:
                            parent=ident;d=goals.command(root,{'action':'detail','id':parent})
                            ident=goals.command(root,{'action':'rework','id':parent,'revision':d['plan']['revision'],
                                'work_revision':d['work']['revision'],'request_id':'recovery-fixture-'+name,
                                'kind':'correction','note':'保持全部要求','goal':goal,'start_step':1})['id']
                            d=goals.command(root,{'action':'detail','id':ident})
                            r=goals.command(root,{'action':'review_quote_rework','id':ident,'revision':d['plan']['revision']})
                            child_task=goals.command(root,{'action':'approve','id':ident,'revision':r['revision'],
                                'acceptance':{**r['acceptance'],'coverage':'complete'}})['task_id']
                            if name=='correct':core.run_task(child_task)
                            parent_records[ident]=core.tasks.actions(child_task)
                            completion_command(core,{'action':'completion_feedback','id':tid,'request_id':'feedback-fixture-'+name,
                                'fingerprint':refresh(core,tid)['fingerprint'],'kind':'reject','note':'核对新的反馈，保持全部有效要求'})
                            if name=='conflict':
                                store=Dialogues(root)
                                try:
                                    raw=decode(store.turn(turn)['request']);raw['text']+='，必须保修三年'
                                    store.db.execute('UPDATE turns SET request=?,digest=? WHERE id=?',(canonical(raw),digest(raw),turn))
                                finally:store.close()
                    cases.append({'name':name,'id':ident})
                (out/'fixture.json').write_text(dump({'cases':cases,'sourceReview':args.sources,'changeReview':args.changes,'inheritanceReview':args.inheritance,'settings':core.preferences.public(core.credentials.available)}),encoding='utf-8')
                script=Path(__file__).with_name('probe_quote_requests_ui.cjs') if args.requests or args.sources or args.changes or args.inheritance or args.recovery else Path(__file__).with_suffix('.cjs')
                if args.inheritance:script=Path(__file__).with_name('probe_inheritance_ui.cjs')
                if args.recovery:script=Path(__file__).with_name('probe_recovery_ui.cjs')
                subprocess.run(['node',str(script),fixture.base,str(out)],check=True,timeout=120)
                if args.inheritance or args.recovery:
                    children=json.loads((out/'children.json').read_text('utf-8'))
                    for case in cases:
                        old=goals.command(root,{'action':'detail','id':case['id']})
                        assert core.tasks.actions(old['task']['id'])==parent_records[case['id']]
                        if args.recovery:
                            assert old['task']['status']==('SUCCEEDED' if case['name']=='correct' else 'CANCELLED' if case['name']=='uncovered' else 'READY')
                        case['id']=children[case['name']]
                details=[goals.command(root,{'action':'detail','id':case['id']}) for case in cases]
                calls=core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n']
                report={'scope':'feedback-only recovery, unchanged requirements, old actions and shared budget through real UI' if args.recovery else 'executed Work requirement inheritance through real UI; synthetic offline quotes' if args.inheritance else 'explicit synthetic chat additions, replacements and withdrawals' if args.changes else 'linked synthetic chat sources, explicit omissions and conflicts' if args.sources else 'bounded original-request review on synthetic Chinese clauses' if args.requests else 'three synthetic quote tasks; UI requirements and independent oracle, no natural-language extraction',
                        'production_deployed':False,'model_calls':calls,'tasks':[{'id':d['task']['id'],'status':d['task']['status'],'spent':d['task']['spent'],
                        'completion':d['completion'],'closure':d['work_closure']} if d['task'] else None for d in details]}
                (out/'runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                executed=details[:2] if args.requests or args.sources or args.changes or args.inheritance or args.recovery else details
                assert calls==0 and all(d['task']['status']=='SUCCEEDED' and d['task']['spent']==2 for d in executed)
                if args.inheritance:
                    assert all(d['work']['spent_cost_units']==4 for d in executed)
                if args.recovery:
                    assert [d['work']['spent_cost_units'] for d in executed]==[6,4]
                    assert [d['completion']['state'] for d in executed]==['VERIFIED','WAITING_EVIDENCE']
                    assert len(details[-1]['work']['versions'])==2 and details[-1]['task']['status']=='READY'
                elif args.requests or args.sources or args.changes or args.inheritance:
                    assert [d['completion']['state'] for d in executed]==['VERIFIED','WAITING_EVIDENCE'] and details[-1]['task'] is None
                else:assert [d['completion']['state'] for d in details]==['VERIFIED','NEEDS_CORRECTION','VERIFIED']
            finally:core.close()
        finally:fixture.close()


if __name__=='__main__':main()
