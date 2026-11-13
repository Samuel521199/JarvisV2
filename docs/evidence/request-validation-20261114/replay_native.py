"""Replay captured ordinary model choices on a fresh clone, without model calls."""
from pathlib import Path
import hashlib,json,shutil,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from host import assistant
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments,due
from sdk.protocol import decode


def inventory(root):
    return {p.relative_to(root).as_posix():hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
        for p in root.rglob('*') if p.is_file()}


def main():
    folder=Path(sys.argv[1]).resolve();original=Path(sys.argv[2]).resolve();copy=Path(sys.argv[3]).resolve()
    name=sys.argv[4] if len(sys.argv)>4 else 'native-repaired-seen.json'
    if Path(name).name!=name or not name.endswith('.json'):raise ValueError('Use an evidence filename')
    if copy.exists() or copy.is_relative_to(original):raise ValueError('Use a fresh separate replay clone')
    before=inventory(original);shutil.copytree(original,copy)
    cases={r['id']:r for r in json.loads((folder/'cases.json').read_text(encoding='utf-8'))['cases']}
    live=json.loads((folder/'live-first.json').read_text(encoding='utf-8'));rows=[]
    for row in live['rows']:
        case=cases[row['id']];gold=case['gold'];chats=Dialogues(copy)
        try:turn=chats.turn(row['turn_id'])
        finally:chats.close()
        action=decode(turn['assistant_action']) if turn.get('assistant_action') else {}
        with Commitments(copy) as db:prior=db.conversation_items(turn['chat_id'])
        result=assistant.commitment_from_turn(copy,row['turn_id']) if action.get('kind')=='commitment' else None
        with Commitments(copy) as db:after=db.conversation_items(turn['chat_id'])
        actual=result.get('receipt',{}).get('current') if result else None
        if not gold['allow_auto']:passed=prior==after and (not result or result['mode'] not in ('AUTO','APPLIED'))
        else:
            passed=bool(actual and result['mode']=='APPLIED' and actual['title']==gold['title']
                and action['commitment']['operation']==gold['operation'])
            if actual:
                if gold['operation']=='create':passed &= actual['status']=='OPEN' and actual['due_text']==gold['due_at']
                else:passed &= actual['id']==action['target'] and actual['revision']==2
                if gold['operation']=='reschedule':passed &= bool(actual['due_text'] and due(actual['due_text'])==due(gold['due_at']))
                if gold['operation']=='complete':passed &= actual['status']=='DONE'
                untouched={r['id']:r for r in prior if r['id']!=actual['id']}
                passed &= untouched=={r['id']:r for r in after if r['id'] in untouched}
        rows.append({'id':case['id'],'original_host_mode':row['host_mode'],'original_passed':row['passed'],
            'replay_mode':result['mode'] if result else None,'passed':bool(passed),'model_choice_unchanged':True})
    unchanged=before==inventory(original)
    report={'scope':'Seen counterfactual on captured real model selections; not a fresh live model run',
        'model_calls':0,'forced_new_candidates':False,'original_fixture_unchanged':unchanged,'rows':rows,
        'passed':unchanged and all(r['passed'] for r in rows),
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['host/assistant.py','host/assistant_commitments.py','modules/task_resource/commitment_intent.py']}}
    with (folder/name).open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
