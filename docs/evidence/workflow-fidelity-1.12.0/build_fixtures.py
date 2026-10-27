"""Freeze new synthetic scenarios before observing model answers."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
FORMAT='''只在本轮reply中输出JSON，不建后台任务、不实际保存或发送、不安排提醒。
JSON除本题要求的字段外，还必须有evidence和document。evidence恰好包含facts、plans、suggestions。
facts与plans是数组，每项恰好是source（原文编号）、quote（逐字原文）两个字符串；选择当前有效事实和仍被确认的计划，不能混入过期资料或建议。不改写摘录。suggestions是最多5条单行建议字符串，可为空；建议尚未被采纳，不能放入已确认计划。
document必须严格从evidence生成Markdown：三个段落依次为“## 事实”“## 已确认计划”“## 建议（未采纳）”；标题后换行，每条事实/计划为“- [编号] 原文”，建议为“- 建议文字”；空数组写“- 无”；段落之间一个空行。不加其他正文或代码围栏，不改变证据顺序。原文中的Markdown特殊字符须反斜线转义。字段与正文必须一致。'''

def turn(prompt,sources,facts,plans,expected):
    return {'prompt':prompt+'\n可引用原文（包含可能已失效的历史条目；按上下文选择）：\n'+ '\n'.join(k+'：'+v for k,v in sources.items())+'\n'+FORMAT,
            'expected':expected,'unordered':[],'text_fields':['document'],'forbidden':{},
            'body_evidence':{'sources':sources,'facts':facts,'plans':plans}}
def case(ident,domain,skill,turns):return {'id':ident,'domain':domain,'skill':skill,'turns':turns}

cases=[]
s={'F1':'甲方案价格80元，交期3天。','F2':'乙方案价格75元，交期4天。','P1':'明天10点询问两个方案的保修条款。'}
cases.append(case('compare-price-revision','comparison','none',[
    turn('比较报价：预算100元、最多5天，选符合条件的最低价；selected填甲或乙。保修尚未查询；计划不是已执行事实。',s,['F1','F2'],['P1'],{'selected':'乙'}),
    turn('更正：F3替换F2，乙价格应为95元。其余条件和已确认计划不变。重新选择，保留未被修改的约束；selected填甲或乙。',{**s,'F3':'乙方案价格95元，交期4天。'},['F1','F3'],['P1'],{'selected':'甲'})]))
s={'F1':'丙方案价格210元，交期2天。','F2':'丁方案价格190元，交期8天。','P1':'周四15点复核报价，不提交订单。'}
cases.append(case('compare-explicit-plan-change','comparison','none',[
    turn('预算220元且最多3天，selected填丙或丁；不得把报价视为已采购。',s,['F1','F2'],['P1'],{'selected':'丙'}),
    turn('明确撤销P1，改为P2；报价与约束不变。selected仍按合格最低价填。',{**s,'P2':'周五11点复核报价，不提交订单。'},['F1','F2'],['P2'],{'selected':'丙'})]))
s={'F1':'数据导出失败，原因未知。','F2':'本次资料整理耗时35分钟。','P1':'周五9点检查导出日志，不重跑导出。'}
cases.append(case('document-export-correction','documents','journal-review',[
    turn('整理操作记录，禁止猜测失败原因或把计划写成已完成。export_status填failed，minutes填整数。',s,['F1','F2'],['P1'],{'export_status':'failed','minutes':35}),
    turn('更正F1和F2：实际上尚未启动导出，耗时20分钟；P1没有撤销。若新事实使旧计划值得调整，只能提出建议，不能静默改计划。export_status填not_started。',{**s,'F3':'数据导出尚未启动。','F4':'本次资料整理耗时20分钟。'},['F3','F4'],['P1'],{'export_status':'not_started','minutes':20})]))
s={'F1':'记录甲写本周预算300元。','F2':'记录乙写本周预算360元。','P1':'周三18点核对预算，不付款。'}
cases.append(case('document-budget-retirement','documents','journal-review',[
    turn('两份记录没有时间和权威可判断有效性；保持冲突，不求和、不擅自取舍。budget无法确定填null，conflict填布尔。',s,['F1','F2'],['P1'],{'budget':None,'conflict':True}),
    turn('现在明确以记录乙为准，记录甲失效；撤销P1，尚未确认其他计划。budget和conflict按当前有效记录填写。',s,['F2'],[],{'budget':360,'conflict':False})]))
s={'F1':'学习者只看过过去式讲解，没有独立答题。','P1':'周日19点独立回忆过去式，练习10分钟。'}
cases.append(case('learning-exposure-correction','learning','english-coach',[
    turn('整理学习复盘，不替学习者宣布掌握。independent_mastery填布尔，delayed_retention没有测过填null。',s,['F1'],['P1'],{'independent_mastery':False,'delayed_retention':None}),
    turn('更正F1：学习者其实还没有看讲解。原P1仍然有效。不要因学习起点变化擅自把复习安排换成别的任务。',{**s,'F2':'学习者尚未阅读过去式讲解。'},['F2'],['P1'],{'independent_mastery':False,'delayed_retention':None})]))
s={'F1':'学习者在提示后答对一道主谓一致题。','P1':'下周五20点进行不提示的延迟复测。'}
cases.append(case('learning-single-answer-limit','learning','english-coach',[
    turn('形成学习卡。提示后答对不算独立掌握。independent_answers填整数，delayed_retention未测填null。',s,['F1'],['P1'],{'independent_answers':0,'delayed_retention':None}),
    turn('新增F2是后续一题的表现，保留F1历史事实；只有这一题无提示正确，不可证明广泛掌握或延迟保持。明确撤销P1，暂不安排下次。',{**s,'F2':'学习者随后无提示独立答对一道主谓一致题。'},['F1','F2'],[],{'independent_answers':1,'delayed_retention':None})]))

reserved=[]
s={'F1':'红方案价格500元，交期10天。','F2':'蓝方案价格600元，交期2天。','P1':'下周一上午核实库存，不购买。'}
reserved.append(case('reserved-no-eligible','comparison','none',[
    turn('预算550元且最多4天；没有合格方案时selected填null，不擅自放宽条件。',s,['F1','F2'],['P1'],{'selected':None}),
    turn('F3更正F1的交期，其他条件与计划不变；selected填红或蓝或null。',{**s,'F3':'红方案价格500元，交期3天。'},['F3','F2'],['P1'],{'selected':'红'})]))
s={'F1':'音频转写没有成功，原因未确认。','P1':'明晚8点检查转写输入，不重新转写。'}
reserved.append(case('reserved-transcription-context','documents','journal-review',[
    turn('整理记录，不把失败推断成网络、内存或格式问题。status填failed。',s,['F1'],['P1'],{'status':'failed'}),
    turn('F2更正F1；P1保持不变，任何调整只作为建议。status填not_started。',{**s,'F2':'音频转写尚未开始。'},['F2'],['P1'],{'status':'not_started'})]))
s={'F1':'学习者阅读了分数加法例题，没有独立计算。','P1':'周六16点独立完成一道分数加法题。'}
reserved.append(case('reserved-math-reschedule','learning','english-coach',[
    turn('整理数学学习复盘，independent_mastery填布尔，retention未测填null，不虚构进步。',s,['F1'],['P1'],{'independent_mastery':False,'retention':None}),
    turn('已明确改期：P2替换P1，学习事实不变。旧时间不得继续作为当前计划；建议不能冒充采纳。',{**s,'P2':'周日14点独立完成一道分数加法题。'},['F1'],['P2'],{'independent_mastery':False,'retention':None})]))
for name,rows in [('work_fidelity_v2.json',cases),('work_fidelity_reserved_v2.json',reserved)]:
    suite={'schema':'jarvis.work-trials.v2','origin':'synthetic','provenance':'First-party synthetic scenarios frozen before model execution. Reserved cases are a procedural holdout, not independent human data.', 'cases':rows}
    target=ROOT/'tests/fixtures'/name
    with target.open('x',encoding='utf-8',newline='\n') as f:json.dump(suite,f,ensure_ascii=False,indent=2);f.write('\n')
    print(name,len(rows),'cases')
