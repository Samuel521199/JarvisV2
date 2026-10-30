"""One character asset: bounded four-view review using owner's stated priorities.

The model sees explicit image IDs only, and its observations are never executed.
"""
import argparse
import hashlib
import json
import msvcrt
import time
import uuid
from pathlib import Path
from control.local_access import install_client
from control.recovery.gate import StopGate
from host.studio3d_reference import record as reference_record
from modules.context_knowledge.character_experience import record
from modules.skills.studio3d.character_contract import FAMILY, VIEWS
from modules.skills.studio3d.character_priorities import load as priorities_load
from tools import studio3d_character_trial as api
from tools.studio3d_character_iterate import ASSET, DATA, ROOT, digest, load, save, sha

# User reference names correspond to image-facing direction. These FBX-based
# renders use the opposite camera-side labels. Pair the actual views explicitly.
RENDER_FOR_REFERENCE={'front':'front','rear':'rear','right':'left','left':'right'}


def run(candidate):
    if not candidate.startswith('user-fbx-') or '/' in candidate or '\\' in candidate or '..' in candidate:
        raise ValueError('Expected a named character FBX-derived candidate')
    folder=(ASSET/candidate).resolve()
    if folder.parent!=ASSET.resolve():raise ValueError('Candidate must remain in this character asset')
    manifest=load(folder/'manifest.json'); manifest_hash=sha(folder/'manifest.json')
    trial=load(ASSET/'metadata/trial.json');asset=trial['asset_id']
    priorities,priority_hash=priorities_load(ASSET/'metadata/visual-priorities.json',asset)
    for view in VIEWS:
        path=folder/('view-'+RENDER_FOR_REFERENCE[view]+'.png')
        if sha(path)!=manifest['files'][path.name]:raise ValueError('Candidate image identity changed: '+view)
        if sha(ASSET/'references'/(view+'.png'))!=trial['reference_sha256'][view]:raise ValueError('Reference changed: '+view)
        ref,_=reference_record(DATA,trial['reference_ids'][view])
        if ref['sha256']!=trial['reference_sha256'][view]:raise ValueError('Registered reference mismatch')
    instance=api.get('/api/instance')
    if instance.get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong Jarvis instance')
    install_client(api.ORIGIN,DATA)
    path=folder/'priority-review.json'
    state=load(path) if path.exists() else {'schema':'jarvis.character.priority-review.v1','asset_id':asset,
        'candidate':candidate,'manifest_sha256':manifest_hash,'priority_sha256':priority_hash,'views':{},
        'status':'STARTED','max_calls':4,'automatic_promotion':False,'user_approval':False,
        'source':'User-provided FBX plus first-party manual modifications; not independently reconstructed'}
    if state['asset_id']!=asset or state['candidate']!=candidate or state['manifest_sha256']!=manifest_hash or state['priority_sha256']!=priority_hash:
        raise ValueError('Existing review evidence or priorities differ')
    save(path,state)
    for view in VIEWS:
        StopGate(DATA).require_running()
        if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
        if sha(folder/'manifest.json')!=manifest_hash:raise ValueError('Candidate manifest changed')
        render_view=RENDER_FOR_REFERENCE[view]
        img=folder/('view-'+render_view+'.png'); expected=manifest['files'][img.name]
        if sha(img)!=expected:raise ValueError('Render changed')
        row=state['views'].setdefault(view,{'status':'CREATED','render_sha256':expected,'candidate_render_view':render_view})
        if row.get('render_sha256')!=expected or row.get('candidate_render_view')!=render_view:raise ValueError('Review image or view mapping mismatch')
        if row['status']=='SUCCEEDED':continue
        if row['status'] in ('SUBMITTING','UNKNOWN','FAILED','CANCELLED'):
            raise RuntimeError('Existing review requires inspection, no automatic replay: '+view)
        if 'render_id' not in row:
            row['render_id']=api.upload(img,'人物形体脸发重点复核 '+view);save(path,state)
        registered,_=reference_record(DATA,row['render_id'])
        if registered['sha256']!=expected:raise ValueError('Registered image differs')
        if 'chat_id' not in row:
            row['chat_id']=api.post('/api/chats',{'project_id':trial['project_id']})['id']
            api.post('/api/chat/update',{'id':row['chat_id'],'patch':{'title':'人物重点复核 · '+view}})
            row['request_id']='character-priority-'+uuid.uuid4().hex;save(path,state)
        prompt=('用户要求优先关注这个人物的形体、人体曲线、脸部和头发细节。'
            '用户进一步指出上一版下身太宽、肩膀太窄、头发像少量片状且材质不达要求；本轮请特别核查这些问题。'
            '第一张为用户 '+view+' 参考，第二张为现有用户 FBX 派生并由作者手工修改的实际渲染。'
            '逐项比较可见的身体轮廓和连接、脸型与眼神、刘海侧发后发，明确哪些被遮挡；'
            '不能把相机或光照差异直接断言为几何事实。不要称已还原、已验收或自主从图生成，不输出代码。'
            '只列最多五个有证据的缺口，说明如何通过真实渲染确认。任务专属要求：'+json.dumps(priorities,ensure_ascii=False))
        signature=digest({'text':prompt,'images':[trial['reference_ids'][view],row['render_id']],'route':trial['route']})
        if row.get('signature') and row['signature']!=signature:raise ValueError('Request context changed')
        if row['status']=='CREATED':
            row.update(status='SUBMITTING',signature=signature,known_usd=None);save(path,state)
            body={'chat_id':row['chat_id'],'request_id':row['request_id'],'text':prompt,**trial['route'],
                  'reasoning':'default','skill':'none','memory_enabled':False,
                  'reference_images':[trial['reference_ids'][view],row['render_id']]}
            try:row['accepted']=api.post('/api/chat/send',body)
            except BaseException as exc:
                row.update(status='UNKNOWN',error=str(exc));save(path,state);raise
            row['status']='ACCEPTED';save(path,state)
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            StopGate(DATA).require_running();chat=api.get('/api/chats/'+row['chat_id'])
            turn=next((t for t in chat['turns'] if t['id']==row['request_id']),None)
            if turn and turn['status'] not in ('READY','RUNNING'):
                row.update(status=turn['status'],reply=turn.get('reply'),error=turn.get('error'))
                try:
                    usage=[u for u in api.get('/api/usage') if u.get('turn_id')==row['request_id']]
                    amounts=[(u.get('billing') or {}).get('amount') for u in usage]
                    if usage and all(type(x) in (int,float) for x in amounts):row['known_usd']=sum(amounts)
                except Exception:pass
                save(path,state)
                if row['status']!='SUCCEEDED':raise RuntimeError('Review did not succeed: '+view)
                break
            time.sleep(1)
        else:
            row.update(status='UNKNOWN',error='Observation deadline; do not automatically resubmit');save(path,state)
            raise TimeoutError('Review outcome unknown: '+view)
    record(DATA,family=FAMILY,asset_id=asset,iteration=candidate+'-priorities',evidence_sha256=manifest_hash,
           reviews={v:state['views'][v]['reply'] for v in VIEWS})
    state.update(status='REVIEWED',complete_views=list(VIEWS));save(path,state)
    status_path=ASSET/'metadata/priority-refinement.json'
    if status_path.is_file():
        status=load(status_path)
        if status.get('output')==str(folder) and status.get('manifest_sha256')==manifest_hash:
            status.update(status='REVIEWED_AWAITING_USER',review_sha256=sha(path),user_approval=False)
            save(status_path,status)
    return state


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args()
    path=ASSET/'metadata/iteration-controller.lock'
    with path.open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:state=run(a.candidate);print(json.dumps({'status':state['status'],'views':state['complete_views']},ensure_ascii=False),flush=True)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':main()
