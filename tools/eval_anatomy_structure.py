"""Explicit, bounded Jarvis model generation and evidence review.

Uses Jarvis' configured route, execution lane, cancellation and usage ledger.
Two maximum submissions, no automatic retry; the reviewer receives data, NOT
screenshots. Visual score must therefore be null. Run only with user authorization.
"""
import argparse,json,re,shutil,subprocess,time,urllib.request,uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/evidence/anatomy-structure-2026-10-23'
def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18282');p.add_argument('--label',required=True);p.add_argument('--browser',required=True);p.add_argument('--reuse-generation');a=p.parse_args()
    if not re.fullmatch(r'http://127\.0\.0\.1:\d{4,5}',a.origin) or not all(re.fullmatch('[a-z0-9-]+',x) for x in [a.label,a.browser]+([a.reuse_generation] if a.reuse_generation else [])):raise SystemExit('Expected local origin and evidence labels')
    folder=BASE/a.label;folder.mkdir(parents=True,exist_ok=False);report={'status':'running','model_submissions':0,'scope':'real Jarvis generation and data-only model review'}
    def save():
        (folder/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def get(path):
        with urllib.request.urlopen(a.origin+path,timeout=10) as r:return json.load(r)
    # Key-protected workbench: run as `python -m tools.eval_anatomy_structure` from the project root.
    try:from control.local_access import install_client;install_client(a.origin)
    except ImportError:pass
    token=get('/api/session')['token']
    def post(path,value):
        req=urllib.request.Request(a.origin+path,data=json.dumps(value,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    def poll(read,done):
        deadline=time.monotonic()+145
        while time.monotonic()<deadline:
            state=read()
            if done(state):return state
            time.sleep(.8)
        raise RuntimeError('Model deadline exceeded; no automatic resend. Check Jarvis ledger before retrying.')
    try:
        browser=json.loads((BASE/a.browser/'browser.json').read_text(encoding='utf-8'))
        if browser['status']!='passed':raise RuntimeError('Browser evidence failed; repair before model review')
        settings=get('/api/snapshot')['settings'];route=next(c for c in settings['connections'] if c['id']=='vertex' and c['enabled'] and c['credential_available']);provider=route['id'];model=route['model'];report.update(provider=provider,model=model,browser_evidence=a.browser+'/browser.json');save()
        prompt='制作一个复杂三维机械科普实验：四缸发动机含气门、凸轮轴、正时和冷却水套，经20:40齿轮驱动离心泵，再驱动干涉水波；另加单轴喷气引擎作对照。显示燃烧室内3D火焰、气流和水流，最多5个组件。说明内部关键结构，以及单向联动与示意效果的限制；不承诺真实CFD、制造CAD或受力结果。'
        if a.reuse_generation:
            previous=json.loads((BASE/a.reuse_generation/'evaluation.json').read_text(encoding='utf-8'))
            if previous['generation']['status']!='DELIVERED':raise RuntimeError('No successful generation to reuse')
            ident=previous['composition_id'];delivered=previous['generation'];report.update(composition_id=ident,generation_reused_from=a.reuse_generation+'/evaluation.json')
            report['refreshed_artifact']=post('/api/anatomy/render',{'mechanism':'studio','scene':delivered['scene']})
        else:
            ident=uuid.uuid4().hex;report.update(composition_id=ident,generation_prompt=prompt);save()
            post('/api/anatomy/compose',{'id':ident,'prompt':prompt,'provider':provider,'model':model});report['model_submissions']+=1;save()
            state=poll(lambda:get('/api/anatomy/compositions/'+ident),lambda s:s['status'] not in {'READY','RUNNING'})
            report['generation']=state;save()
            if state['status']!='CANDIDATE':raise RuntimeError('Scene did not pass the strict Jarvis validator: '+state['status'])
            delivered=post('/api/anatomy/finish',{'id':ident})
        report['generation']=delivered;save()
        node=shutil.which('node')
        if not node:raise RuntimeError('Node required for geometry audit')
        audit_process=subprocess.run([node,str(ROOT/'modules/skills/anatomy/structure-audit.mjs')],input=json.dumps(delivered['scene'],ensure_ascii=False).encode(),capture_output=True,timeout=15)
        if audit_process.returncode:raise RuntimeError('Trusted geometry audit failed')
        audit=json.loads(audit_process.stdout);(folder/'geometry.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        if not all(audit['checks'].values()):raise RuntimeError('Deterministic geometry check failed')
        numerical=subprocess.run([node,str(ROOT/'tests/anatomy_structure3d.mjs')],capture_output=True,timeout=20)
        if numerical.returncode:raise RuntimeError('Independent structure tests failed')
        checked=json.loads(numerical.stdout);(folder/'numerical.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2),encoding='utf-8')
        summary={'checks':audit['checks'],'independent_numerical_checks':{k:v for k,v in checked.items() if k!='inventories'},'modules':[{'id':m['id'],'type':m['type'],'stats':m['stats'],'parts':[p['label'] for p in m['parts'][:18]],'part_count':len(m['parts']),'effect_instances':{kind:sum(e['kind']==kind for e in m['effects']) for kind in ['flow','flame']},'configuration':{k:v for k,v in m['configuration'].items() if k!='parts'}} for m in audit['modules']],'limits':audit['limits'],'browser':{'status':browser['status'],'checks':browser['checks'],'errors':browser['errors'],'animation_updates_in_1300ms':browser.get('animation_updates')},'unfulfilled':audit['unfulfilled']}
        question=('你是Jarvis的机械科普工具评审员。只根据实际结构数据、几何检查及浏览器回执严格评审；你没有收到截图，不能声称看过画面或评定视觉美感。不要因为生成者是自己就给高分。科普表达与工程求解严格区分。'
          '返回一个严格JSON对象：schema="anatomy.review.v1"，evidence_mode="data-only"，visual_score=null；scores包含structure、motion_consistency、effect_consistency、inspectability四个0—10数字或null；'
          'strengths为中文字符串数组；issues为对象数组，每项含severity(high/medium/low)、finding、evidence、improvement；unverified为字符串数组。没有证据的维度应为null。'
          '评分应解释部件与通道的结构覆盖、受限模型与效果的一致性、实际交互测试；禁止把空间粒子当作CFD验证、把源码坐标当作碰撞验证。一个20:40齿轮副是一级传动，不要把两个齿轮误述为两级。更新率为实测短时观测，不等于低配长时性能结论。不要执行任何任务或更改权限。实际证据：'+json.dumps(summary,ensure_ascii=False,separators=(',',':')))
        if len(question)>12000:raise RuntimeError('Review input exceeds the existing dialogue limit')
        chat=post('/api/chats',{})['id'];turn='anatomy-review-'+uuid.uuid4().hex;report.update(review_chat_id=chat,review_turn_id=turn);save()
        post('/api/chat/send',{'chat_id':chat,'request_id':turn,'text':question,'provider':provider,'model':model,'reasoning':'default','skill':'none','memory_enabled':False});report['model_submissions']+=1;save()
        review=poll(lambda:get('/api/chats/'+chat),lambda c:bool(c['turns']) and c['turns'][-1]['status'] not in {'READY','RUNNING'})['turns'][-1];report['review_turn']=review;save()
        if review['status']!='SUCCEEDED':raise RuntimeError('Review did not complete: '+review['status'])
        answer=json.loads(review['reply']);scores=answer.get('scores',{});required={'structure','motion_consistency','effect_consistency','inspectability'}
        if answer.get('schema')!='anatomy.review.v1' or answer.get('evidence_mode')!='data-only' or answer.get('visual_score','missing') is not None or set(scores)!=required or any(v is not None and (type(v) not in [int,float] or not 0<=v<=10) for v in scores.values()):raise RuntimeError('Review output failed its evidence/score contract')
        weights={'structure':.3,'motion_consistency':.3,'effect_consistency':.25,'inspectability':.15};valid=[k for k in required if scores[k] is not None];overall=round(sum(scores[k]*weights[k] for k in valid)/sum(weights[k] for k in valid),2) if valid else None
        report.update(review=answer,technical_score=overall,score_scope='data-only technical review; excludes visual quality, independent engineering validation and general success rate')
        usage=get('/api/usage');report['usage']=[x for x in usage if x.get('turn_id') in {turn,'anatomy-'+ident}];report['status']='passed';save()
        print(json.dumps({'status':report['status'],'model_submissions':report['model_submissions'],'artifact':delivered['artifact']['url'],'technical_score':overall,'visual_score':None},ensure_ascii=True))
    except BaseException as exc:report.update(status='failed',error=str(exc));save();raise
if __name__=='__main__':main()
