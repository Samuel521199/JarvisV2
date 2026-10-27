"""Render this evidence bundle from the recorded acceptance results."""
from pathlib import Path
import html
import json

ROOT=Path(__file__).resolve().parent
read=lambda path:json.loads((ROOT/path).read_text('utf-8'))
report=read('frozen-r2/run/report.json')
tests=read('frozen-r2/run/tests.json')
snapshot=read('frozen-r2/snapshot.json')
wrapper=read('frozen-r2/result.json')
assert report['local_verdict']=='PASS' and wrapper['local_verdict']=='PASS' and tests['passed']
quote=read('frozen-r2/run/quote/runtime.json')
old=json.loads((ROOT.parent/'workflow-closure-1.4.0/frozen-r4/run/plan.json').read_text('utf-8'))['test_ids']
new=read('frozen-r2/run/plan.json')['test_ids']
missing=sorted(set(old)-set(new))
assert not missing
esc=html.escape
rows=''.join(f'<tr><td>{esc(c["id"])}</td><td class="{c["status"].lower()}">{esc(c["status"])}</td></tr>' for c in report['checks'])
cases=''.join(f'<tr><td>{name}</td><td>{t["status"]}</td><td>{t["completion"]["state"]}</td><td>{t["closure"]["state"]}</td><td>{t["spent"]}</td></tr>' for name,t in zip(['正确选择 B','错误选择 A','无合格报价'],quote['tasks']))
verification={'version':'workflow-domain-1.5.0','local_verdict':report['local_verdict'],'tests':tests['run'],'baseline_retained':len(old),
              'new_cases':len(set(new)-set(old)),'missing_baseline':missing,'gates':len(report['checks']),
              'seven_browser_workflows':all(c['status']=='PASS' for c in report['checks'] if 'browser' in c['id'] or c['id'].endswith('_ui')),
              'source_count':snapshot['source_count'],'source_fixed':report['source_unchanged'],
              'shared_workspace_is_frozen_version':wrapper['shared_workspace_is_frozen_version'],
              'prediction_results':{'bounded_domain_correctness':'met','input_binding':'met','legacy_regression':'met'},
              'real_work_quality':None,'token_savings':None,'learning_gain':None,'production_deployed':False}
