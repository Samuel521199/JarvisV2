"""One explicit data-only review through Jarvis after final geometry/UI checks."""
import json,re,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/evidence/anatomy-engineering-2026-10-23';ORIGIN='http://127.0.0.1:18282'
def main():
    folder=BASE/'final-review';folder.mkdir(exist_ok=False);record={'status':'running','model_submissions':0,'evidence_mode':'data-only','visual_score':None}
    def save():(folder/'evaluation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def get(path):
        with urllib.request.urlopen(ORIGIN+path,timeout=15) as r:return json.load(r)
    token=get('/api/session')['token']
    def post(path,value):
        q=urllib.request.Request(ORIGIN+path,data=json.dumps(value,ensure_ascii=False).encode(),headers={'Origin':ORIGIN,'X-Jarvis-Token':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(q,timeout=20) as r:return json.load(r)
    try:
        final=json.loads((BASE/'final-delivery-v2.json').read_text(encoding='utf-8'));browser=json.loads((BASE/'frozen-plan-browser/browser.json').read_text(encoding='utf-8'));initial=json.loads((BASE/'model-1/evaluation.json').read_text(encoding='utf-8'))
        evidence={'actual_checks':final['artifact']['checks'],'parts':len(final['configuration']['parts']),'parts_and_mates_preserved':True,'method':'Google generated seven-part data; native B-rep found head/flange overlap; model revision fixed static overlap. Subsequent native insertion sampling found path obstructions. Trusted bounded order/direction search changed steps only; rebuilt and rechecked all static and 7-sample insertion checks. No continuous collision guarantee.','browser':{'status':browser['status'],'checks':browser['checks'],'errors':browser['errors']},'limits':['CAD validity and STEP roundtrip are not manufacturing certification','7 samples may miss thin obstructions between samples','No general rigid body contact, turbulent combustion, CFD or FSI','Two bolts in four-hole flange are explicitly requested, not a claim of full structural fastening','No screenshots provided to reviewer']}
        text='依据真实证据对Jarvis Anatomy技能评分，只返回JSON对象：schema="anatomy.engineering.review.v1",evidence_mode="data-only",visual_score=null,scores={structure:0到10,assembly_correctness:0到10,numerical_evidence:0到10,usability_evidence:0到10},issues数组,unverified数组。没有充分数值实验结果时不要推断全面工程精度。只对本证据范围评分，不能宣称普遍成功率或制造合格。证据：'+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
        chat=post('/api/chats',{})['id'];turn='anatomy-final-review-'+uuid.uuid4().hex;record.update(chat_id=chat,turn_id=turn,artifact=final['artifact']['url'],evidence=evidence);save()
        post('/api/chat/send',{'chat_id':chat,'request_id':turn,'text':text,'provider':initial['provider'],'model':initial['model'],'reasoning':'low','skill':'none','memory_enabled':False});record['model_submissions']=1;save();deadline=time.monotonic()+145
        while time.monotonic()<deadline:
            r=get('/api/chats/'+chat)['turns'][-1]
            if r['status'] not in ('READY','RUNNING'):break
            time.sleep(.8)
        else:raise RuntimeError('Review unknown at deadline, no retry')
        record['review_turn']=r;save()
        if r['status']!='SUCCEEDED':raise RuntimeError('Review failed; no retry')
        raw=r['reply'];match=re.fullmatch(r'\s*```json[ \t]*\r?\n([\s\S]*?)\r?\n```\s*',raw)
        if match:raw=match.group(1);record['format_normalization']='Removed one enclosing JSON fence; raw turn retained; no data edits'
        review=json.loads(raw);scores=review.get('scores',{});keys={'structure','assembly_correctness','numerical_evidence','usability_evidence'}
        if review.get('schema')!='anatomy.engineering.review.v1' or review.get('evidence_mode')!='data-only' or review.get('visual_score','missing') is not None or set(scores)!=keys or any(type(v) not in (int,float) or not 0<=v<=10 for v in scores.values()):raise RuntimeError('Review score/evidence contract rejected')
        record.update(status='passed',review=review,technical_score=round(sum(scores.values())/4,2),usage=[u for u in get('/api/usage') if u.get('turn_id')==turn]);save();print(json.dumps({'status':'passed','technical_score':record['technical_score'],'visual_score':None,'model_submissions':1}))
    except BaseException as e:record.update(status='failed',error=str(e));save();raise
if __name__=='__main__':main()
