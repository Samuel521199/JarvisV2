"""Preregistered unseen subset through ordinary model selection and Host writes."""
from pathlib import Path
import hashlib,json,shutil,sys,time,uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from host.core import Core
from host.dialogue import DialogueHost
from host import assistant
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from modules.task_resource.commitments import Commitments,due


def main():
    folder=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve()
    plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    for name,value in plan['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value:raise ValueError('Frozen source changed')
    cases={r['id']:r for r in json.loads((folder/'cases.json').read_text(encoding='utf-8'))['cases']}
    selected=[cases[ident] for ident in plan['live_subset_ids']]
    dev=ROOT/'user-data';status=exchange(dev,'/status')
    if status['daily_call_limit']-status['calls_in_24h']<len(selected):raise RuntimeError('Existing allowance insufficient')
    work.mkdir(parents=True,exist_ok=False);root=work/'data';Core.initialize(root).close()
    for name in ['config/development.json','private/development-bridge.dpapi']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
    cfg=exchange(dev,'/catalog')['catalog'];provider=cfg['default_provider']
    cfg.update(automatic_fallback=False,fallback_order=[provider])
    prefs=Preferences(root)
    try:prefs.install(cfg,{})
    finally:prefs.close()
    report={'scope':'Six preregistered synthetic unseen utterances; real model selection and ordinary Host application',
        'source_sha256':plan['source_sha256'],'proxy_build':status['build_id'],'rows':[],
        'forced_action':False,'gold_in_prompt':False,'model_retries':0,'external_actions':False}
    output=folder/'live-first.json'
    if output.exists():raise FileExistsError('First result must remain immutable')
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    host=DialogueHost(root)
    try:
        for case in selected:
            store=Dialogues(root)
            try:chat=store.create()
            finally:store.close()
            target=uuid.uuid4().hex
            with Commitments(root) as db:
                for index in range(case['active_count']):
                    db.command({'action':'create','id':target if index==0 else uuid.uuid4().hex,'request_id':uuid.uuid4().hex,
                        'title':case['target_title'] if index==0 else 'unrelated item remains open',
                        'source':'synthetic local fixture','due_at':None},origin={'chat_id':chat,'turn_id':'fixture','source_digest':'0'*64})
                before=db.conversation_items(chat)
            ident='unseen-live-'+uuid.uuid4().hex
            host.submit({'chat_id':chat,'request_id':ident,'text':case['text'],'provider':provider,
                'model':cfg['providers'][provider]['model'],'reasoning':'default','skill':'none','memory_enabled':False,'assistant_mode':True})
            deadline=time.monotonic()+145
            while True:
                with host.lock:active=ident in host.active
                if not active:break
                if time.monotonic()>deadline:raise TimeoutError('No replay after observation timeout')
                time.sleep(.15)
            store=Dialogues(root)
            try:turn=store.read(chat)['turns'][-1]
            finally:store.close()
            action=turn.get('assistant_action') or {};receipt=None
            if action.get('kind')=='commitment':receipt=assistant.commitment_from_turn(root,ident)
            with Commitments(root) as db:after=db.conversation_items(chat)
            gold=case['gold'];passed=turn['status']=='SUCCEEDED';actual=None
            if not gold['allow_auto']:passed &= before==after and (not receipt or receipt['mode'] not in ('APPLIED','AUTO'))
            else:
                actual=receipt.get('receipt',{}).get('current') if receipt else None
                passed &= bool(receipt and receipt['mode']=='APPLIED' and actual and actual['title']==gold['title'])
                if actual:
                    passed &= action.get('commitment',{}).get('operation')==gold['operation']
                    if gold['operation']=='create':passed &= len(after)==len(before)+1 and actual['status']=='OPEN'
                    else:passed &= len(after)==len(before) and actual['id']==target and actual['revision']==2
                    if gold['operation']=='reschedule':passed &= bool(actual['due_text'] and due(actual['due_text'])==due(gold['due_at']))
                    if gold['operation']=='create':passed &= actual['due_text']==gold['due_at']
                    if gold['operation'] in ('cancel','complete'):passed &= actual['status']==('DONE' if gold['operation']=='complete' else 'CANCELLED')
                    untouched=[r for r in before if r['id']!=actual['id']]
                    passed &= untouched==[r for r in after if r['id'] in {r['id'] for r in untouched}]
            row={'id':case['id'],'turn_id':ident,'turn_status':turn['status'],'action_kind':action.get('kind'),
                'host_mode':receipt['mode'] if receipt else None,'passed':bool(passed),'usage':turn.get('usage',{}),
                'business_before_count':len(before),'business_after_count':len(after),'error':turn.get('error')}
            report['rows'].append(row);save();print(json.dumps(row,ensure_ascii=False),flush=True)
        report['passed']=all(row['passed'] for row in report['rows'])
    finally:
        host.close();credential=root/'private/development-bridge.dpapi'
        credential.resolve().relative_to(work);credential.unlink();report['temporary_bridge_credential_removed']=True;save()
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