(ROOT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jarvis · 领域核验 1.5.0</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#101720;color:#e5edf6;font:16px/1.75 "Segoe UI","Microsoft YaHei",sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 24px 70px}}h1{{font-size:clamp(28px,5vw,43px);line-height:1.3}}h2{{margin-top:34px;font-size:23px}}p{{margin:12px 0}}a{{color:#8dcdff}}.sub{{color:#a9bbce}}.tag{{color:#8fe0b6;font-size:13px;letter-spacing:2px}}.callout,.card{{padding:22px;border:1px solid #344759;border-radius:14px;background:#182330}}.callout{{border-color:#519bc3}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}.number{{font-size:30px;color:#8bd6ff;display:block}}.number small{{font-size:15px}}.card{{padding:18px}}.card p{{font-size:13px;color:#adbed0}}.flow{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0}}.node{{padding:13px 16px;background:#21384a;border:1px solid #467897;border-radius:8px}}.arrow{{color:#83bcdd}}.scroll{{overflow:auto;border:1px solid #314355;border-radius:10px;margin:14px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #314355}}th{{background:#203244;color:#d8ebfa}}.pass{{color:#8ce1b0}}.fail{{color:#ff9f9f}}.bar{{display:flex;height:30px;border-radius:7px;overflow:hidden;margin:12px 0;background:#283948}}.old{{width:{len(old)/len(new)*100:.4f}%;background:#4c91b6}}.added{{flex:1;background:#88d6a8}}.caption{{font-size:13px;color:#a9bbce}}code{{overflow-wrap:anywhere;color:#b3d8f2}}details{{padding:16px;border:1px solid #314355;border-radius:10px;margin:16px 0}}summary{{cursor:pointer}}img{{width:100%;border:1px solid #314355;border-radius:10px}}@media(max-width:680px){{main{{padding:24px 16px}}.grid{{grid-template-columns:repeat(2,1fr)}}.flow{{align-items:stretch;flex-direction:column}}.arrow{{text-align:center}}.card{{padding:13px}}}}
</style><main><div class="tag">JARVIS / WORKFLOW DOMAIN / 1.5.0</div><h1>让“做完了”接受独立核对</h1>
<p class="sub">2026-10-27 · 结构化报价的预算、交期、最低价与来源核验 · 固定候选本地验收</p>
<div class="callout"><strong>结论：本地技术验收 {esc(report['local_verdict'])}。</strong> 正确报价与“无符合项”可按约定结案；工具成功但选错最低价的结果被拦截。原任务、授权、预算、返工和反馈机制继续生效。<p>适用范围仅为已审阅的结构化报价与已发布的纯文本能力。自然语言理解、真实供应商可信性、长期成长与生产发布仍未签收。</p></div>
<div class="grid"><div class="card"><span class="number">{tests['run']}</span>不同测试用例<p>原 {len(old)} 项保留，新增 {len(set(new)-set(old))} 项</p></div><div class="card"><span class="number">7</span>浏览器工作流程<p>新增报价，原六条继续验收</p></div><div class="card"><span class="number">{len(report['checks'])}</span>验收门<p>沿用原性能门槛与无跳过规则</p></div><div class="card"><span class="number">未测</span>真实质量与成长收益<p>不把测试通过率写成业务评分</p></div></div>
<h2>改进什么，会发生什么</h2><div class="flow"><span class="node">审阅结构化条件</span><span class="arrow">→</span><span class="node">冻结原文摘要</span><span class="arrow">→</span><span class="node">原工具链执行</span><span class="arrow">→</span><span class="node">独立重算与交付核对</span><span class="arrow">→</span><span class="node">原结案 / 纠正接续</span></div>
<p class="caption">迟到反馈、来源失效或产物变化 → 重新打开当前工作；历史回执保留。此图描述本轮接线，不代表全部产品目标已经完成。</p>
<div class="scroll"><table><tr><th>改进</th><th>结果</th><th>限制</th></tr><tr><td>输入摘要绑定</td><td>执行前锁定预算、交期与全部报价，错配回滚整次受理</td><td>原始资料的真实性需另核对</td></tr><tr><td>独立领域核验</td><td>集合遗漏、错选最低价、伪造引用均不能结案</td><td>不处理保修、税费、资质等未知条件</td></tr><tr><td>明确反例与空结果</td><td>并列最低价可任选；无合格项须明确返回空集合</td><td>不强行生成“看似有用”的报价</td></tr><tr><td>固定要求含义与版本</td><td>任意文字不能冒充已核对；核验器变化更新证据指纹</td><td>目标漏项识别仍待实现</td></tr></table></div>
<h2>预测与实测：本轮达到哪些边界</h2><div class="scroll"><table><tr><th>实施前预测</th><th>实测</th><th>差距</th></tr><tr><td>错误结果独立拦截</td><td>正确 / 选错 / 无符合项三条真实界面流程均符合预期</td><td>合成资料，尚无真实用户任务对照</td></tr><tr><td>冻结输入不可替换</td><td>摘要、执行链、集合反例与受理回滚检查通过</td><td>未自动提取自然语言约束</td></tr><tr><td>不破坏已有机制</td><td>{len(old)} 项旧用例零遗漏，{tests['run']} 项全部通过</td><td>限定测试覆盖，不等于生产迁移证明</td></tr><tr><td>更聪明、更省钱、更少介入</td><td>未测；报价经验未自动入库</td><td>完整费用、盲测与负迁移实验仍待后续</td></tr></table></div>
<div class="bar" aria-label="回归组成：旧316项加新28项"><div class="old"></div><div class="added"></div></div><p class="caption">蓝：旧用例；绿：新增领域/集成反例。这是覆盖构成，不是智能水平增长图。</p>
<h2>工具成功，不等于结果正确</h2><p>预算 10000 最小货币单位，交期 5 天：A=9000/5天，B=8000/4天，C=7000/6天，D=10001/1天。合格集合必须是 A、B，最低价选择 B。</p><div class="scroll"><table><tr><th>合成任务</th><th>执行状态</th><th>独立验收</th><th>当前工作</th><th>动作单位</th></tr>{cases}</table></div>
<p>“包含 selected_id”这样的弱字面检查可以通过错误报告，但原系统也只给 SATISFIED、未证明完整覆盖。本轮新增核验器进一步识别具体业务错误，不能把这个反例宣称为旧系统曾错误判定全业务完成。</p>
<h2>兼容性与保留的失败</h2><p>没有新增数据库 schema、执行器、许可或知识库。原工作状态文件与 JPF/r1 预测摘要保持不变。核验器附加版本、输入摘要与原因，不在新核验审计中重复写报价正文。旧二进制兼容新检查与生产热降级尚未演练。</p>
<p>首轮专项两项预期与原接口不符，修正为取消后拒绝重启、产物改动进入 NEEDS_CORRECTION；仍检查无动作和不可结案。首轮界面发现390px下溢出，表单局部修正后复测。<a href="narrow-r1.log">原专项失败</a> · <a href="ui-r1/browser.json">原界面失败</a> · <a href="ui-r2/browser.json">界面复测</a></p>
<p>第一轮完整回归和七条界面通过，但冻结副本文档缺少固定说明文件，链接门拒绝。包装器补齐该文件并增加文档预检，重新冻结执行；没有删除链接或降低门槛。<a href="frozen-r1/run/report.json">首轮 FAIL</a></p><details><summary>查看全部验收门与可复核证据</summary><div class="scroll"><table><tr><th>验收门</th><th>结果</th></tr>{rows}</table></div><p>冻结 {snapshot['source_count']} 个源码输入、{len(snapshot['supporting_input_digests'])} 个支持输入。副本一致性：{report['source_unchanged']}；本轮结束时共享源码与副本一致：{wrapper['shared_workspace_is_frozen_version']}。</p><p><a href="plan.json">实施前预测</a> · <a href="frozen-r2/snapshot.json">固定候选</a> · <a href="frozen-r2/run/report.html">完整验收报告</a> · <a href="frozen-r2/run/tests.json">逐例结果</a> · <a href="frozen-r2/run/quote/runtime.json">实际动作与结案</a> · <a href="candidate-audit.json">文件审计</a></p></details>
<h2>下一步，继续补齐真实委托</h2><p>先把真实来源的自然请求转为可审阅约束，测试遗漏、歧义和资料变更；再接完整费用与有限常设委托。随后才做报价经验归纳的独立对照和负迁移实验，再扩大多 Bot 协作。一般语义、长期成长与机器人控制仍沿原阶段分别验收。</p><p><a href="../../core-bootstrap.md#workflow-domain-runtime">运行权威页</a> · <a href="../../contracts.md#workflow-domain-contract">输入与输出契约</a> · <a href="../../delivery-validation.md#workflow-domain-evidence">验收权威页</a></p>
<details><summary>真实验收界面</summary><img src="frozen-r2/run/quote/correct-result.png" alt="正确报价经独立核验后结案"><img src="frozen-r2/run/quote/wrong-result.png" alt="工具执行成功但所选报价不正确，需要纠正"></details></main></html>'''
(ROOT/'report.html').write_text(doc,encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False))
