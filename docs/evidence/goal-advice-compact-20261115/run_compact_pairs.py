"""One frozen goal-planning advice pair, real native model or labelled dry run."""
from pathlib import Path
import hashlib,importlib.util,json,os,random,shutil,sys,time,traceback
from unittest.mock import patch
ROOT=Path('E:/Jarvis/dev');sys.path.insert(0,str(ROOT))
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
from host.core import Core
from host import goals,goal_context
from host.completion import refresh
from adapters.models.native import NativeModel,message_bytes
from adapters.development_bridge import exchange
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.methods import text_digest
from modules.preferences.store import Preferences
from sdk.protocol import canonical,decode,digest
spec=importlib.util.spec_from_file_location('domain_probe',ROOT/'docs/evidence/goal-advice-20261114/run_native.py')
domain=importlib.util.module_from_spec(spec);spec.loader.exec_module(domain)
CASES={
 'documents':{'id':'compact-notes-pair-01','domain':'documents','goal':'整理这两条资料，原样摘录每条原文并保留来源ID和顺序，不概括、不把草稿估价写成确认结论，保存报告',
  'input':{'schema':'jarvis.notes-input.v1','sources':[{'id':'note-C28','text':'草稿：287元只是估价，尚未最终确认。\n请保留这条限定。'},{'id':'note-D19','text':'已确认：交付清单为3个零件；日期待另行确认。'}]},
  'expected':{'schema':'jarvis.notes-result.v1','excerpts':[{'id':'note-C28','text':'草稿：287元只是估价，尚未最终确认。\n请保留这条限定。'},{'id':'note-D19','text':'已确认：交付清单为3个零件；日期待另行确认。'}]}},
 'learning':{'id':'compact-practice-pair-01','domain':'learning','goal':'用当前给出的三组数生成乘法练习和正确答案，保留题目顺序，保存练习表；不要评价学习者是否掌握',
  'input':{'schema':'jarvis.practice-input.v1','pairs':[[13,16],[24,7],[31,12]]},
  'expected':{'schema':'jarvis.practice-result.v1','exercises':[{'a':13,'b':16,'answer':208},{'a':24,'b':7,'answer':168},{'a':31,'b':12,'answer':372}]}}
}
CASES['comparison']={'id':'compact-quotes-pair-01','domain':'comparison','goal':'比较当前报价，预算218元以内且交期不超过6天，筛选合格者再选择其中最低价，保留来源并保存报告',
 'input':{'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':21800,'max_delivery_days':6,'offers':[{'id':'A81','price_minor':18200,'delivery_days':9,'source':'synthetic:A81'},{'id':'B36','price_minor':20300,'delivery_days':5,'source':'synthetic:B36'},{'id':'C29','price_minor':19900,'delivery_days':6,'source':'synthetic:C29'}]},
 'expected':{'eligible_ids':['B36','C29'],'selected_id':'C29','selected_source':'synthetic:C29'}}
