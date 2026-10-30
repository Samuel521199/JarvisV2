"""Bounded, restart-observable character production and four-view review.

All modelling is performed by a fixed first-party scene recipe and worker.
The model may suggest numeric contract values only; returned code is never run.
"""
import argparse
import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from control.local_access import install_client
from control.recovery.gate import StopGate
from host.studio3d_learning import _process, validate_export
from host.studio3d_reference import record as reference_record
from modules.context_knowledge.character_experience import methods, record
from modules.skills.studio3d.character_contract import FAMILY, VIEWS, BOUNDS, patch, validate
from modules.skills.studio3d import character_recipe
from tools import studio3d_character_trial as api

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'user-data'
ASSET=ROOT/'3DModels/SilverHairCharacter'
MAX_CALLS=12
MAX_KNOWN_USD=1.0
UNKNOWN_RESERVE_USD=.10
PARAMETER_MEANINGS={'height':'整体比例缩放，不单独调整腿长','head_scale':'头部体块尺寸',
    'shoulder_scale':'躯干上部和肩位置的横向宽度','waist_scale':'腰部横向宽度',
    'hip_scale':'骨盆横向宽度','leg_scale':'大腿和小腿横截面粗细，不改变腿长',
    'arm_scale':'手臂横截面粗细','depth_scale':'躯干前后厚度',
    'eye_scale':'眼部宽高','hair_length':'后发体块长度','hair_volume':'头顶发壳前后及横向尺寸',
    'face_width':'头部体块宽度'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temp,path)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


