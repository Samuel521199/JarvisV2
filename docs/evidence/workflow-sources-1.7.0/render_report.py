"""Present measured source-reconciliation evidence; never fabricate quality scores."""
from pathlib import Path
import hashlib
import html
import json

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[2]
read=lambda name:json.loads((ROOT/name).read_text('utf-8'))
write=lambda name,value:(ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
report=read('frozen-r3/run/report.json');tests=read('frozen-r3/run/tests.json');snapshot=read('frozen-r3/snapshot.json')
wrapper=read('frozen-r3/result.json');runtime=read('frozen-r3/run/quote_sources/runtime.json')
performance=read('frozen-r3/run/performance.json');old_p95=performance['task_ms']['False']['p95'];new_p95=performance['task_ms']['True']['p95'];added_p95=round(new_p95-old_p95,3)
assert report['local_verdict']==wrapper['local_verdict']=='PASS' and tests['passed']
baseline=json.loads((ROOT.parent/'workflow-requirements-1.6.0/frozen-r1/run/plan.json').read_text('utf-8'))['test_ids']
current=read('frozen-r3/run/plan.json')['test_ids'];missing=sorted(set(baseline)-set(current));assert not missing
assert len(current)==tests['run'] and len(current)==len(set(current))
verification={'version':'workflow-sources-1.7.0','local_verdict':'PASS','tests':tests['run'],
              'baseline_retained':len(baseline),'new_cases':len(set(current)-set(baseline)),'missing_baseline':missing,
              'gates':len(report['checks']),'browser_workflows':9,'source_count':snapshot['source_count'],
              'supporting_count':len(snapshot['supporting_input_digests']),'source_fixed':report['source_unchanged'],
              'real_user_accuracy':None,'unnecessary_rejection_rate':None,'all_cost_gain':None,'token_savings':None,
              'learning_gain':None,'original_observer_p95_ms':{'off':old_p95,'on':new_p95,'added':added_p95,'budget':25},'production_deployed':False}
write('verification.json',verification)
before=read('plan.json')['source_before'];frozen=snapshot['source_digests']
changes=[{'path':p,'before':before.get(p),'candidate':frozen.get(p),'created':p not in before}
         for p in sorted(before.keys()|frozen.keys()) if before.get(p)!=frozen.get(p)]
forecast=hashlib.sha256((ROOT.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()
work_status=hashlib.sha256((PROJECT/'host/work_status.py').read_bytes()).hexdigest()
assert forecast=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f'
assert work_status=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10'
write('candidate-audit.json',{'changed_sources':changes,'new_files':[c['path'] for c in changes if c['created']],
      'old_work_status_preserved':True,'original_forecast_preserved':True,'forecast_sha256':forecast,
      'frozen_result':wrapper,'production_deployed':False})
esc=html.escape
gates=''.join(f'<tr><td>{esc(c["id"])}</td><td class="pass">{esc(c["status"])}</td></tr>' for c in report['checks'])
task_rows=''
for label,task in zip(['原话、Goal与输入一致；报价附件原样传入','原话有保修要求，Goal遗漏','原话预算90元，Goal/输入却为100元'],runtime['tasks']):
    task_rows+=f'<tr><td>{label}</td><td>{task["status"] if task else "未受理"}</td><td>{task["completion"]["state"] if task else "无Task"}</td><td>{task["closure"]["state"] if task else "待修订"}</td><td>{task["spent"] if task else 0}</td></tr>'
document=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jarvis · 聊天来源 1.7.0</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#101720;color:#e5edf6;font:16px/1.75 "Segoe UI","Microsoft YaHei",sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 24px 70px}}h1{{font-size:clamp(28px,5vw,43px);line-height:1.3}}h2{{margin-top:34px;font-size:23px}}p{{margin:12px 0}}a{{color:#93d0ff}}.sub,.caption{{color:#a9bbce}}.caption{{font-size:13px}}.tag{{color:#92e1ba;font-size:13px;letter-spacing:2px}}.callout,.card{{padding:22px;border:1px solid #344759;border-radius:14px;background:#182330}}.callout{{border-color:#519bc3}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0}}.number{{font-size:30px;color:#8bd6ff;display:block}}.card{{padding:18px}}.card p{{font-size:13px;color:#adbed0}}.flow{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0}}.node{{padding:13px 16px;background:#21384a;border:1px solid #467897;border-radius:8px}}.arrow{{color:#83bcdd}}.scroll{{overflow:auto;border:1px solid #314355;border-radius:10px;margin:14px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #314355;overflow-wrap:anywhere}}th{{background:#203244}}.pass{{color:#8ce1b0}}.warn{{color:#ffd291}}.paths{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.paths div{{padding:16px;border-radius:9px;background:#1d2d39;border-top:3px solid #72b7cc}}.paths div:nth-child(2){{border-color:#d4ae65}}.paths div:nth-child(3){{border-color:#d1868e}}details{{padding:16px;border:1px solid #314355;border-radius:10px;margin:16px 0}}summary{{cursor:pointer}}code{{overflow-wrap:anywhere;color:#b3d8f2}}img{{width:100%;border:1px solid #314355;border-radius:10px}}@media(max-width:680px){{main{{padding:24px 16px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.paths{{grid-template-columns:1fr}}.flow{{align-items:stretch;flex-direction:column}}.arrow{{text-align:center}}.card{{padding:13px}}}}
</style><main><div class="tag">JARVIS / SOURCE RECONCILIATION / 1.7.0</div><h1>原话没有进入目标，也不能被忘掉</h1><p class="sub">2026-10-27 · 原始来源 → 目标对账 → 执行守卫 → 失效重开</p>
<div class="callout"><strong>结论：本地候选技术验收 PASS。</strong> 新增聊天来源核验，能保留被Goal遗漏的明确要求、阻止来源冲突，并在来源改变后停止后续动作或撤销旧通过结论。<p>目前仍是有限报价任务。前文、图片、附件含义和多轮覆盖关系尚未理解时，明确保留待核验。生产未部署，真实工作质量和长期成长未评分。</p></div>
<div class="grid"><div class="card"><span class="number">{tests['run']}</span>不同回归用例<p>原{len(baseline)}项保留，新增{len(set(current)-set(baseline))}项</p></div><div class="card"><span class="number">9</span>浏览器流程<p>原8条保留，新增来源对账</p></div><div class="card"><span class="number">{len(report['checks'])}</span>验收门通过<p>不降低原预算与验收标准</p></div><div class="card"><span class="number">未测</span>真实质量与成长<p>测试通过率不等于智能评分</p></div></div>
<h2>改了哪里，会产生什么效果</h2><div class="scroll"><table><tr><th>改进</th><th>直接效果</th><th>仍不能声称</th></tr><tr><td>同时核对原话、会话要求、Goal</td><td>模型漏写的保修要求仍会挡住完整结案</td><td>理解全部自然语言或自动补全未知规则</td></tr><tr><td>明确区分引用资料与权限</td><td>附件指令不授予能力；仅逐字一致的输入标明原样传入</td><td>供应商可信、资料真实、附件含义已理解</td></tr><tr><td>绑定来源摘要和规则版本</td><td>陈旧审阅不能受理；执行检查点和完成评价重新核验</td><td>撤销已发生效果，或消除所有跨库竞争窗口</td></tr><tr><td>前文、背景、修订范围显式保留</td><td>没有证据时不会默认“无关”或“旧要求被覆盖”</td><td>已经完整绑定全部历史正文，或理解多轮撤销语义</td></tr></table></div>
<h2>来源贯穿原有工作链</h2><div class="flow" role="img" aria-label="原话与资料经过Goal对账、来源绑定、原任务执行、独立评价，最后决定结案或重新核对"><div class="node">原话与资料</div><span class="arrow">→</span><div class="node">Goal与输入对账</div><span class="arrow">→</span><div class="node">冻结来源摘要</div><span class="arrow">→</span><div class="node">原Task执行与复核</div><span class="arrow">→</span><div class="node">独立评价</div></div>
<div class="paths"><div><strong class="pass">一致 + 范围完整</strong><p>独立结果与原结案前提也通过 → 可以结案。</p></div><div><strong class="warn">仍有未核验内容</strong><p>仅执行明确约定的部分 → WAITING_EVIDENCE，不得以认可反馈绕过。</p></div><div><strong>冲突或来源变化</strong><p>受理拒绝 / 后续检查点停止 / 旧完成证据失效 → 重新核对。</p></div></div>
<h2>预测与实测差距</h2><div class="scroll"><table><tr><th>实施前预测</th><th>实际证据</th><th>差距或后续条件</th></tr><tr><td>避免模型改写丢失要求</td><td>原话和会话要求漏写保修仍待核验；预算或交期错配阻止受理</td><td>命中的是合成工程反例，真实召回率和误拒率未测</td></tr><tr><td>来源变化及时重开</td><td>执行前变化零动作；首动作后变化阻止交付；完成后变化INVALIDATED；重启保持摘要一致</td><td>已有副作用保持事实，未证明全局原子性</td></tr><tr><td>保持原机制和边界</td><td>{len(baseline)}项旧用例零遗漏；共{tests['run']}项、9条浏览器流程通过</td><td>只说明本地候选覆盖范围，未生产迁移或热降级演练</td></tr><tr><td>知识不因部分成功变成错误经验</td><td>部分成功只能保留限定观察，不能自动形成报价方法；无源码级新知识库</td><td>长期经验贡献、负迁移和token节省仍未测</td></tr><tr><td>减少人工介入、提高全自动程度</td><td>当前明确暴露更多未核验来源</td><td>可能增加核对次数；需独立真实对照才能判断净收益</td></tr></table></div>
<h2>真实界面与执行结果</h2><div class="scroll"><table><tr><th>合成聊天场景</th><th>工具执行</th><th>验收</th><th>当前工作</th><th>动作单位</th></tr>{task_rows}</table></div><p class="caption">真实浏览器、HTTP和隔离worker，使用临时合成数据；零模型调用。动作单位不是token或货币，也不是业务评分。</p>
<p class="caption">原观察器性能门：30次/组P95 {old_p95} → {new_p95} ms，增加{added_p95} ms，低于原25 ms预算。该指标衡量原观察器开销，未测新增来源核验在规模数据下的成本。</p>
<h2>三位一体与“越用越聪明”的边界</h2><p>Host组合来源，任务资源模块执行纯规则核验，原许可、Ledger/Scheduling和检查点控制动作，Completion与工作状态显示可采信结论。沿用原模块分工，无新增执行器、授权或数据库。Direction得到原话对账证据，Engagement仍经原授权执行并呈现范围，Reflection可以反证旧通过结论；三者仍共享同一连续身份。</p><p>这次补的是成长所需的证据质量：先知道原话有没有丢、成功覆盖了什么、来源何时失效。自愈仍经原修订/返工；自改造仍须独立回归；部分成功不会自动升级成可采用方法。真实经验带来的质量、成本收益与错误复发，必须另外测量。</p>
<h2>下一步按什么顺序</h2><div class="scroll"><table><tr><th>顺序</th><th>具体交付</th><th>预期效果与签收条件</th></tr><tr><td>1</td><td>独立真实请求样本；建立新增、替换、撤销的逐条来源关系</td><td>减少无谓待核对，同时保留旧约束；分别测漏项、错放行和误拒绝，不只测通过率</td></tr><tr><td>2</td><td>端到端费用账与有限常设委托</td><td>已授权常见任务少打扰；预算超限和重要事务仍可控，计入模型、工具与人工成本</td></tr><tr><td>3</td><td>带适用条件、反例和到期复核的经验候选</td><td>近似问题更省成本；独立复测确认收益，反例能暂停旧方法</td></tr><tr><td>4</td><td>单任务负责人、多Bot委派与租约接管</td><td>分工自动化且责任可追踪；停止、重复执行、接管冲突和总费用必须通过故障演练</td></tr></table></div>
<details><summary>验收门、失败轮与证据</summary><div class="scroll"><table><tr><th>验收门</th><th>状态</th></tr>{gates}</table></div><p>冻结{snapshot['source_count']}个源码输入、{len(snapshot['supporting_input_digests'])}个支持输入。早期专项测试语法错误和探针文案错配保留。首次联合验收的414项回归通过，但1.6界面探针未等待刷新后的新DOM而失败；修复为等待HTTP成功和新节点。第二次冻结因并行文档引用的证据尚未复制齐备而在预检失败。各失败轮保留，最终重新冻结完整验收，没有放宽运行判定。全仓git格式检查另有非本轮修改文件的换行问题，本轮修改范围通过；详见交付检查。</p><p><a href="plan.json">实施前预测</a> · <a href="candidate-audit.json">候选审计</a> · <a href="frozen-r3/run/report.html">联合验收</a> · <a href="frozen-r3/run/tests.json">逐项测试</a> · <a href="frozen-r3/run/quote_sources/runtime.json">执行记录</a> · <a href="delivery-checks.json">交付检查</a></p></details>
<p><a href="../../core-bootstrap.md#workflow-sources-runtime">Markdown：实施与边界</a> · <a href="../../contracts.md#workflow-sources-contract">实际契约</a> · <a href="../../delivery-validation.md#workflow-sources-evidence">预测与实测权威页</a></p>
<details><summary>查看实际来源审阅界面</summary><img src="frozen-r3/run/quote_sources/review-desktop.png" alt="展开用户原话与附件对账"><img src="frozen-r3/run/quote_sources/uncovered-review.png" alt="Goal遗漏保修要求，原话仍保留且仅允许部分范围"></details></main></html>'''
(ROOT/'report.html').write_text(document,encoding='utf-8',newline='\n')
print(json.dumps(verification,ensure_ascii=False))
