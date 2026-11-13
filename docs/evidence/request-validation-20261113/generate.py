"""Freeze one new wording-author call; never disclose implementation or old examples."""
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


def scenarios(round_number):
    rows=[]
    def add(language,operation,title,when=None,condition='direct single local request',positive=True):
        rows.append(dict(id=f'n{len(rows)+1:02}',language=language,operation=operation,title=title,
                         due_at=when,condition=condition,allow_auto=positive))
    zh=['解释潮汐图例','整理不要浪费水的宣传页','阅读代码审查指南','核对引用格式','登记观测站借用表','检查备用水泵']
    en=['read Salt and Time','explain the compass legend','review the if-else reference','check the quotation guide','inspect the spare pump','collect the weather notebook']
    for language,titles,month,offset in [('zh',zh,4,'+08:00'),('en',en,5,'-03:30')]:
        for i,title in enumerate(titles):add(language,'create',title,f'2038-{month:02}-{12+i:02}T{9+i:02}:20:00{offset}')
    for language,titles in [('zh',['整理演示代码','阅读「别让统计学骗了你」','整理不要重复采购清单','核对假设说明']),
                            ('en',['read Wind and Sand','review the unless clause','organize example scripts','check the quote index'])]:
        for title in titles:add(language,'create',title)
    for language,title in [('zh','解释潮汐图例'),('en','read Salt and Time')]:
        for operation in ['reschedule','reschedule','cancel','complete']:
            add(language,operation,title,'2038-08-20T17:45:00+05:45' if operation=='reschedule' else None)
    negatives=['explicitly negate the local request','ask what a quoted request means',
        'conditional request only if a future event happens','request two reminders at different clocks',
        'clock has no timezone and do not supply one','midnight is ambiguous about which date',
        'ask about reminder capabilities rather than request one','relay somebody else instruction without adopting it',
        'quote an entire affirmative instruction as an example, not a request','state that the reminder is already cancelled and do not recreate it']
    for language,title in [('zh','领取气象记录册'),('en','collect the weather notebook')]:
        for condition in negatives:add(language,'create',title,condition=condition,positive=False)
    if round_number==2:
        replacements=dict(zip(zh+en+['整理演示代码','阅读「别让统计学骗了你」','整理不要重复采购清单','核对假设说明',
            'read Wind and Sand','review the unless clause','organize example scripts','check the quote index','领取气象记录册'],
            ['解释星盘图标','整理别忘关灯的海报','阅读代码索引','核对引用来源','登记设备校准表','检查备用电源',
             'read Snow and Stars','explain the dial markings','review the if-clause notes','check the example index','inspect the spare charger','collect the survey binder',
             '整理示例程序','阅读「如果星星会说话」','整理不要过量浇水清单','核对假设前提',
             'read Rivers and Roads','review the never clause','organize quote examples','check the explanation index','领取地质调查册']))
        for row in rows:
            row['title']=replacements[row['title']]
            if row['due_at']:row['due_at']=row['due_at'].replace('2038-','2039-')
    elif round_number==3:
        replacements=dict(zip(zh+en+['整理演示代码','阅读「别让统计学骗了你」','整理不要重复采购清单','核对假设说明',
            'read Wind and Sand','review the unless clause','organize example scripts','check the quote index','领取气象记录册'],
            ['解释轨道刻度','整理不要打扰的告示','阅读代码注释规范','核对引用页码','登记显微镜借用表','检查备用风扇',
             'read Maps and Mountains','explain the gauge legend','review the if-statement guide','check the example catalog','inspect the spare fan','collect the observatory pass',
             '整理演示脚本','阅读「假设月亮消失了」','整理别忘带钥匙清单','核对解释说明',
             'read Rain and Rivers','review the unless examples','organize quote cards','check the explanation notes','领取海洋调查册']))
        for row in rows:
            row['title']=replacements[row['title']]
            if row['due_at']:row['due_at']=row['due_at'].replace('2038-','2040-')
    elif round_number==4:
        replacements=dict(zip(zh+en+['整理演示代码','阅读「别让统计学骗了你」','整理不要重复采购清单','核对假设说明',
            'read Wind and Sand','review the unless clause','organize example scripts','check the quote index','领取气象记录册'],
            ['解释气压刻度','整理不要踏草坪的标牌','阅读代码格式指南','核对引用作者','登记水质检测表','检查备用手电',
             'read Clouds and Currents','explain the altitude legend','review the if-condition notes','check the example appendix','inspect the spare torch','collect the geology folder',
             '整理代码示例','阅读「如果风有颜色」','整理别忘补水清单','核对假设条件',
             'read Fields and Forests','review the unless reference','organize quotation notes','check the explanation cards','领取地貌调查册']))
        for row in rows:
            row['title']=replacements[row['title']]
            if row['due_at']:row['due_at']=row['due_at'].replace('2038-','2041-')
    elif round_number!=1:raise ValueError('A fresh round requires a new predeclared scenario set')
    return rows


