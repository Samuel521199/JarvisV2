"""Record source changes, costs, interruption, and post-hoc qualitative review."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from tools.accept_frozen import sources

read=lambda p:json.loads(p.read_text('utf-8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=sources(ROOT);before=read(HERE/'plan.json')['source_before']
changed=[{'path':p,'before':before.get(p),'after':now.get(p)} for p in sorted(now.keys()|before.keys()) if now.get(p)!=before.get(p)]
write(HERE/'candidate-audit.json',{'source_count':len(now),'changed_sources':changed,'production_deployed':False})
assert len(changed)==19
summaries=[read(HERE/name/'summary.json') for name in ['live-prose-r1','live-excerpt-r1']]
write(HERE/'cost-overview.json',{'calls':sum(x['costs']['attempts'] for x in summaries),
      'known_tokens':sum(x['costs']['known_tokens'] for x in summaries),
      'known_api_estimate_usd':sum(x['costs']['known_api_estimates']['USD'] for x in summaries),
      'tokens_complete':all(x['costs']['tokens_complete'] for x in summaries),
      'full_cost':None,'missing':['human effort','local compute','supplier invoice reconciliation'],
      'underlying_scenarios':3,'formats':2,'workflow_arms':2,'turns_per_scenario':2,
      'independent_real_user_samples':0,'quality_gain':None,'learning_gain':None})
assert not (HERE/'frozen-r1/result.json').exists()
write(HERE/'frozen-r1-interruption.json',{'observed_at':datetime.now(timezone.utc).isoformat(),
      'state':'INCOMPLETE','last_log':'RUN regression','result_file_present':False,
      'process_present_when_resumed':False,'cause':'UNKNOWN; no successful completion receipt',
      'decision':'Retain incomplete evidence. Rerun all unchanged gates against final source in frozen-r2; never count r1 as pass.'})
rows=[]
for p in sorted((HERE/'live-prose-r1/turns').glob('*.result.json')):
    r=read(p);domain=r['case_id'];turn=r['turn'];arm=r['arm']
    if domain=='shadow-quote':
        note='报价、约束、选择和明天10点询问保修/不下单的计划均保留；未声称实际下单。';risk=None
    elif domain=='shadow-journal':
        note='失败原因未知/更正为尚未开始得到保留；原明天10点检查日志、不重跑计划保留。'
        risk='workflow_on第0轮增加“当前无进行中导出任务”，用户未提供该事实。' if arm=='workflow_on' and turn==0 else None
        if turn==1:note+=' 调整建议单独标为未采纳；没有覆盖当前计划。'
    else:
        note='没有独立作答的证据状态、mastery=false/retention=null得到保留；改期后明确撤销周五并采用周六10点。' if turn else '没有独立作答的证据状态、mastery=false/retention=null与周五19点复测计划保留。'
        risk='“完成讲解的学习”可能夸大“只看过讲解”，应使用来源原意；未把独立掌握设为true。' if turn==0 else None
    rows.append({'record':p.relative_to(HERE).as_posix(),'record_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                 'case_id':domain,'arm':arm,'turn':turn,'observation':note,'remaining_risk':risk,
                 'shadow_state':r['delivery_review']['state'],'formal_quality_score':None})
write(HERE/'prose-review.json',{'reviewer':'Codex assistant, post-hoc qualitative inspection of all twelve free-prose replies',
      'independent_human_review':False,'preset_semantic_acceptance':False,'reviewed_replies':len(rows),'rows':rows,
      'conclusion':'All twelve REVIEW signals are not twelve verified semantic defects. These selected inputs show plan retention but still permit unsupported additions and overstatement.',
      'original_issues':{'TRIAL-SEM-01':'OPEN','TRIAL-SEM-02':'OPEN'},'quality_gain':None})
print(json.dumps({'changed_sources':len(changed),'source_count':len(now),'reviewed_replies':len(rows)}))
