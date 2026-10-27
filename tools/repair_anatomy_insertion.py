"""Bounded two-call insertion repair through existing Jarvis chat/render APIs.

Keeps all physical parts and mates unchanged. Only step data may be replaced.
Used when the full-scene repair exhausts its response budget; no global settings
change, retry, hot reload or direct provider access.
"""
import json,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/evidence/anatomy-engineering-2026-10-23';ORIGIN='http://127.0.0.1:18282'
def main():
    folder=BASE/'insertion-model-1';folder.mkdir(exist_ok=False);report={'status':'running','model_submissions':0,'reasoning':'low','scope':'Existing Jarvis API; step-only data repair, immutable prior parts/mates'}
    def save():(folder/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def get(path):
        with urllib.request.urlopen(ORIGIN+path,timeout=15) as r:return json.load(r)
    # Key-protected workbench: run as `python -m tools.repair_anatomy_insertion` from the project root.
    try:from control.local_access import install_client;install_client(ORIGIN)
    except ImportError:pass
    token=get('/api/session')['token']
    def post(path,body):
        req=urllib.request.Request(ORIGIN+path,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':ORIGIN,'X-Jarvis-Token':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
    previous=json.loads((BASE/'model-2/evaluation.json').read_text(encoding='utf-8'));scene=previous['generation']['scene'];checked=json.loads((BASE/'model-2/path-recheck.json').read_text(encoding='utf-8'));provider=previous['provider'];model=previous['model'];turns=[]
    def ask(text):
        chat=post('/api/chats',{})['id'];turn='anatomy-insertion-'+uuid.uuid4().hex;turns.append(turn);report.setdefault('turns',[]).append({'chat_id':chat,'turn_id':turn});save()
        post('/api/chat/send',{'chat_id':chat,'request_id':turn,'text':text,'provider':provider,'model':model,'reasoning':'low','skill':'none','memory_enabled':False});report['model_submissions']+=1;save();deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            r=get('/api/chats/'+chat)['turns'][-1]
            if r['status'] not in ('READY','RUNNING'):
                report.setdefault('model_turns',[]).append(r);save()
                if r['status']!='SUCCEEDED':raise RuntimeError('Known model failure; no automatic retry: '+r['status'])
                return json.loads(r['reply'])
            time.sleep(.8)
        raise RuntimeError('Model outcome unknown; inspect ledger before any retry')
    save()
    try:
        prompt=('请修订装配插入步骤，只返回严格JSON对象 {"schema":"anatomy.steps-repair.v1","steps":[...]}。每个step保持part/instruction/direction/distance四字段。严禁更改任何零件尺寸、mate/gap或新增零件。'
          'direction是从终点指向起点：start=final+direction*distance，插入运动方向与direction相反。螺栓头位于+Z，杆沿-Z；从法兰正面插入的起点应该在法兰+Z外侧。'
          '每件必须出现一次且父先子后；可以调整顺序、从轴的两端选择方向，避免穿过已经装好的大直径零件。距离0..300mm。'
          '静态装配已无体积干涉；七点采样发现的实际障碍如下，先根据明确几何关系修订步骤，不需要重新推导热力学或长篇解释。'
          +json.dumps({'parts':scene['parts'],'mates':scene['mates'],'steps':scene['steps'],'insertion':checked['checks']['insertion']},ensure_ascii=False,separators=(',',':')))
        answer=ask(prompt);report['repair']=answer;save()
        if not isinstance(answer,dict) or set(answer)!={'schema','steps'} or answer['schema']!='anatomy.steps-repair.v1':raise RuntimeError('Step-only repair contract rejected')
        repaired={**scene,'steps':answer['steps']};artifact=post('/api/anatomy/render',{'mechanism':'engineering','scene':repaired});report.update(configuration=repaired,artifact=artifact,revision_of=previous['composition_id']);save()
        if artifact['checks']['collisions'] or artifact['checks']['insertion']['hits']:raise RuntimeError('Geometry still finds an obstruction; no pass issued')
        with urllib.request.urlopen(ORIGIN+artifact['downloads']['report.json']['url'],timeout=15) as r:physical=json.load(r)
        evidence={'parts_preserved':repaired['parts']==scene['parts'],'mates_preserved':repaired['mates']==scene['mates'],'static_and_sampled_checks':physical['assembly'],'experiments':[{'kind':e['kind'],'summary':e['summary']} for e in physical['experiments']],'browser_evidence':{'predefined_cases':'9 checks passed on isolated final-code workbench','generated_case':'not yet browser-checked at review time'},'limits':'7 insertion samples are not continuous collision proof; no manufacturing or general dynamics certification. No screenshots sent.'}
        review=ask('根据证据严格评审，返回JSON：schema="anatomy.engineering.review.v1",evidence_mode="data-only",visual_score=null,scores={structure:0到10,assembly_correctness:0到10,numerical_evidence:0到10,usability_evidence:0到10},issues数组,unverified数组。不要把离散无干涉当作连续路径或制造合格；用户明确要求7件含两枚螺栓，不能擅自要求补成四枚。证据：'+json.dumps(evidence,ensure_ascii=False,separators=(',',':')))
        scores=review.get('scores',{});keys={'structure','assembly_correctness','numerical_evidence','usability_evidence'}
        if review.get('schema')!='anatomy.engineering.review.v1' or review.get('evidence_mode')!='data-only' or review.get('visual_score','missing') is not None or set(scores)!=keys or any(type(v) not in (int,float) or not 0<=v<=10 for v in scores.values()):raise RuntimeError('Review contract rejected')
        report.update(review=review,technical_score=round(sum(scores.values())/4,2),visual_score=None,usage=[u for u in get('/api/usage') if u.get('turn_id') in turns],status='passed');save();print(json.dumps({'status':'passed','technical_score':report['technical_score'],'model_submissions':report['model_submissions'],'artifact':artifact['url'],'insertion_hits':artifact['checks']['insertion']['hits']}))
    except BaseException as e:report.update(error=str(e),status='failed');save();raise
if __name__=='__main__':main()
