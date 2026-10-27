"""Render the measured requirements-review evidence, without inventing gains."""
from pathlib import Path
import html
import json

ROOT=Path(__file__).resolve().parent
read=lambda name:json.loads((ROOT/name).read_text('utf-8'))
report=read('frozen-r1/run/report.json');tests=read('frozen-r1/run/tests.json');snapshot=read('frozen-r1/snapshot.json')
wrapper=read('frozen-r1/result.json');runtime=read('frozen-r1/run/quote_request/runtime.json')
assert report['local_verdict']==wrapper['local_verdict']=='PASS' and tests['passed']
baseline=json.loads((ROOT.parent/'workflow-domain-1.5.0/frozen-r2/run/plan.json').read_text('utf-8'))['test_ids']
current=read('frozen-r1/run/plan.json')['test_ids'];missing=sorted(set(baseline)-set(current));assert not missing
cases=json.loads((ROOT.parents[2]/'tests/fixtures/quote_requests_v1.json').read_text('utf-8'))
counts={'ready':sum(c['ready'] for c in cases),'blocked':sum(c['blocking'] for c in cases),'uncovered':sum(not c['ready'] and not c['blocking'] for c in cases)}
verification={'version':'workflow-requirements-1.6.0','local_verdict':'PASS','source_scope':'stored_goal_only','tests':tests['run'],
              'baseline_retained':len(baseline),'new_cases':len(set(current)-set(baseline)),'missing_baseline':missing,
              'gates':len(report['checks']),'browser_workflows':8,'source_count':snapshot['source_count'],
              'supporting_count':len(snapshot['supporting_input_digests']),'source_fixed':report['source_unchanged'],
              'synthetic_grammar_case_counts':counts,'real_user_accuracy':None,'all_cost_gain':None,'token_savings':None,'learning_gain':None,
              'production_deployed':False}
