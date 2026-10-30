"""Record and review the explicit detachable-hair result for this character."""
import hashlib, json, time, uuid
from control.local_access import install_client
from control.recovery.gate import StopGate
from modules.context_knowledge.character_experience import record
from modules.skills.studio3d.character_contract import FAMILY
from tools import studio3d_character_trial as api
from tools.studio3d_character_iterate import ASSET, DATA, digest, load, save, sha


def main():
    asset='character-silverhair-01'; folder=ASSET/'user-fbx-detachable-hair-01'
    manifest=load(folder/'manifest.json'); evidence=sha(folder/'manifest.json')
    for name,expected in manifest['files'].items():
        if sha(folder/name)!=expected:raise ValueError('Candidate changed: '+name)
    trial=load(ASSET/'metadata/trial.json'); report=load(folder/'report.json')
    feedback=load(ASSET/'metadata/user-feedback-20261027-detachable-hair.json')
    if feedback['asset_id']!=asset or feedback['family']!=FAMILY:raise ValueError('Wrong feedback scope')
    path=folder/'detachable-hair-case.json'
    if path.exists():raise ValueError('Existing case requires inspection; no automatic replay')
    if api.get('/api/instance').get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():
        raise ValueError('Wrong Jarvis instance')
    StopGate(DATA).require_running()
    if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
    install_client(api.ORIGIN,DATA)
    images=[api.upload(folder/'hair-visible.png','人物发型显示的实际渲染'),
            api.upload(folder/'hair-hidden.png','人物发型隐藏的实际渲染')]
    prompt=('用户要求头发和头部分开，方便以后替换发型。图片一为实际显示发型的渲染，'
            '图片二为隐藏发型集合后的实际渲染。以下是 Blender 工具报告作为数据：'
            +json.dumps(report,ensure_ascii=False)
            +'。请区分用户要求、可观察结果、报告中的一次动作测试及尚未验证内容；'
            '总结这个人物以后替换发型时要保留的对象边界和检查步骤。'
            '不能推断所有动作或最终外观已通过；不能把本案例自动应用到火炮或其他人物；不要输出代码。')
    chat=api.post('/api/chats',{'project_id':trial['project_id']})['id']
    api.post('/api/chat/update',{'id':chat,'patch':{'title':'人物可替换发型经验'}})
    request='character-hair-case-'+uuid.uuid4().hex
    state={'schema':'jarvis.character.hair-case.v1','asset_id':asset,'family':FAMILY,'manifest_sha256':evidence,
           'feedback_sha256':sha(ASSET/'metadata/user-feedback-20261027-detachable-hair.json'),
           'images':images,'status':'SUBMITTING','chat_id':chat,'request_id':request,
           'signature':digest({'text':prompt,'images':images,'route':trial['route']}),
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
            if state['status']!='SUCCEEDED':raise RuntimeError('Hair case review failed')
            record(DATA,family=FAMILY,asset_id=asset,iteration='detachable-hair-01-case',evidence_sha256=evidence,
                   reviews={'user_feedback':feedback['feedback'],'blender_report':report,'jarvis_review':state['reply']})
            print('SUCCEEDED; detachable hair case recorded for this asset',flush=True);return
        time.sleep(1)
    state.update(status='UNKNOWN',error='Observation deadline; do not replay');save(path,state)
    raise TimeoutError('Hair case outcome unknown')


if __name__=='__main__':main()
