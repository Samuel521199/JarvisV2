"""Ask Jarvis to inspect one actual head render against the cropped reference."""
import hashlib,time,uuid
from pathlib import Path
from control.local_access import install_client
from control.recovery.gate import StopGate
from modules.context_knowledge.character_experience import record
from modules.skills.studio3d.character_contract import FAMILY
from tools import studio3d_character_trial as api
from tools.studio3d_character_iterate import ASSET,DATA,digest,load,save,sha

def main():
 folder=DATA/'artifacts/studio3d-character/face-proportion-design-study-04';evidence=sha(folder/'candidate.blend')
 trial=load(ASSET/'metadata/trial.json');ref=folder/'reference-side-crop.png';render=folder/'bald-side-mirrored.png'
 path=folder/'face-review-side.json'
 if path.exists():raise ValueError('Existing review requires inspection')
 if api.get('/api/instance').get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong Jarvis instance')
 StopGate(DATA).require_running()
 if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
 install_client(api.ORIGIN,DATA)
 reference_hash=sha(ref);image_hash=sha(render)
 images=[api.upload(ref,'用户新增人物眼睛与脸型参考正面裁剪'),api.upload(render,'人物脸部正交实际渲染')]
 if sha(ref)!=reference_hash or sha(render)!=image_hash:raise ValueError('Images changed during upload')
 prompt=('第一张是用户人物设计图的模型正交侧面与概念侧面；第二张是根据用户FBX派生的Blender正交实渲，已水平镜像以对齐朝向。'
         '概念图不是三维渲染，两张取景、光照和视角可能不同。请比较可见的头颅、眼睑睫毛、鼻嘴侧轮廓和颌部，并指出无法判断的部分。最多列三项可验证的差距，不要声称还原。')
 chat=api.post('/api/chats',{'project_id':trial['project_id']})['id'];api.post('/api/chat/update',{'id':chat,'patch':{'title':'人物脸部对照'}})
 request='character-face-review-'+uuid.uuid4().hex
 state={'schema':'jarvis.character.face-review.v1','asset_id':'character-silverhair-01','candidate_manifest_sha256':evidence,
        'reference_crop_sha256':reference_hash,'render_sha256':image_hash,'images':images,'status':'SUBMITTING',
        'chat_id':chat,'request_id':request,'signature':digest({'text':prompt,'images':images,'route':trial['route']}),
        'automatic_promotion':False,'memory_enabled':False,'known_usd':None}
 save(path,state)
 try:state['accepted']=api.post('/api/chat/send',{'chat_id':chat,'request_id':request,'text':prompt,**trial['route'],
          'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':images})
 except BaseException as exc:state.update(status='UNKNOWN',error=str(exc));save(path,state);raise
 state['status']='ACCEPTED';save(path,state);deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  StopGate(DATA).require_running();turn=next((t for t in api.get('/api/chats/'+chat)['turns'] if t['id']==request),None)
  if turn and turn['status'] not in ('READY','RUNNING'):
   state.update(status=turn['status'],reply=turn.get('reply'),error=turn.get('error'))
   try:
    usage=[u for u in api.get('/api/usage') if u.get('turn_id')==request];amounts=[(u.get('billing') or {}).get('amount') for u in usage]
    if usage and all(type(x) in (float,int) for x in amounts):state['known_usd']=sum(amounts)
   except Exception:pass
   save(path,state)
   if state['status']!='SUCCEEDED':raise RuntimeError('Face review failed')
   record(DATA,family=FAMILY,asset_id='character-silverhair-01',iteration='face-proportion-design-study-04-side-review',evidence_sha256=evidence,
          reviews={'visual_hypotheses':state['reply'],'source':'reference crop and orthographic Blender render','not_verified':True})
   print('SUCCEEDED: face review saved',flush=True);return
  time.sleep(1)
 state.update(status='UNKNOWN',error='Observation deadline; do not replay');save(path,state)
 raise TimeoutError('Face review outcome unknown')

if __name__=='__main__':main()
