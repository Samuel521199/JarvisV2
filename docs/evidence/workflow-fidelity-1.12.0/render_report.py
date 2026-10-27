"""Measured fidelity report: source-excerpt checks and free-prose review stay separate."""
from pathlib import Path
from collections import Counter
import hashlib
import html
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads((HERE/p).read_text('utf-8'))
def write(p,v):(HERE/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
run=read('frozen-r1/run/report.json');tests=read('frozen-r1/run/tests.json');snapshot=read('frozen-r1/snapshot.json');wrapper=read('frozen-r1/result.json')
assert wrapper['local_verdict']==run['local_verdict']=='PASS' and tests['passed']
baseline_ids=json.loads((HERE.parent/'workflow-trials-1.11.0/frozen-r1/run/plan.json').read_text('utf-8'))['test_ids']
ids=read('frozen-r1/run/plan.json')['test_ids'];missing=sorted(set(baseline_ids)-set(ids));assert not missing
perf=read('frozen-r1/run/performance.json');off=perf['task_ms']['False']['p95'];on=perf['task_ms']['True']['p95']
names=('baseline-r1','candidate-r1','reserved-r1','v1-replay-r1')
summaries={n:read(n+'/summary.json') for n in names}
records={n:[json.loads(p.read_text('utf-8')) for p in sorted((HERE/n/'turns').glob('*.result.json'))] for n in names}
counts={n:dict(Counter(state for c in s['cases'] for arm in c['arms'].values() for state in arm['turn_states'])) for n,s in summaries.items()}
base=read('baseline-r1/frozen.json')['source_digests'];candidate=read('candidate-r1/frozen.json')['source_digests']
pair_diff=sorted(p for p in base.keys()|candidate.keys() if base.get(p)!=candidate.get(p));assert pair_diff==['host/assistant.py']
assert candidate==snapshot['source_digests']
for n in ('reserved-r1','v1-replay-r1'):assert read(n+'/frozen.json')['source_digests']==candidate
before=read('plan.json')['source_before'];after=snapshot['source_digests']
changes=[{'path':p,'before':before.get(p),'candidate':after.get(p),'created':p not in before} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
forecast=hashlib.sha256((HERE.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()
status=hashlib.sha256((ROOT/'host/work_status.py').read_bytes()).hexdigest()
assert forecast=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f'
assert status=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10'
write('candidate-audit.json',{'changed_sources':changes,'paired_source_differences':pair_diff,'original_forecast_preserved':True,'old_work_status_preserved':True,'frozen_result':wrapper,'production_deployed':False})
pooled=Counter()
for n in ('candidate-r1','reserved-r1'):pooled.update(counts[n])
v={'version':'workflow-fidelity-1.12.0','local_verdict':'PASS','tests':tests['run'],'baseline_retained':len(baseline_ids),'new_tests':len(set(ids)-set(baseline_ids)),
   'missing_baseline':missing,'browser_workflows':12,'gates':len(run['checks']),'source_count':snapshot['source_count'],'supporting_count':len(snapshot['supporting_input_digests']),
   'original_observer_p95_ms':{'off':off,'on':on,'added':round(on-off,3),'budget':25},'round_counts':counts,
   'candidate_v2_pooled':dict(pooled),'paired_source_differences':pair_diff,'new_synthetic_cases':9,'replayed_v1_cases':6,
   'free_prose_verdict':'NOT_ACCEPTED','open_prior_issues':['TRIAL-SEM-01','TRIAL-SEM-02'],'automatic_knowledge_promotion':False,
   'independent_user_cases':0,'formal_quality_score':None,'quality_gain':None,'learning_gain':None,'emotion_quality':None,'full_cost':None,'production_deployed':False}
write('verification.json',v)
write('adoption-review.json',{'kind':'report_only_not_runtime_policy','engineering_verdict':'PASS','bounded_excerpt_evidence':'See frozen per-domain checks; do not substitute for arbitrary prose',
    'free_prose_verdict':'NOT_ACCEPTED','open_prior_issues':['TRIAL-SEM-01','TRIAL-SEM-02'],'production_deployed':False,'automatic_knowledge_promotion':False,
    'decision':'Retain source-excerpt checks as implemented test capability. Do not label prompt-only repair as verified free-prose fidelity or use it to auto-approve arbitrary documents.',
    'next_evidence':'Visible source/current-plan representation, independent real tasks and calibrated false-accept/false-reject measurement before automatic completion gating.'})
costs={};unknown=0;tokens=0;calls=0
for s in summaries.values():
    c=s['costs'];unknown+=c['unpriced_attempts'];tokens+=c['known_tokens'];calls+=c['attempts']
    for currency,amount in c['known_api_estimates'].items():costs[currency]=costs.get(currency,0)+amount
write('cost-overview.json',{'rounds':{n:s['costs'] for n,s in summaries.items()},'known_api_estimates':costs,'unpriced_attempts':unknown,'known_tokens':tokens,'calls':calls,'full_cost':None,'reconciled_invoice':False})
money=' / '.join(f'{k} {value:.6f}' for k,value in costs.items())
def count_text(d):return f'{d.get("PASS",0)}通过 / {d.get("FAIL",0)}失败 / {d.get("UNMEASURED",0)}待测'
rows=''
for d,label in [('comparison','报价与多约束比较'),('documents','资料整理与文档'),('learning','学习复盘')]:
    for n in names:
        s=summaries[n]['domains'][d]
        rows+=f'<tr><td>{label}</td><td>{n}</td><td>{count_text(s["workflow_off"])}</td><td>{count_text(s["workflow_on"])}</td></tr>'
round_rows='';bars=''
for n in names:
    s=summaries[n];c=s['costs'];money_one=' / '.join(f'{k} {a:.6f}' for k,a in c['known_api_estimates'].items())
    round_rows+=f'<tr><td><a href="{n}/summary.json">{n}</a></td><td>{s["recorded_turns"]}/{s["planned_turns"]}</td><td>{count_text(counts[n])}</td><td>{s["complete_pairs"]}/{s["independent_cases"]}</td><td>{money_one}<br>未知{c["unpriced_attempts"]}次</td></tr>'
    bars+=f'<p>{n}：{count_text(counts[n])}</p><div class="bar" role="img" aria-label="{html.escape(count_text(counts[n]))}">'
    for key,style in [('PASS','good'),('FAIL','bad'),('UNMEASURED','unknown')]:
        if counts[n].get(key):bars+=f'<span class="{style}" style="flex:{counts[n][key]}"></span>'
    bars+='</div>'
fail_rows=''
for n in names:
    for r in records[n]:
        if r['assessment']['state']=='PASS':continue
        key=f'{r["case_id"]}-{r["arm"]}-{r["turn"]}'
        failures=', '.join(c['id'] for c in r['assessment']['checks'] if c['status']!='passed')
        fail_rows+=f'<tr><td><a href="{n}/turns/{key}.result.json">{n}<br>{key}</a></td><td>{r["assessment"]["state"]}</td><td>{html.escape(str(r["error"] or failures))}</td></tr>'
review=read('prose-review.json');review_rows=''
for issue in review['findings']:
    review_rows+=f'<tr><td>{html.escape(issue["id"])}</td><td>{html.escape(issue["observation"])}</td><td>{html.escape(issue["status"])}</td></tr>'
gates=''.join(f'<tr><td>{html.escape(c["id"])}</td><td>{c["status"]}</td></tr>' for c in run['checks'])
css='''*{box-sizing:border-box}body{margin:0;background:#0a1220;color:#e8eff8;font:17px/1.72 system-ui,sans-serif}main{max-width:1140px;margin:auto;padding:42px 24px}h1{font-size:39px;line-height:1.25}h2{font-size:25px;margin-top:36px}p{color:#c4d0df}a{color:#80d3ff;overflow-wrap:anywhere}strong{color:#80e0bb}.tag{letter-spacing:2px;font-size:13px;color:#80d3ff}.cards,.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,.flow>div{background:#14243b;border:1px solid #34506c;border-radius:12px;padding:18px}.number{font-size:30px;display:block;color:#80e0bb}.small{font-size:14px;color:#aebed3}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;vertical-align:top;padding:13px;border-bottom:1px solid #30465f;min-width:100px}th{color:#80d3ff}.note{border-left:3px solid #dfb16b;padding:12px 18px;background:#172236}.flow{grid-template-columns:repeat(5,1fr);font-size:15px}.bar{height:22px;border-radius:5px;display:flex;overflow:hidden}.good{background:#4cac89}.bad{background:#d37670}.unknown{background:#d4aa62}details{border:1px solid #34506c;border-radius:12px;padding:16px;margin:24px 0}summary{cursor:pointer}code{overflow-wrap:anywhere}li{margin:8px 0}@media(max-width:720px){main{padding:24px 16px}h1{font-size:29px}.cards,.flow{grid-template-columns:repeat(2,1fr)}.flow>div:last-child{grid-column:span 2}}'''
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis 1.12 正文忠实性验收</title><style>{css}</style><main>
<div class="tag">JARVIS · WORKFLOW FIDELITY 1.12.0</div><h1>字段、正文和计划，必须讲同一件事</h1>
<p><strong>已补来源摘录正文核验、计划保留与显式撤销检查，并更新原助手的通用提示。</strong> 技术验收通过；限定格式中的事实扩写、旧计划复活和字段/正文不一致会被试验器判失败。</p>
<p class="note"><strong>自由正文修复未达预期。</strong> 原v1的24轮字段检查通过，但开启日志工作流后仍把失败扩写为“异常阻断”，更正时仍未保留“明天排查”；另有“已归档”等措辞缺少真实回执。原问题保持OPEN，不能用新格式的通过覆盖它们。</p>
<p class="small"><a href="adoption-review.json">采用判断</a>：保留已验证的限定试验能力；自由正文为NOT_ACCEPTED，不自动晋升知识或放宽完成条件。这是本轮报告结论，尚未实现为新的运行时发布门。</p>
<p class="note">当前普通回答获得的是提示改进；来源摘录核验用于显式要求的v2试验格式，尚未作为生产回复的自动审核关卡。它不认证任意改写、来源真实性或建议质量，Q与真实净收益仍未测，未部署。</p>
<div class="cards"><div class="card"><b class="number">{tests['run']}</b>不同回归用例<br><span class="small">原538＋新增{v['new_tests']}，全部保留</span></div><div class="card"><b class="number">12 / {len(run['checks'])}</b>浏览器流程 / 验收门<br><span class="small">原门限全部通过</span></div><div class="card"><b class="number">9＋6</b>新合成任务＋旧题回放<br><span class="small">6对照题、3保留题、6个v1旧题</span></div><div class="card"><b class="number">{pooled.get('PASS',0)}/36</b>候选v2硬条件通过<br><span class="small">失败{pooled.get('FAIL',0)}，待测{pooled.get('UNMEASURED',0)}；不是Q</span></div></div>
<h2>改了什么，预测与实测对得上吗</h2><div class="scroll"><table><tr><th>改进</th><th>原缺口</th><th>实际证据</th><th>预测边界</th></tr>
<tr><td>引用逐字支持＋当前依据覆盖</td><td>字段正确，正文却添加失败原因或遗漏比较依据</td><td>反例测试拒绝无依据扩写、旧来源、漏项和重复引用；基线真实试跑也捕获来源遗漏</td><td>仅摘录协议；自由改写需要额外语义复核</td></tr>
<tr><td>计划动作、时间、禁止条件同时保留</td><td>事实更正后，助手静默改计划</td><td>检查漏计划、擅改时间/动作；同时允许明确替换或撤销，防止机械沿用旧经验</td><td>新事实与旧计划冲突时，可提出建议但不自动当作已采纳</td></tr>
<tr><td>正文与证据字段完全一致</td><td>只有结构化字段通过，正文失真仍标绿</td><td>额外结尾、原因替换、建议冒充计划均有反例覆盖；原回复完整保留</td><td>试验器只记录失败，不自动改写答案后冒充原交付</td></tr>
<tr><td>通用提示修正＋保留题＋旧模式回放</td><td>可能只对新格式有效，原Markdown仍退步</td><td>同六题对照仅host/assistant.py变化；三题首次运行；旧v1另外回放并补审正文</td><td>小样本单次观察；不把通过率解释为通用智能或因果提升</td></tr></table></div>
<h2>三领域分别看</h2><div class="scroll"><table><tr><th>领域</th><th>试验</th><th>关闭工作流</th><th>开启工作流</th></tr>{rows}</table></div>
<p>baseline/candidate是同六个新题，reserved是三个程序性保留题，v1-replay是原六题。每题各配置两轮（v1各题轮数不同），仍按不同任务计算样本，不用调用数放大证据。报价none/none仍是同路径控制。</p>
{bars}<p class="small">绿色：冻结硬条件通过；红色：明确失败；黄色：待测。不同schema的条件分不直接作高低对比。</p>
<h2>旧Markdown模式有没有变好</h2><div class="scroll"><table><tr><th>原问题 / 补审项</th><th>本轮观察</th><th>结论状态</th></tr>{review_rows}</table></div>
<p><a href="prose-review.json">正文补审及原始证据</a>是事后模型辅助审阅，不是独立人工金标准，不追改冻结分数。没有延迟学习测试和用户情绪反馈，不能据此签收教学或陪伴效果。</p>
<h2>完整改进循环及三位一体</h2><div class="flow"><div>① 定向<br>保留请求与明确变更</div><div>② 协作<br>原对话通道生成交付</div><div>③ 观察<br>独立纯策略核对来源与正文</div><div>④ 分析<br>区分来源、覆盖、格式与效果</div><div>⑤ 新轮验证<br>保留旧失败，验证后决定采用</div></div>
<p>本轮没有新增授权主体、执行器或生产HTTP动作；解析器、Goal受理、预算、取消、知识存储不放宽。失败经验只进入证据记录，没有自动晋升到知识库。现有学习与发布机制保持原验收状态。</p>
<h2>失败和代价都保留</h2><div class="scroll"><table><tr><th>轮次</th><th>记录/计划</th><th>通过/失败/待测</th><th>完整配对</th><th>API估算</th></tr>{round_rows}</table></div>
<p>本轮实际{calls}次调用，已知{tokens:,} token，API估算{money}，另{unknown}次用量或价格未知。使用调用时SDK费率快照，未核销供应商账单，人工与本机成本未知；没有据此声称省token或完整效率收益。</p>
<div class="scroll"><table><tr><th>未通过记录</th><th>状态</th><th>失败条件</th></tr>{fail_rows or '<tr><td colspan="3">本轮没有记录失败或缺测；仍不等于全面验收。</td></tr>'}</table></div>
<p>全量来源覆盖是本次摘录试验的严格规则，不代表所有业务摘要必须逐条照录。应继续检查题干要求与评判口径是否足够明确，避免把合理摘要误判为能力退步。引用真实但选择错误、正文不一致与格式差异应分别记录。</p>
<h2>下一步顺序</h2><ol><li>收集三领域独立真实请求，明确全文忠实性与合理摘要边界；加入自由改写、长文、相互矛盾的资料及未见表达，测误放行和误拒。</li><li>把受限核验结果接到可见的交付核对流程前，先影子运行，检查误拦截和人工介入；通过后才考虑自动提示修订。</li><li>补完整费用与限定委托，然后让经验按适用条件、反例、版本及失效条件复用；多Bot仍需同一任务负责人和共同预算。</li></ol>
<details><summary>展开完整技术验收与审计来源</summary><p>{v['source_count']}个源码输入、{v['supporting_count']}个支持输入冻结；原观察器p95关闭{off:.3f}ms、开启{on:.3f}ms，增加{on-off:.3f}ms，原门限25ms。</p><div class="scroll"><table><tr><th>门</th><th>结果</th></tr>{gates}</table></div><p><a href="plan.json">事前计划</a> · <a href="prompt-plan.json">事前提示修订</a> · <a href="plan-amendment-v1-regression.json">补原模式回放的事前修订</a> · <a href="verification.json">汇总</a> · <a href="candidate-audit.json">源码变更</a> · <a href="frozen-r1/run/report.json">联合验收</a> · <a href="delivery-checks.json">交付审计</a> · <a href="cost-overview.json">全部代价</a></p><p>专项首轮错误导入夹具导致测试未加载，已修正导入并保留失败日志；未删断言、未降验收门。共享树其他改动的格式问题单独登记，不声称全树格式通过。</p></details>
<p class="small"><a href="../../delivery-validation.md#workflow-fidelity-evidence">权威验收章节</a> · <a href="../../core-bootstrap.md#workflow-fidelity-runtime">操作与实施边界</a> · <a href="../../contracts.md#workflow-fidelity-contract">格式契约</a></p></main></html>'''
(HERE/'report.html').write_text(page,encoding='utf-8',newline='\n')
print(json.dumps(v,ensure_ascii=False))
