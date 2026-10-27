"""Render measured explicit-change results, retaining missing real-world evidence."""
from pathlib import Path
import hashlib
import html
import json
import re

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda name:json.loads((HERE/name).read_text('utf-8'))
write=lambda name,value:(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
r=read('frozen-r1/run/report.json');t=read('frozen-r1/run/tests.json');snapshot=read('frozen-r1/snapshot.json');wrapper=read('frozen-r1/result.json')
assert r['local_verdict']==wrapper['local_verdict']=='PASS' and t['passed']
baseline=json.loads((HERE.parent/'workflow-sources-1.7.0/frozen-r3/run/plan.json').read_text('utf-8'))['test_ids']
current=read('frozen-r1/run/plan.json')['test_ids'];missing=sorted(set(baseline)-set(current));assert not missing
runtime=read('frozen-r1/run/quote_changes/runtime.json');perf=read('frozen-r1/run/performance.json')
off=perf['task_ms']['False']['p95'];on=perf['task_ms']['True']['p95'];added=round(on-off,3)
value={'version':'workflow-changes-1.8.0','local_verdict':'PASS','tests':t['run'],'baseline_retained':len(baseline),
       'new_cases':len(set(current)-set(baseline)),'missing_baseline':missing,'browser_workflows':10,'gates':len(r['checks']),
       'source_count':snapshot['source_count'],'supporting_count':len(snapshot['supporting_input_digests']),
       'original_observer_p95_ms':{'off':off,'on':on,'added':added,'budget':25},'real_user_accuracy':None,
       'unnecessary_rejection_rate':None,'quality_gain':None,'token_savings':None,'learning_gain':None,'production_deployed':False}
write('verification.json',value)
before=read('plan.json')['source_before'];after=snapshot['source_digests']
changes=[{'path':p,'before':before.get(p),'candidate':after.get(p),'created':p not in before} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
forecast=hashlib.sha256((HERE.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()
assert forecast=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f'
assert hashlib.sha256((ROOT/'host/work_status.py').read_bytes()).hexdigest()=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10'
write('candidate-audit.json',{'changed_sources':changes,'original_forecast_preserved':True,'old_work_status_preserved':True,'frozen_result':wrapper,'production_deployed':False})
css=re.search(r'<style>(.*?)</style>',(HERE.parent/'workflow-sources-1.7.0/report.html').read_text('utf-8'),re.S)[1]
rows=''
for label,task in zip(['预算100→90，明确撤销保修，其他条件保留','明确新增保修条件，当前仍不支持其核验','原话替换预算，模型却保留旧预算'],runtime['tasks']):
    rows+=f'<tr><td>{label}</td><td>{task["status"] if task else "未受理"}</td><td>{task["completion"]["state"] if task else "无Task"}</td><td>{task["closure"]["state"] if task else "待修订"}</td><td>{task["spent"] if task else 0}</td></tr>'
gates=''.join(f'<tr><td>{html.escape(c["id"])}</td><td class="pass">{html.escape(c["status"])}</td></tr>' for c in r['checks'])
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis · 明确变更 1.8.0</title><style>{css}</style><main>
<div class="tag">JARVIS / EXPLICIT REQUIREMENT CHANGES / 1.8.0</div><h1>要求可以改变，来龙去脉仍然保留</h1><p class="sub">2026-10-27 · 新增、替换、撤销 → 有效要求 → 独立验收</p>
<div class="callout"><strong>结论：本地候选技术验收 PASS。</strong> 新增“对照明确要求变更核验”，在尚未执行的聊天Goal中重放最多3次已接受的明确修订。旧条件保留去向；没有被点名修改的条件继续有效。<p>只支持严格引用单条原文的有限报价变更。旧1.7方式保持原义；生产未部署，自由语言、执行后返工和真实成长收益仍未签收。</p></div>
<div class="grid"><div class="card"><span class="number">{t['run']}</span>不同回归用例<p>原{len(baseline)}项保留，新增{value['new_cases']}项</p></div><div class="card"><span class="number">10</span>浏览器流程<p>新增变更历史与三种结果分流</p></div><div class="card"><span class="number">{len(r['checks'])}</span>验收门通过<p>原性能预算与旧条件保持</p></div><div class="card"><span class="number">未测</span>真实质量和成长<p>合成反例不是独立用户留出集</p></div></div>
<h2>改进与预测效果放在一起看</h2><div class="scroll"><table><tr><th>改进</th><th>本轮证据</th><th>剩余边界</th></tr><tr><td>引用原话的新增、替换、撤销</td><td>明确变更后可得到当前有效要求；旧预算标记已替换，保修标记已撤销</td><td>含糊语句、手工Goal改写、执行后Work返工不能按此方式自动合并</td></tr><tr><td>未点名的条件保留</td><td>模型漏掉来源引用或增加未请求条件，会阻止受理</td><td>只按有限表达和精确目标引用，不等于语义理解所有说法</td></tr><tr><td>约束与报价资料分开核对</td><td>允许预算/交期上限随要求变化，修改报价项、价格、引用或币种被阻止</td><td>允许改预算不会授予换资料、外发或新增执行权限</td></tr><tr><td>来源失效继续反证旧结论</td><td>执行前变化零动作；首动作后变化不继续交付；历史回复变化使完成结论失效</td><td>已发生动作不撤销；没有跨库全局原子性证明</td></tr><tr><td>保留旧方式兼容性</td><td>旧414项全部保留；新策略版本变化不会使旧quote_sources模式失效</td><td>旧结果不能追认为已验证明确修订；未演练生产升级/热降级</td></tr></table></div>
<h2>一项明确修订怎样流经原系统</h2><div class="flow" role="img" aria-label="初始原话经已接受变更重放，形成有效要求，对照当前目标后沿原任务执行并独立验收"><div class="node">原话与会话要求</div><span class="arrow">→</span><div class="node">重放已接受变更</div><span class="arrow">→</span><div class="node">有效要求 + 历史去向</div><span class="arrow">→</span><div class="node">Goal / 输入对账</div><span class="arrow">→</span><div class="node">原Task与独立验收</div></div>
<div class="paths"><div><strong class="pass">明确一致</strong><p>剩余条件全部可核验，原授权与结果检查通过 → 可以结案。</p></div><div><strong class="warn">仍有未知条件</strong><p>新增保修等未支持要求 → 保留有效条件，部分成功不能宣告全部完成。</p></div><div><strong>变更含糊或错配</strong><p>找不到旧条件、引用不唯一、模型漏项、资料被换 → 阻止受理。</p></div></div>
<h2>本轮工程示例：改变两项，其他条件保留</h2><div class="scroll"><table><tr><th>原条件</th><th>明确操作</th><th>历史状态</th><th>当前有效条件</th></tr><tr><td>预算不超过100元</td><td>将要求「预算不超过100元」替换为「预算不超过90元」</td><td>已替换</td><td>预算不超过90元</td></tr><tr><td>必须保修三年</td><td>撤销要求「必须保修三年」</td><td>已撤销</td><td>不再属于本次要求</td></tr><tr><td>5天内、最低价、来源引用、本机保存</td><td>未点名修改</td><td>仍有效</td><td>全部继续核验</td></tr></table></div><p class="caption">对应本轮实际浏览器合成场景。撤销一条任务条件不会清除停止锁存、撤回历史动作或改变全局会话设置。</p>
<h2>执行与结案实测</h2><div class="scroll"><table><tr><th>合成场景</th><th>工具执行</th><th>结果验收</th><th>工作结案</th><th>动作单位</th></tr>{rows}</table></div><p class="caption">真实HTTP、隔离worker与浏览器，临时合成数据，零模型调用。动作单位不是token或货币。原观察器30次/组P95：{off}→{on} ms，增加{added} ms，小于原25 ms预算；未测新增重放器的规模性能。</p>
<h2>比预测更好，还是更差？</h2><p>工程预测得到支持：严格明确的替换/撤销不必永远停在“有修订未核对”，同时原条件不会因模型摘要而消失。无法从这些正反例推算实际用户的误拒率下降、工作成功率提升或token节省。</p><p>下一轮真实对照必须同时记录正确结案、错误结案、正确拒绝、不必要拒绝、人工介入与完整费用。当前没有独立且未参与规则编写的真实请求集，因此不填业务Q、成长分和收益百分比。原JPF/r1预测保留。</p>
<h2>三位一体与知识成长保持什么</h2><p>Direction得到可追溯的有效要求；Engagement沿原许可和账本执行并展示范围；Reflection用来源变化反证旧通过结论。仍共享原身份、Goal、Task与事实，没有第二执行器、数据库或最高权限角色。</p><p>本轮没有把一次报价通过变成可自动采用的经验。未知条件下的执行仍只是限定观察；自愈/自改造需要后续独立修复及验收。经验收益、负迁移和长期错误复发要另行测量。</p>
<h2>下一步的顺序与交付条件</h2><div class="scroll"><table><tr><th>顺序</th><th>具体工作</th><th>可以签收什么</th></tr><tr><td>1</td><td>执行后返工的逐项要求继承与显式变更；独立真实请求对照</td><td>完成记录保持事实，新版本能证明保留和变化范围；真实漏项/误拒率有证据</td></tr><tr><td>2</td><td>完整费用账和有限常设委托</td><td>常见低影响任务减少打扰，同时总费用和重要决策可控</td></tr><tr><td>3</td><td>带适用条件、反例、到期复核的经验候选</td><td>近似任务省成本且质量不退化；反例可暂停方法</td></tr><tr><td>4</td><td>单工作负责人、多Bot委派与租约接管</td><td>责任、停止、重复执行、接管冲突和总费用通过故障演练</td></tr></table></div>
<details><summary>完整验收门与失败记录</summary><div class="scroll"><table><tr><th>门</th><th>结果</th></tr>{gates}</table></div><p>冻结{snapshot['source_count']}个源码输入和{len(snapshot['supporting_input_digests'])}个支持输入。早期测试夹具的非法会话编号和过期工具引用，分别触发原接口拒绝；修正夹具后复测。浏览器探针原先强求刷新更换DOM，修为核对HTTP结果对应的视图签名和实际完成文字，保留原断言。失败记录不覆写。</p><p><a href="plan.json">实施前预测</a> · <a href="frozen-r1/run/report.html">联合验收</a> · <a href="frozen-r1/run/tests.json">逐项结果</a> · <a href="candidate-audit.json">候选源码审计</a> · <a href="delivery-checks.json">最终交付检查</a> · <a href="frozen-r1/run/real-task-trial-template.json">尚未运行的真实试验记录模板</a></p></details>
<p><a href="../../core-bootstrap.md#workflow-changes-runtime">Markdown：实施与目标保持</a> · <a href="../../contracts.md#workflow-changes-contract">契约</a> · <a href="../../delivery-validation.md#workflow-changes-evidence">预测与实测权威页</a></p>
<details><summary>实际界面：有效、已替换、已撤销</summary><img src="frozen-r1/run/quote_changes/review-desktop.png" alt="逐条变更与当前有效要求"><img src="frozen-r1/run/quote_changes/uncovered-review.png" alt="新增保修要求仍待独立核验"></details></main></html>'''
(HERE/'report.html').write_text(page,encoding='utf-8',newline='\n')
print(json.dumps(value,ensure_ascii=False))
