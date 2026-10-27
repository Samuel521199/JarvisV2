"""Freeze explicit user declarations independently of the hidden answer checks."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
data=[
 {'id':'shadow-quote','domain':'comparison','skill':'none','turns':[
  {'prompt':'比较两方案，预算最多100元、交期最多5天，选符合条件的最低价。文档保留两份原报价以说明排除原因，保留已确认计划，不把询问或下单写成已完成。JSON字段document、selected（甲或乙）。',
   'facts':['甲方案价格90元，交期3天。','乙方案价格80元，交期7天。'],'plans':['明天10点询问保修，不下单。'],'expected':{'selected':'甲'}},
  {'prompt':'乙报价被明确更正，重新按相同约束选择。其余资料和已确认计划保持。JSON字段document、selected（甲或乙）。',
   'facts':['甲方案价格90元，交期3天。','乙方案价格85元，交期4天。'],'plans':['明天10点询问保修，不下单。'],'expected':{'selected':'乙'}}]},
 {'id':'shadow-journal','domain':'documents','skill':'journal-review','turns':[
  {'prompt':'整理操作日志，失败原因未确认，不能编造原因或效果。JSON字段document、status（failed）。',
   'facts':['数据导出失败，原因未知。'],'plans':['明天10点检查日志，不重跑导出。'],'expected':{'status':'failed'}},
  {'prompt':'更正操作状态，原来不是失败而是尚未开始；已确认计划没有撤销。若认为需要调整计划，只写未采纳建议。JSON字段document、status（not_started）。',
   'facts':['数据导出尚未开始。'],'plans':['明天10点检查日志，不重跑导出。'],'expected':{'status':'not_started'}}]},
 {'id':'shadow-learning','domain':'learning','skill':'english-coach','turns':[
  {'prompt':'整理学习复盘；只看讲解不等于掌握，没有独立作答或延迟复测不能编造学习成效。JSON字段document、independent_mastery（布尔）、retention（未测填null）。',
   'facts':['学习者只看过过去式讲解，尚未独立作答。'],'plans':['周五19点独立复测过去式。'],'expected':{'independent_mastery':False,'retention':None}},
  {'prompt':'明确撤销旧时间并改期，学习事实不变；不要恢复旧计划，也不要提前声称完成。JSON字段document、independent_mastery、retention。',
   'facts':['学习者只看过过去式讲解，尚未独立作答。'],'plans':['周六10点独立复测过去式。'],'expected':{'independent_mastery':False,'retention':None}}]}
]
common='\n只在reply中输出JSON，不创建后台任务，不执行外部动作。document为Markdown正文。'
excerpt='''\n另给evidence，严格只有facts、plans、suggestions。facts与plans分别是{source,quote}数组，按宿主本轮核对依据的编号和原文逐字引用全部当前事实、计划；suggestions为单行字符串数组，可为空，均未采纳。document严格按evidence顺序生成三个段落：标题依次“## 事实”“## 已确认计划”“## 建议（未采纳）”，标题后换行，事实/计划每行“- [编号] 原文”，建议每行“- 建议文字”；空数组写“- 无”；段落间一个空行，无其他正文。'''
inputs={'schema':'jarvis.delivery-inputs.v1','cases':{c['id']:[{'expected_revision':i,'facts':t['facts'],'plans':t['plans']} for i,t in enumerate(c['turns'])] for c in data}}
for version in (1,2):
 cases=[]
 for c in data:
  turns=[]
  for t in c['turns']:
   turn={'prompt':t['prompt']+common+(excerpt if version==2 else ''),'expected':t['expected'],'unordered':[],'text_fields':['document'],'forbidden':{}}
   if version==2:
    sources={prefix+str(i):q for field,prefix in [('facts','F'),('plans','P')] for i,q in enumerate(t[field],1)}
    turn['body_evidence']={'sources':sources,'facts':['F'+str(i) for i in range(1,len(t['facts'])+1)],'plans':['P'+str(i) for i in range(1,len(t['plans'])+1)]}
   turns.append(turn)
  cases.append({k:c[k] for k in ('id','domain','skill')}|{'turns':turns})
 value={'schema':'jarvis.work-trials.v'+str(version),'origin':'synthetic','provenance':'Three first-party scenarios; same explicit user declarations in free-prose and source-excerpt formats. No automatic extraction or independent user data.','cases':cases}
 p=ROOT/'tests/fixtures'/('delivery_shadow_v'+str(version)+'.json')
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=ROOT/'tests/fixtures/delivery_shadow_inputs.json'
with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(inputs,f,ensure_ascii=False,indent=2);f.write('\n')
print('Frozen three scenarios, two formats and a separate explicit user-input pack')