class Iteration:
    def __init__(self):
        self.path=ASSET/'metadata/iteration-controller.json'
        self.trial=load(ASSET/'metadata/trial.json')
        self.contract=validate(load(ASSET/'metadata/contract.json'))
        if self.contract['family']!=FAMILY or self.trial['asset_id']!=self.contract['asset_id']:
            raise ValueError('Character project identity mismatch')
        for view in VIEWS:
            if sha(ASSET/'references'/f'{view}.png')!=self.contract['reference_sha256'][view]:
                raise ValueError('Frozen character reference changed: '+view)
            reference,_=reference_record(DATA,self.trial['reference_ids'][view])
            if reference['sha256']!=self.contract['reference_sha256'][view]:
                raise ValueError('Registered reference ID does not match frozen character image: '+view)
        self.state=load(self.path) if self.path.exists() else {'schema':'jarvis.character.iteration.v1','family':FAMILY,
            'asset_id':self.contract['asset_id'],'project_id':self.trial['project_id'],'route':self.trial['route'],
            'references':self.contract['reference_sha256'],'calls':{},'iterations':[],'status':'INITIALIZED',
            'max_model_calls':MAX_CALLS,'user_approval':False,'automatic_promotion':False,
            'known_usd_cap':MAX_KNOWN_USD,'unknown_call_reserve_usd':UNKNOWN_RESERVE_USD,
            'author_intervention':'Codex authored fixed recipe and controller; model is reviewer and bounded parameter planner.'}
        if (self.state['family']!=FAMILY or self.state['asset_id']!=self.contract['asset_id'] or
                self.state['project_id']!=self.trial['project_id'] or self.state['references']!=self.contract['reference_sha256']):
            raise ValueError('Character controller identity mismatch')
        instance=api.get('/api/instance')
        if instance.get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong Jarvis data root')
        install_client(api.ORIGIN,DATA)
        self.persist()

    def persist(self):
        self.state['updated_at']=time.time();save(self.path,self.state)

    def check(self):
        StopGate(DATA).require_running()
        if (ASSET/'metadata/STOP').exists():raise RuntimeError('Character STOP requested')
        for view in VIEWS:
            if sha(ASSET/'references'/f'{view}.png')!=self.contract['reference_sha256'][view]:raise ValueError('Character reference changed')

    def call(self,key,text,images):
        self.check()
        signature=digest({'text':text,'images':images,'route':self.state['route']})
        call=self.state['calls'].get(key)
        if call:
            if call['signature']!=signature:raise ValueError('Existing call has different inputs')
            if call['status']=='SUCCEEDED':return call['reply']
            if call['status'] in ('FAILED','UNKNOWN','CANCELLED'):raise RuntimeError('Retained call requires inspection: '+key)
        else:
            if len(self.state['calls'])>=MAX_CALLS:raise RuntimeError('Character model call budget reached')
            known=sum(c.get('known_usd') or 0 for c in self.state['calls'].values())
            unknown=sum(1 for c in self.state['calls'].values() if c.get('known_usd') is None)
            if known+(unknown+1)*UNKNOWN_RESERVE_USD>MAX_KNOWN_USD:
                raise RuntimeError('Character known cost plus unknown reserves reached budget')
            chat=api.post('/api/chats',{'project_id':self.state['project_id']})['id']
            api.post('/api/chat/update',{'id':chat,'patch':{'title':'人物建模 · '+key}})
            call={'status':'CREATED','chat_id':chat,'request_id':'character-'+uuid.uuid4().hex,
                  'signature':signature,'images':images,'created_at':time.time(),'known_usd':None,
                  'billing_note':'unknown until matching usage record; reservation is not a provider billing guarantee'}
            self.state['calls'][key]=call;self.persist()
            body={'chat_id':chat,'request_id':call['request_id'],'text':text,**self.state['route'],
                  'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':images}
            call['status']='SUBMITTING';self.persist()
            try:call['accepted']=api.post('/api/chat/send',body)
            except BaseException as e:
                call.update(status='UNKNOWN',error=str(e));self.persist();raise
            call['status']='ACCEPTED';self.persist()
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            self.check();chat=api.get('/api/chats/'+call['chat_id'])
            turn=next((t for t in chat['turns'] if t['id']==call['request_id']),None)
            if turn and turn['status'] not in ('READY','RUNNING'):
                call.update(status=turn['status'],reply=turn.get('reply'),error=turn.get('error'),finished_at=time.time())
                try:
                    usage=[r for r in api.get('/api/usage') if r.get('turn_id')==call['request_id']]
                    amounts=[(r.get('billing') or {}).get('amount') for r in usage]
                    call['usage']=[{'id':r.get('id'),'usage':r.get('usage'),'billing':r.get('billing')} for r in usage]
                    if usage and all(type(x) in (int,float) for x in amounts):call['known_usd']=sum(amounts)
                except Exception:
                    call['billing_note']='Usage lookup failed; actual cost remains unknown'
                self.persist()
                if call['status']!='SUCCEEDED':raise RuntimeError('Model call failed: '+key)
                return call['reply']
            time.sleep(1)
        call.update(status='UNKNOWN',error='Observation timeout; do not resubmit');self.persist()
        raise TimeoutError('Character call outcome unknown: '+key)

    def build(self,iteration):
        self.check();name=iteration['id'];out=ASSET/name
        if iteration.get('status')=='BUILDING':
            raise RuntimeError('Interrupted build outcome requires inspection; no replay')
        if iteration.get('status') in ('BUILT','REVIEWING','REVIEWED'):
            for name,sha256 in iteration['files'].items():
                if sha(out/name)!=sha256:raise ValueError('Retained output changed')
            return
        run=uuid.uuid4().hex;folder=DATA/'artifacts/studio3d-character'/run;folder.mkdir(parents=True)
        recipe=ROOT/'modules/skills/studio3d/character_recipe.py'
        source_hash=sha(recipe);scene=character_recipe.scene(iteration['parameters']);save(folder/'scene.json',scene)
        sources=['modules/skills/studio3d/character_recipe.py','modules/skills/studio3d/character_surface.py','modules/skills/studio3d/character_contract.py',
                 'modules/skills/studio3d/contract.py','apps/studio3d/character_worker.py',
                 'adapters/studio3d/worker.py','control/studio3d_lane.py']
        iteration.update(status='BUILDING',run_id=run,recipe_sha256=source_hash,scene_sha256=sha(folder/'scene.json'))
        iteration['source_sha256']={p:sha(ROOT/p) for p in sources}
        self.state['status']='BUILDING';self.persist()
        prepared=load(DATA/'optional/studio3d/prepared.json');exe=Path(prepared['executable'])
        if sha(exe)!=prepared['executable_sha256']:raise ValueError('Prepared Blender changed')
        _process(DATA,folder,exe,operation='character')
        if any(sha(ROOT/p)!=h for p,h in iteration['source_sha256'].items()):raise ValueError('Worker or recipe source changed during build')
        report=load(folder/'report.json')
        if not report['glb_roundtrip']['passed']:raise ValueError('GLB roundtrip failed')
        official=validate_export(folder/'model.glb');save(folder/'format-validation.json',official)
        if out.exists():raise ValueError('Candidate output already exists; do not overwrite')
        out.mkdir()
        for file in ['model.blend','model.glb','preview.png','report.json','format-validation.json','resource-lane.json']+['view-'+v+'.png' for v in VIEWS]:
            shutil.copyfile(folder/file,out/file)
        iteration['files']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
        save(out/'manifest.json',{'iteration':iteration['id'],'source_sha256':iteration['source_sha256'],'scene_sha256':iteration['scene_sha256'],
             'reference_sha256':self.contract['reference_sha256'],'files':iteration['files']})
        iteration.update(status='BUILT',manifest_sha256=sha(out/'manifest.json'));self.persist()

    def review(self,iteration):
        out=ASSET/iteration['id'];iteration['status']='REVIEWING';self.state['status']='REVIEWING';self.persist()
        reviews=iteration.setdefault('reviews',{});uploads=iteration.setdefault('render_ids',{})
        for view in VIEWS:
            self.check();render=out/('view-'+view+'.png')
            if sha(render)!=iteration['files'][render.name]:raise ValueError('Review rendering changed')
            if view not in uploads:
                uploads[view]=api.upload(render,'人物 '+iteration['id']+' 实际渲染 '+view);self.persist()
            registered,_=reference_record(DATA,uploads[view])
            if registered['sha256']!=iteration['files'][render.name]:raise ValueError('Registered rendering ID changed')
            previous_text,previous_source=self.prior_review(iteration,view)
            seeds=methods(FAMILY)
            applied={'catalog_sha256':sha(ROOT/'modules/skills/studio3d/character-methods.json'),
                     'method_ids':[m['id'] for m in seeds], 'prior_review_scope':'same asset candidate, not independently verified',
                     'prior_review_sha256':digest(previous_text) if previous_text else None,
                     'prior_review_source':previous_source}
            iteration.setdefault('knowledge_used',{})[view]=applied;self.persist()
            prompt=('你负责风格化人物三维资产的视觉核验。第一张是用户提供的'+view+'参考，第二张是本轮真实 Blender 正交渲染。'
                    '请只比较可见轮廓、比例、姿势、手足、头发、面部与身体连接；区分遮挡、光照和相机问题。'
                    '指出严重错误与具体可核验之处。不得把渲染或格式通过说成用户验收。不要输出代码。'
                    '以下方法为人工种子，仅供适用时参考：'+json.dumps(seeds,ensure_ascii=False)+
                    '。以下是同一资产早期审查意见，可能出错，必须以本次图像重新核对：'+previous_text[:2500])
            reviews[view]=self.call(iteration['id']+'-'+view,prompt,[self.trial['reference_ids'][view],uploads[view]])
            self.persist()
        save(out/'reviews.json',reviews)
        self.check()
        if sha(out/'manifest.json')!=iteration['manifest_sha256'] or any(sha(out/n)!=h for n,h in iteration['files'].items()):
            raise ValueError('Evidence changed before recording candidate')
        record(DATA,family=FAMILY,asset_id=self.state['asset_id'],iteration=iteration['id'],
               evidence_sha256=iteration['manifest_sha256'],reviews=reviews)
        iteration['status']='REVIEWED';self.state['status']='REVIEWED';self.persist()

    def prior_review(self,iteration,view):
        source=iteration.get('source_iteration')
        if source:
            prior=next((x for x in self.state['iterations'] if x['id']==source),None)
            if not prior or prior.get('status')!='REVIEWED' or view not in prior.get('reviews',{}):
                raise ValueError('Preceding character review missing: '+view)
            reviews_path=ASSET/source/'reviews.json'
            reviews=load(reviews_path)
            if reviews!=prior['reviews'] or sha(ASSET/source/'manifest.json')!=prior['manifest_sha256']:
                raise ValueError('Preceding character review evidence changed')
            return reviews[view],{'kind':'preceding_iteration','iteration':source,'reviews_sha256':sha(reviews_path),'manifest_sha256':prior['manifest_sha256']}
        previous=self.trial.get('reviews',{}).get(view,{})
        text=previous.get('reply','') if isinstance(previous,dict) else ''
        if text:return text,{'kind':'initial_blockout_review','trial_sha256':sha(ASSET/'metadata/trial.json')}
        path=ASSET/'metadata/intake-rear-left.json'
        if view in ('rear','left') and path.is_file():
            data=load(path)
            if data.get('status')!='SUCCEEDED' or any(data.get('source_sha256',{}).get(v)!=self.contract['reference_sha256'][v] for v in ('rear','left')):
                raise ValueError('Initial character reference analysis identity mismatch')
            replies=[r.get('reply','') for r in data.get('model_calls',[]) if isinstance(r.get('reply'),str)]
            return '\n'.join(replies),{'kind':'initial_reference_analysis','views':['rear','left'],'sha256':sha(path)}
        return '',None

    def plan(self,iteration):
        prompt=('根据下面四视图的人物审查，选择最多4个数值参数做小幅修正。只输出JSON对象，格式 '
                '{"updates":{"head_scale":1.02},"reason":"..."}；如无法用参数改善则updates为空。'
                '只允许这些数值参数和当前值：'+json.dumps({k:iteration['parameters'][k] for k in BOUNDS},ensure_ascii=False)+
                '。参数真实作用（不得把粗细当作长度）：'+json.dumps(PARAMETER_MEANINGS,ensure_ascii=False)+
                '。单次数值变化绝对值不能超过0.08，且所有参数必须在既有范围内。不可输出代码。审查：'+
                json.dumps(iteration['reviews'],ensure_ascii=False)[:7000])
        # Existing transport requires at least one image in this workflow; use
        # the front reference, not unrelated project content.
        raw=self.call(iteration['id']+'-plan',prompt,[self.trial['reference_ids']['front']])
        raw=raw.strip()
        if raw.startswith('```'):
            raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        candidate=json.loads(raw)
        if not isinstance(candidate,dict) or set(candidate)!={'updates','reason'} or not isinstance(candidate['reason'],str):
            raise ValueError('Invalid bounded character plan')
        if not isinstance(candidate['updates'],dict) or set(candidate['updates'])-set(BOUNDS):
            raise ValueError('Only bounded numeric character parameters are allowed')
        updated=patch(iteration['parameters'],candidate['updates'])
        save(ASSET/iteration['id']/'plan.json',{'model_output':candidate,'accepted_parameters':updated,'scope':'candidate only'})
        return updated

    def run(self,rounds):
        if not self.state['iterations']:
            self.state['iterations'].append({'id':'character-r02','parameters':self.contract['parameters'],'status':'CREATED'})
            self.persist()
        for idx in range(rounds):
            if idx>=len(self.state['iterations']):break
            item=self.state['iterations'][idx];self.build(item);self.review(item)
            if idx+1<rounds and idx+1>=len(self.state['iterations']):
                try:params=self.plan(item)
                except (ValueError,json.JSONDecodeError) as exc:
                    item['plan_error']=str(exc);self.state['status']='STALLED_INVALID_PLAN';self.persist();break
                if params==item['parameters']:
                    self.state['status']='STALLED_NO_BOUNDED_CHANGE';self.persist();break
                self.state['iterations'].append({'id':'character-r%02d'%(idx+3),'parameters':params,'status':'CREATED','source_iteration':item['id']});self.persist()
        if self.state['status']=='REVIEWED':self.state['status']='ROUND_LIMIT_REACHED';self.persist()
        return self.state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--rounds',type=int,default=1);args=parser.parse_args()
    if args.rounds not in (1,2):raise ValueError('Choose one or two bounded iterations')
    path=ASSET/'metadata/iteration-controller.lock';path.parent.mkdir(parents=True,exist_ok=True)
    import msvcrt
    with path.open('a+b') as lock:
        if not path.stat().st_size:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        driver=Iteration()
        try:
            state=driver.run(args.rounds)
            print(json.dumps({'status':state['status'],'iterations':[(i['id'],i['status']) for i in state['iterations']]},ensure_ascii=False),flush=True)
        except BaseException as exc:
            driver.state.update(status='INTERRUPTED_OR_FAILED',error=str(exc));driver.persist();raise

if __name__=='__main__':main()
