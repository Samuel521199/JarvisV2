"""Record only completed frozen results in the existing authority pages."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
v=json.loads((HERE/'verification.json').read_text('utf-8'));assert v['local_verdict']=='PASS'
p=ROOT/'docs/delivery-validation.md';s=p.read_text('utf-8')
old='**当前 implemented，最终冻结回归待完成；生产未部署。**'
new=f'''**2026-10-27：最终冻结候选本地技术验收PASS；{v['tests']}项不同用例全部通过，零失败、零错误、零跳过；11条浏览器流程和{v['gates']}道验收门全部通过。生产未部署，真实业务Q、费用收益及长期成长未测。** [结论、流程与实际分数](evidence/workflow-inheritance-1.9.0/report.html) · [最终联合验收](evidence/workflow-inheritance-1.9.0/frozen-r3/run/report.json) · [逐项用例](evidence/workflow-inheritance-1.9.0/frozen-r3/run/tests.json)。'''
assert old in s;s=s.replace(old,new)
start=s.index('<a id="workflow-inheritance-evidence">');end=s.index('<!-- book-footer:start -->',start)
extra=f'''实际结果：新增{v['new_cases']}项、保留原{v['baseline_retained']}项；最终[浏览器流程](evidence/workflow-inheritance-1.9.0/frozen-r3/run/quote_rework/browser.json)实际创建返工版本、修改输入、查看继承链并运行。[执行记录](evidence/workflow-inheritance-1.9.0/frozen-r3/run/quote_rework/runtime.json)显示正常变更为VERIFIED/COMPLETE，受支持条件分100；未知保修继承后为WAITING_EVIDENCE/NEEDS_EVIDENCE，条件分为空；模型遗漏来源引用的子版未受理。条件分不是业务Q或智能分，未知项不以0分或父版分数代替。两个执行场景各父2＋子2＝4成本单位，另有三次接续累计8单位测试；模型调用为0，完整token与费用收益仍为空。

本轮预测在有限正反例范围得到支持，不能推算真实成功率提升或误拒率下降。冻结{v['source_count']}个源码输入及{v['supporting_count']}个支持输入；原观察器P95为{v['original_observer_p95_ms']['off']:.3f}→{v['original_observer_p95_ms']['on']:.3f}ms，增加{v['original_observer_p95_ms']['added']:.3f}ms，低于原25ms门槛；不是新继承核验的规模性能。[原预测与工作状态审计](evidence/workflow-inheritance-1.9.0/candidate-audit.json)保留原摘要；[最终交付检查](evidence/workflow-inheritance-1.9.0/delivery-checks.json)覆盖文档、架构、报告窄屏与最终源码一致性。

失败和修复保留：[首轮专项](evidence/workflow-inheritance-1.9.0/narrow-r1.log)21项通过；[扩展轮](evidence/workflow-inheritance-1.9.0/narrow-r2.log)28项中取消测试误认为已取消任务仍能调用启动，原接口返回invalid_state。修正测试预期，继续检查CANCELLED及零动作，[取消复验](evidence/workflow-inheritance-1.9.0/cancel-r3.log)通过，未修改执行机制。[首轮冻结](evidence/workflow-inheritance-1.9.0/frozen-r1/result.json)已全部通过；随后发现三个文件被写为CRLF，[仅恢复原LF](evidence/workflow-inheritance-1.9.0/format-normalization.json)后再次冻结，第二轮479项通过，但[原预算浏览器门失败](evidence/workflow-inheritance-1.9.0/frozen-r2/run/budget/browser.json)：详情先读PREPARED交付，后读SUCCEEDED任务，形成混合时刻响应。[补充修复范围](evidence/workflow-inheritance-1.9.0/plan-amendment-r1.json)先冻结；[稳定复现](evidence/workflow-inheritance-1.9.0/consistency-reproduction.json)后将详情及观察评价放在同一核心账本事务，新用例通过，原预算断言不变。[最终第三轮](evidence/workflow-inheritance-1.9.0/frozen-r3/result.json)重新通过全部验收。重复轮次不计为新增用例。全仓仍有非本轮文件的既有格式问题；本轮修改范围的格式检查单独签收，不称全仓通过。

下一步先补已受理版本来源失效后的新版本恢复路径（现有重审仅支持未受理草案），同步收集独立真实请求并做成对评测，再接完整费用与有限常设委托、条件化经验候选及多Bot负责人/委派。当前未签收通用自然语言、部分前缀语义复用、自动诊断修码、自主发布、长期知识增益或多机器人控制。

'''
s=s[:end]+extra+s[end:]
s=s.replace('及[1.8明确变更](#workflow-changes-evidence)的预测','、[1.8明确变更](#workflow-changes-evidence)及[1.9返工继承](#workflow-inheritance-evidence)的预测')
s=s.replace('[来源对账](#workflow-sources-evidence)与[明确变更](#workflow-changes-evidence)沿原Goal','[来源对账](#workflow-sources-evidence)、[明确变更](#workflow-changes-evidence)与[返工继承](#workflow-inheritance-evidence)沿原Goal')
s=s.replace('| 原话/明确变更→Goal→结果验收 | [1.7来源对账](#workflow-sources-evidence)和[1.8明确变更](#workflow-changes-evidence)为有限报价任务提供局部链路 | 仍需执行后返工的逐项继承、自由语言与混杂上下文、独立真实请求和完整费用证据 |','| 原话/变更/返工继承→Goal→结果验收 | [1.7来源对账](#workflow-sources-evidence)、[1.8明确变更](#workflow-changes-evidence)及[1.9全量返工继承](#workflow-inheritance-evidence)为有限报价任务提供局部链路 | 仍需部分复用的语义依据、自由语言与混杂上下文、独立真实请求和完整费用证据 |')
p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'docs/core-bootstrap.md';s=p.read_text('utf-8').replace('实现状态 implemented；最终验证以[验收记录](delivery-validation.md#workflow-inheritance-evidence)为准。','实现状态 implemented/verified（以下有限范围）；最终冻结证据见[验收记录](delivery-validation.md#workflow-inheritance-evidence)。')
s=s.replace('后续先建立独立真实请求样本、扩展执行后返工的逐项来源关系，再接完整费用和有限常设委托；','执行后全量返工的逐项继承见[1.9](#workflow-inheritance-runtime)；后续先建立独立真实请求样本，再接完整费用和有限常设委托；')
s=s.replace('报价成功不会自动成为可复用知识；','研发与生产采用的分离仍按[退化处理规则（proposed）](evolution-release.md#growth-regression-policy)验收。报价成功不会自动成为可复用知识；')
p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'docs/decisions-review.md';s=p.read_text('utf-8');old='接下来优先补执行后Work返工的逐项条件继承和独立真实请求对照，再接完整费用与有限常设委托；'
assert old in s;s=s.replace(old,'[1.9返工继承](core-bootstrap.md#workflow-inheritance-runtime)已补有限报价的全量重做条件链，[实际证据](delivery-validation.md#workflow-inheritance-evidence)分别记录。接下来先补已受理版本来源失效后的新版本恢复，同时收集独立真实请求并进行对照，再接完整费用与有限常设委托、条件化经验候选及多Bot责任链；');p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'README.md';s=p.read_text('utf-8');lines=s.splitlines();idx=next(i for i,line in enumerate(lines) if line.startswith('**明确变更 1.8.0：**'))
lines[idx+1:idx+1]=['',f"**返工继承 1.9.0：**已执行版本可保留全部有效要求，按明确指令变更；纠错保持标准，新结果独立验收。原451项与新增{v['new_cases']}项、11条浏览器流程及{v['gates']}道验收门通过。[结论、流程与实测分数](docs/evidence/workflow-inheritance-1.9.0/report.html) · [实施与边界](docs/core-bootstrap.md#workflow-inheritance-runtime) · [验收记录](docs/delivery-validation.md#workflow-inheritance-evidence)。限于有限报价的全量返工；原回执、预算及取消机制保持，真实收益和自动改造未签收，未部署。"]
p.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print('Recorded final measured evidence in existing authority pages')
