"""Real approved model -> ordinary DialogueHost -> local fixture commitments.

No forced action proposals, personal messages, mailbox access, or model retries.
Gold expectations stay in this operator harness and never enter the prompt.
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from host.core import Core
from host.dialogue import DialogueHost
from host import assistant
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from modules.task_resource.commitments import Commitments


def run(work):
    dev=ROOT/'user-data';status=exchange(dev,'/status')
    remaining=status['daily_call_limit']-status['calls_in_24h']
    if remaining<8:raise RuntimeError('At least eight approved calls required; allowance unchanged')
    work.mkdir(parents=True,exist_ok=False);root=work/'data';Core.initialize(root).close()
    for name in ('config/development.json','private/development-bridge.dpapi'):
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
    cfg=exchange(dev,'/catalog')['catalog'];provider=cfg['default_provider']
    cfg['automatic_fallback']=False;cfg['fallback_order']=[provider]
    prefs=Preferences(root)
    try:prefs.install(cfg,{})
    finally:prefs.close()
    store=Dialogues(root)
    try:chat=store.create()
    finally:store.close()
    cases=[
      ('create','帮我记个待办：核对望远镜清单','APPLIED','OPEN',1),
      ('reschedule','将“核对望远镜清单”的时间重新安排为 2099-07-19T17:40:00+05:30。','APPLIED','OPEN',1),
      ('cancel','请取消现有的待办事项“核对望远镜清单”。','APPLIED','CANCELLED',1),
      ('english','Remind me locally at 2099-06-11T10:35:00-04:00 to verify the greenhouse labels.','APPLIED','OPEN',2),
      ('complete','Mark the existing to-do verify the greenhouse labels as done.','APPLIED','DONE',2),
      ('negative','不要设置提醒，也不要创建待办：明天去买纸。','NO_WRITE',None,2),
      ('vague','明天下午提醒我归还图册','NEEDS_TIME',None,2),
      ('clarification','15:00 UTC+08:00','APPLIED','OPEN',3),
    ]
    report={'scope':'real model selection and host application on local synthetic data',
            'proxy_build':status['build_id'],'provider':provider,'rows':[],
            'paid_mail_or_external_actions':False,'model_retries':0}
    host=DialogueHost(root)
    try:
        for name,text,mode,state,count in cases:
            ident='live-'+uuid.uuid4().hex
            host.submit({'chat_id':chat,'request_id':ident,'text':text,'provider':provider,
                'model':cfg['providers'][provider]['model'],'reasoning':'default','skill':'none',
                'memory_enabled':False,'assistant_mode':True})
            deadline=time.monotonic()+145
            while True:
                with host.lock:active=ident in host.active
                if not active:break
                if time.monotonic()>deadline:raise TimeoutError('One model request timed out; no replay')
                time.sleep(.15)
            store=Dialogues(root)
            try:turn=store.read(chat)['turns'][-1]
            finally:store.close()
            action=turn.get('assistant_action') or {};receipt=None
            if action.get('kind')=='commitment':receipt=assistant.commitment_from_turn(root,ident)
            with Commitments(root) as store:records=store.listing()
            correct=(len(records)==count and turn['status']=='SUCCEEDED')
            if mode=='NO_WRITE':correct &= not receipt or receipt['mode'] not in ('APPLIED','AUTO')
            else:correct &= bool(receipt and receipt['mode']==mode)
            if state:correct &= bool(receipt and receipt.get('receipt',{}).get('current',{}).get('status')==state)
            row={'case':name,'turn_status':turn['status'],'action':action.get('kind'),
                 'host_mode':receipt['mode'] if receipt else None,'record_count':len(records),
                 'passed':bool(correct),'usage':turn.get('usage',{}),'error':turn.get('error')}
            report['rows'].append(row)
            (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(row,ensure_ascii=False),flush=True)
        report['passed']=all(row['passed'] for row in report['rows'])
    finally:
        host.close()
        credential=root/'private/development-bridge.dpapi';credential.resolve().relative_to(work.resolve());credential.unlink()
        report['temporary_bridge_credential_removed']=True
        report['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('host/dialogue.py','host/assistant.py','host/assistant_commitments.py','modules/task_resource/commitment_intent.py')}
        (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    result=run(Path(sys.argv[1]).resolve())
    raise SystemExit(0 if result.get('passed') else 1)
