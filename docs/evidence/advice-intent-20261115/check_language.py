"""Freeze operator-authored challenge before execution; preserve first-pass gaps."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
OUT=Path(__file__).parent
NEW=[
 ('n01','notes',True,'请帮我逐字引用所有资料；保持来源编号及原始顺序；不要改写'),
 ('n02','notes',True,'把这批笔记按原始顺序逐条照抄成报告，附上各自来源标识'),
 ('n03','notes',True,'保留原顺序与来源ID；原样摘录每条原文'),
 ('n04','notes',True,'保留来源标识，保持输入顺序，将这些笔记逐条逐字摘录'),
 ('n05','notes',True,'Quote every note word for word; retain source identifiers; keep their input order.'),
 ('n06','notes',True,'Please transcribe all sources verbatim. Preserve the source ids and original order. Do not rewrite.'),
 ('n07','notes',True,'按给定顺序完整照录资料，并标明每条来源编号，不要摘要。'),
 ('n08','notes',True,'原文一字不改地整理成报告，来源ID和排列次序都沿用输入。'),
 ('p01','practice',True,'制作当前乘法题；给出每题的正确答案；保持输入顺序'),
 ('p02','practice',True,'用当前数对制作乘法练习及答案；顺序不变；勿评价学生是否掌握'),
 ('p03','practice',True,'根据整数对出乘法题和正确答案，保持原始顺序，保存练习表'),
 ('p04','practice',True,'Create multiplication questions from the pairs; add correct answers; retain their original order.'),
 ('p05','practice',True,'Generate multiplication exercises and answers from current pairs, keep input order, do not assess learner mastery.'),
 ('p06','practice',True,'按原顺序把当前整数对做成乘法练习，并且给出正确答案'),
 ('p07','practice',True,'每组数字各出一道乘法题，写出正确结果，题序照旧。'),
 ('p08','practice',True,'Turn these pairs into a multiplication worksheet with solutions in the given sequence.'),
 ('x01','notes',False,'原样引用每条原文，保留来源标识和原顺序，然后删掉未确认的内容'),
 ('x02','notes',False,'不要逐字摘录每条原文，保留来源编号与顺序'),
 ('x03','notes',False,'将这些资料逐条照抄成报告，保留来源ID，但按时间重新排序'),
 ('x04','notes',False,'请解释“逐字摘录每条原文，保留来源ID和顺序”这条命令'),
 ('x05','notes',False,'Copy each source verbatim; preserve source ids; reverse original order.'),
 ('x06','notes',False,'Copy each source verbatim; keep source ids; keep original order; remove the second source.'),
 ('x07','notes',False,'原样摘录每条原文，保留来源ID和顺序，但是把暂估值写成成交价'),
 ('x08','notes',False,'将这批笔记逐条照抄成报告，保持来源编号和顺序，发到群里'),
 ('x09','practice',False,'制作乘法题，提供正确答案，保持输入顺序，但是把第一个答案改成零'),
 ('x10','practice',False,'根据数对出乘法题和答案，顺序不变，告诉我已经完全掌握'),
 ('x11','practice',False,'生成当前乘法练习及正确答案，保留题目顺序，只显示偶数题'),
 ('x12','practice',False,'Make multiplication exercises from these pairs; provide answers; do not preserve input order.'),
 ('x13','practice',False,'Generate multiplication questions from current pairs; add answers; keep order; email the worksheet.'),
 ('x14','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，如果有负数就改成除法'),
 ('x15','practice',False,'如果明天下雨，生成当前乘法练习和正确答案，保留题目顺序'),
 ('x16','practice',False,'生成当前乘法练习和正确答案，保留题目顺序，不要生成当前乘法练习'),
]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 old=ROOT/'docs/evidence/advice-purpose-20261115/language-r1/freeze.json'
 prior=json.loads(old.read_text(encoding='utf-8'))
 target=OUT/'language-r1';target.mkdir(exist_ok=False)
 source={p:sha(ROOT/p) for p in ('modules/task_resource/advice_scope.py','modules/task_resource/advice_intent.py')}
 freeze={'scope':'operator-authored first-pass challenge; not independent user holdout','frozen_at':time.time(),
  'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'runtime_sha256':source,'harness_sha256':sha(Path(__file__)),'cases':NEW,'inputs':prior['inputs'],
  'prior_freeze_sha256':sha(old),'gate':'All negatives must reject; all intended positives stay in recall denominator. Known replay is not new accuracy.'}
 (target/'freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 from modules.task_resource.advice_scope import selectors
 from modules.task_resource.advice_intent import analyze
 from sdk.protocol import canonical
 def run(cases,version):
  rows=[]
  for ident,domain,expected,goal in cases:
   data=prior['inputs'][domain];plan={'request':{'goal':goal,'input_text':canonical(data)}}
   value=selectors(plan,version);matched='task_purpose' in value
   rows.append({'id':ident,'domain':domain,'goal':goal,'expected':expected,'matched':matched,'correct':expected==matched,
    'selectors':value,'diagnostic':analyze(goal,data['schema']) if version==4 else None})
  pos=[r for r in rows if r['expected']];neg=[r for r in rows if not r['expected']]
  return {'version':version,'rows':rows,'positive_matches':sum(r['matched'] for r in pos),'positive_count':len(pos),
   'false_matches':sum(r['matched'] for r in neg),'negative_count':len(neg),'negative_gate_passed':not any(r['matched'] for r in neg)}
 result={'known_v3_replay':run(prior['cases'],3),'known_v4_replay':run(prior['cases'],4),'new_v4_first_pass':run(NEW,4),
  'runtime_unchanged':all(sha(ROOT/p)==value for p,value in source.items()),'cloud_calls':0,'production_data_used':False,
  'scope':'Advice-purpose selection only; unmatched advice does not block independent planning. Not task success or long-term learning.'}
 (target/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:({a:b for a,b in v.items() if a!='rows'} if isinstance(v,dict) else v) for k,v in result.items()}))
 assert result['runtime_unchanged']
 assert all(result[k]['negative_gate_passed'] for k in ('known_v3_replay','known_v4_replay','new_v4_first_pass'))

if __name__=='__main__':main()
