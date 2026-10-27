"""Render recorded trial outcomes without turning field checks into quality scores."""
from pathlib import Path
from collections import Counter
import hashlib
import html
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
read=lambda p:json.loads((HERE/p).read_text('utf-8'))
def write(p,value):
    (HERE/p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

run=read('frozen-r1/run/report.json');tests=read('frozen-r1/run/tests.json')
snapshot=read('frozen-r1/snapshot.json');wrapper=read('frozen-r1/result.json')
assert run['local_verdict']==wrapper['local_verdict']=='PASS' and tests['passed']
baseline=json.loads((HERE.parent/'workflow-recovery-1.10.0/frozen-r2/run/plan.json').read_text('utf-8'))['test_ids']
current=read('frozen-r1/run/plan.json')['test_ids'];missing=sorted(set(baseline)-set(current));assert not missing
perf=read('frozen-r1/run/performance.json');off=perf['task_ms']['False']['p95'];on=perf['task_ms']['True']['p95']
rounds={name:read(name+'/summary.json') for name in ('live-r1','live-r2','live-r3','live-r4')}
records={name:[json.loads(p.read_text('utf-8')) for p in sorted((HERE/name/'turns').glob('*.result.json'))] for name in rounds}
counts={name:dict(Counter(r['assessment']['state'] for r in values)) for name,values in records.items()}
before=read('plan.json')['source_before'];after=snapshot['source_digests']
changes=[{'path':p,'before':before.get(p),'candidate':after.get(p),'created':p not in before} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
assert hashlib.sha256((HERE.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f'
assert hashlib.sha256((ROOT/'host/work_status.py').read_bytes()).hexdigest()=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10'
write('candidate-audit.json',{'changed_sources':changes,'original_forecast_preserved':True,'old_work_status_preserved':True,'frozen_result':wrapper,'production_deployed':False})
pooled=Counter(r['assessment']['state'] for name in ('live-r3','live-r4') for r in records[name])
verification={'version':'workflow-trials-1.11.0','local_verdict':'PASS','tests':tests['run'],
    'baseline_retained':len(baseline),'added_to_union':len(set(current)-set(baseline)),'new_trial_tests':24,'existing_personal_workflow_tests_added':4,
    'missing_baseline':missing,'browser_workflows':12,'gates':len(run['checks']),'source_count':snapshot['source_count'],
    'supporting_count':len(snapshot['supporting_input_digests']),'original_observer_p95_ms':{'off':off,'on':on,'added':round(on-off,3),'budget':25},
    'round_turn_counts':counts,'postfix_pooled_turns':dict(pooled),'independent_synthetic_cases':6,
    'quality_gain':None,'learning_gain':None,'emotion_quality':None,'full_cost':None,'real_work_gain':None,'all_functional_excellence_verified':False,'production_deployed':False}
write('verification.json',verification)
domains={'comparison':'报价 / 多约束比较','documents':'资料整理 / 文档','learning':'学习 / 复盘'}
def states(d):return f"{d['PASS']}通过 · {d['FAIL']}失败 · {d['UNMEASURED']}待测"
domain_rows=''
for d,label in domains.items():
    for name in ('live-r3','live-r4'):
        v=rounds[name]['domains'][d]
        domain_rows+=f'<tr><td>{label}</td><td>{name}</td><td>{states(v["workflow_off"])}</td><td>{states(v["workflow_on"])}</td></tr>'
round_rows='';known_costs={};unknown_cost=0
for name,v in rounds.items():
    c=v['costs'];unknown_cost+=c['unpriced_attempts']
    for currency,amount in c['known_api_estimates'].items():known_costs[currency]=known_costs.get(currency,0)+amount
    money=' / '.join(f'{k} {a:.6f}' for k,a in c['known_api_estimates'].items())
    n=counts[name]
    round_rows+=f'<tr><td><a href="{name}/summary.json">{name}</a></td><td>{v["recorded_turns"]}/24</td><td>{n.get("PASS",0)} / {n.get("FAIL",0)} / {n.get("UNMEASURED",0)}</td><td>{v["complete_pairs"]}/6</td><td>{c["known_tokens"]:,}</td><td>{money}<br>未知 {c["unpriced_attempts"]} 次</td></tr>'
money=' / '.join(f'{k} {a:.6f}' for k,a in known_costs.items())
write('cost-overview.json',{'rounds':{n:v['costs'] for n,v in rounds.items()},'known_api_estimates_all_rounds':known_costs,'unpriced_attempts':unknown_cost,'full_cost':None,'note':'All exploratory and repeat calls retained. Token usage and supplier prices are reported snapshots, not reconciled invoices.'})
failures=''
for name in ('live-r3','live-r4'):
    for r in records[name]:
        if r['assessment']['state']=='PASS':continue
        key=f'{r["case_id"]}-{r["arm"]}-{r["turn"]}'
        failures+=f'<li><a href="{name}/turns/{key}.result.json">{name} / {key}</a>：{html.escape(str(r["error"] or r["failure_stage"]))}，{r["assessment"]["state"]}。</li>'
gates=''.join(f'<tr><td>{html.escape(c["id"])}</td><td>{c["status"]}</td></tr>' for c in run['checks'])
details=''
for name in ('live-r3','live-r4'):
    for r in records[name]:
        key=f'{r["case_id"]}-{r["arm"]}-{r["turn"]}'
        artifacts=' '.join(f'<a href="{name}/{html.escape(a["file"])}">{html.escape(a["kind"])}</a>' for a in r['artifacts'])
        details+=f'<tr><td>{name}<br>{html.escape(key)}</td><td>{r["assessment"]["state"]}</td><td><a href="{name}/turns/{key}.result.json">原记录</a> {artifacts}</td></tr>'
css='''*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e9f0f8;font:17px/1.7 system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:40px 24px}h1{font-size:39px;line-height:1.25}h2{font-size:25px;margin-top:36px}p{color:#c4cfdf}a{color:#82cfff;overflow-wrap:anywhere}strong{color:#87e5c0}.label{font-size:13px;letter-spacing:2px;color:#82cfff}.cards,.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,.flow>div{border:1px solid #34506b;background:#132239;border-radius:12px;padding:18px}.value{font-size:30px;display:block;color:#87e5c0}.small{font-size:14px;color:#adbdcf}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:15px}th,td{padding:13px;border-bottom:1px solid #30455e;text-align:left;vertical-align:top;min-width:100px}th{color:#82cfff}.note{border-left:3px solid #ecba6a;padding:12px 18px;background:#172133}.flow{grid-template-columns:repeat(5,1fr);font-size:15px}details{border:1px solid #34506b;border-radius:12px;padding:16px;margin:22px 0}summary{cursor:pointer}code{overflow-wrap:anywhere}.bar{display:flex;height:24px;border-radius:6px;overflow:hidden;background:#35455b}.pass{background:#4ca98a}.fail{background:#dd7870}.unknown{background:#d7ab61}.legend{font-size:14px;color:#bbc8db}li{margin:8px 0}img{width:100%;max-width:390px}@media(max-width:720px){main{padding:24px 16px}h1{font-size:29px}.cards,.flow{grid-template-columns:repeat(2,1fr)}.flow>div:last-child{grid-column:span 2}}'''
bars=''
for name in ('live-r3','live-r4'):
    n=counts[name];bars+=f'<p>{name}：{n.get("PASS",0)}通过 / {n.get("FAIL",0)}失败 / {n.get("UNMEASURED",0)}待测</p><div class="bar" role="img" aria-label="{html.escape(name+str(n))}">'
    for key,style in [('PASS','pass'),('FAIL','fail'),('UNMEASURED','unknown')]:
        if n.get(key):bars+=f'<span class="{style}" style="flex:{n[key]}"></span>'
    bars+='</div>'
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis 1.11 三领域对照验收</title><style>{css}</style><main>
<div class="label">JARVIS · WORKFLOW TRIALS 1.11.0</div><h1>三类都测，失败要能定位，进步要有证据</h1>
<p><strong>三领域的采集、对照和失败归因已实现，并修正了真实试跑暴露的助手协议与回复路由提示。</strong> 原有完整技术验收通过；本轮仍不能认证“全功能都优秀”。</p>
<p class="note">修复后两轮合计：{pooled.get('PASS',0)}轮硬条件通过、{pooled.get('FAIL',0)}轮失败、{pooled.get('UNMEASURED',0)}轮待测。仍只有6个不同合成任务；真实模型 ≠ 独立真实任务。Q、学习增益、情绪体验及完整费用未测，未部署生产。</p>
<p class="note">正文补审仍发现缺口：r4将“烘焙失败”扩写成“异常中断”；更正后没有保留“明天排查”，改为“启动并执行”。字段通过不代表正文忠实。详见<a href="semantic-review.json">事后语义问题记录</a>；它不追改冻结分数，也不是独立人工评分。</p>
<div class="cards"><div class="card"><b class="value">{tests['run']}</b>不同回归用例<br><span class="small">原510＋新24＋原有4补入联合验收</span></div><div class="card"><b class="value">12 / {len(run['checks'])}</b>浏览器流程 / 验收门<br><span class="small">全部通过，原门槛保留</span></div><div class="card"><b class="value">3 × 2</b>领域 × 不同任务<br><span class="small">重复试跑不增加独立样本数</span></div><div class="card"><b class="value">未签收</b>全功能优秀<br><span class="small">不能用工程绿灯代替业务质量</span></div></div>
<h2>改了什么，实际效果如何</h2><div class="scroll"><table><tr><th>改进</th><th>预测效果</th><th>实际观察</th><th>仍差什么</th></tr>
<tr><td>冻结参考、配置与代码，分域对照</td><td>能复核哪类退步，避免平均分掩盖失败</td><td>报价、文档、学习分别记录；缺测不填零；失败后缺轮不算完整配对</td><td>六个合成任务不足以推断泛化</td></tr>
<tr><td>区分外层助手协议与reply内JSON</td><td>减少assistant_invalid</td><td>第二轮的协议失败在第三轮未复现；第四轮独立保留于下表</td><td>随机生成仍可能波动；不能宣称根治</td></tr>
<tr><td>明确仅回复时使用chat</td><td>整理文档不误建Goal</td><td>第三轮所有已交付回复走原chat路径；外部动作仍受原Goal规则控制</td><td>需测试开放表达、长文和相反意图</td></tr>
<tr><td>试验推理LOW、上限4096</td><td>给正文留下输出空间</td><td>1800上限时的截断在后续轮次未复现；不修改用户默认配置</td><td>推理档位与上限一起变更，不能独立归因或认定最优</td></tr>
<tr><td>保留原始协议、回执与文件</td><td>把超时、协议、路由、内容和交付分开定位</td><td>第三轮一次60秒model_timeout保留UNKNOWN，费用用量未知</td><td>并未因此实现自动网络自愈或安全重试</td></tr></table></div>
<h2>三类分别看，任何一类缺口都保留</h2><div class="scroll"><table><tr><th>领域</th><th>修复后轮次</th><th>关闭工作流：2个任务</th><th>开启工作流：2个任务</th></tr>{domain_rows}</table></div>
<p>报价是none/none的同路径控制；文档使用journal-review，学习使用english-coach。两组都使用当前助手代码，不能把两组差异解释为整个1.11版本的净收益。</p>
{bars}<p class="legend">绿：冻结硬条件通过；红：明确失败；黄：未测。轮次通过率不是质量总分。</p><ul>{failures or '<li>修复后未记录新的失败或缺测；仍须扩展独立样本。</li>'}</ul>
<h2>怎样接成可复验的改进循环</h2><div class="flow"><div>① 事前冻结<br>来源、目标、参考、预算</div><div>② 原助手执行<br>两配置，隔离会话</div><div>③ 保存事实<br>模型输出、交付文件、用量</div><div>④ 分域归因<br>通过 / 失败 / 待测</div><div>⑤ 修复后新测<br>保留旧失败，再决定采用</div></div>
<p>三位一体仍使用原定向、协作和观察职责；新增纯检查模块不获得执行权限。正式评分、记忆和知识库不写回：试验经验先成为待验证候选，经过未见任务、反例和成本核对后才谈采用。</p>
<h2>全部试跑与代价，失败也计入</h2><div class="scroll"><table><tr><th>轮次</th><th>已记录/预定</th><th>通过/失败/待测</th><th>完整配对</th><th>已知token</th><th>API估算</th></tr>{round_rows}</table></div>
<p>全部已知API估算合计 {money}，另有{unknown_cost}次用量或价格未知。费率来自调用时SDK快照，尚未与供应商账单核销；人工、本机计算未合并，完整成本为未知。第一轮v1把响应失败列待测，后续v2明确区分失败与UNKNOWN；旧统计不追改。</p>
<p>第一轮MEDIUM/1800，第二轮LOW/4096，第三轮修正提示，第四轮同源独立复测。跨轮结果只描述观察，不作因果结论；第四轮不能覆盖第三轮超时。原预测JPF与host/work_status.py摘要保持。</p>
<h2>下一步的顺序和采用条件</h2><div class="scroll"><table><tr><th>顺序</th><th>实施内容</th><th>通过后能得到什么</th></tr>
<tr><td>1 三域未见题</td><td>优先补正文事实/推断/建议分离、计划保留与字段一致性；再用独立真实请求、长文和矛盾资料冻结参考与复核</td><td>避免“字段正确、正文失真”，知道修复是否泛化，补误放行、误拒、人工介入统计</td></tr>
<tr><td>2 可用性与费用</td><td>给超时分类；只对可证明无外部副作用的读取设计有界重试，并对账用量与费用</td><td>减少瞬时波动导致的丢交付；未知效果不被盲目重放</td></tr>
<tr><td>3 条件化经验</td><td>只存适用前提、来源、反例、版本、收益及失效条件；未见题受益才晋升</td><td>更快更省的证据成立后才能复用，不把偶然通过变成教条</td></tr>
<tr><td>4 扩大自治与协作</td><td>完整费用和委托范围先接通，再接单任务负责人、多Bot责任与恢复链</td><td>减少不必要决策，同时能定位责任和回滚退步</td></tr></table></div>
<p>陪伴和教学并行补用户体验、独立作答与延迟复测。温柔的一句鼓励不等于情绪效果已验证；答对样例不等于用户真的学会。后续执行顺序仍归原K路线，不新增第二条时间线。</p>
<details><summary>查看技术验收、失败历史与来源</summary><p>{snapshot['source_count']}个源码输入、{len(snapshot['supporting_input_digests'])}个支持输入冻结。原观察器p95：关闭{off:.3f}ms → 开启{on:.3f}ms，增加{on-off:.3f}ms，原门限25ms。</p><div class="scroll"><table><tr><th>门</th><th>结果</th></tr>{gates}</table></div><p><a href="frozen-r1/run/report.json">完整验收</a> · <a href="verification.json">汇总</a> · <a href="candidate-audit.json">变更清单</a> · <a href="delivery-checks.json">交付审计</a> · <a href="plan.json">事前计划</a> · <a href="plan-amendment-r1.json">配置修订</a> · <a href="plan-amendment-r2.json">提示修订</a> · <a href="plan-amendment-r3.json">独立复测约定</a></p><p>离线首轮替身忽略会话上下文、证据.md触发章节登记检查的失败均保留。前两轮原包已逐字节核对后封存为<a href="live-r1-original.zip">r1 ZIP</a>、<a href="live-r2-original.zip">r2 ZIP</a>；阅读副本改.md.txt，原记录与旧相对路径在ZIP中完整保留。</p></details>
<details><summary>查看修复后每轮的原始结果与交付文件</summary><div class="scroll"><table><tr><th>样本</th><th>硬条件</th><th>可回读证据</th></tr>{details}</table></div></details>
<p class="small"><a href="../../delivery-validation.md#workflow-trials-evidence">权威验收章节</a> · <a href="../../core-bootstrap.md#workflow-trials-runtime">操作与实施边界</a> · <a href="../../../README.md">工程入口</a></p></main></html>'''
(HERE/'report.html').write_text(page,encoding='utf-8',newline='\n')
print(json.dumps({'verification':verification,'report':'report.html'},ensure_ascii=False))
