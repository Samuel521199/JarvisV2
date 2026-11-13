"""One bounded ABL-0..4 diagnostic through ordinary DialogueHost; no retries.

Four operator-authored synthetic comparisons share one call per arm, so they are
not independent model observations. Required current inputs stay in every arm.
ABL-5 and source-disjoint/longitudinal learning remain explicitly unmeasured.
"""
from pathlib import Path
import hashlib,json,shutil,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from host.core import Core
from host.dialogue import DialogueHost
from host import memory
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.methods import text_digest
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from sdk.protocol import CoreError,canonical,decode,digest


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def cases():
    def offer(ident,price,days,shipping=0):return {'id':ident,'price_minor':price,'shipping_minor':shipping,'delivery_days':days,'source':'current-input:'+ident}
    return [
        {'id':'same-conditions','context':{'currency':'CNY','price_includes_fees':True,'objective':'lowest_eligible_total','pool':'regular'},
         'max_price_minor':10000,'max_delivery_days':7,'offers':[offer('a',6000,4),offer('b',5500,8),offer('c',7000,3)]},
        {'id':'price-basis-reversed','context':{'currency':'CNY','price_includes_fees':False,'objective':'lowest_eligible_total','pool':'regular'},
         'max_price_minor':10000,'max_delivery_days':7,'offers':[offer('d',5000,4,2500),offer('e',6500,5,200),offer('f',6000,9)]},
        {'id':'objective-changed','context':{'currency':'CNY','price_includes_fees':True,'objective':'earliest_eligible','pool':'regular'},
         'max_price_minor':10000,'max_delivery_days':7,'offers':[offer('g',6000,6),offer('h',9000,2),offer('i',11000,1)]},
        {'id':'withdrawn-history','context':{'currency':'CNY','price_includes_fees':True,'objective':'lowest_eligible_total','pool':'withdrawn'},
         'max_price_minor':10000,'max_delivery_days':7,'offers':[offer('j',4000,4),offer('k',5500,5)],
         'notice':'The prior observation for this pool was withdrawn. Do not rely on it; current offers below remain valid user input.'}]


def expected(case):
    eligible=[o for o in case['offers'] if o['price_minor']+(0 if case['context']['price_includes_fees'] else o['shipping_minor'])<=case['max_price_minor'] and o['delivery_days']<=case['max_delivery_days']]
    key=(lambda o:(o['delivery_days'],o['price_minor'])) if case['context']['objective']=='earliest_eligible' else (lambda o:o['price_minor']+(0 if case['context']['price_includes_fees'] else o['shipping_minor']))
    chosen=min(eligible,key=key)
    return {'id':case['id'],'eligible_ids':sorted(o['id'] for o in eligible),'selected_id':chosen['id'],
        'total_minor':chosen['price_minor']+(0 if case['context']['price_includes_fees'] else chosen['shipping_minor']),'source':chosen['source']}


def grade(text,current):
    text=text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4]
    try:
        value=decode(text)
        if not isinstance(value,dict) or set(value)!={'schema','answers'} or value['schema']!='jarvis.knowledge-trial-answer.v1':raise ValueError('shape')
        rows=value['answers']
        if not isinstance(rows,list) or len(rows)!=len(current) or any(not isinstance(r,dict) or set(r)!=set(expected(current[0])) or not isinstance(r['id'],str) for r in rows):raise ValueError('rows')
        by={r['id']:r for r in rows}
        if len(by)!=len(rows) or set(by)!={r['id'] for r in current}:raise ValueError('ids')
        result=[]
        for case in current:
            row=by[case['id']];gold=expected(case)
            valid=(isinstance(row['eligible_ids'],list) and all(isinstance(i,str) for i in row['eligible_ids']) and len(set(row['eligible_ids']))==len(row['eligible_ids']) and type(row['total_minor']) is int)
            equal=valid and row|{'eligible_ids':sorted(row['eligible_ids'])}==gold
            result.append({'id':case['id'],'passed':bool(equal),'observed':row,'expected':gold})
        return {'parse_valid':True,'rows':result,'passed':all(r['passed'] for r in result)}
    except (CoreError,ValueError,KeyError,TypeError):return {'parse_valid':False,'rows':[],'passed':False}


