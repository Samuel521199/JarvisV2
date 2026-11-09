"""Run old/new host admission over a sealed set, never apply the candidates."""
import argparse,hashlib,json
from datetime import datetime
from pathlib import Path
import sys,uuid

HERE=Path(__file__).resolve().parent

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--cases',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime.resolve();sys.path.insert(0,str(runtime))
    from host.core import Core
    from host import assistant
    from host.assistant_commitments import decision
    from modules.dialogue.store import Dialogues
    from modules.task_resource.commitments import Commitments,due
    from sdk.protocol import canonical,CoreError
    data=json.loads(args.cases.read_text(encoding='utf-8'));reference=datetime.fromisoformat(data['reference_utc'].replace('Z','+00:00')).timestamp()
    args.work.mkdir(parents=True,exist_ok=False);rows=[];seed_unchanged=True
    for case in data['cases']:
        root=(args.work/case['id']).resolve();root.mkdir();Core.initialize(root).close();chats=Dialogues(root)
        try:chat=chats.create()
        finally:chats.close()
        target='a'*32;title=case.get('target_title','核对订单')
        with Commitments(root) as store:
            for i in range(case['active_count']):
                store.command({'action':'create','id':target if i==0 else 'b'*32,'request_id':uuid.uuid4().hex,
                    'title':title if i==0 else 'another local item','source':'synthetic fixture','due_at':None},
                    origin={'chat_id':chat,'turn_id':'fixture','source_digest':'0'*64})
            def snapshot():
                return canonical({table:[dict(row) for row in store.db.execute('SELECT * FROM '+table+' ORDER BY 1')]
                    for table in ('commitments','history','operations','conversation_operations')})
            initial=snapshot()
        envelope={'schema':'jarvis.assistant-turn.v1','reply':'candidate only','action':{'kind':'commitment','goal':'','input_text':'',
            'target':target if case['candidate']['operation']!='create' else '', 'commitment':case['candidate']}}
        row={'id':case['id'],'group':case['group'],'language':case.get('language','zh'),'mode':'REJECTED','error':None}
        try:
            _,action=assistant.parse(canonical(envelope),assistant.context(root,chat))
            turn={'id':'shadow-'+case['id'],'chat_id':chat,'request':canonical({'text':case['text'],'assistant_mode':True}),
                'assistant_action':canonical(action),'created':reference,'lane':'foreground'}
            result=decision(root,turn,{'id':chat})
            row.update(mode=result['mode'],title=result['title'],due_at=result['due_at'],operation=action['commitment']['operation'],target=action['target'])
        except (CoreError,ValueError,KeyError) as error:row['error']=getattr(error,'code',type(error).__name__)
        gold=case['gold'];auto=row['mode']=='AUTO';time_ok=row.get('due_at') is None and gold['due_at'] is None
        if row.get('due_at') and gold['due_at']:time_ok=due(row['due_at'])==due(gold['due_at'])
        content_ok=(row.get('title')==gold.get('title',case['candidate']['title']) and row.get('operation')==gold['operation']
            and row.get('target')==('' if gold['operation']=='create' else target) and time_ok)
        row.update(unsafe_auto=auto and not gold['allow_auto'],wrong_auto_content=auto and gold['allow_auto'] and not content_ok,
            correct_auto=auto and gold['allow_auto'] and content_ok,missed_clear=gold['allow_auto'] and not (auto and content_ok))
        with Commitments(root) as store:seed_unchanged=seed_unchanged and initial==snapshot()
        rows.append(row)
    clear=sum(case['gold']['allow_auto'] for case in data['cases'])
    groups={}
    for group in sorted({row['group'] for row in rows}):
        subset=[row for row in rows if row['group']==group];ids={row['id'] for row in subset}
        n=sum(case['gold']['allow_auto'] for case in data['cases'] if case['id'] in ids)
        groups[group]={'cases':len(subset),'clear':n,'correct_auto':sum(row['correct_auto'] for row in subset),
            'unsafe_auto':sum(row['unsafe_auto'] for row in subset),'wrong_auto_content':sum(row['wrong_auto_content'] for row in subset)}
    report={'runtime':str(runtime),'source_sha256':hashlib.sha256((runtime/'modules/task_resource/commitment_intent.py').read_bytes()).hexdigest(),
        'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),'scope':'forced-candidate admission; not model selection or actual reminders',
        'seed_state_unchanged':seed_unchanged,'summary':{'cases':len(rows),'clear_requests':clear,
            'correct_auto':sum(row['correct_auto'] for row in rows),'coverage':sum(row['correct_auto'] for row in rows)/clear,
            'unsafe_auto':sum(row['unsafe_auto'] for row in rows),'wrong_auto_content':sum(row['wrong_auto_content'] for row in rows),
            'missed_clear':sum(row['missed_clear'] for row in rows)},'groups':groups,'rows':rows}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps(report['summary']))
