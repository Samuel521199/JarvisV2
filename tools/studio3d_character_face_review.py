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
 folder=ASSET/'user-fbx-face-study-01';manifest=load(folder/'manifest.json');evidence=sha(folder/'manifest.json')
 for name,expected in manifest['files'].items():
  if sha(folder/name)!=expected:raise ValueError('Candidate changed: '+name)
 trial=load(ASSET/'metadata/trial.json');ref=DATA/'artifacts/studio3d-character/reference-face-crop.png';render=folder/'head-front.png'
 path=folder/'face-review.json'
 if path.exists():raise ValueError('Existing review requires inspection')
 if api.get('/api/instance').get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong Jarvis instance')
 StopGate(DATA).require_running()
 if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
 install_client(api.ORIGIN,DATA)
 reference_hash=sha(ref);image_hash=sha(render)
 images=[api.upload(ref,'人物原参考图的脸部裁剪'),api.upload(render,'人物脸部正交实际渲染')]
 if sha(ref)!=reference_hash or sha(render)!=image_hash:raise ValueError('Images changed during upload')
 prompt=('第一张是用户提供的参考正面脸部裁剪，第二张是现有用户 FBX 手工修改的 Blender 正面实际渲染。'
         '渲染使用正交相机，不能推测成透视镜头。两图取景与光照不同。'
         '请重点比较可见眼形、眼角、脸轮廓、嘴和刘海，明确已知与看不出的项目，'
         '列出最多三项可通过实际建模与多视图验证的差距；不要声称已还原或输出代码。')
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
   record(DATA,family=FAMILY,asset_id='character-silverhair-01',iteration='user-fbx-face-study-01-review',evidence_sha256=evidence,
          reviews={'visual_hypotheses':state['reply'],'source':'reference crop and orthographic Blender render','not_verified':True})
   print('SUCCEEDED: face review saved',flush=True);return
  time.sleep(1)
 state.update(status='UNKNOWN',error='Observation deadline; do not replay');save(path,state)
 raise TimeoutError('Face review outcome unknown')

if __name__=='__main__':main()
