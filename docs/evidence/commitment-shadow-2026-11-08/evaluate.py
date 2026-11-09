"""Evaluate proposals without applying them. Gold labels never enter prompts."""
from datetime import datetime
import hashlib,json
from pathlib import Path
import sys,uuid

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from host.core import Core
from host import assistant
from host.assistant_commitments import decision
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments,due
from sdk.protocol import canonical,CoreError


def fixture(root, case, reference):
    Core.initialize(root).close();chats=Dialogues(root)
    try:chat=chats.create()
    finally:chats.close()
    target='a'*32
    with Commitments(root) as store:
        for i in range(case['active_count']):
            store.command({'action':'create','id':target if i==0 else 'b'*32,'request_id':uuid.uuid4().hex,
                'title':'核对订单' if i==0 else '准备会议','source':'synthetic fixture','due_at':'2031-06-18T09:10:00+08:00'},
                origin={'chat_id':chat,'turn_id':'fixture','source_digest':'0'*64})
    return chat,target


def candidate(case,target):
    return {'schema':'jarvis.assistant-turn.v1','reply':'synthetic proposal only',
        'action':{'kind':'commitment','goal':'','input_text':'','target':target if case['candidate']['operation']!='create' else '',
                  'commitment':case['candidate']}}


def score(root,chat,case,envelope,reference):
    row={'id':case['id'],'group':case['group'],'mode':'NO_ACTION','action_kind':None,'error':None}
    try:
        reply,action=assistant.parse(canonical(envelope),assistant.context(root,chat));row['action_kind']=action['kind']
        if action['kind']=='commitment':
            row.update(operation=action['commitment']['operation'],target=action['target'])
            turn={'id':'shadow-'+case['id'],'chat_id':chat,'request':canonical({'text':case['text'],'assistant_mode':True}),
                'assistant_action':canonical(action),'created':reference,'lane':'foreground'}
            result=decision(root,turn,{'id':chat});row.update(mode=result['mode'],title=result['title'],due_at=result['due_at'])
    except (CoreError,ValueError,KeyError) as error:row.update(mode='REJECTED',error=getattr(error,'code',type(error).__name__))
    auto=row['mode']=='AUTO';gold=case['gold'];right_time=(row.get('due_at') is None and gold['due_at'] is None)
    if row.get('due_at') and gold['due_at']:
        right_time=due(row['due_at'])==due(gold['due_at'])
    row.update(unsafe_auto=auto and not gold['allow_auto'],wrong_auto_time=auto and gold['allow_auto'] and not right_time,
        correct_auto=auto and gold['allow_auto'] and right_time and row.get('operation')==gold['operation'] and row.get('title')==case['candidate']['title'],
        missed_clear=gold['allow_auto'] and not (auto and right_time and row.get('operation')==gold['operation'] and row.get('title')==case['candidate']['title']))
    return row


def summary(rows,cases):
    byid={c['id']:c for c in cases};clear=sum(byid[r['id']]['gold']['allow_auto'] for r in rows)
    supported=[r for r in rows if r['group']=='supported']
    return {'cases':len(rows),'unsafe_auto':sum(r['unsafe_auto'] for r in rows),'wrong_auto_time':sum(r['wrong_auto_time'] for r in rows),
        'clear_single_local_requests':clear,'correct_auto':sum(r['correct_auto'] for r in rows),
        'automatic_coverage':sum(r['correct_auto'] for r in rows)/clear if clear else None,
        'supported_automatic_coverage':sum(r['correct_auto'] for r in supported)/len(supported) if supported else None,
        'missed_clear':sum(r['missed_clear'] for r in rows)}


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    data=json.loads((HERE/'cases.json').read_text(encoding='utf-8'));reference=datetime.fromisoformat(data['reference_utc'].replace('Z','+00:00')).timestamp()
    rows=[]
    for case in data['cases']:
        root=work/case['id'];root.mkdir();chat,target=fixture(root,case,reference)
        rows.append(score(root,chat,case,candidate(case,target),reference))
    result={'source_sha256':hashlib.sha256((ROOT/'modules/task_resource/commitment_intent.py').read_bytes()).hexdigest(),
        'cases_sha256':hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest(),'scope':'forced candidate host-admission shadow; no proposal was applied',
        'summary':summary(rows,data['cases']),'rows':rows}
    (HERE/('offline-'+sys.argv[2]+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary']))
