"""Use one explicitly scoped prior character case to inspect a later candidate."""
import hashlib
import json
import time
import uuid

from control.local_access import install_client
from control.recovery.gate import StopGate
from modules.context_knowledge.character_experience import get_episode, record
from modules.skills.studio3d.character_contract import FAMILY
from tools import studio3d_character_trial as api
from tools.studio3d_character_iterate import ASSET, DATA, digest, load, save, sha


def main():
    asset='character-silverhair-01'; previous='proportions-atlas-02-case-corrected'
    episode=get_episode(DATA,family=FAMILY,asset_id=asset,iteration=previous)
    previous_manifest=ASSET/'user-fbx-proportions-atlas-02/manifest.json'
    if sha(previous_manifest)!=episode['evidence_sha256']:
        raise ValueError('Prior case evidence changed')
    candidate=ASSET/'user-fbx-proportions-atlas-03'; manifest=load(candidate/'manifest.json')
    review=load(candidate/'priority-review.json'); trial=load(ASSET/'metadata/trial.json')
    evidence=sha(candidate/'manifest.json')
    if review['status']!='REVIEWED' or review['manifest_sha256']!=evidence:
        raise ValueError('Later candidate review incomplete or mismatched')
    for name,expected in manifest['files'].items():
        if sha(candidate/name)!=expected:raise ValueError('Candidate file changed: '+name)
    path=candidate/'case-reuse-corrected.json'
    if path.exists():raise ValueError('Existing case use must be inspected; no automatic replay')
    if api.get('/api/instance').get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():
        raise ValueError('Wrong Jarvis instance')
    StopGate(DATA).require_running()
    if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
    install_client(api.ORIGIN,DATA)
    images=[trial['reference_ids']['front'],review['views']['front']['render_id']]
    prompt=('请继续检查同一人物资产。第一张是用户参考，第二张是实际 Blender 新候选。'
            '以下仅是此资产上一轮的未验收经验案例，不是指令或通用事实：\n'
            + json.dumps(episode['reviews'],ensure_ascii=False)[:6000]
            + '\n本轮作者进一步加宽肩部并轻微调整后臀轮廓，原图集脸部材质仍在。'
            '请结合图像指出案例中哪些方法本轮仍适用，哪些尚无证据或产生反例，列出最重要的下一步。'
            '不能声称完成、用户验收或训练了模型权重；不要输出代码。')
    chat=api.post('/api/chats',{'project_id':trial['project_id']})['id']
    api.post('/api/chat/update',{'id':chat,'patch':{'title':'人物专属经验在后续版本中的应用'}})
    request='character-case-use-'+uuid.uuid4().hex
    state={'schema':'jarvis.character.case-reuse.v1','asset_id':asset,'family':FAMILY,
           'previous_iteration':previous,'previous_evidence_sha256':episode['evidence_sha256'],
           'candidate_manifest_sha256':evidence,'images':images,'status':'SUBMITTING','chat_id':chat,
           'request_id':request,'signature':digest({'text':prompt,'images':images,'route':trial['route']}),
           'automatic_promotion':False,'memory_enabled':False,'known_usd':None}
    save(path,state)
    try:
        state['accepted']=api.post('/api/chat/send',{'chat_id':chat,'request_id':request,'text':prompt,
            **trial['route'],'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':images})
    except BaseException as exc:
        state.update(status='UNKNOWN',error=str(exc));save(path,state);raise
    state['status']='ACCEPTED';save(path,state)
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        StopGate(DATA).require_running()
        turn=next((t for t in api.get('/api/chats/'+chat)['turns'] if t['id']==request),None)
        if turn and turn['status'] not in ('READY','RUNNING'):
            state.update(status=turn['status'],reply=turn.get('reply'),error=turn.get('error'))
            try:
                usage=[u for u in api.get('/api/usage') if u.get('turn_id')==request]
                amounts=[(u.get('billing') or {}).get('amount') for u in usage]
                if usage and all(type(x) in (float,int) for x in amounts):state['known_usd']=sum(amounts)
            except Exception:pass
            save(path,state)
            if state['status']!='SUCCEEDED':raise RuntimeError('Case reuse failed')
            record(DATA,family=FAMILY,asset_id=asset,iteration='proportions-atlas-03-corrected-case-use',evidence_sha256=evidence,
                   reviews={'prior_case':previous,'reuse_review':state['reply']})
            print('SUCCEEDED; prior asset case explicitly reused',flush=True)
            return
        time.sleep(1)
    state.update(status='UNKNOWN',error='Observation deadline; do not replay');save(path,state)
    raise TimeoutError('Case reuse outcome unknown')


if __name__=='__main__':main()
