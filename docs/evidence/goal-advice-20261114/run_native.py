"""Three one-shot domain planning runs, with real model and restricted tools.
Not an on/off causal comparison: the existing development budget has three slots.
All cases are operator-authored synthetic inputs, never independent user work.
"""
from pathlib import Path
import hashlib,json,shutil,sys,time,uuid
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from host.core import Core
from host import goals,goal_context
from host.completion import refresh,command as completion_command
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.methods import text_digest
from modules.preferences.store import Preferences
from modules.task_resource.plans import Plans
from sdk.protocol import canonical,decode,digest

TOOLS={
 'comparison':{'capability':'plugin.advice-quote.v1','description':'Read jarvis.quote-input.v1 JSON. Filter by current max_price_minor AND max_delivery_days, then select lowest eligible price. Return JSON eligible_ids, selected_id and selected_source; null if none. No network.',
 'code':"import json\ndef run(text):\n    x=json.loads(text)\n    eligible=[o for o in x['offers'] if o['price_minor']<=x['max_price_minor'] and o['delivery_days']<=x['max_delivery_days']]\n    chosen=min(eligible,key=lambda o:o['price_minor']) if eligible else None\n    return json.dumps({'eligible_ids':sorted(o['id'] for o in eligible),'selected_id':chosen['id'] if chosen else None,'selected_source':chosen['source'] if chosen else None},ensure_ascii=False,sort_keys=True,separators=(',',':'))\n",
 'sample':{'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':100,'max_delivery_days':2,'offers':[{'id':'sample','price_minor':80,'delivery_days':1,'source':'sample-only'}]},
 'expected':{'eligible_ids':['sample'],'selected_id':'sample','selected_source':'sample-only'}},
 'documents':{'capability':'plugin.advice-notes.v1','description':'Read jarvis.notes-input.v1 JSON sources array of {id,text}; emit jarvis.notes-result.v1 JSON with excerpts preserving every source id/text byte-for-byte and in order. Do not paraphrase or invent facts.',
 'code':"import json\ndef run(text):\n    x=json.loads(text)\n    return json.dumps({'schema':'jarvis.notes-result.v1','excerpts':x['sources']},ensure_ascii=False,sort_keys=True,separators=(',',':'))\n",
 'sample':{'schema':'jarvis.notes-input.v1','sources':[{'id':'s','text':'Sample excerpt.'}]},'expected':{'schema':'jarvis.notes-result.v1','excerpts':[{'id':'s','text':'Sample excerpt.'}]}},
 'learning':{'capability':'plugin.advice-practice.v1','description':'Read jarvis.practice-input.v1 JSON pairs array of two positive integers; emit jarvis.practice-result.v1 with exercises {a,b,answer} using current multiplication products. Produce a practice worksheet only; no claim the learner mastered it.',
 'code':"import json\ndef run(text):\n    x=json.loads(text)\n    return json.dumps({'schema':'jarvis.practice-result.v1','exercises':[{'a':p[0],'b':p[1],'answer':p[0]*p[1]} for p in x['pairs']]},ensure_ascii=False,sort_keys=True,separators=(',',':'))\n",
 'sample':{'schema':'jarvis.practice-input.v1','pairs':[[2,3]]},'expected':{'schema':'jarvis.practice-result.v1','exercises':[{'a':2,'b':3,'answer':6}]}}
}
CASES=[
 {'id':'fresh-price-delay','domain':'comparison','goal':'比较报价，预算不超过135元，交期不超过6天，选择符合条件的最低价报价，保留来源引用，保存报告',
 'input':{'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':13500,'max_delivery_days':6,'offers':[{'id':'M47','price_minor':6500,'delivery_days':9,'source':'new:M47'},{'id':'N38','price_minor':11200,'delivery_days':4,'source':'new:N38'},{'id':'P26','price_minor':12800,'delivery_days':3,'source':'new:P26'}]},
 'expected':{'eligible_ids':['N38','P26'],'selected_id':'N38','selected_source':'new:N38'}},
 {'id':'fresh-source-excerpts','domain':'documents','goal':'将两条资料的id和text按原顺序逐字整理为excerpts JSON并保存结果；不能改写或补充事实。',
 'input':{'schema':'jarvis.notes-input.v1','sources':[{'id':'new-h7','text':'试制件将在周四完成检验。'},{'id':'new-j4','text':'预算仍为暂估值，尚未得到确认。'}]},
 'expected':{'schema':'jarvis.notes-result.v1','excerpts':[{'id':'new-h7','text':'试制件将在周四完成检验。'},{'id':'new-j4','text':'预算仍为暂估值，尚未得到确认。'}]}},
 {'id':'fresh-current-worksheet','domain':'learning','goal':'用当前pairs生成乘法练习与准确答案JSON并保存练习；不要声称我已经掌握，也不要使用过去题目。',
 'input':{'schema':'jarvis.practice-input.v1','pairs':[[7,13],[16,9],[24,11]]},
 'expected':{'schema':'jarvis.practice-result.v1','exercises':[{'a':7,'b':13,'answer':91},{'a':16,'b':9,'answer':144},{'a':24,'b':11,'answer':264}]}}
]


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def main(output,work):
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';status=exchange(dev,'/status');available=status['daily_call_limit']-status['calls_in_24h']
    if available<3:raise RuntimeError('Three approved development calls required; quota is never raised')
    root=work/'data';Core.initialize(root).close()
    for name in ['config/development.json','private/development-bridge.dpapi']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
    shutil.copytree(dev/'worker-runtime',root/'worker-runtime')
    catalog=exchange(dev,'/catalog')['catalog'];provider=catalog['default_provider'];catalog.update(automatic_fallback=False,fallback_order=[provider])
    prefs=Preferences(root)
    try:prefs.install(catalog,{})
    finally:prefs.close()
    core=Core(root);results=[]
    try:
        for domain,tool in TOOLS.items():
            sample=canonical(tool['sample']);gold=canonical(tool['expected'])
            spec={'schema':'jarvis.development.v1','request_id':'seed-'+domain,'principal_id':'owner.local','scope_id':'personal',
                'grant_id':'development-test','goal':tool['description'],'capability':tool['capability'],'description':tool['description'],
                'public_cases':[{'input':sample,'expected':gold}],'evaluation_cases':[{'input':'\n'+sample,'expected':gold}],
                'sample_input':sample,'limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
            candidate={'schema':'jarvis.code-candidate.v1','summary':'Reviewed deterministic synthetic native probe tool','files':[{'path':'main.py','content':tool['code']}]}
            ident=core.packages.stage(candidate,spec);checked=core.packages.verify(ident)
            if not checked['passed']:raise RuntimeError('Restricted tool verification failed: '+domain)
            core.packages.activate(ident,0)
        def source(title,text):return Knowledge(core.db).save({'id':'','scope':'personal','title':title,'text':text,'providers':[provider],'paused':False},0)
        cards=[]
        for domain in TOOLS:
            observation='Operator-authored synthetic procedural observation; not a real successful user task: '+TOOLS[domain]['description']
            evidence=source('Synthetic observation '+domain,observation)
            card={'schema':'jarvis.method-card.v1','id':'advice-'+domain,'revision':1,'status':'CANDIDATE','recipe':'current-input-'+domain,
                'requires':{'channel':'task','planner':'goal-plan-v1','input_kind':'text'},
                'summary':'Use only current input, inspect the capability description and choose the smallest exact tool chain. '+TOOLS[domain]['description'],
                'counterexamples':['A different input schema or current goal overrides this advice. Past answers, budgets, sources and learning results are not current facts.'],
                'evidence':[{'source_id':evidence['id'],'revision':1,'sha256':text_digest(observation)}],'expires':time.time()+3600}
            tags={'comparison':'报价 比较 预算 交期 选择 来源 保存 报告','documents':'资料 整理 原文 摘录 原样 顺序 保存 来源','learning':'练习 学习 乘法 答案 当前 题目 工作表'}
            saved=source('Task planning advice '+domain+' '+tags[domain],canonical(card))
            cards.append({'source_id':saved['id'],'card':card,'title_tags':tags[domain]})
        files=['host/planning_advice.py','host/goal_context.py','host/goals.py','host/completion.py','host/knowledge_cleanup.py','control/application_compatibility.py','config/goal-advice-compatibility.json']
        freeze={'origin':'operator_authored_synthetic','cases':CASES,'tools':TOOLS,'advice_corpus':cards,'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
            'proxy_build':status['build_id'],'provider':provider,'model':catalog['providers'][provider]['model'],
            'budget':{'available_before':available,'planned_calls':3,'fallback':False,'retry':False},
            'predeclared_checks':['one correct input-source tool','explicit input unchanged','current artifact matches frozen independent expected result','advice dispatch has actual model receipt','result observation recorded'],
            'prediction':'All three finite artifact tasks should pass their declared checks; no quality, token or speed gain is predicted without paired control.',
            'not_measured':['paired no-advice baseline','independent real user work','educational learning gain','longitudinal transfer','full maintenance cost']}
        write(output/'freeze.json',freeze)
        # All expectations and current source hashes are persisted before any model request.
        for i,case in enumerate(CASES):
            request={'request_id':'goal-advice-native-'+case['id'],'goal':case['goal'],'input_text':canonical(case['input']),
                'provider':provider,'model':catalog['providers'][provider]['model'],'reasoning':'default'}
            ident=goals.command(root,{'action':'create','request':request,'context':{'scope':'personal','enabled':True,'chat_id':'','turn_id':''}})['id']
            begin=time.monotonic();planned=goals.execute(root,ident);detail=goals.command(root,{'action':'detail','id':ident})
            proposal=planned.get('proposal');expected_cap=TOOLS[case['domain']]['capability'];plan_ok=bool(proposal and proposal['input_text']==request['input_text'] and not proposal['questions'] and len(proposal['steps'])==1 and proposal['steps'][0]['capability']==expected_cap and proposal['steps'][0]['source']=='input')
            row={'id':case['id'],'domain':case['domain'],'goal_id':ident,'planning_status':planned['status'],'proposal':proposal,'plan_passed':plan_ok,'planning_advice':detail['planning_advice'],'elapsed_seconds':round(time.monotonic()-begin,3)}
            if plan_ok:
                rules={'coverage':'complete','criteria':[{'id':'exact-artifact','step_id':'step-1','check':'text_equals','expected':canonical(case['expected'])}],
                    'requirements':[{'id':'frozen-current-artifact','text':'Frozen synthetic current artifact and source values','kind':'literal','criterion_ids':['exact-artifact']}]}
                task=goals.command(root,{'action':'approve','id':ident,'revision':planned['revision'],'acceptance':rules})['task_id']
                result=core.run_task(task);assessment=refresh(core,task);final=goals.command(root,{'action':'detail','id':ident})
                row.update(task_id=task,task_status=result['status'],completion=assessment,planning_advice=final['planning_advice'])
                row['passed']=result['status']=='SUCCEEDED' and assessment['state']=='VERIFIED' and final['planning_advice']['model_dispatched'] and final['planning_advice']['observation']['condition_score']==100
            else:row['passed']=False
            write(output/(case['id']+'.json'),row);results.append(row)
            print(json.dumps({'id':row['id'],'planning_status':row['planning_status'],'plan_passed':row['plan_passed'],'passed':row['passed'],'calls':row['planning_advice']['model_calls'] if row['planning_advice'] else None}),flush=True)
        # A late rejected result must hold a future exact advice revision, without replay.
        first=next((r for r in results if r.get('passed')),None)
        if first:
            current=refresh(core,first['task_id']);completion_command(core,{'action':'completion_feedback','id':first['task_id'],'request_id':'native-late-counterevidence','fingerprint':current['fingerprint'],'kind':'reject','note':'Synthetic late counterevidence; cause not established. Preserve first-run score separately.'})
            later=goals.command(root,{'action':'create','request':{**Plans(core.db).get(first['goal_id'])['request'],'request_id':'native-after-counterevidence'},'context':{'scope':'personal','enabled':True,'chat_id':'','turn_id':''}})['id']
            # Held advice must not be dispatched again automatically, irrespective of tokens.
            hold={'earlier_goal':first['goal_id'],'feedback_state':refresh(core,first['task_id'])['state'],'later_offered':goals.command(root,{'action':'detail','id':later})['planning_advice']}
            before_ids={r['source_id'] for r in first['planning_advice']['offered']}
            after_ids={r['source_id'] for r in (hold['later_offered'] or {}).get('offered',[])}
            hold['same_revision_held']=not bool(before_ids&after_ids);assert hold['same_revision_held']
            write(output/'late-counterevidence.json',hold)
        write(output/'summary.json',{'first_run_passed':sum(bool(r['passed']) for r in results),'cases':len(CASES),'rows':[{k:r[k] for k in ['id','domain','planning_status','plan_passed','passed']} for r in results],
            'paired_baseline':'UNMEASURED_EXISTING_QUOTA','quality_gain':None,'token_savings':None,'production_adopted':False,'formal_generalization_acceptance':False,
            'proxy_status_after':{k:v for k,v in exchange(dev,'/status').items() if k in ['daily_call_limit','calls_in_24h','build_id']}})
    finally:
        core.close();secret=root/'private/development-bridge.dpapi';assert secret.resolve().is_relative_to(work.resolve())
        if secret.exists():secret.unlink()
        write(output/'cleanup.json',{'temporary_bridge_credential_removed':not secret.exists(),'production_data_copied':False,'daily_application_adopted':False,'external_actions':False})


if __name__=='__main__':
    output=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve()
    try:main(output,work)
    except BaseException:
        import traceback
        output.mkdir(parents=True,exist_ok=True)
        (output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        secret=work/'data/private/development-bridge.dpapi'
        if secret.exists():
            assert secret.resolve().is_relative_to(work)
            secret.unlink()
            (output/'emergency-cleanup.json').write_text('{"temporary_bridge_credential_removed":true}',encoding='utf-8')
