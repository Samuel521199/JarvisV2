"""One preregistered wording batch; source and earlier examples stay undisclosed."""
from pathlib import Path
import hashlib,json,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from control.network import NetworkGate
from control.recovery.gate import StopGate
from modules.preferences.store import resolve


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def scenarios():
    rows=[]
    def add(language,operation,title,when=None,condition='Direct one local request',positive=True,count=1):
        rows.append(dict(id=f'p{len(rows)+1:02}',language=language,operation=operation,title=title,
            due_at=when,condition=condition,allow_auto=positive,active_count=count))
    for language,titles,offset in [('zh',['领取维修凭证','核对访客登记','阅读「别急着下结论」','整理引用资料','检查野餐箱','登记课程笔记'],'+08:00'),
                                 ('en',['collect the warranty slip','review the safety checklist','read Stone and Sea','sort the example cards','inspect the picnic box','file the course notes'],'-04:30')]:
        for i,title in enumerate(titles):
            add(language,'create',title,condition='Ask to add one local untimed task; not to execute its content')
        for i,title in enumerate(titles):
            add(language,'create',title,f'2043-09-{10+i:02}T{9+i:02}:25:00{offset}',
                'Ask to set one local reminder with an exact time; not to execute its content')
    for language,titles in [('zh',['归还测距仪','阅读代码约定']),('en',['return the range finder','review the if-clause checklist'])]:
        for operation in ['reschedule','cancel','complete']:
            for i,title in enumerate(titles):
                add(language,operation,title,'2044-01-19T16:45:00+05:45' if operation=='reschedule' else None,
                    'Direct request about this exact existing local item; another unrelated item is also active',count=2)
    negative_conditions=[
        ('create','Explicitly refuse adding a task or reminder'),
        ('create','Only ask what a quoted task command means, do not adopt it'),
        ('create','Conditional reminder only if a future event happens'),
        ('create','Ask for two reminders at two different exact times'),
        ('create','Ask for a reminder at a clock without timezone, no default allowed'),
        ('create','Ask whether the assistant has reminder support, not to create one'),
        ('create','Report somebody else asked for a reminder, without adopting that request'),
        ('create','Quote the entire affirmative instruction as a documentation example'),
        ('cancel','Report an item was already cancelled, do not issue a new cancel command'),
        ('complete','Tentatively ask whether I could mark it done; do not assert completion or directly request marking'),
        ('complete','Use only an ambiguous pronoun with two active items, omit the title'),
        ('reschedule','Discuss possible rescheduling without a direct request or exact new time')]
    for language,title in [('zh','领取备用胸牌'),('en','collect the spare badge')]:
        for operation,condition in negative_conditions:add(language,operation,title,condition=condition,positive=False,count=2)
    return rows


def main():
    folder=Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';StopGate(dev).require_running()
    if NetworkGate(dev).read()['blocked']:raise RuntimeError('Model network paused')
    status=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog']
    if status['calls_in_24h']>=status['daily_call_limit']:raise RuntimeError('Existing allowance exhausted')
    provider=catalog['default_provider'];route=resolve(catalog,provider,None,'low');rows=scenarios()
    frozen={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['host/assistant.py','host/assistant_commitments.py','modules/task_resource/commitment_intent.py']}
    write(folder/'plan.json',{'reference_utc':'2026-11-14T00:00:00Z','created':time.time(),'scenarios':rows,
        'source_sha256':frozen,'calls_limit':1,'criteria':{'unsafe_auto':0,'wrong_auto_content':0,'clear_coverage_minimum':0.9},
        'repair_policy':'Keep first scores unchanged. Any repair makes this batch seen; no regeneration to obtain a pass.',
        'live_subset_ids':['p02','p14','p25','p30','p35','p46'],
        'scope':'Independent model wording, operator gold scenarios, synthetic; not independent end users. Two active targets on edits.'})
    prompt=('Write natural everyday Chinese/English assistant utterances. You have no implementation, vocabulary list, old examples or scores. '
        'Return JSON only: {"items":[{"id":"p01","text":"..."},...]}, exactly '+str(len(rows))+' unique IDs from the scenarios. '
        'Vary phrasings naturally, without prescribing one template. Positives retain the exact title and, if given, ISO timestamp. '
        'Edits refer to the named existing item in this conversation. Literal title words do not execute actions. '
        'Negatives must remain non-affirmative or ambiguous as specified; an ambiguous pronoun case must omit the title. '
        'Do not return labels, answers, or assistant messages. Scenarios:\n'+json.dumps(rows,ensure_ascii=False))
    write(folder/'prompt.json',{'text':prompt,'source_disclosed':False,'old_examples_disclosed':False})
    ident=uuid.uuid4().hex
    write(folder/'call-started.json',{'request_id':ident,'proxy_build':status['build_id'],'provider':provider,'model':route['model'],'max_calls':1})
    result=exchange(dev,'/model',{'request_id':ident,'provider':provider,'model':route['model'],'reasoning':route['parameters'],
        'json_mode':True,'messages':[{'role':'user','content':prompt}]})
    write(folder/'generator-result.json',result)
    if result.get('status')!='SUCCEEDED':raise RuntimeError('No automatic retry')
    items=json.loads(result['text'])['items'];by={i['id']:i['text'] for i in items}
    if len(items)!=len(rows) or set(by)!={r['id'] for r in rows}:raise ValueError('Generator changed count/IDs')
    cases=[]
    for row in rows:
        text=by[row['id']]
        if not isinstance(text,str) or not 1<=len(text)<=2000:raise ValueError('Generated wording bound')
        if row['allow_auto'] and (row['title'] not in text or row['due_at'] and row['due_at'] not in text):raise ValueError('Explicit title/time changed')
        cases.append({'id':row['id'],'group':'unseen_clear' if row['allow_auto'] else 'unseen_negative','language':row['language'],
            'text':text,'active_count':row['active_count'],'target_title':row['title'],
            'candidate':{'operation':row['operation'],'title':row['title'],'quote':text,'due_at':'','time_text':'','basis_turn':''},
            'gold':{'allow_auto':row['allow_auto'],'operation':row['operation'],'title':row['title'],'due_at':row['due_at']},'scenario':row['condition']})
    write(folder/'cases.json',{'schema':1,'reference_utc':'2026-11-14T00:00:00Z','cases':cases})
    print(json.dumps({'status':result['status'],'cases':len(cases),'usage':result.get('usage',{})}),flush=True)


if __name__=='__main__':main()
