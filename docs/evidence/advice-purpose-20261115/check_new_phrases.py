"""First-pass operator-authored language challenge; freeze before parser calls.
Not an independent user holdout or evidence of population accuracy.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from sdk.protocol import canonical
OUT=Path(__file__).parent/'language-r1'
NOTES={'schema':'jarvis.notes-input.v1','sources':[{'id':'memo-R72','text':'报价为估计值，需再次核对。'}]}
PRACTICE={'schema':'jarvis.practice-input.v1','pairs':[[19,7],[28,12]]}
CASES=[
 ('n01','notes',True,'请整理资料；原样摘录每条原文；保留来源ID和顺序；不要概括；保存报告。'),
 ('n02','notes',True,'整理当前资料\n原样摘录每条原文\n保留来源ID和顺序\n不把草稿估价写成确认结论'),
 ('n03','notes',True,'把这些资料按原顺序逐条原样引用，附上各自来源ID，不要总结。'),
 ('n04','notes',True,'整理资料，逐字摘录各条原文，保持来源ID与顺序，保存报告。'),
 ('n05','notes',True,'请保留来源ID和顺序，将当前资料逐条照抄成报告，不改写。'),
 ('n06','notes',True,'Organize these notes by copying each source verbatim in order with its ID.'),
 ('p01','practice',True,'请生成当前乘法练习和正确答案；保留题目顺序；保存练习表；不得声称已经掌握。'),
 ('p02','practice',True,'用当前给出的数生成乘法练习和正确答案\n保留题目顺序\n不要评价学习者是否掌握'),
 ('p03','practice',True,'按顺序把当前整数对做成乘法练习，并附正确答案。'),
 ('p04','practice',True,'生成当前乘法练习及正确答案，保留题目顺序，保存练习表。'),
 ('p05','practice',True,'根据pairs出乘法题和答案，顺序不变，勿判断我是否掌握。'),
 ('p06','practice',True,'Make multiplication exercises and correct answers from these pairs, preserving their order.'),
 ('x01','notes',False,'整理资料，原样摘录每条原文，保留来源ID和顺序，只留下已确认结论'),
 ('x02','notes',False,'整理资料，原样摘录每条原文，保留来源ID和顺序，但重写成摘要'),
 ('x03','notes',False,'整理资料，原样摘录每条原文，删除来源ID，保存报告'),
 ('x04','notes',False,'整理资料，原样摘录每条原文，保留来源ID和顺序，先按价格排序'),
 ('x05','notes',False,'不要整理资料，原样摘录每条原文，保留来源ID和顺序'),
 ('x06','notes',False,'整理资料，原样摘录每条原文，保留来源ID和顺序，发给供应商'),
 ('x07','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，并判断我已经掌握'),
 ('x08','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，但不要提供答案'),
 ('x09','practice',False,'生成当前除法练习和正确答案，保留题目顺序'),
 ('x10','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，只计算第一题'),
 ('x11','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，随机打乱题目'),
 ('x12','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，上传到云端'),
]

def main():
 OUT.mkdir(exist_ok=False)
 frozen={'scope':'24 new operator-authored phrases; broader intended meaning vs finite implementation; not independent user holdout',
  'frozen_at':time.time(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'runtime_sha256':hashlib.sha256((ROOT/'modules/task_resource/advice_scope.py').read_bytes()).hexdigest(),
  'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':CASES,'inputs':{'notes':NOTES,'practice':PRACTICE},
  'gate':'No negative may match; positive recall is measured without relabelling rejected paraphrases as successes. This is not the existing independent 90% language gate.'}
 (OUT/'freeze.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 from modules.task_resource.advice_scope import inspect
 rows=[]
 for ident,domain,expected,goal in CASES:
  result=inspect(goal,canonical(NOTES if domain=='notes' else PRACTICE));matched='task_purpose' in result
  rows.append({'id':ident,'domain':domain,'expected_match':expected,'actual_match':matched,'correct':expected==matched,'selectors':result})
 positives=[r for r in rows if r['expected_match']];negatives=[r for r in rows if not r['expected_match']]
 report={'rows':rows,'positive_matches':sum(r['actual_match'] for r in positives),'positive_count':len(positives),
  'false_matches':sum(r['actual_match'] for r in negatives),'negative_count':len(negatives),
  'overall_correct':sum(r['correct'] for r in rows),'count':len(rows),'cloud_calls':0,'production_data_used':False,
  'scope':'first pass retained; no parser edits or sample relabelling','negative_gate_passed':not any(r['actual_match'] for r in negatives)}
 (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
if __name__=='__main__':main()
