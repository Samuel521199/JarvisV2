"""Paired offline strategy experiment, not a historical-binary or real-user benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from host import goals
from host.core import Core
from tools.probe_concurrency import configure

CASES=[
    ' A | 120 | 5 | source-A \n B | 90 | 8 | source-B ',
    ' A | 80 | 6 | source-A \n B | 95 | 4 | source-B ',
    ' A | 50 | 3 | source-A \n B | 60 | 2 | source-B ',
    ' A | 100 | 5 | source-A \n B | 90 | 10 | source-B ',
    ' A | 110 | 2 | source-A \n B | 120 | 1 | source-B ',
    ' 甲 | 90 | 4 | source-first \n 乙 | 90 | 4 | source-second ',
]
NORMALIZE='''def run(text):
    lines = []
    for line in text.splitlines():
        fields = []
        for item in line.split('|'):
            fields.append(item.strip())
        lines.append('|'.join(fields))
    return '\\n'.join(lines)
'''
CHEAP='''def run(text):
    best = None
    for line in text.splitlines():
        fields = line.split('|')
        if best is None or int(fields[1]) < int(best[1]):
            best = fields
    return '最低报价：' + best[0] + '\\n来源：' + best[3]
'''
BOTH='''def run(text):
    best = None
    for line in text.splitlines():
        fields = line.split('|')
        if int(fields[1]) <= 100 and int(fields[2]) <= 5:
            if best is None or int(fields[1]) < int(best[1]):
                best = fields
    if best is None:
        return '无符合条件报价'
    return '符合条件：' + best[0] + '\\n来源：' + best[3]
'''


def oracle(text):
    rows=[[v.strip() for v in line.split('|')] for line in text.splitlines()]
    valid=[r for r in rows if int(r[1])<=100 and int(r[2])<=5]
    chosen=min(valid,key=lambda r:int(r[1])) if valid else None
    return ('符合条件：'+chosen[0]+'\n来源：'+chosen[3]) if chosen else '无符合条件报价'


def publish(core, cap, code, cases):
    spec={'schema':'jarvis.development.v1','request_id':'budget-fixture-'+cap.split('.')[1],'principal_id':'owner.local',
          'scope_id':'personal','grant_id':'fixture-unused','goal':'Bounded synthetic report fixture','capability':cap,
          'description':'Synthetic deterministic text processing; no external effects','public_cases':cases[:1],
          'evaluation_cases':cases[1:],'sample_input':cases[0]['input'],'limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
    package=core.packages.stage({'schema':'jarvis.code-candidate.v1','summary':'First-party synthetic comparison fixture',
        'files':[{'path':'main.py','content':code}]},spec)
    report=core.packages.verify(package)
    if not report['passed']:raise RuntimeError('Fixture failed its package checks: '+cap)
    core.packages.activate(package,0)


def detail(root,ident):return goals.command(root,{'action':'detail','id':ident})


def original(core,text,key):
    root=core.root
    ident=goals.command(root,{'action':'create','request':{'request_id':key,'goal':'选择价格不超过100且交期不超过5天的最低报价；无符合项则明确说明；保留来源。',
        'input_text':text,'provider':'auto','model':'','reasoning':'default'}})['id']
    steps=[{'title':'规范空格并保留字段','capability':'plugin.budget-normalize.v1','source':'input','expected':'规范字段'},
           {'title':'比较报价','capability':'plugin.budget-cheap.v1','source':'previous','expected':'选择报价并保留来源'}]
    goals.command(root,{'action':'edit','id':ident,'revision':1,'proposal':{'schema':'jarvis.goal-plan.v1','summary':'Synthetic reviewed proposal; price-only comparison deliberately misses delivery',
        'input_text':text,'steps':steps,'questions':[]}})
    rules={'coverage':'complete','criteria':[{'id':'price-label','step_id':'step-2','check':'text_contains','expected':'最低报价：'}],
        'requirements':[{'id':'budget-and-delivery','text':'价格<=100且交期<=5','kind':'semantic','criterion_ids':[]}]}
    tid=goals.command(root,{'action':'approve','id':ident,'revision':2,'acceptance':rules,'budget_limit':6})['task_id']
    assert core.run_task(tid)['status']=='SUCCEEDED'
    return ident


def repair(core,ident,start,key,expected):
    root=core.root;before=detail(root,ident);old_actions=core.tasks.actions(before['task']['id'])
    child=goals.command(root,{'action':'rework','id':ident,'revision':before['plan']['revision'],'work_revision':before['work']['revision'],
        'request_id':key,'kind':'correction','note':'原比较遗漏交期；规范化字段没有改变','goal':before['plan']['request']['goal'],'start_step':start})['id']
    p=detail(root,child)['plan'];proposal=p['proposal'];proposal['steps'][-1]['capability']='plugin.budget-both.v1'
    goals.command(root,{'action':'edit','id':child,'revision':p['revision'],'proposal':proposal})
    p=detail(root,child)['plan'];step='step-'+str(len(proposal['steps']))
    rules={'coverage':'complete','criteria':[{'id':'oracle','step_id':step,'check':'text_equals','expected':expected}],
        'requirements':[{'id':'oracle-text','text':'输出与事先独立计算的夹具基准一致','kind':'literal','criterion_ids':['oracle']}]}
    t0=time.perf_counter();tid=goals.command(root,{'action':'approve','id':child,'revision':p['revision'],'acceptance':rules})['task_id']
    assert core.run_task(tid)['status']=='SUCCEEDED'
    seconds=time.perf_counter()-t0;after=detail(root,child);output=after['actions'][-2]['result']['text']
    assert core.tasks.actions(before['task']['id'])==old_actions
    return {'goal_id':child,'task_id':tid,'start_step':start,'output':output,'oracle_pass':output==expected,
        'repair_cost_units':after['task']['spent'],'work_cost_units':after['work']['budget']['spent_units'],
        'available_units':after['work']['budget']['available_units'],'condition_score':after['completion']['condition_score'],
        'prefix_replayed':sum(a['capability']=='plugin.budget-normalize.v1' for a in after['actions']),
        'local_seconds':round(seconds,4),'original_actions_unchanged':True,'actions':after['actions']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=False)
    frozen={'cases':[{'input':t,'expected':oracle(t)} for t in CASES],'constraints':{'price_max':100,'days_max':5,'tie':'first source row'},
        'strategy_order':'alternate full/suffix within each pair','tool_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in {'normalize':NORMALIZE,'cheap':CHEAP,'both':BOTH}.items()},
        'scope':'Synthetic structured report strategy comparison under the same 1.3.0 runtime; not real user work or a prior binary benchmark'}
    (out/'fixture-frozen.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-budget-paired-') as tmp:
        root=Path(tmp);configure(root);shutil.copytree(Path(__file__).resolve().parents[1]/'user-data/worker-runtime',root/'worker-runtime');core=Core(root)
        try:
            publish(core,'plugin.budget-normalize.v1',NORMALIZE,[{'input':' A | 1 | 2 | S ','expected':'A|1|2|S'},{'input':'甲|3|4|T','expected':'甲|3|4|T'}])
            publish(core,'plugin.budget-cheap.v1',CHEAP,[{'input':'A|20|1|S\nB|10|8|T','expected':'最低报价：B\n来源：T'},{'input':'甲|3|4|T','expected':'最低报价：甲\n来源：T'}])
            publish(core,'plugin.budget-both.v1',BOTH,[{'input':'A|20|1|S\nB|10|8|T','expected':'符合条件：A\n来源：S'},{'input':'甲|300|4|T','expected':'无符合条件报价'}])
            for i,case in enumerate(frozen['cases']):
                ids={s:original(core,case['input'],'paired-'+s+'-'+str(i)) for s in ['full','suffix']}
                row={'case':i+1,'input':case['input'],'expected':case['expected'],'strategies':{}}
                for strategy in (['full','suffix'] if i%2==0 else ['suffix','full']):
                    row['strategies'][strategy]=repair(core,ids[strategy],1 if strategy=='full' else 2,'repair-'+strategy+'-'+str(i),case['expected'])
                rows.append(row)
            # Counterexample: a source correction cannot be smuggled into a reused-prefix input.
            parent=original(core,CASES[0],'counterexample-full-original');p=detail(root,parent)
            child=goals.command(root,{'action':'rework','id':parent,'revision':p['plan']['revision'],'work_revision':p['work']['revision'],
                'request_id':'counterexample-new-input','kind':'new_requirement','note':'供应商输入资料变化，需从首步重算','goal':'采用新的报价资料','start_step':1})['id']
            draft=detail(root,child)['plan'];proposal=draft['proposal'];proposal['input_text']=' NEW | 1 | 1 | new-source '
            proposal['steps'][-1]['capability']='plugin.budget-both.v1'
            goals.command(root,{'action':'edit','id':child,'revision':draft['revision'],'proposal':proposal})
            tid=goals.command(root,{'action':'approve','id':child,'revision':detail(root,child)['plan']['revision']})['task_id']
            assert core.run_task(tid)['status']=='SUCCEEDED'
            actual_new=detail(root,child)['actions'][-2]['result']['text']
            assert actual_new==oracle(proposal['input_text'])
            # A separate draft from an original two-step root demonstrates prefix pinning.
            original_id=original(core,CASES[0],'counterexample-original');p=detail(root,original_id)
            pinned=goals.command(root,{'action':'rework','id':original_id,'revision':p['plan']['revision'],'work_revision':p['work']['revision'],
                'request_id':'counterexample-pinned','kind':'new_requirement','note':'新输入不能套旧规范化结果','goal':'采用新报价','start_step':2})['id']
            draft=detail(root,pinned)['plan'];changed={**draft['proposal'],'input_text':'NEW|1|1|new-source'}
            try:goals.command(root,{'action':'edit','id':pinned,'revision':draft['revision'],'proposal':changed})
            except Exception as exc:counterexample=getattr(exc,'code',type(exc).__name__)
            else:counterexample='NOT_BLOCKED'
            assert counterexample=='rework_invalid'
            result={'passed':all(v['oracle_pass'] and v['original_actions_unchanged'] for r in rows for v in r['strategies'].values()),'pairs':rows,
                'summary':{s:{'oracle_passes':sum(r['strategies'][s]['oracle_pass'] for r in rows),'repair_units':sum(r['strategies'][s]['repair_cost_units'] for r in rows),
                            'total_work_units':sum(r['strategies'][s]['work_cost_units'] for r in rows),'prefix_executions_during_repair':sum(r['strategies'][s]['prefix_replayed'] for r in rows)} for s in ['full','suffix']},
                'counterexample':{'changed_input_while_reusing_prefix':counterexample,'full_rework_new_input':actual_new,'full_rework_new_input_pass':True},
                'model_calls':core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n'],'production_deployed':False,'limitations':frozen['scope']}
            (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            assert result['passed'] and result['model_calls']==0
            print(json.dumps({'passed':True,'pairs':len(rows),'summary':result['summary'],'counterexample':counterexample},ensure_ascii=False))
        finally:core.close()


if __name__=='__main__':main()