(ROOT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
esc=html.escape
gates=''.join(f'<tr><td>{esc(c["id"])}</td><td class="pass">{esc(c["status"])}</td></tr>' for c in report['checks'])
sample_rows=''.join(f'<tr><td>{esc(c["goal"])}</td><td>{"明确一致" if c["ready"] else "阻止受理" if c["blocking"] else "待核对，可做约定部分"}</td></tr>' for c in cases)
task_rows=''
for label,task in zip(['明确请求，与输入一致','增加“必须保修三年”','预算90元，输入仍为100元'],runtime['tasks']):
    task_rows+=f'<tr><td>{label}</td><td>{task["status"] if task else "未受理"}</td><td>{task["completion"]["state"] if task else "无执行任务"}</td><td>{task["closure"]["state"] if task else "待修订"}</td><td>{task["spent"] if task else 0}</td></tr>'
document=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jarvis · 目标要求 1.6.0</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#101720;color:#e5edf6;font:16px/1.75 "Segoe UI","Microsoft YaHei",sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 24px 70px}}h1{{font-size:clamp(28px,5vw,43px);line-height:1.3}}h2{{margin-top:34px;font-size:23px}}p{{margin:12px 0}}a{{color:#93d0ff}}.sub,.caption{{color:#a9bbce}}.caption{{font-size:13px}}.tag{{color:#92e1ba;font-size:13px;letter-spacing:2px}}.callout,.card{{padding:22px;border:1px solid #344759;border-radius:14px;background:#182330}}.callout{{border-color:#519bc3}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}.number{{font-size:30px;color:#8bd6ff;display:block}}.card{{padding:18px}}.card p{{font-size:13px;color:#adbed0}}.flow{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0}}.node{{padding:13px 16px;background:#21384a;border:1px solid #467897;border-radius:8px}}.arrow{{color:#83bcdd}}.scroll{{overflow:auto;border:1px solid #314355;border-radius:10px;margin:14px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #314355}}th{{background:#203244}}.pass{{color:#8ce1b0}}.warn{{color:#ffd291}}.bar{{display:flex;height:32px;border-radius:8px;overflow:hidden;margin:16px 0}}.ready{{background:#397b65;width:{counts['ready']/len(cases)*100}%}}.unknown{{background:#8a693e;width:{counts['uncovered']/len(cases)*100}%}}.blocked{{background:#85505c;flex:1}}details{{padding:16px;border:1px solid #314355;border-radius:10px;margin:16px 0}}summary{{cursor:pointer}}code{{overflow-wrap:anywhere;color:#b3d8f2}}img{{width:100%;border:1px solid #314355;border-radius:10px}}@media(max-width:680px){{main{{padding:24px 16px}}.grid{{grid-template-columns:repeat(2,1fr)}}.flow{{align-items:stretch;flex-direction:column}}.arrow{{text-align:center}}.card{{padding:13px}}}}
</style><main><div class="tag">JARVIS / REQUIREMENTS REVIEW / 1.6.0</div><h1>把漏掉的要求留在眼前</h1><p class="sub">2026-10-27 · 目标原文 → 逐句提取 → 输入对照 → 独立验收</p>
<div class="callout"><strong>结论：本地候选技术验收 PASS。</strong> 明确报价表达可提取并核对；附加保修要求不会被丢弃；预算冲突或未支持的否定/条件表达阻止受理。<p>本轮只对照计划中实际保存的目标原文。聊天转Goal时是否遗漏、附件和多轮上下文是否完整，尚未核验；不能称为通用自然语言理解。</p></div>
<div class="grid"><div class="card"><span class="number">{tests['run']}</span>不同回归用例<p>原{len(baseline)}项保留，新增{len(set(current)-set(baseline))}项</p></div><div class="card"><span class="number">8</span>浏览器流程<p>新增目标原文审阅流程</p></div><div class="card"><span class="number">{len(report['checks'])}</span>验收门<p>不放宽原性能、源码和无跳过门槛</p></div><div class="card"><span class="number">未测</span>真实工作与成长收益<p>无真实请求泛化、费用和token收益结论</p></div></div>
<h2>改进后，任务会怎样推进</h2><div class="flow"><span class="node">当前目标原文</span><span class="arrow">→</span><span class="node">逐句提取并标出未覆盖</span><span class="arrow">→</span><span class="node">对照冻结报价输入</span><span class="arrow">→</span><span class="node">原执行与核验链</span></div>
<div class="scroll"><table><tr><th>审阅结果</th><th>下一步</th><th>是否可结案</th></tr><tr><td>明确表达全部识别，输入一致</td><td>沿原授权执行，并由1.5领域核验器独立验证结果</td><td>明确声明范围覆盖完整且其他原检查通过时可结案</td></tr><tr><td>保修、税费等附加要求未覆盖</td><td>可明确只做已约定的本地文字部分；保留未覆盖原文</td><td>不可自动结案，保持WAITING_EVIDENCE</td></tr><tr><td>预算/交期/币种不符或重复条件</td><td>先修订目标或输入；受理前拒绝</td><td>无执行任务</td></tr><tr><td>未覆盖片段包含“不要、或者、除非”等控制词</td><td>先澄清，不把控制条件当成普通附加项</td><td>阻止受理；有限词表不代表理解全部逻辑表达</td></tr></table></div>
<h2>本轮预测与实测</h2><div class="scroll"><table><tr><th>实施前预测</th><th>实际证据</th><th>差距或限制</th></tr><tr><td>明确条件能被提取和对照</td><td>20个固定合成正反例按预期分类；含换序、精确小数、万元、零值</td><td>未测试真实用户请求的召回率，不能以20题概括语言理解</td></tr><tr><td>遗漏和歧义不会假装完成</td><td>强制complete、反馈认可不能消除未覆盖内容；控制词和错配阻止受理</td><td>只分析保存的Goal，不验证聊天摘要或附件无遗漏</td></tr><tr><td>审阅不能变成执行权限</td><td>只读审阅无Task/新执行许可/模型调用；陈旧revision与绑定拒绝；截断目标拒绝</td><td>常设委托和完整费用仍未接入</td></tr><tr><td>旧机制保持兼容</td><td>{len(baseline)}项旧用例全部保留，{tests['run']}项通过；原七条界面流程继续通过</td><td>未生产部署；旧版本热降级未演练</td></tr><tr><td>更聪明、更省token</td><td>未测；未覆盖任务只能保留有限的执行观察，报价经验不自动采用</td><td>没有长期对照和经验净贡献，不给未知收益填分</td></tr></table></div>
<h2>一个不能被忽略的取舍</h2><p>新的核对方式可能让更多任务进入待核对，因为它拒绝把“完成了一部分”叫作全部完成。这不自动等于能力退化，也不证明已经变聪明。后续必须同时测错误交付减少量、不必要拒绝量、人工介入和完整成本。</p>
<div class="bar" aria-label="固定合成样本分类"><div class="ready"></div><div class="unknown"></div><div class="blocked"></div></div><p class="caption">绿：{counts['ready']}项明确一致；黄：{counts['uncovered']}项未覆盖附加要求；红：{counts['blocked']}项阻止受理。分组来自刻意构造的工程样本，不是实际用户请求的完成率。</p>
<h2>真实界面与工作链结果</h2><div class="scroll"><table><tr><th>合成场景</th><th>工具执行</th><th>验收</th><th>当前工作</th><th>动作单位</th></tr>{task_rows}</table></div><p class="caption">临时数据实例，真实HTTP、浏览器和隔离worker；零模型调用，不触碰生产任务与业务数据库。动作单位不是token或货币。</p>
<h2>如何避免旧机制被改坏</h2><p>沿用Goal版本、Task受理事务、共享动作额度、Ledger/Scheduling、Completion和知识限定。没有新数据库、第二执行器或新增自主权限。新核验在受理和结果评价时都重新计算，客户端不能用ready=true或complete绕过；解析版本变化使旧绑定失效。</p><p>原1.5“结构化报价核验”继续保持原含义；1.6“对照目标原文核验”才增加原文覆盖检查。部分成功不会自动变成报价经验，保留下来的执行观察带有覆盖未证实限定。</p>
<details><summary>20个固定表达样本与预期分类</summary><div class="scroll"><table><tr><th>目标原文</th><th>预期</th></tr>{sample_rows}</table></div></details>
<details><summary>完整验收门和证据</summary><div class="scroll"><table><tr><th>门</th><th>结果</th></tr>{gates}</table></div><p>冻结{snapshot['source_count']}个源码输入、{len(snapshot['supporting_input_digests'])}个支持输入；运行中源码一致：{report['source_unchanged']}。整个产品仍未签收，生产未部署。</p><p><a href="plan.json">实施前预测</a> · <a href="candidate-audit.json">候选文件审计</a> · <a href="frozen-r1/run/report.html">联合验收报告</a> · <a href="frozen-r1/run/tests.json">逐项测试</a> · <a href="frozen-r1/run/quote_request/runtime.json">执行与结案记录</a></p></details>
<h2>下一步的优先顺序</h2><p>先对账聊天原话、附件与保存的Goal，建立未参与规则编写的真实请求测试；区分识别错误、正确拒绝与不必要拒绝。随后接完整费用与有限常设委托，再用独立对照评估经验复用，最后扩大多Bot负责人和接管机制。</p><p><a href="../../core-bootstrap.md#workflow-requirements-runtime">Markdown：使用与边界</a> · <a href="../../contracts.md#workflow-requirements-contract">契约</a> · <a href="../../delivery-validation.md#workflow-requirements-evidence">验收权威页</a></p>
<details><summary>查看实际目标审阅界面</summary><img src="frozen-r1/run/quote_request/review-desktop.png" alt="当前目标原文逐句审阅"><img src="frozen-r1/run/quote_request/uncovered-review.png" alt="保修要求保留为未覆盖，不能自动结案"></details></main></html>'''
(ROOT/'report.html').write_text(document,encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False))
