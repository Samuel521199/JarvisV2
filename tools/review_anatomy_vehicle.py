"""One evidence-only review using the existing Jarvis Google dialogue lane."""
import json,re,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/evidence/anatomy-vehicle-2026-10-23';ORIGIN='http://127.0.0.1:18282'

def main():
    file=BASE/'google-review.json'
    if file.exists():raise RuntimeError('Review already recorded; do not replay a model call')
    record={'status':'running','model_submissions':0,'evidence_mode':'data-only','visual_score':None}
    def save():file.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def get(path):
        with urllib.request.urlopen(ORIGIN+path,timeout=15) as r:return json.load(r)
    # Key-protected workbench: run as `python -m tools.review_anatomy_vehicle` from the project root.
    try:from control.local_access import install_client;install_client(ORIGIN)
    except ImportError:pass
    token=get('/api/session')['token']
    def post(path,value):
        q=urllib.request.Request(ORIGIN+path,data=json.dumps(value,ensure_ascii=False).encode(),headers={'Origin':ORIGIN,'X-Jarvis-Token':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(q,timeout=20) as r:return json.load(r)
    try:
        native=json.loads((BASE/'native-v3.json').read_text(encoding='utf-8'))['receipt'];browser=json.loads((BASE/'browser-2/browser.json').read_text(encoding='utf-8'))
        evidence={'parts':len(native['configuration']['parts']),'subassemblies':native['configuration']['assembly_plan'],'checks':native['checks'],'browser':browser,'implementation':'Independent first-party bounded data factories. Single-part insertion; rigid whole subassemblies; sequential batches with simultaneous parts. Typed ideal Ackermann front pivots and independent wheel phases, ideal differential rotor uses mean rear speed. Body held fixed on a demonstration stand. Dynamic geometry uses world-space rigid transforms, no scripts in input. Python/JS numeric transforms match to 1e-9.','limits':['No full vehicle suspension or bodywork','Differential internal gears, tie rods, fasteners and wire harness are simplified or omitted','Motor/traction loads, tyre deformation and road contact are not solved','Changing inspection scope restores completed pose; it is a teaching viewer, not manual snap-to-assemble game or assembly training record','Nine co-phased wheel/steering native poses are not complete cycle or independent-phase collision certification','Seven insertion samples can miss thin obstacles','CAD valid export is not manufacturing certification','No images supplied to this text reviewer']}
        text='对Jarvis Anatomy 5.1的32件车辆组装样例做严格技术评审。只返回JSON：schema="anatomy.vehicle.review.v1", evidence_mode="data-only", visual_score=null, scores={structure:0到10,assembly_correctness:0到10,kinematics:0到10,usability_evidence:0到10}, issues数组, improvements数组, unverified数组。仅评估所给有限证据，不能称为任意复杂车辆自由生成成功或制造合格，不要虚构看到截图。证据：'+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
        chat=post('/api/chats',{})['id'];turn='anatomy-vehicle-review-'+uuid.uuid4().hex;record.update(chat_id=chat,turn_id=turn,provider='vertex',model='gemini-3.8-flash',evidence=evidence);save()
        post('/api/chat/send',{'chat_id':chat,'request_id':turn,'text':text,'provider':record['provider'],'model':record['model'],'reasoning':'low','skill':'none','memory_enabled':False});record['model_submissions']=1;save();deadline=time.monotonic()+145
        while time.monotonic()<deadline:
            r=get('/api/chats/'+chat)['turns'][-1]
            if r['status'] not in ('READY','RUNNING'):break
            time.sleep(.8)
        else:raise RuntimeError('Review UNKNOWN at deadline; no replay')
        record['raw_turn']=r;save()
        if r['status']!='SUCCEEDED':raise RuntimeError('Review did not succeed; no retry')
        raw=r['reply'];match=re.fullmatch(r'\s*```json[ \t]*\r?\n([\s\S]*?)\r?\n```\s*',raw)
        if match:raw=match.group(1);record['normalization']='Removed one enclosing JSON fence; original response retained'
        review=json.loads(raw);scores=review['scores']
        if review.get('schema')!='anatomy.vehicle.review.v1' or review.get('visual_score','missing') is not None or review.get('evidence_mode')!='data-only' or set(scores)!={'structure','assembly_correctness','kinematics','usability_evidence'} or any(type(x) not in (int,float) or not 0<=x<=10 for x in scores.values()):raise RuntimeError('Review data contract rejected')
        record.update(status='passed',review=review,technical_score=round(sum(scores.values())/4,2),usage=[u for u in get('/api/usage') if u.get('turn_id')==turn]);save();print(json.dumps({'status':record['status'],'score':record['technical_score'],'visual_score':None,'model_submissions':1}))
    except BaseException as exc:record.update(status='failed',error=str(exc));save();raise
if __name__=='__main__':main()
