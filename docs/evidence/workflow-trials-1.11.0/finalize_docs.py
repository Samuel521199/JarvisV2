"""Record measured outcomes in the existing authoritative chapters only."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads((HERE/p).read_text('utf-8'))
v=read('verification.json');p=v['original_observer_p95_ms'];cost=read('cost-overview.json')
def replace(name,old,new):
    path=ROOT/name;s=path.read_text('utf-8');assert s.count(old)==1,(name,old[:60]);path.write_text(s.replace(old,new),encoding='utf-8',newline='\n')

replace('README.md',
'**三领域对照 1.11.0：**报价、资料整理/Markdown交付、学习练习/复盘均进入冻结试验与分领域核验；已接真实对话、回执、原会话文件与费用估算。首轮暴露路由和输出上限问题，后续试跑与联合验收进行中。[实施](docs/core-bootstrap.md#workflow-trials-runtime) · [预测、实测与缺口](docs/delivery-validation.md#workflow-trials-evidence)。尚不能签收全功能优秀或真实长期收益，未部署。',
'**三领域对照 1.11.0：**报价、资料整理/Markdown交付、学习练习/复盘全部实测；修正助手协议与仅回复路由提示。538项不同用例、12条浏览器流程、30道验收门通过；修复后两轮48次调用，47轮冻结硬条件通过、1轮超时待测。正文补审仍发现无依据扩写及计划保留缺口，不能将字段通过率当作全文质量。[结论、图表与逐轮证据](docs/evidence/workflow-trials-1.11.0/report.html) · [实施](docs/core-bootstrap.md#workflow-trials-runtime) · [实测与缺口](docs/delivery-validation.md#workflow-trials-evidence)。仍仅6个合成任务，完整助手、真实净收益未签收，未部署。')

path=ROOT/'docs/delivery-validation.md';s=path.read_text('utf-8');start=s.index('<a id="workflow-trials-evidence"></a>');end=s.index('<!-- book-footer:start -->',start)
section=f'''<a id="workflow-trials-evidence"></a>
## 三领域对照 1.11.0：分开测质量、交付和代价

**结论：三类都实测，采集、对照与归因达到本地技术验收；“全功能都优秀”尚未达到。** 原510项完整保留，新写24项试验检查与原有4项个人工作流补入联合验收，共{v['tests']}项不同用例、12条浏览器流程、30道门通过。真实试跑触发了助手协议与仅回复路由提示修正；修复后两轮48次调用，47轮硬条件通过、1轮超时待测。正文补审仍有无依据扩写及计划约束遗漏。[图表报告](evidence/workflow-trials-1.11.0/report.html) · [事前计划](evidence/workflow-trials-1.11.0/plan.json) · [验证汇总](evidence/workflow-trials-1.11.0/verification.json) · [实施](core-bootstrap.md#workflow-trials-runtime) · [契约](contracts.md#workflow-trials-contract)。未部署。

| 改进与预测 | 实际结果 | 与完整目标的差距 |
|---|---|---|
| 冻结参考与配置；坏结果能归因 | 原始模型协议、路由、回执、会话文件与费用均留证；缺轮不算完整配对 | 独立真实样本、自由语言语义仍不足 |
| 区分助手外层协议与reply内JSON，明确仅回复走chat | 第二轮协议/路由失败；修复后两轮已交付47轮未再出现，另1轮超时 | 单模型、6题重复观察，不证明普遍根治或因果净收益 |
| 分域检查避免平均分掩盖短板 | 三域分别列通过/失败/待测；正文补审单独登记缺口 | 字段满分不证明正文忠实，不能成为业务Q |
| 保留旧失败与全部代价 | 四轮共81次调用，已知API估算USD {cost['known_api_estimates_all_rounds']['USD']:.7f}，另1次用量未知 | 人工、本机计算和供应商账单未核销，完整费用未知 |

闭环观察：`事前冻结 → 原助手执行 → 文件与用量回读 → 分域硬检查＋正文补审 → 定位协议/路由/超时/内容问题 → 小范围修正 → 新轮复测并保留旧失败 → 未见题与真实任务再决定采用`。本轮完成技术采集与修复复测；正文忠实性、长期学习和正式经验晋升仍未闭合，不以已完成的前半段代替整个目标。

| 领域（每轮2个不同任务） | r3 关闭/开启工作流 | r4 关闭/开启工作流 | 测到什么、没测什么 |
|---|---|---|---|
| 报价/多约束比较 | 2通过 / 2通过 | 2通过 / 2通过 | 合格集合、最低价、来源和无合格项；none/none同路径控制，不能归因技能收益；未核实供应商或实际采购 |
| 资料整理/文档 | 2通过 / 1通过1待测 | 2通过 / 2通过 | 当前字段、来源更正、冲突裁决和文件回读；正文有额外缺口，任意长文、Word/PDF未验 |
| 学习/复盘 | 2通过 / 2通过 | 2通过 / 2通过 | 出题、纠错、不提前泄露重试答案、未答不能写掌握；用户独立掌握、延迟保持、情绪体验未验 |

全部为自建合成样本，只有6个不同任务；每轮两配置共预定24个对话轮次，重复四轮不扩充独立样本数。真实模型不等于真实用户任务。Q、情绪体验、长期学习、真实自主收益与预测差值保持null。工作流开关只比较当前代码中技能指导的有无；没有未测的旧版真实业务对照，不能凭跨轮数字声称整个1.11净收益。

| 真实模型轮次 | 记录/计划轮次 | 完整配对 | 主要观察 |
|---|---|---|---|
| [r1](evidence/workflow-trials-1.11.0/live-r1/summary.json) | 10/24 | 2/6 | Gemini 3.8 Flash/MEDIUM、1800上限；报价通过，文档误转Goal，连续3次回复不完整后停止；学习未运行 |
| [r2](evidence/workflow-trials-1.11.0/live-r2/summary.json) | 23/24 | 5/6 | 同模型LOW、4096；三域运行，文档路由和assistant_invalid仍失败，学习一项协议失败 |
| [r3](evidence/workflow-trials-1.11.0/live-r3/summary.json) | 24/24 | 5/6 | 提示修正后23轮通过；文档更正开启工作流的第二轮60秒model_timeout，UNKNOWN，费用用量未知 |
| [r4](evidence/workflow-trials-1.11.0/live-r4/summary.json) | 24/24 | 6/6 | 相同源码、配置和参考的独立复测，24轮硬条件通过；不能覆盖r3超时 |

首轮用量显示每次约1725推理token＋71正文token接近1800上限。[第一修订](evidence/workflow-trials-1.11.0/plan-amendment-r1.json)事前固定后续LOW/4096；用户默认设置不改。原v1把响应失败列待测，v2明确区分已知交付失败与UNKNOWN；旧统计不追改。[第二修订](evidence/workflow-trials-1.11.0/plan-amendment-r2.json)仅改变助手提示边界，保留解析器与原Goal权限；增加解析前原始输出。[第三修订](evidence/workflow-trials-1.11.0/plan-amendment-r3.json)事前约定只作一次完整独立复测，不挑最好轮次替换旧记录。跨轮配置、评估版本与提示有变化，只描述观察，不作因果推断。[全部代价](evidence/workflow-trials-1.11.0/cost-overview.json)使用当时SDK费率快照，不是核销账单。

**字段通过但正文仍有问题。** [补充正文审阅](evidence/workflow-trials-1.11.0/semantic-review.json)为事后模型辅助审阅，不是独立人工金标准，也不追改冻结分数。r4文档把原始“烘焙失败”扩写成“异常中断”；更正轮把“明天排查”改为“启动并执行烘焙”，没有保留原时间与动作。修正烘焙状态后计划是否需要改变可以提出建议，但应与已确认计划分开，不能静默替换。后续要把事实、推断、建议、旧计划去向及正文/字段一致性纳入新一轮冻结规则，用未见任务验证；不能仅给当前6题补关键词便宣布语义核验完成。

[离线首轮](evidence/workflow-trials-1.11.0/narrow-r1.log)21项中2项失败：替身忽略同末轮文字的不同学习上下文。修正替身选取整段会话后[21项通过](evidence/workflow-trials-1.11.0/narrow-r2.log)，未改领域参考。补缺轮配对、交付失败与UNKNOWN分离、配置边界后[28项通过](evidence/workflow-trials-1.11.0/narrow-r3.log)；提示与采集调整后[同28项通过](evidence/workflow-trials-1.11.0/narrow-r4.log)。

文档预检曾把生成.md证据当成未登记章节。未放宽检查器：前两轮[原包r1](evidence/workflow-trials-1.11.0/live-r1-original.zip)、[原包r2](evidence/workflow-trials-1.11.0/live-r2-original.zip)逐文件核对字节一致后，仅把阅读副本改为.md.txt，旧相对路径和记录完整保存在ZIP中。[r1映射](evidence/workflow-trials-1.11.0/live-r1/artifact-storage.json)与[r2映射](evidence/workflow-trials-1.11.0/live-r2/artifact-storage.json)可复核；后续直接采集证据文本后缀，原会话.md保持原格式。

[冻结联合验收](evidence/workflow-trials-1.11.0/frozen-r1/run/report.json)冻结{v['source_count']}个源码输入、{v['supporting_count']}个支持输入；原观察器p95关闭{p['off']:.3f}ms、开启{p['on']:.3f}ms，增加{p['added']:.3f}ms，小于原25ms门限。[交付审计](evidence/workflow-trials-1.11.0/delivery-checks.json)核对当前源码与冻结一致、文档/架构/选定差异、报告1400/390像素及原预测摘要；共享树其他改动的格式发现单独保留，不声称全树格式通过。原任务、取消、预算、记忆、权限与工作流用例全部保留；这不等于全部现实场景已验证。

下一步按[真实任务协议](#completion-real-work-acceptance)先扩三域独立真实请求与未见保留题，优先补正文忠实性和计划保留，再做可用性分类、完整费用与有限委托；之后才扩大条件化经验采用与多Bot责任链。学习与陪伴并行取得独立作答、延迟复测及体验反馈。正式评分、知识库晋升和V-TRI/V-CLC完整目标保持原状态，不把本轮试验自动写成长期记忆或默认策略。

'''
path.write_text(s[:start]+section+s[end:],encoding='utf-8',newline='\n')

path=ROOT/'docs/core-bootstrap.md';s=path.read_text('utf-8');start=s.index('<a id="workflow-trials-runtime"></a>');end=s.index('<!-- book-footer:start -->',start)
chunk=s[start:end]
lines=chunk.splitlines()
for i,line in enumerate(lines):
    if line.startswith('**'):
        lines[i]='**implemented；本地技术verified，实际业务质量未签收。** 538项不同用例、12条浏览器流程及30道门通过。三领域真实模型试跑与修复复测已完成；修复后48轮中47轮硬条件通过、1轮超时待测，正文补审仍有事实扩写与计划保留缺口。完整结果归[权威验收](delivery-validation.md#workflow-trials-evidence)，不能用字段检查替代Q或全功能优秀。[实际契约](contracts.md#workflow-trials-contract)。'
        break
else:raise AssertionError('status paragraph missing')
path.write_text(s[:start]+'\n'.join(lines)+'\n\n'+s[end:],encoding='utf-8',newline='\n')
replace('docs/decisions-review.md',
'接下来用独立真实请求与未见保留题扩大对照，测清误放行、误拒、人工介入及完整成本，再接完整费用与有限常设委托、条件化经验候选及多Bot责任链；',
'本轮正文补审仍见无依据扩写和计划约束遗漏；接下来先补正文与字段一致、事实/推断/建议分离及计划保留，用三域独立真实请求和未见保留题验证，再测误放行、误拒、人工介入及完整成本，接完整费用与有限常设委托、条件化经验候选及多Bot责任链；')
print('Updated measured outcomes in README, core bootstrap and delivery validation')
