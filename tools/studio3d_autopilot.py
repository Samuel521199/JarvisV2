"""Persistent bounded Jarvis reference -> recipe -> Blender -> review -> repair loop.

Run: python -m tools.studio3d_autopilot --asset-root 3DModels/PaK38 --rounds 3
Existing model requests/jobs are observed, never blindly replayed. Every turn
uses Jarvis's configured dialogue provider. All state and candidates stay local.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid
from pathlib import Path
from modules.skills.studio3d import artillery_recipe as recipe
from modules.skills.studio3d.production_loop import VERSION, digest, decode, validate_patch, patch_prompt, adoption, candidate_lesson, repair_focus
from modules.skills.studio3d.hard_surface_review import VIEWS, prompt, parse, review_gate
from modules.skills.studio3d.review_evidence import candidate_manifest, verify_manifest
from modules.context_knowledge.studio3d_experience import Studio3DExperience
from modules.skills.studio3d.learning_contract import context
from modules.skills.studio3d import paired_review
from modules.skills.studio3d.production_recovery import new_request_allowed,quarantined,RESERVE_USD

ROOT=Path(__file__).resolve().parents[1]


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Driver:
    def __init__(self,asset,origin,rounds,inspection=False,resume=False):
        endpoint=urlsplit(origin)
        if endpoint.scheme!='http' or endpoint.hostname!='127.0.0.1' or endpoint.path not in ('','/') or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:raise ValueError('Use verified local Jarvis origin')
        self.asset=asset.resolve();self.folder=self.asset/'metadata/autopilot';self.folder.mkdir(parents=True,exist_ok=True)
        self.origin=origin;self.path=self.folder/'state.json';self.rounds=rounds;self.use_inspection=inspection
        instance=self.get('/api/instance')
        expected=hashlib.sha256(str((ROOT/'user-data').resolve()).casefold().encode()).hexdigest()
        if instance.get('service')!='jarvis-workbench' or instance.get('root_digest')!=expected:raise ValueError('Wrong Jarvis data root')
        from control.local_access import install_client
        install_client(origin,ROOT/'user-data')
        if not str(self.asset).lower().startswith(str((ROOT/'3DModels').resolve()).lower()+os.sep):raise ValueError('Use project 3DModels asset folder')
        self.policy={'shield':'curved_double','notes':'PaK38: established low curved double sheet shield; no leFH18 folded shield rule. One weapon-left slot. Ignore top duplicate opposite slot and top-facing brake ports; side references govern those. Exclude unsupported rear pipe from right image. Keep the deployed split-trail pose established by rear/top; side-view overlap does not prove folded trails. Generated views are not calibrated; distinguish camera mismatch from geometry.'}
        feedback=self.asset/'metadata/user-feedback-detail-20261027.json'
        if feedback.exists():
            note=load(feedback)
            if note.get('classification')!='user_visual_feedback' or note.get('user_feedback')!='细节太少了':raise ValueError('Unexpected user feedback record')
            self.policy['notes']+=' User reviewed r18 and reports insufficient details. Prioritize reference-visible wheel disc/hub, attached control housings, breech exterior and trail/spade fittings; make only evidence-supported changes, avoid invented mechanics.'
        self.state=load(self.path) if self.path.exists() else {'schema':1,'version':VERSION,'created_at':now(),'status':'INITIALIZED','calls':{},'uploads':{},'iterations':[],
            'current_parameters':recipe.parameters(),'best_iteration':None,'author_interventions':[{'kind':'tool_and_recipe_implementation','author':'Codex','scope':'Original parameterized exterior recipe and controller authored before independent trial; not learned autonomously'}],
            'references':{v:{'path':'reference-'+v+'.png','sha256':sha(self.asset/('reference-'+v+'.png'))} for v in VIEWS},'policy':self.policy,'user_approval':False,'lod_authorized':False,'global_experience_promotion':False}
        if feedback.exists():self.state['user_feedback_context']={'path':str(feedback.relative_to(self.asset)),'sha256':sha(feedback),'scope':'user visual critique and tentative regions; not user approval'}
        self.use_inspection=inspection or self.state.get('inspection_enabled',False)
        self.state['inspection_enabled']=self.use_inspection
        self.state['controller_version']=VERSION
        if resume and self.state['status'] in ('ROUND_LIMIT_REACHED','STALLED_RETAINED_BEST'):
            self.state.setdefault('continuations',[]).append({'at':now(),'prior_status':self.state['status'],'reason':'Authorized bounded production continuation; request and USD caps unchanged'})
            self.state['status']='CONTINUING'
        for v,r in self.state['references'].items():
            if sha(self.asset/r['path'])!=r['sha256']:raise ValueError('Frozen reference changed: '+v)
        self.state['policy']=self.policy;self.persist()
        if 'native_references' not in self.state:
            self.state['native_references']={v:{'path':str(self.asset/'metadata/native'/('reference-right-v1.png' if v=='right' else 'reference-'+v+'.png'))} for v in VIEWS}
            for row in self.state['native_references'].values():row['sha256']=sha(row['path'])
        for row in self.state['native_references'].values():
            if sha(row['path'])!=row['sha256']:raise ValueError('Native reference changed')
        self.source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'tools/studio3d_inspection_review.py',ROOT/'adapters/studio3d/worker.py',ROOT/'adapters/studio3d/weathering.py',*[ROOT/'modules/skills/studio3d'/name for name in ('artillery_recipe.py','assembly_geometry.py','assembly_frames.py','exterior_details.py','trail_details.py','production_loop.py','reference_policy.py','paired_review.py','semantic_patch.py','production_receipt.py','render_inspection.py','production_recovery.py','export_materials.py')]]}
        self.persist()
        settings=self.get('/api/snapshot')['settings']
        if 'route' not in self.state:
            c=next(c for c in settings['connections'] if c['id']==settings['default_provider']);self.state['route']={'provider':c['id'],'model':c['model']};self.persist()
        store=Studio3DExperience(ROOT/'user-data')
        try:self.methods=store.retrieve(context(load(self.asset/'metadata/learning-contract-intake.json')))['methods']
        finally:store.close()
        self.state['retrieved_methods']=[{'id':m['id'],'revision':m['revision']} for m in self.methods];self.persist()

    def persist(self):
        self.state['updated_at']=now();save(self.path,self.state)

    def check_stop(self):
        if (self.folder/'STOP').exists():raise RuntimeError('Asset STOP requested')

    def get(self,path):
        with urllib.request.urlopen(self.origin+path,timeout=25) as r:return json.load(r)

    def post(self,path,body):
        self.check_stop();token=self.get('/api/session')['token']
        req=urllib.request.Request(self.origin+path,json.dumps(body,ensure_ascii=False).encode(),{'Content-Type':'application/json','Origin':self.origin,'X-Jarvis-Token':token})
        try:
            with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
        except urllib.error.HTTPError as e:raise RuntimeError('HTTP '+str(e.code)+': '+e.read(2000).decode(errors='replace')) from e

    def upload(self,path,label):
        raw=path.read_bytes();h=hashlib.sha256(raw).hexdigest()
        if h in self.state['uploads']:return self.state['uploads'][h]['id']
        row=self.post('/api/studio3d/references',{'name':label[:100],'source':'PaK38 bounded production reference/render; metadata/autopilot evidence','license':'User project visual evidence','data':base64.b64encode(raw).decode()})
        self.state['uploads'][h]={'id':row['id'],'path':str(path),'sha256':h};self.persist();return row['id']

    def call(self,key,text,images=()):
        if len(images)>2 or len(text)>12000:raise ValueError('Model request exceeds existing shared context/image transport contract')
        self.check_stop();calls=self.state['calls'];signature=digest({'text':text,'images':list(images),'route':self.state['route']})
        row=calls.get(key)
        if row:
            if row['signature']!=signature:raise ValueError('Existing model request input changed: '+key)
            if row['status']=='SUCCEEDED':return row['reply']
            if row['status'] in ('FAILED','CANCELLED','UNKNOWN','REJECTED_BEFORE_INVOCATION'):raise RuntimeError('Retained terminal model request: '+key+' '+row['status'])
        else:
            new_request_allowed(calls,signature)
            if len(calls)>=400:raise RuntimeError('Trial 400-call cap reached')
            known_cost=sum((u.get('billing') or {}).get('amount') or 0 for c in calls.values() for u in c.get('usage',[]))
            reserve=sum(RESERVE_USD for c in calls.values() if quarantined(c))
            if known_cost+reserve>=5:raise RuntimeError('Trial $5 known estimate plus unresolved-call reserve cap reached')
            chat=self.post('/api/chats',{})['id'];self.post('/api/chat/update',{'id':chat,'patch':{'title':'PaK38 autonomous '+key}})
            row={'chat_id':chat,'request_id':'pak38-loop-'+uuid.uuid4().hex,'signature':signature,'status':'CREATED','started_at':now(),'request':{'text':text,'images':list(images)},'usage':[]};calls[key]=row;self.persist()
            body={'chat_id':chat,'request_id':row['request_id'],'text':text,**self.state['route'],'reasoning':'default','skill':'none','memory_enabled':False}
            if images:body['reference_images']=list(images)
            row['status']='SUBMITTING';self.persist()
            try:row['accepted']=self.post('/api/chat/send',body)
            except BaseException as e:
                row['status']='UNKNOWN';row['error']=str(e);self.persist();raise
            self.persist()
        tick=time.monotonic()
        while time.monotonic()-tick<240:
            self.check_stop();chat=self.get('/api/chats/'+row['chat_id']);turn=next((t for t in chat['turns'] if t['id']==row['request_id']),None)
            if turn and turn['status'] not in ('READY','RUNNING'):
                row.update(status=turn['status'],reply=turn.get('reply'),error=turn.get('error'),finished_at=now(),observed_seconds=time.monotonic()-tick)
                row['usage']=[u for u in self.get('/api/usage') if u['turn_id']==row['request_id']];self.persist()
                if row['status']!='SUCCEEDED':raise RuntimeError(key+': '+row['status'])
                print(key+' SUCCEEDED',flush=True);return row['reply']
            time.sleep(1)
        row.update(status='UNKNOWN',error='Observation deadline; do not resubmit');self.persist();raise RuntimeError(key+' timed out')

    def front_intake(self):
        if self.state['calls'].get('front-intake',{}).get('status')=='SUCCEEDED':
            # Historical planning is retained as unverified advice. A changed
            # refinement policy does not require paying to repeat intake.
            return
        path=self.asset/'metadata/native/reference-front.png';ref=self.upload(path,'PaK38 final front intake')
        previous=load(self.asset/'metadata/jarvis-handoff.json')
        prior=[{'stage':s['stage'],'notes':s.get('reply','')[:2300]} for s in previous['stages'] if s['status']=='SUCCEEDED']
        brief='You are Jarvis preparing an exterior game-art model. Image is the FRONT view. Four other reference views have already been analyzed; their notes are unverified advice, not facts. Return JSON with checks (up to 10), conflicts, unverified. Do not invent hidden mechanics, tyre construction or rib count; no code. The host recipe is an initial artist-authored candidate, not proof of historical accuracy. '+json.dumps({'policy':self.policy,'prior':prior},ensure_ascii=False)
        result=self.call('front-intake',brief,[ref]);save(self.folder/'front-intake.json',{'reply':result,'status':'UNVERIFIED_PLANNING_ADVICE'})

    def build(self,it):
        folder=self.folder/it['id'];folder.mkdir(exist_ok=True);scene,semantic=recipe.build(it['parameters'])
        if it.get('source_iteration'):
            from modules.skills.studio3d.semantic_patch import merge
            prior=self.folder/it['source_iteration'];verify_manifest(load(prior/'evidence.json'))
            scene,semantic=merge(load(prior/'scene.json'),load(prior/'semantics.json'),scene,semantic,it['proposed_actions'])
        source_hash=digest(scene)
        if it.get('scene_digest') and it['scene_digest']!=source_hash:raise ValueError('Recipe/source changed during existing iteration')
        save(folder/'scene.json',scene);save(folder/'semantics.json',semantic);it['scene_digest']=source_hash;it['recipe_version']=recipe.VERSION
        if 'job_id' not in it:
            it.update(job_id=uuid.uuid4().hex,status='SUBMITTING',started_at=now(),recipe_source_sha256=self.source_hashes);self.persist()
            try:it['accepted']=self.post('/api/studio3d/jobs',{'id':it['job_id'],'scene':scene})
            except BaseException as e:it.update(status='UNKNOWN',error=str(e));self.persist();raise
            self.persist()
        deadline=time.monotonic()+370
        while time.monotonic()<deadline:
            self.check_stop();job=self.get('/api/studio3d/jobs/'+it['job_id']);it['status']=job['status'];it['phase']=job['phase'];self.persist()
            if job['status']=='DELIVERED':break
            if job['status'] in ('FAILED','UNKNOWN','CANCELLED'):
                save(folder/'job.json',job);raise RuntimeError('Native build '+job['status']+': '+str(job.get('error')))
            time.sleep(2)
        else:raise RuntimeError('Build observation deadline; inspect retained job')
        save(folder/'job.json',job);receipt=job['receipt'];it['native_elapsed_seconds']=receipt.get('report',{}).get('elapsed_seconds')
        for name in ('preview.png','model.blend','model.glb','report.json',*['view-'+v+'.png' for v in VIEWS]):
            row=receipt['files'][name];q=folder/name
            if not q.exists():
                with urllib.request.urlopen(self.origin+row['url'],timeout=60) as r:q.write_bytes(r.read())
            if sha(q)!=row['sha256']:raise ValueError('Export hash mismatch: '+name)
        report=load(folder/'report.json');it['native_elapsed_seconds']=report['elapsed_seconds'];it['triangles']=report['triangles']
        if not report['glb_roundtrip']['passed']:raise ValueError('GLB roundtrip failed')
        manifest=candidate_manifest(folder/'model.glb',{v:folder/('view-'+v+'.png') for v in VIEWS},iteration=it['id'],camera_settings=report.get('orthographic_views'))
        save(folder/'evidence.json',manifest);it['model_sha256']=manifest['model']['sha256'];it['finished_build_at']=now();self.persist()
        print(it['id']+' built '+str(it['triangles'])+' triangles',flush=True)

    def review(self,it):
        folder=self.folder/it['id'];evidence=load(folder/'evidence.json');verify_manifest(evidence)
        sem=load(folder/'semantics.json');reviews=[]
        facts={'reference_priority':self.policy['notes'],'candidate_wheel_ribs':it['parameters']['wheel_ribs'],'candidate_trail_pose':'deployed','semantic_groups':{k:[n for n,g in sem['groups'].items() if g==k] for k in sorted(set(sem['groups'].values()))},'constraints':'Fixed exterior recipe; inspect geometry; no claim of physical mechanism accuracy. Model units nominal. Counts describe candidate data, not proof of reference identity.'}
        for view in VIEWS:
            ref=self.asset/'metadata/native'/('reference-right-v1.png' if view=='right' else 'reference-'+view+'.png')
            if sha(ref)!=self.state['native_references'][view]['sha256']:raise ValueError('Reference changed during run')
            rend=folder/('view-'+view+'.png')
            if ref.stat().st_size+rend.stat().st_size>12*1024**2:raise ValueError('Pair exceeds image transport budget')
            ids=[self.upload(ref,'PaK38 '+view+' reference'),self.upload(rend,it['id']+' actual '+view)]
            text=prompt(view,it['id'],geometry_facts=facts,reference_policy=self.policy,methods=self.methods)
            audit=parse(self.call(it['id']+'-review-'+view,text,ids),view);audit['coverage']='full';reviews.append(audit)
            save(folder/'reviews.json',reviews)
        it['gate']=review_gate(reviews);it['status']='REVIEWED';self.persist();return reviews

    def deliver(self,it):
        folder=self.folder/it['id'];out=self.asset/'renders';out.mkdir(exist_ok=True)
        for src,dst in [('model.blend','PaK38-high.blend'),('model.glb','PaK38-high.glb')]:shutil.copy2(folder/src,self.asset/dst)
        for view in VIEWS:shutil.copy2(folder/('view-'+view+'.png'),out/(view+'.png'))
        shutil.copy2(folder/'preview.png',out/'preview.png')
        inspection=it.get('inspection')
        if inspection and inspection['status']=='REVIEWED':
            for view in VIEWS:
                source=ROOT/'user-data/artifacts/studio3d-inspection'/inspection['id']/('inspection-'+view+'.png')
                shutil.copy2(source,out/('inspection-'+view+'.png'))
        else:
            # Supplemental pictures from a different retained source must not
            # masquerade as the current model. Keep them in their evidence run.
            for obsolete in out.glob('inspection-*.png'):obsolete.unlink()
        save(self.asset/'metadata/current-model.json',{'iteration':it['id'],'job_id':it['job_id'],'model_sha256':sha(self.asset/'PaK38-high.glb'),'blend_sha256':sha(self.asset/'PaK38-high.blend'),'triangles':it['triangles'],'viewer':self.origin+'/api/studio3d/view/'+it['job_id'],'gate':it.get('gate'),'inspection':inspection,'status':self.state['status'],'user_approval':False,'lod_authorized':False,'limitations':['GLB base PBR differs from procedural Blender coating','Declared movement groups need rigging validation','Candidate exterior, not historical engineering reconstruction']})

    def compare(self,old,new):
        folders=[self.folder/it['id'] for it in (old,new)]
        for f in folders:verify_manifest(load(f/'evidence.json'))
        rows=[]
        for view in VIEWS:
            ref=Path(self.state['native_references'][view]['path'])
            sheet=folders[1]/('comparison-'+view+'.png')
            composition=paired_review.make_sheet(folders[0]/('view-'+view+'.png'),folders[1]/('view-'+view+'.png'),sheet)
            save(folders[1]/('comparison-'+view+'.json'),composition)
            paths=[ref,sheet]
            if sum(p.stat().st_size for p in paths)>12*1024**2:raise ValueError('Paired images exceed transport budget')
            ids=[self.upload(p,view+' '+label) for p,label in zip(paths,('reference','lossless before-after'))]
            raw=self.call(new['id']+'-compare-'+old['id']+'-'+view+'-sheet-v1',paired_review.prompt(view,new.get('proposed_actions',[]),self.policy),ids)
            rows.append(paired_review.parse(raw,view));save(folders[1]/'paired-reviews.json',rows)
        return paired_review.decide(rows)

    def run(self):
        if self.state['status'] in ('READY_FOR_USER_REVIEW','ROUND_LIMIT_REACHED','STALLED_RETAINED_BEST','UNSUPPORTED_REPAIR'):return
        if self.state.get('last_error'):
            self.state.setdefault('error_history',[]).append({'recorded_at':now(),'error':self.state.pop('last_error')})
        self.state['status']='RUNNING';self.persist()
        self.front_intake()
        pending=self.state.get('pending_iteration')
        if not pending:
            # Migrate an interrupted earlier controller without revisiting a rejected candidate.
            pending=next((x['id'] for x in reversed(self.state['iterations']) if x['status']!='REVIEWED'),None)
        ident=pending or self.state['best_iteration'] or 'r0'
        for number in range(self.rounds+1):
            self.check_stop()
            it=next((x for x in self.state['iterations'] if x['id']==ident),None)
            if not it:
                it={'id':ident,'parameters':dict(self.state['current_parameters']),'status':'CREATED','created_at':now()};self.state['iterations'].append(it);self.persist()
            folder=self.folder/ident
            if it['status']=='REVIEWED':
                # A reviewed artifact stays frozen across first-party recipe upgrades.
                # Do not rebuild it using new code or repeat its paid reviews.
                verify_manifest(load(folder/'evidence.json'))
                if sha(folder/'model.glb')!=it['model_sha256']:raise ValueError('Frozen artifact changed')
                reviews=load(folder/'reviews.json')
                if set(r['view'] for r in reviews)!=set(VIEWS):raise ValueError('Frozen review incomplete')
            else:
                self.build(it);reviews=self.review(it)
            best=next((x for x in self.state['iterations'] if x['id']==self.state['best_iteration']),None)
            if best and best['id']!=ident:
                before=load(self.folder/best['id']/'reviews.json');it['ordinal_diagnostic']=adoption(before,reviews)
                outcome=self.compare(best,it);it['adoption']=outcome
                save(self.folder/ident/'lesson-candidate.json',candidate_lesson(best['model_sha256'],it['model_sha256'],it.get('proposed_actions',[]),outcome))
                if not outcome['accepted']:
                    self.state.pop('pending_iteration',None)
                    self.persist();self.deliver(best)
                    if number==self.rounds:
                        self.state['status']='STALLED_RETAINED_BEST';self.persist();self.deliver(best);return
                    # Re-plan against the retained artifact, with the rejected
                    # change evidence. No failed mesh is silently adopted.
                    it=best;ident=best['id'];reviews=before
            self.state['best_iteration']=ident;self.state['current_parameters']=dict(it['parameters']);self.persist()
            self.state.pop('pending_iteration',None)
            self.deliver(it)
            if self.use_inspection:
                from tools.studio3d_inspection_review import inspect
                reviews=inspect(self,it)
            if it['gate']['model_based_near_match'] and (not self.use_inspection or it['inspection']['gate']['model_based_near_match']):
                self.state['status']='READY_FOR_USER_REVIEW';self.persist();self.deliver(it);return
            if number==self.rounds:
                self.state['status']='ROUND_LIMIT_REACHED';self.persist();self.deliver(it);return
            source=digest({'scene':it['scene_digest'],'model':it['model_sha256'],'reviews':reviews})
            failures=[]
            for failed in self.state['iterations']:
                if failed.get('adoption',{}).get('accepted') is False:
                    paired=self.folder/failed['id']/'paired-reviews.json'
                    findings=load(paired) if paired.exists() else []
                    failures.append({'iteration':failed['id'],'changes':[(a['parameter'],a['value']) for a in failed.get('proposed_actions',[])],
                                     'reason':failed['adoption']['reason'],'comparisons':[{'view':r['view'],'change':r['change'],'regressions':r['regressions'][:1],'improvements':r['improvements'][:1]} for r in findings]})
            failures=failures[-2:]
            focus=repair_focus(self.state['iterations'],reviews)
            request=patch_prompt(it['parameters'],reviews,source,self.policy,failures,focus=focus)
            raw=self.call(ident+'-plan-patch-'+recipe.VERSION+'-'+digest(request)[:12],request)
            try:
                updated,actions=validate_patch(decode(raw),it['parameters'],reviews,source)
                if focus and any(a['group']!=focus for a in actions):raise ValueError('Operation outside current workflow focus')
            except (ValueError,TypeError,KeyError) as e:
                it['patch_rejection']=str(e);self.state['status']='UNSUPPORTED_REPAIR';self.persist();self.deliver(it);return
            if not actions:
                it['unresolved']=decode(raw)['unresolved'];self.state['status']='UNSUPPORTED_REPAIR';self.persist();self.deliver(it);return
            if any(x.get('recipe_version')==recipe.VERSION and recipe.parameters(x['parameters'])==updated and x.get('adoption',{}).get('accepted') is False for x in self.state['iterations']):
                it['patch_rejection']='Repeated rejected parameter combination';self.state['status']='UNSUPPORTED_REPAIR';self.persist();self.deliver(it);return
            nxt='r'+str(max(int(x['id'][1:]) for x in self.state['iterations'])+1)
            self.state['iterations'].append({'id':nxt,'parameters':updated,'status':'CREATED','created_at':now(),'proposed_actions':actions,'source_digest':source,'source_iteration':it['id'],'workflow_focus':focus,'evidence_source':'inspection' if self.use_inspection else 'canonical'})
            self.state['pending_iteration']=nxt;ident=nxt
            self.persist()


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--origin',default='http://127.0.0.1:18283');p.add_argument('--rounds',type=int,default=3);p.add_argument('--inspection',action='store_true');p.add_argument('--resume',action='store_true');a=p.parse_args()
    if not 0<=a.rounds<=5:raise ValueError('Use 0..5 bounded rounds')
    # Windows advisory OS lock is released on process exit; do not mistake stale file existence for a live run.
    import msvcrt
    lock=a.asset_root/'metadata/autopilot/run.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        driver=Driver(a.asset_root,a.origin,a.rounds,a.inspection,a.resume)
        try:driver.run()
        except BaseException as e:
            driver.state['status']='INTERRUPTED_OR_FAILED';driver.state['last_error']=str(e);driver.persist();raise
        finally:
            from tools.studio3d_trial_report import update
            update(a.asset_root)
            print(json.dumps({'status':driver.state['status'],'best':driver.state['best_iteration'],'calls':len(driver.state['calls'])}),flush=True)

if __name__=='__main__':main()
