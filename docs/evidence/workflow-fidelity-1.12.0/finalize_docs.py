"""Publish measured fidelity evidence into the existing authority pages."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads((HERE/p).read_text('utf-8'))
v=read('verification.json');cost=read('cost-overview.json');review=read('prose-review.json');p=v['original_observer_p95_ms']
def write(path,s):path.write_text(s,encoding='utf-8',newline='\n')
def replace_section(name,anchor,text):
    f=ROOT/name;s=f.read_text('utf-8');start=s.index('<a id="'+anchor+'"></a>');end=s.index('<!-- book-footer:start -->',start)
    write(f,s[:start]+text+'\n\n'+s[end:])
def count(d):return f"{d.get('PASS',0)}通过、{d.get('FAIL',0)}失败、{d.get('UNMEASURED',0)}待测"
names=('baseline-r1','candidate-r1','reserved-r1','v1-replay-r1')
summaries={n:read(n+'/summary.json') for n in names}
table='| 领域 | 同六题：旧提示→候选（关闭/开启工作流） | 三保留题（关闭/开启） | 原v1回放（关闭/开启） |\n|---|---|---|---|\n'
for d,label in [('comparison','报价/多约束'),('documents','资料/文档'),('learning','学习/复盘')]:
    def domain(n):return ' / '.join(count(summaries[n]['domains'][d][arm]) for arm in ('workflow_off','workflow_on'))
    table+=f'| {label} | {domain("baseline-r1")} → {domain("candidate-r1")} | {domain("reserved-r1")} | {domain("v1-replay-r1")} |\n'
rounds='| 轮次 | 已记录/预定 | 硬条件（含缺测） | 完整配对 |\n|---|---|---|---|\n'
for n,s in summaries.items():rounds+=f'| [{n}](evidence/workflow-fidelity-1.12.0/{n}/summary.json) | {s["recorded_turns"]}/{s["planned_turns"]} | {count(v["round_counts"][n])} | {s["complete_pairs"]}/{s["independent_cases"]} |\n'
reviews='| 补审项 | 观察 | 状态 |\n|---|---|---|\n'+''.join(f'| {x["id"]} | {x["observation"]} | {x["status"]} |\n' for x in review['findings'])
text=f'''<a id="workflow-fidelity-evidence"></a>
## 正文忠实性 1.12.0：从字段正确补到正文与计划一致

**结论：限定来源摘录正文核验与通用提示修订已实现，并通过本地技术验收；任意自由文本忠实性与真实净收益仍未签收。** 原538项全部保留，新增{v['new_tests']}项，共{v['tests']}项不同用例、12条浏览器流程、30道门通过。候选同六题与三保留题合计36轮：{count(v['candidate_v2_pooled'])}。旧Markdown模式另作回放与正文补审，具体结果下列，不用字段分替代全文质量。[图表报告](evidence/workflow-fidelity-1.12.0/report.html) · [验证汇总](evidence/workflow-fidelity-1.12.0/verification.json) · [事前计划](evidence/workflow-fidelity-1.12.0/plan.json) · [实施](core-bootstrap.md#workflow-fidelity-runtime) · [契约](contracts.md#workflow-fidelity-contract)。未部署。

**自由正文修复未达预期。** 原v1的24轮字段检查通过，但开启日志工作流后仍将失败扩写为“异常阻断”，更正时仍未保留“明天排查”；还出现缺少真实回执的归档措辞。TRIAL-SEM-01/02继续OPEN；限定新格式的36轮通过不能替代原模式的语义质量。后续要接来源/当前计划表示与可见的修订核对，不能只叠提示就宣称修好。

| 改进与预测 | 实际核验 | 尚未证明 |
|---|---|---|
| 事实、推断、建议分开；更正不静默改计划 | 原assistant提示明确保留动作、时间和禁止条件；撤销、改期、替换仍有效 | 提示不能保证所有自由回答忠实 |
| 正文与有来源的证据字段一致 | 当前依据覆盖、逐字支持、计划版本、重复引用、额外正文、Markdown转义均有反例测试 | 不认证来源在现实中为真，不认证建议质量 |
| 字段正确但正文错误不再漏检 | 旧提示真实试跑两轮选中方案正确，但遗漏另一方案的当前来源，v2按覆盖条件判FAIL | 严格摘录口径不适合直接评价所有合理摘要；须继续测误拒 |
| 修复后用新题及旧模式复测 | 同六题仅host/assistant.py有源码差异；三题候选冻结后首次运行；原v1六题单列回放 | 单次合成试验，不能宣布普遍泛化或因果质量增益 |

流程：`冻结材料、当前事实与计划 → 原助手生成 → 来源支持＋当前覆盖＋正文一致 → 分域失败归因 → 新候选复测 → 保留题＋旧模式回放 → 记录剩余缺口`。试验器不静默改写答案，旧失败和正式评分不追改。观察策略只负责检查，不增加执行权限，也不自动晋升经验。

{table}
{rounds}
本轮9个新合成任务（6对照＋3程序性保留），加6个旧任务回放，均非独立真实用户请求。保留题在候选冻结后首次运行，没有按其输出调参重测；但题目仍由同一开发方制作，不能等同盲测人工集。报价两组none/none为同路径控制，不能算工作流收益。条件分只反映冻结要求，schema不同不直接比较高低；Q、长期学习、情绪体验、真实净收益及原JPF预测差值保持null。

**原模式正文补审。** 依据[补审记录](evidence/workflow-fidelity-1.12.0/prose-review.json)检查原问题TRIAL-SEM-01/02和文档范围。这是事后模型辅助审阅，不是独立人工金标准，不追改冻结分数。

{reviews}
旧提示基线的两个FAIL来自同一个报价任务漏掉未选方案的来源，方案选择本身正确；这是严格来源覆盖检查发现的差异。题干中“当前有效事实”的全量含义仍需更明确，后续真实摘要任务应事前约定覆盖范围，不能把所有压缩都定为退步。对于自由改写、长文和建议适当性，仍须独立人工或经过校准的语义复核。

费用共{cost['calls']}次调用，已知{cost['known_tokens']} token，已知API估算USD {cost['known_api_estimates'].get('USD',0):.7f}，另{cost['unpriced_attempts']}次用量或价格未知。[费用明细](evidence/workflow-fidelity-1.12.0/cost-overview.json)使用调用时SDK费率快照，尚未核销供应商账单；人工、本机成本未知，不能据此声称省token、全成本下降或净效率提高。

[事前提示修订](evidence/workflow-fidelity-1.12.0/prompt-plan.json)在查看新基线答案前记录；[补回放的事前修订](evidence/workflow-fidelity-1.12.0/plan-amendment-v1-regression.json)增加原v1模式最多24次调用，总上限84次，无自动重试。原基线在修改提示前已[回读核验](evidence/workflow-fidelity-1.12.0/baseline-prechange-recheck.json)；候选与保留题和v1回放均绑定最终源码，不能将基线旧源码误写为当前候选。

专项[首轮失败](evidence/workflow-fidelity-1.12.0/narrow-r1.log)是错误导入测试夹具，导致模块未加载；修正导入后[23项通过](evidence/workflow-fidelity-1.12.0/narrow-r2.log)，与原试验及个人工作流[51项合跑通过](evidence/workflow-fidelity-1.12.0/narrow-combined.log)，实际提示修订后[同51项通过](evidence/workflow-fidelity-1.12.0/narrow-candidate.log)。未删断言或降验收门。

[完整冻结验收](evidence/workflow-fidelity-1.12.0/frozen-r1/run/report.json)使用{v['source_count']}个源码、{v['supporting_count']}个支持输入；原观察器p95关闭{p['off']:.3f}ms、开启{p['on']:.3f}ms，增加{p['added']:.3f}ms，小于原25ms门限。[交付审计](evidence/workflow-fidelity-1.12.0/delivery-checks.json)核对当前源码、原始试验重算、文档/架构/选定差异、报告1400/390像素及原预测摘要。共享树其他改动的3705处格式发现保留，未擅自改动，不宣称全树格式通过。

下一步先用三领域独立真实请求明确全文与摘要覆盖，扩自由改写、长文、矛盾资料及未见表达，测误放行/误拒；随后影子接入交付核对，达到要求再扩大自动修订。完整费用、有限委托、条件化经验采用和多Bot责任链继续按[后续顺序](decisions-review.md#real-work-followup-analysis)。正式评分、知识库晋升及V-TRI/V-CLC完整目标不因本轮部分验证而签收。
'''
replace_section('docs/delivery-validation.md','workflow-fidelity-evidence',text)
f=ROOT/'docs/core-bootstrap.md';s=f.read_text('utf-8');old='**限定正文核验已implemented，实际收益待本轮验收。**'
assert s.count(old)==1
write(f,s.replace(old,f'**implemented；本地技术verified，真实业务质量未签收。** {v["tests"]}项不同用例、12条浏览器流程、30道门通过；候选36轮v2检查{count(v["candidate_v2_pooled"])}。旧Markdown回放仍复现日志工作流中的扩写与计划遗漏，通用提示修复未达预期；[实际验收](delivery-validation.md#workflow-fidelity-evidence)保留反证。'))
f=ROOT/'README.md';s=f.read_text('utf-8');anchor='**三领域对照 1.11.0：**';assert s.count(anchor)==1 and '**正文忠实性 1.12.0：**' not in s
intro=f'**正文忠实性 1.12.0：**新增来源摘录正文与计划一致性核验，更新原助手事实/推断/建议及计划保留提示。{v["tests"]}项不同用例、12条浏览器流程、30道门通过；候选v2共36轮，{count(v["candidate_v2_pooled"])}。但旧Markdown回放仍复现日志工作流中的扩写与计划遗漏，通用提示修复未达预期。[结论与图表](docs/evidence/workflow-fidelity-1.12.0/report.html) · [实施边界](docs/core-bootstrap.md#workflow-fidelity-runtime) · [实测和未闭合项](docs/delivery-validation.md#workflow-fidelity-evidence)。限定摘录协议不等于通用语义核验，未部署，完整助手与真实净收益未签收。\n\n'
write(f,s.replace(anchor,intro+anchor))
f=ROOT/'docs/decisions-review.md';s=f.read_text('utf-8');anchor='本轮正文补审仍见无依据扩写和计划约束遗漏；'
assert s.count(anchor)==1
write(f,s.replace(anchor,'1.11正文补审发现无依据扩写和计划约束遗漏；[1.12正文忠实性](core-bootstrap.md#workflow-fidelity-runtime)已补限定摘录核验与通用提示，并登记[新题、保留题及原模式回放](delivery-validation.md#workflow-fidelity-evidence)，自由语言和真实净收益仍待验证；'))
print('Recorded measured 1.12 evidence in authoritative pages and README')
