"""Record measured results only after frozen gates pass."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
r=json.loads((HERE/'verification.json').read_text('utf-8'));assert r['local_verdict']=='PASS'
def change(name,fn):
    p=ROOT/name;p.write_text(fn(p.read_text('utf-8')),encoding='utf-8',newline='\n')
summary=f"{r['tests']}项不同用例、{r['browser_workflows']}条浏览器流程及{r['gates']}道验收门全部通过"
change('README.md',lambda s:s.replace('专项与临时界面已通过，联合冻结验收待完成。',summary+'。[结论、流程与实测分数](docs/evidence/workflow-recovery-1.10.0/report.html) · '))
change('docs/core-bootstrap.md',lambda s:s.replace('本轮 implemented，专项和临时浏览器流程已验证；联合冻结验收待完成，证据集中在','本轮 implemented/verified（以下有限范围），'+summary+'；证据集中在'))
p95=r['original_observer_p95_ms']
actual=f'''**2026-10-27：冻结候选本地技术验收PASS；{summary}，零失败、零错误、零跳过。生产未部署，真实业务质量、token收益和长期成长未测。** [结论、流程与实际分数](evidence/workflow-recovery-1.10.0/report.html) · [联合验收](evidence/workflow-recovery-1.10.0/frozen-r2/run/report.json) · [不同测试记录](evidence/workflow-recovery-1.10.0/frozen-r2/run/tests.json)。'''
extra=f'''
| 最终测量 | 结果 | 可说明什么 |
|---|---|---|
| 旧基线＋新增 | 原{r['baseline_retained']}项全部保留＋新增{r['new_cases']}项 | 既有覆盖范围回归通过，不等于没有任何未知缺陷 |
| 浏览器 | 原11条＋恢复1条，共{r['browser_workflows']}条全部通过 | 真实UI→HTTP→临时执行→结果检查；合成数据、零模型调用 |
| 冻结输入 | {r['source_count']}源码＋{r['supporting_count']}支持输入 | 测试输入可核对；[最终交付检查](evidence/workflow-recovery-1.10.0/delivery-checks.json)要求交付源码与候选一致 |
| 原观察器P95 | {p95['off']:.3f}→{p95['on']:.3f}ms，差值{p95['added']:+.3f}ms | 原25ms阈值保留；不是恢复耗时和真实任务效率 |
| 正常恢复明确条件分 | 100%；VERIFIED/COMPLETE | 只适用于有限支持要求，semantic_goal_verified仍为false |
| 未知要求 | WAITING_EVIDENCE；无条件总分；不可晋升方法 | 不把执行完成或主观接受当作知识可信证据 |
| 错误工具输出 | NEEDS_CORRECTION | 独立判定未放宽；新版本不能继承旧分数 |
| 预测差距 | 有限技术预测达到；真实收益未知 | 不回写原JPF、不声称业务Q或学习收益提高 |

最终[恢复界面](evidence/workflow-recovery-1.10.0/frozen-r2/run/recovery/browser.json)、[执行记录](evidence/workflow-recovery-1.10.0/frozen-r2/run/recovery/runtime.json)及[源码差异审计](evidence/workflow-recovery-1.10.0/candidate-audit.json)分别保留。全仓既有3705项格式问题位于其他共享文件；本轮选定范围通过，未称全仓格式通过。[报告桌面/窄屏检查](evidence/workflow-recovery-1.10.0/report-ui.json)另行签收。其[首轮展开截图溢出](evidence/workflow-recovery-1.10.0/report-ui-r1.json)已修复为图片随父容器收缩；展示失败保留，未改运行代码。

'''
def evidence(s):
    s=s.replace('**结论：已实现反馈变化的有限新版本恢复，正在做联合冻结验收；不能据此签收通用自愈或业务质量提高。**',actual)
    s=s.replace('旧测试和门槛不变。', '旧测试和门槛不变；[两轮输入对照](evidence/workflow-recovery-1.10.0/compatibility-change-audit.json)确认仅一处源码文件变化、测试ID和性能阈值相同。')
    s=s.replace('| 事前预期 | 已有专项证据 | 仍待核对 |',extra+'| 事前预期 | 实测证据 | 仍待核对 |')
    s=s.replace('| 联合回归及真实误拒率 |','| 联合回归通过；真实误拒率未测 |')
    s=s.replace('新增停止/过期许可复验另存。','[停止/过期许可复验](evidence/workflow-recovery-1.10.0/authority-r4.log)2项通过。最终冻结重新执行全部30项新用例与480项旧用例。')
    s=s.replace('及[1.9返工继承](#workflow-inheritance-evidence)','、[1.9返工继承](#workflow-inheritance-evidence)及[1.10来源恢复](#workflow-recovery-evidence)')
    s=s.replace('[文本反馈](#completion-loop-evidence)和[关联返工](#workflow-rework-evidence)有局部实现/证据；通用修码进化未签收',
        '[文本反馈](#completion-loop-evidence)、[关联返工](#workflow-rework-evidence)及[反馈来源恢复](#workflow-recovery-evidence)有局部实现/证据；通用修码进化未签收')
    s=s.replace('[来源对账](#workflow-sources-evidence)、[明确变更](#workflow-changes-evidence)与[返工继承](#workflow-inheritance-evidence)沿原Goal、Task、许可和Completion增量接入',
        '[来源对账](#workflow-sources-evidence)、[明确变更](#workflow-changes-evidence)、[返工继承](#workflow-inheritance-evidence)与[来源恢复](#workflow-recovery-evidence)沿原Goal、Task、许可和Completion增量接入')
    s=s.replace('及[1.9全量返工继承](#workflow-inheritance-evidence)为有限报价任务提供局部链路',
        '、[1.9全量返工继承](#workflow-inheritance-evidence)及[1.10反馈来源恢复](#workflow-recovery-evidence)为有限报价任务提供局部链路')
    return s
change('docs/delivery-validation.md',evidence)
print(summary)
