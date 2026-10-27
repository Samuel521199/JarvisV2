"""Two explicit Jarvis calls: generate engineering data, then review evidence.

No direct provider client/key, retry or model fallback; visual score stays null.
"""
import argparse,json,re,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--revision-of');p.add_argument('--insertion-feedback',action='store_true');p.add_argument('--origin',default='http://127.0.0.1:18282');a=p.parse_args()
    if not re.fullmatch('[a-z0-9-]+',a.label) or (a.revision_of is not None and not re.fullmatch('[a-f0-9]{32}',a.revision_of)) or not re.fullmatch(r'http://127\.0\.0\.1:\d{4,5}',a.origin):raise SystemExit('Local origin / label required')
    folder=ROOT/'docs/evidence/anatomy-engineering-2026-10-23'/a.label;folder.mkdir(parents=True,exist_ok=False);report={'status':'running','model_submissions':0}
    def save():(folder/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def get(path):
        with urllib.request.urlopen(a.origin+path,timeout=15) as r:return json.load(r)
    # Key-protected workbench: run as `python -m tools.eval_anatomy_engineering` from the project root.
    try:from control.local_access import install_client;install_client(a.origin)
    except ImportError:pass
    token=get('/api/session')['token']
    def post(path,body):
        request=urllib.request.Request(a.origin+path,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=60) as r:return json.load(r)
    def poll(read,done):
        deadline=time.monotonic()+170
        while time.monotonic()<deadline:
            state=read()
            if done(state):return state
            time.sleep(.8)
        raise RuntimeError('Deadline reached; no resend. Inspect existing Jarvis call ledger before continuing.')
    save()
    try:
        s=get('/api/snapshot')['settings'];route=next(c for c in s['connections'] if c['id']=='vertex' and c['enabled'] and c['credential_available']);provider=route['id'];model=route['model'];report.update(provider=provider,model=model);save()
        ident=uuid.uuid4().hex;report['composition_id']=ident;save()
        prompt='制作一个参数化机械装配：主传动轴、一个滚动轴承、两个定位隔套、一个带孔法兰和两枚穿过法兰孔的螺栓，共7件。名义孔轴必须留正间隙，不能互相穿透。通过端口和gap定位，各步父先子后，说明安装方向；轴承与隔套在轴的不同轴向位置，法兰和螺栓远离轴承避免干涉。可选电机—泵负载瞬态和理想Otto两个独立计算。明确静态干涉、插入路径和制造公差的验证边界。只使用登记零件类型。'
        body={'id':ident,'prompt':prompt,'provider':provider,'model':model,'mode':'engineering'}
        if a.revision_of:body.update(revision_of=a.revision_of,prompt='根据真实实体交集修订原七件装配，保留零件尺寸和实验。法兰孔在中面，螺栓axis是头下肩面；请修正被证明有问题的轴向放置，确保螺栓头在法兰外侧。保留插入路径未验证等边界。')
        if a.insertion_feedback:body['prompt']='继续修订原七件装配。新增7时刻实体路径采样发现：bearing安装时穿过spacer-a；spacer-b穿过spacer-a和bearing；两枚bolt的头在插入途中穿过flange。direction是从最终位置指向起点的单位向量：起点=终点+direction*distance，实际插入运动与direction反向，不要混淆。保留所有零件尺寸、mate/gap和计算实验，只修订steps的顺序、方向、distance和文字。从内部件向外安排，并考虑从轴的两端安装，避免已装零件挡路。保留离散采样不能证明连续路径等边界。'
        post('/api/anatomy/compose',body);report['model_submissions']+=1;save()
        state=poll(lambda:get('/api/anatomy/compositions/'+ident),lambda s:s['status'] not in ('READY','RUNNING'));report['generation']=state;save()
        if state['status']!='CANDIDATE':raise RuntimeError('Generated data rejected: '+state['status'])
        delivered=post('/api/anatomy/finish',{'id':ident});report['generation']=delivered;save();artifact=delivered['artifact']
        with urllib.request.urlopen(a.origin+artifact['downloads']['report.json']['url'],timeout=15) as r:actual=json.load(r)
        browser=json.loads((ROOT/'docs/evidence/anatomy-engineering-2026-10-23/deployed-1/browser.json').read_text(encoding='utf-8'))
        evidence={'generated_scene':delivered['scene'],'actual_assembly':actual['assembly'],'actual_bom':actual['bom'],'experiments':[{'kind':e['kind'],'summary':e['summary'],'limits':e['limits']} for e in actual['experiments']],'browser':{'status':browser['status'],'checks':browser['checks'],'errors':browser['errors']},'scope':'Browser tests cover predefined 19-part scene; generated scene has actual native CAD checks but its browser inspection is recorded separately. No screenshots provided to reviewer.','independent_tests':['known box intersection volume=500mm3','actual solid cap on Y=0','STEP volume/bounds/units roundtrip','motor energy balance and load response','Otto analytic energy/efficiency','Poiseuille profile and grid refinement','wet shallow-water mass/positivity/refinement','pendulum energy/period','Cantera element/enthalpy conservation']}
        (folder/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        question=('根据真实证据评审Jarvis Anatomy参数化组装技能。没有截图，visual_score必须为null。数值测试不是制造认证，装配静态无干涉不是插入路径无碰撞；报告中mismatch或unverified必须区分。生成是否完全满足用户7件要求与模型能力应分别评价。返回严格JSON，schema="anatomy.engineering.review.v1", evidence_mode="data-only", visual_score=null, scores={structure:0到10,assembly_correctness:0到10,numerical_evidence:0到10,usability_evidence:0到10}, strengths字符串数组, issues对象数组(含severity/finding/evidence/improvement),unverified字符串数组。评分不能替代工程校核。证据：'+json.dumps(evidence,ensure_ascii=False,separators=(',',':')))
        if len(question)>12000:raise RuntimeError('Review context exceeds dialogue limit')
        chat=post('/api/chats',{})['id'];turn='anatomy-engineering-review-'+uuid.uuid4().hex;report.update(review_chat_id=chat,review_turn_id=turn);save()
        post('/api/chat/send',{'chat_id':chat,'request_id':turn,'text':question,'provider':provider,'model':model,'reasoning':'default','skill':'none','memory_enabled':False});report['model_submissions']+=1;save()
        reviewed=poll(lambda:get('/api/chats/'+chat),lambda c:bool(c['turns']) and c['turns'][-1]['status'] not in ('READY','RUNNING'))['turns'][-1];report['review_turn']=reviewed;save()
        if reviewed['status']!='SUCCEEDED':raise RuntimeError('Review did not complete')
        answer=json.loads(reviewed['reply']);keys={'structure','assembly_correctness','numerical_evidence','usability_evidence'};scores=answer.get('scores',{})
        if answer.get('schema')!='anatomy.engineering.review.v1' or answer.get('evidence_mode')!='data-only' or answer.get('visual_score','missing') is not None or set(scores)!=keys or any(type(v) not in (int,float) or not 0<=v<=10 for v in scores.values()):raise RuntimeError('Review evidence/score contract rejected')
        report.update(review=answer,technical_score=round(sum(scores.values())/4,2),visual_score=None,score_scope='data-only model opinion, not visual or manufacturing certification',usage=[x for x in get('/api/usage') if x.get('turn_id') in {turn,'anatomy-'+ident}],status='passed');save();print(json.dumps({'status':'passed','model_submissions':report['model_submissions'],'url':artifact['url'],'technical_score':report['technical_score'],'collisions':artifact['checks']['collisions']},ensure_ascii=True))
    except BaseException as e:report.update(status='failed',error=str(e));save();raise
if __name__=='__main__':main()
