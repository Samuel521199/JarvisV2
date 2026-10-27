"""Predefined synthetic counterexamples; counts do not estimate real-world rates."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
from modules.dialogue.delivery_basis import update,empty
from modules.task_resource.delivery_review import review

scenarios=[('comparison','甲方案价格90元，交期3天。','明天10点询问保修，不下单。','甲报价九十元，三天交货；次日上午十时问保修，暂不购买。','该方案已经确认终身保修。'),
 ('documents','数据导出失败，原因未知。','明天10点检查日志，不重跑导出。','导出没成功且原因尚不清楚；次日上午十时查日志，不重新执行。','失败原因已经确定为内存不足。'),
 ('learning','学习者只看过讲解，尚未独立作答。','明天10点独立复测，不给提示。','学生仅阅读了解释、没有自己回答；次日上午十时无提示复习测验。','学习者已经全面掌握该知识。')]
cases=[]
for domain,fact,plan,paraphrase,unsupported in scenarios:
 basis=update({'expected_revision':0,'facts':[fact],'plans':[plan]},fact+'\n'+plan,'calibration-source',empty())
 for name,text,bad in [('exact',fact+'\n'+plan,False),('paraphrase',paraphrase,False),('missing-plan',fact,True),('changed-time',fact+'\n'+plan.replace('明天10点','今天15点'),True),('unsupported-addition',fact+'\n'+plan+'\n'+unsupported,True)]:
  cases.append({'id':domain+'-'+name,'domain':domain,'basis':basis,'reply':text,'preset_semantic_defect':bad})
with (HERE/'calibration-inputs.json').open('x',encoding='utf-8',newline='\n') as f:json.dump({'cases':cases,'origin':'first_party_synthetic_preset_labels','independent_human_reference':False},f,ensure_ascii=False,indent=2);f.write('\n')
rows=[];counts={'true_alert':0,'false_alert':0,'missed_alert':0,'correct_no_alert':0}
for c in cases:
 r=review(c['basis'],c['reply'],'SUCCEEDED');alert=r['state']=='REVIEW'
 key=('true_alert' if c['preset_semantic_defect'] else 'false_alert') if alert else ('missed_alert' if c['preset_semantic_defect'] else 'correct_no_alert')
 counts[key]+=1;rows.append({**c,'review':r,'classification':key})
value={'counts':counts,'cases':rows,'population_inference':False,'would_block_count':sum(x['review']['would_block'] for x in rows),'quality_score':None,'conclusion':'Literal review both overflags paraphrases and misses unsupported additions when original quotes remain. It must not be used as an automatic semantic completion gate.'}
(HERE/'calibration.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(counts))