CASE=CASES[sys.argv[3]]
ADVICE_RULE='conditional_advice若存在，仅是历史候选建议；先重查当前目标、输入和反例。不得照搬旧答案、预算或约束，不得扩展工具和权限；没有适用建议就独立规划。'

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main(output,work,dry):
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';status=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog'];provider=catalog['default_provider']
    if not dry and status['daily_call_limit']-status['calls_in_24h']<2:raise RuntimeError('Two slots are not currently available; no dispatch')
    catalog.update(automatic_fallback=False,fallback_order=[provider])
    root=work/'data';Core.initialize(root).close();core=None;rows=[];captures={};current_label=None
    credential=root/'private/development-bridge.dpapi'
    try:
        if not dry:
            for name in ['config/development.json','private/development-bridge.dpapi']:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
        shutil.copytree(dev/'worker-runtime',root/'worker-runtime')
        prefs=Preferences(root)
        try:prefs.install(catalog,{})
        finally:prefs.close()
        core=Core(root)
        for name,tool in domain.TOOLS.items():
            sample=canonical(tool['sample']);gold=canonical(tool['expected'])
            tool_spec={'schema':'jarvis.development.v1','request_id':'pair-seed-'+name,'principal_id':'owner.local','scope_id':'personal','grant_id':'development-test','goal':tool['description'],'capability':tool['capability'],'description':tool['description'],
              'public_cases':[{'input':sample,'expected':gold}],'evaluation_cases':[{'input':'\n'+sample,'expected':gold}],
              'sample_input':sample,'limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
            candidate={'schema':'jarvis.code-candidate.v1','summary':'Reviewed synthetic pair tool','files':[{'path':'main.py','content':tool['code']}]}
            ident=core.packages.stage(candidate,tool_spec);assert core.packages.verify(ident)['passed'];core.packages.activate(ident,0)
        def source(title,text):return Knowledge(core.db).save({'id':'','scope':'personal','title':title,'text':text,'providers':[provider],'paused':False},0)
        cards=[]
        for name,tool in domain.TOOLS.items():
            observation='Operator-authored synthetic procedural observation, not independent user success: '+tool['description']
            evidence=source('Synthetic pair observation '+name,observation)
            card={'schema':'jarvis.method-card.v1','id':'pair-advice-'+name,'revision':1,'status':'CANDIDATE','recipe':'current-input-'+name,
             'requires':{'channel':'task','planner':'goal-plan-v1','input_kind':'text'},'summary':'Use only current input and the smallest exact tool chain. '+tool['description'],
             'counterexamples':['Current goal and input schema override historical advice. Never reuse old prices, sources, deadlines or answers.'],
             'evidence':[{'source_id':evidence['id'],'revision':1,'sha256':text_digest(observation)}],'expires':time.time()+3600}
            tags={'comparison':'报价 比较 预算 交期 选择 来源 保存 报告','documents':'资料 整理 原文 摘录 原样 顺序 保存 来源','learning':'练习 学习 乘法 答案 当前 题目 工作表'}
            saved=source('Pair planning advice '+name+' '+tags[name],canonical(card));cards.append({'source_id':saved['id'],'card':card})
        ids={}
        for label in ['full-v1','compact-v2']:
            ids[label]=goals.command(root,{'action':'create','request':{'request_id':'goal-pair-'+label,'goal':CASE['goal'],'input_text':canonical(CASE['input']),'provider':provider,'model':catalog['providers'][provider]['model'],'reasoning':'default'},
              'context':{'scope':'personal','enabled':True,'chat_id':'','turn_id':''}})['id']
            context=goal_context.get(core,ids[label]);assert context['view']['conditional_advice']['version']==2
            if label=='full-v1':
                context['view']['conditional_advice']['version']=1
                with core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ids[label]))
        from modules.task_resource.plans import Plans
        contexts={label:goal_context.get(core,ident) for label,ident in ids.items()}
        assert contexts['compact-v2']['view']['facts']==contexts['full-v1']['view']['facts']
        assert contexts['full-v1']['view']['conditional_advice']['receipt']==contexts['compact-v2']['view']['conditional_advice']['receipt']
        assert len(Plans(core.db).get(ids['compact-v2'])['routes'])==1
        assert goals.command(root,{'action':'detail','id':ids['compact-v2']})['planning_advice']['offered']
        order=['compact-v2','full-v1'] if CASE['domain']=='documents' else ['full-v1','compact-v2']
        files=['host/goals.py','host/planning_advice.py','host/goal_context.py','adapters/models/native.py','modules/context_knowledge/methods.py']
        frozen={'schema':1,'frozen_at':time.time(),'execution':'deterministic-dry-run' if dry else 'real-native-model','origin':'operator_authored_synthetic','case':CASE,'tools':domain.TOOLS,'cards':cards,'order':order,
          'contexts':{label:goal_context.get(core,ident) for label,ident in ids.items()},'routes':Plans(core.db).get(ids['compact-v2'])['routes'],
          'harness_sha256':sha(Path(__file__)),'ablation':'Only isolated pre-dispatch goal format differs: full-v1 versus compact-v2; identical method receipts and ordinary background','source_sha256':{name:sha(ROOT/name) for name in files},'source_commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'proxy_before':status,
          'budget':{'planned_calls':0 if dry else 2,'fallback':False,'retry':False,'quota_expansion':False},
          'prediction':{'strict_task_success_each':True,'quality_gain':'No positive gain predicted from a single simple paired case','tokens':'Compact projection should reduce prompt bytes and prompt tokens; total/reasoning, task quality and latency need measurement'},
          'predeclared_checks':['same original goal/input/catalog/routes','identical authorized ordinary background, method receipts and settings; only model card projection differs','one correct input-source domain tool','input text unchanged','actual restricted task and saved artifact match independent frozen expected value','model ledger digest matches captured prompt','no automatic retry or fallback'],
          'not_measured':['independent user work','multiple independent cases per domain','learning gains','longitudinal benefit','statistical significance','complete monetary and maintenance cost']}
        write(output/'freeze.json',frozen)
        class RecordingNative(NativeModel):
            def available(self):return True if dry else super().available()
            def generate(self,prompt,checkpoint=lambda:None):
                assert all(sha(ROOT/name)==value for name,value in frozen['source_sha256'].items()) and sha(Path(__file__))==frozen['harness_sha256']
                assert current_label not in captures
                capture={'prompt':prompt,'input_digest':digest({'prompt':prompt,'schema':'goal-plan'}),'message_bytes':message_bytes([{'role':'user','content':prompt}])}
                captures[current_label]=capture;write(output/(current_label+'-dispatch.json'),capture)
                if dry:
                    checkpoint();return {'status':'SUCCEEDED','value':{'schema':'jarvis.goal-plan.v1','summary':'Dry comparison','input_text':canonical(CASE['input']),
                      'steps':[{'title':'比较当前报价','capability':domain.TOOLS[CASE['domain']]['capability'],'source':'input','expected':'Current quote artifact'}],'questions':[]},'usage':{'total_tokens':0}}
                return super().generate(prompt,checkpoint)
        for label in order:
            current_label=label;ident=ids[label]
            if not dry:
                current=exchange(dev,'/status')
                if current['calls_in_24h']>=current['daily_call_limit']:raise RuntimeError('No remaining slot; no retry or quota changes')
            started=time.monotonic()
            with patch('host.goals.NativeModel',RecordingNative):planned=goals.execute(root,ident)
            elapsed=time.monotonic()-started;proposal=planned.get('proposal')
            plan_ok=bool(proposal and proposal['input_text']==canonical(CASE['input']) and not proposal['questions'] and len(proposal['steps'])==1 and proposal['steps'][0]['capability']==domain.TOOLS[CASE['domain']]['capability'] and proposal['steps'][0]['source']=='input')
            row={'group':label,'goal_id':ident,'planning_status':planned['status'],'proposal':proposal,'plan_passed':plan_ok,'planning_seconds':elapsed}
            if plan_ok:
                rules={'coverage':'complete','criteria':[{'id':'exact-current-comparison','step_id':'step-1','check':'text_equals','expected':canonical(CASE['expected'])}],
                  'requirements':[{'id':'current-frozen-artifact','text':'Frozen current domain artifact, values, source/order and explicit limitations','kind':'literal','criterion_ids':['exact-current-comparison']}]}
                task=goals.command(root,{'action':'approve','id':ident,'revision':planned['revision'],'acceptance':rules})['task_id'];row['task_id']=task
                result=core.run_task(task);row.update(task_status=result['status'],completion=refresh(core,task))
                artifacts=core.db.all("SELECT result FROM actions WHERE task_id=? AND capability='artifact.write.v1' AND status='CONFIRMED'",(task,))
                row['saved_artifact_receipts']=[decode(r['result']) for r in artifacts]
                row['artifact_checks']=[]
                for artifact in row['saved_artifact_receipts']:
                    path=(root/artifact['relative_path']).resolve()
                    assert path.is_relative_to((root/'artifacts').resolve())
                    payload=path.read_bytes()
                    row['artifact_checks'].append({'sha256_matches':hashlib.sha256(payload).hexdigest()==artifact['sha256'],
                        'bytes_match':len(payload)==artifact['bytes'],'actual_text_matches_frozen_expected':decode(payload)['text']==canonical(CASE['expected'])})
                row['passed']=result['status']=='SUCCEEDED' and row['completion']['state']=='VERIFIED' and bool(artifacts) and all(all(check.values()) for check in row['artifact_checks'])
            else:row['passed']=False
            calls=core.db.all('SELECT id,run_id,phase,status,input_digest,usage FROM model_calls WHERE run_id=? ORDER BY created',(ident,))
            for call in calls:call['usage']=decode(call['usage']) if call['usage'] else None
            row['calls']=calls;row['actual_model_calls']=len(calls);row['planning_advice']=goals.command(root,{'action':'detail','id':ident})['planning_advice']
            row['receipt_bound']=len(calls)==1 and label in captures and calls[0]['input_digest']==captures[label]['input_digest']
            row['passed']=row['passed'] and row['receipt_bound'];rows.append(row);write(output/(label+'.json'),row)
            print(json.dumps({'group':label,'passed':row['passed'],'status':row['planning_status'],'calls':len(calls)},ensure_ascii=False),flush=True)
        off=captures['full-v1']['prompt'].rsplit('\n',1);on=captures['compact-v2']['prompt'].rsplit('\n',1)
        off_data=decode(off[1]);on_data=decode(on[1]);offered=on_data.pop('conditional_advice');full=off_data.pop('conditional_advice')
        from modules.context_knowledge.methods import model_projection
        only_treatment_changed=off_data==on_data and on[0]==off[0] and offered==model_projection(full['methods'],2)
        assert only_treatment_changed and offered['methods']
        summary={'execution':frozen['execution'],'pairs':1,'domain':CASE['domain'],'rows':[{k:r[k] for k in ['group','passed','planning_seconds','actual_model_calls']} for r in rows],
          'only_treatment_changed':only_treatment_changed,'both_first_run_passed':all(r['passed'] for r in rows),'causal_generalization':None,'quality_gain_claimed':False,'token_savings_claimed':False,
          'production_application_adopted':False,'other_domain_pairs':'separately recorded; no automatic full-domain acceptance','proxy_after':exchange(dev,'/status')}
        write(output/'summary.json',summary)
    finally:
        if core:core.close()
        if credential.exists():credential.unlink()
        write(output/'cleanup.json',{'temporary_bridge_credential_removed':not credential.exists(),'production_data_copied':False,'production_application_adopted':False,'external_actions':False})
if __name__=='__main__':
    output=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve();dry='--dry-run' in sys.argv[3:]
    assert work.is_relative_to(Path('E:/Jarvis/validation'))
    if output.exists() or work.exists():raise SystemExit('Use a new evidence and work directory; existing runs are never overwritten')
    assert output.is_relative_to(ROOT/'docs/evidence/goal-advice-compact-20261115')
    try:main(output,work,dry)
    except BaseException:
        output.mkdir(parents=True,exist_ok=True);(output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