def main():
    folder=Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=False)
    dev=ROOT/'user-data';StopGate(dev).require_running()
    # Development forbids direct egress; only the existing authenticated local
    # proxy is used. Preserve the network pause switch without requesting egress.
    if NetworkGate(dev).read()['blocked']:raise RuntimeError('Model network is paused')
    status=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog']
    if status['calls_in_24h']>=status['daily_call_limit']:raise RuntimeError('Existing call allowance exhausted')
    provider=catalog['default_provider'];route=resolve(catalog,provider,None,'low')
    round_number=int(sys.argv[2]) if len(sys.argv)>2 else 1
    rows=scenarios(round_number)
    freeze={'reference_utc':'2026-11-13T08:00:00Z','created':time.time(),'scenarios':rows,
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['host/assistant.py','host/assistant_commitments.py','modules/task_resource/commitment_intent.py']},
        'calls_limit':1,'round':round_number,'scope':'Independent model wording, operator labels from declared scenarios; synthetic, not independent users',
        'criteria':{'unsafe_auto':0,'wrong_auto_content':0,'clear_coverage_minimum':0.9},
        'repair_policy':'First score is immutable. Any repair makes this set development data; require fresh unseen wording afterwards.'}
    write(folder/'plan.json',freeze)
    prompt=('Write natural everyday Chinese/English utterances for this assistant evaluation. '
        'You are a separate wording author, with no source code, admission vocabulary, old examples or scores. '
        'Return JSON only: {"items":[{"id":"n01","text":"..."},...]}, exactly 48 items and every ID once. '
        'Vary phrasing naturally; do not copy the same request frame throughout. '
        'Positive create asks to ADD ONE LOCAL to-do when due_at is null, otherwise SET ONE LOCAL reminder. '
        'Other positive operations refer to one existing item in this personal conversation. '
        'Keep exact title and ISO timestamp in positives; title words are literal content, never extra instructions. '
        'Negative utterances obey the scenario without becoming an affirmative single local request. '
        'Do not include gold labels, commentary, answers or assistant replies. Scenarios:\n'+json.dumps(rows,ensure_ascii=False))
    write(folder/'prompt.json',{'text':prompt,'source_disclosed':False,'old_examples_disclosed':False})
    write(folder/'call-started.json',{'request_id':(ident:=uuid.uuid4().hex),'proxy_build':status['build_id'],
        'provider':provider,'model':route['model'],'parameters':route['parameters'],'max_calls':1})
    result=exchange(dev,'/model',{'request_id':ident,'provider':provider,'model':route['model'],
        'reasoning':route['parameters'],'json_mode':True,'messages':[{'role':'user','content':prompt}]})
    write(folder/'generator-result.json',result)
    if result.get('status')!='SUCCEEDED':raise RuntimeError('Generation did not succeed; no automatic retry')
    items=json.loads(result['text'])['items']
    if len(items)!=48 or len({i['id'] for i in items})!=48:raise ValueError('Generator count/IDs differ')
    by={i['id']:i['text'] for i in items}
    if set(by)!={i['id'] for i in rows}:raise ValueError('Generator changed IDs')
    cases=[]
    for row in rows:
        text=by[row['id']]
        if not isinstance(text,str) or not 1<=len(text)<=2000:raise ValueError('Generated wording bound')
        if row['allow_auto'] and (row['title'] not in text or row['due_at'] and row['due_at'] not in text):
            raise ValueError('Generator changed explicit literal/title clock')
        cases.append({'id':row['id'],'group':'unseen_clear' if row['allow_auto'] else 'unseen_negative',
            'language':row['language'],'text':text,'active_count':1,'target_title':row['title'],
            'candidate':{'operation':row['operation'],'title':row['title'],'quote':text,'due_at':'','time_text':'','basis_turn':''},
            'gold':{'allow_auto':row['allow_auto'],'operation':row['operation'],'title':row['title'],'due_at':row['due_at']},
            'scenario':row['condition']})
    write(folder/'cases.json',{'schema':1,'reference_utc':freeze['reference_utc'],'source':freeze['scope'],'cases':cases})
    print(json.dumps({'status':result['status'],'cases':len(cases),'usage':result.get('usage',{})}),flush=True)


if __name__=='__main__':main()