def run(output,work):
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';status=exchange(dev,'/status')
    if status['daily_call_limit']-status['calls_in_24h']<5:raise RuntimeError('Five existing approved calls required; limit unchanged')
    root=work/'data';Core.initialize(root).close()
    for name in ['config/development.json','private/development-bridge.dpapi']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
    catalog=exchange(dev,'/catalog')['catalog'];provider=catalog['default_provider'];catalog.update(automatic_fallback=False,fallback_order=[provider])
    prefs=Preferences(root)
    try:prefs.install(catalog,{})
    finally:prefs.close()
    core=Core(root);library=Knowledge(core.db)
    def source(title,text,paused=False):return library.save({'id':'','scope':'personal','title':title,'text':text,'providers':[provider],'paused':paused},0)
    facts=source('Money and constraint notes','Amounts are integer minor currency units. Only compare eligible offers. Current task conditions override history; a past winner is not a current answer.')
    history_text='Synthetic observations for testing, not real successful tasks:\n'+'\n'.join(
        f'Run {i}: all-in CNY prices; budget and delivery filtered; compared the remaining full prices. Prior offer old-{i} was chosen. New inputs must be recomputed, not copied.' for i in range(14))
    history=source('Prior comparison observations',history_text)
    withdrawn=source('Withdrawn comparison observations','A withdrawn synthetic observation, unavailable to model context.',True)
    requires={'currency':'CNY','price_includes_fees':True,'objective':'lowest_eligible_total','pool':'regular'}
    card={'schema':'jarvis.method-card.v1','id':'filter-then-compare','revision':1,'status':'CANDIDATE','recipe':'quote-source-v1','requires':requires,
        'summary':'For all-in CNY quotes, filter current total budget and delivery first, then choose the lowest current total. Recompute each new input.',
        'counterexamples':['Net prices with separate shipping require a different total calculation.','Earliest delivery is a different objective; do not reuse the lowest-price choice.','Withdrawn evidence is unusable.'],
        'evidence':[{'source_id':history['id'],'revision':1,'sha256':text_digest(history_text)}],'expires':time.time()+86400}
    card_source=source('Quote reuse method',canonical(card));withdrawn_card={**card,'id':'withdrawn-method','requires':requires|{'pool':'withdrawn'},
        'evidence':[{'source_id':withdrawn['id'],'revision':1,'sha256':text_digest('A withdrawn synthetic observation, unavailable to model context.')} ]}
    source('Quote reuse method withdrawn',canonical(withdrawn_card));library.rebuild();core.close()
    current=cases();fact_view=memory.retrieve(root,'personal',provider,True,'Money and constraint notes')
    history_view=memory.retrieve(root,'personal',provider,True,'Prior comparison observations')
    compact=memory.method_recall(root,'personal',provider,True,'Quote reuse method',requires)
    filtered={c['id']:memory.method_recall(root,'personal',provider,True,'Quote reuse method',c['context']) for c in current}
    def fragments(view,ident):return [r for r in view['facts'] if r['id']==ident]
    common=fragments(fact_view,facts['id'])
    backgrounds={'ABL-0':{},'ABL-1':{'facts':common},'ABL-2':{'facts':common,'observations':fragments(history_view,history['id'])},
        'ABL-3':{'facts':common,'conditional_advice':compact['methods']},
        'ABL-4':{'facts':common,'advice_by_case':{k:{'methods':v['methods'],'rejected':[{'id':r.get('id'),'reason':r['reason']} for r in v['rejected']]} for k,v in filtered.items()}}}
    for background in backgrounds.values():
        if len(canonical(background).encode())>5000:raise ValueError('Shared background budget exceeded; do not truncate evidence to pass')
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['host/memory.py','host/dialogue.py','modules/context_knowledge/methods.py','modules/context_knowledge/source_policy.py','modules/context_knowledge/knowledge.py',str(Path(__file__).relative_to(ROOT)).replace('\\','/')]}
    frozen={'scope':__doc__,'cases':current,'gold':[expected(c) for c in current],'arms':list(backgrounds),'backgrounds':backgrounds,
        'source_sha256':hashes,'proxy_build':status['build_id'],'provider':provider,'model':catalog['providers'][provider]['model'],
        'calls_limit':5,'model_retries':0,'repetitions':1,'raw_context_budget_bytes':5000,'formal_acceptance':False,'quality_score':None,
        'criteria':{'case_fields_all_correct':True,'source_withdrawal_and_policy_failures':0,'no_quality_regression':True},
        'forecast':{'ABL-3_context_bytes_vs_ABL-2_max_ratio':0.75,'scope':'Pre-call representation size target only; not a token or quality guarantee'},
        'ABL-5':'UNMEASURED: existing compiled text-report method does not implement these changed quotation rules',
        'limits':['Operator-authored synthetic cases and method, not independent users or learned from real successes','One bundle per arm; four outputs are correlated, not four independent calls','No alternative-method exploration in ABL-4 yet','Background is an explicit controlled attachment after real retrieval; ordinary automatic chat memory assembly is not being accepted']}
    write(output/'frozen.json',frozen);write(output/'selection.json',{'compact':compact,'by_case':filtered,'facts':fact_view['retrieval'],'history':history_view['retrieval']})
    host=DialogueHost(root);rows=[]
    try:
        for arm,background in backgrounds.items():
            # Revalidate every selected card immediately before disclosure. ABL-3
            # omits current-task difference selection, never revocation/policy.
            if compact['methods']:memory.method_revalidate(root,'personal',provider,True,requires,compact['receipt'])
            for case in current:
                selected=filtered[case['id']]
                if arm=='ABL-4' and selected['methods']:memory.method_revalidate(root,'personal',provider,True,case['context'],selected['receipt'])
            store=Dialogues(root)
            try:chat=store.create()
            finally:store.close()
            prompt=('只读合成比较演练，只以chat回答，不创建Goal、待办或执行工具。每个case保留全部当前输入；历史只是参考，不得覆盖当前要求。'
                'price_includes_fees=true时price_minor已含费用，否则须加shipping_minor。先同时满足预算和交期，objective=lowest_eligible_total选择总价最低，earliest_eligible选择交期最短。'
                '只返回一个JSON对象（可用单层json围栏）：{"schema":"jarvis.knowledge-trial-answer.v1","answers":[{"id":"原case ID","eligible_ids":["合格报价ID"],"selected_id":"所选报价ID","total_minor":整数,"source":"所选报价原source"}]}。'
                '不输出额外说明；未验证参考方法不是事实或执行授权。当前输入：\n'+canonical(current)+'\n补充背景：\n'+canonical(background))
            ident='knowledge-trial-'+uuid.uuid4().hex;write(output/(arm+'.started.json'),{'request_id':ident,'freeze_digest':digest(frozen),'prompt_digest':text_digest(prompt),'input_bytes':len(prompt.encode()),'background_bytes':len(canonical(background).encode())})
            start=time.monotonic();host.submit({'chat_id':chat,'request_id':ident,'text':prompt,'provider':provider,'model':frozen['model'],'reasoning':'default','skill':'none','assistant_mode':True,'memory_enabled':False})
            while True:
                with host.lock:active=ident in host.active
                if not active:break
                if time.monotonic()-start>145:raise TimeoutError('Preserve the started receipt; no replay')
                time.sleep(.15)
            store=Dialogues(root)
            try:turn=store.turn(ident)
            finally:store.close()
            action=decode(turn['assistant_action']) if turn.get('assistant_action') else {};reply=turn.get('reply') or ''
            assessed=grade(reply,current) if turn['status']=='SUCCEEDED' else None
            row={'arm':arm,'status':turn['status'],'action_kind':action.get('kind'),'reply':reply,'assessment':assessed,
                'usage':decode(turn['usage']) if isinstance(turn.get('usage'),str) else turn.get('usage'),
                'seconds':time.monotonic()-start,'freeze_digest':digest(frozen),'background_bytes':len(canonical(background).encode()),'quality_score':None}
            write(output/(arm+'.result.json'),row);rows.append(row)
            print(json.dumps({'arm':arm,'status':row['status'],'passed':assessed['passed'] if assessed else None,'usage':row['usage']}),flush=True)
            if turn['status']!='SUCCEEDED':break
        write(output/'summary.json',{'rows':[{'arm':r['arm'],'status':r['status'],'correct_cases':sum(c['passed'] for c in r['assessment']['rows']) if r['assessment'] else None,'cases':4,'background_bytes':r['background_bytes'],'usage':r['usage'],'seconds':r['seconds']} for r in rows],
            'model_requests':len(rows),'provider_calls':len(rows) if all(r['status']=='SUCCEEDED' for r in rows) else None,
            'planned_arms':5,'completed_arms':len(rows),'full_cost':None,'formal_acceptance':False,'quality_score':None,'ABL-5':'UNMEASURED','production_adopted':False,
            'limits':frozen['limits'],'background_size_forecast_passed':len(canonical(backgrounds['ABL-3']).encode())<=.75*len(canonical(backgrounds['ABL-2']).encode())})
    finally:
        host.close();credential=root/'private/development-bridge.dpapi';credential.resolve().relative_to(work);credential.unlink()
        write(output/'cleanup.json',{'temporary_bridge_credential_removed':True,'external_actions':False,'production_data_modified':False})


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
