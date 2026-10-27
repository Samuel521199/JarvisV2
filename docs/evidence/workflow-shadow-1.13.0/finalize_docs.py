"""Update existing authoritative sections from final measured evidence only."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
v=json.loads((HERE/'verification.json').read_text('utf-8'))
assert v['local_verdict']=='PASS' and v['tests']==591
def save(name,text):(ROOT/name).write_text(text,encoding='utf-8',newline='\n')
s=(ROOT/'docs/core-bootstrap.md').read_text('utf-8')
s=s.replace('**implemented；专项和工作台探针已通过，完整联合验收待本轮登记。**','**implemented；2026-10-27最终冻结候选591项回归、13条浏览器流程、32道门通过；仅本节数据链范围verified，生产未部署。**')
save('docs/core-bootstrap.md',s)
s=(ROOT/'docs/delivery-validation.md').read_text('utf-8')
start=s.index('<a id="workflow-shadow-evidence"></a>')
end=s.index('<!-- book-footer:start -->',start)
section='''<a id="workflow-shadow-evidence"></a>
## 交付影子核对 1.13.0：先记录误判，再考虑自动化

**2026-10-27，implemented；显式依据到回复观察的数据链在限定场景verified，自动语义审核未签收，生产未部署。** 用户声明、版本冻结、原Host交付、核对观察与工作台修订已串联。原561项不同用例全部保留，新增30项；最终冻结候选591项、13条浏览器流程、32道验收门通过。三类合成场景的24次真实模型调用中，预设字段/限定格式检查24次通过；这不是全文语义通过率，也不证明全功能优秀。[结论与图表](evidence/workflow-shadow-1.13.0/report.html) · [事前范围](evidence/workflow-shadow-1.13.0/plan.json) · [最终技术验收](evidence/workflow-shadow-1.13.0/frozen-r2/run/report.html) · [实施](core-bootstrap.md#workflow-shadow-runtime) · [契约](contracts.md#workflow-shadow-contract)。

| 改进／事前预期 | 实际观测 | 结论与预测差距 |
|---|---|---|
| 同会话事实、计划与回复可追溯 | 原发送事务保存快照；排队、重启、冲突、修订、清空与旧观察失效有回归和界面证据 | 限定数据链符合预期；未实现自动可信提取 |
| 影子观察不替代原交付 | 检查异常保留原回复和状态；would_block=false、quality_score=null，无额外模型调用 | 限定异常隔离通过；依据上下文会影响生成内容，不能声称输出完全不受影响 |
| 逐字缺失可能只是改写 | 15条预设校准：6正确提示、3误提示、3漏提示、3正确不提示 | 证明当前观察器不能直接用于自动结案；未预设总体误报率目标 |
| 更正回到下一轮 | 报价更新、日志状态更正、复测改期均进入新轮；原计划和显式撤销有局部正面观察 | 是重复合成场景，不能推导独立真实任务收益 |
| 质量、费用与成长收益不预填 | 无独立真实请求、长期跟踪和完整费用 | Q、收益及JPF预测差值仍未测；不能把工程通过率当业务分 |

| 三域共用试验条件 | 自由正文格式 | 来源摘录格式 |
|---|---|---|
| 同3个基础场景：报价、文档、学习；每个2轮×工作流开关2臂 | 12次模型调用、12次字段检查通过 | 12次模型调用、12次限定检查通过 |
| 原回复旁边的影子观察 | 12次REVIEW，可能改写或遗漏，不能算12个已确认错误 | 12次EXCERPT_MATCH，仅代表摘录符合显式声明 |
| 已知token / API估算 | 21826 / USD 0.0242475 | 23988 / USD 0.025086 |
| 数据来源 | 独立于隐藏答案的显式依据包，模拟用户填写 | 同3个场景的另一输出格式；不是新增独立样本 |

共24次、45814已知token、API估算USD 0.0493335；人工、本地计算及供应商账单对账未计，完整费用为空。[成本](evidence/workflow-shadow-1.13.0/cost-overview.json) · [自由正文原汇总](evidence/workflow-shadow-1.13.0/live-prose-r1/summary.json) · [摘录原汇总](evidence/workflow-shadow-1.13.0/live-excerpt-r1/summary.json)。工作流开关各臂均通过当前字段条件，不证明相对增益。核对器不额外请求模型，但依据进入上下文会增加输入token；本轮没有无依据消融，不能宣称零成本或更省token。

[15条反例校准](evidence/workflow-shadow-1.13.0/calibration.json)为第一方预设合成样本，不能估计真实分布误判率。合理改写会被逐字缺失误报，原文保留后添加无依据结论可能漏提示。[全部12条自由正文事后复看](evidence/workflow-shadow-1.13.0/prose-review.json)发现日志增加未提供的“当前无进行中导出任务”，学习文字把“只看过”写成“完成学习”有夸大风险。复看由助手完成，不是独立人工评分；原TRIAL-SEM-01/02仍OPEN，不因新小样本保留计划而关闭。

失败与修复均保留：[专项首轮](evidence/workflow-shadow-1.13.0/narrow-r1.log)27项通过，补边界后[相关模块合跑106项](evidence/workflow-shadow-1.13.0/narrow-r2.log)通过，最终专项30项已纳入591项。[UI r1](evidence/workflow-shadow-1.13.0/ui-r1/browser.json)在初始化完成前填写且清理遗漏临时mail服务；[r2](evidence/workflow-shadow-1.13.0/ui-r2/browser.json)错误期待200，原接口实际202。修复探针后r3通过基础断言，但目视发现窄屏发送按钮底边868px超出844px视口约24px；[事前修复补记](evidence/workflow-shadow-1.13.0/plan-amendment-mobile.json)后限制编辑区高度并补按钮可见断言，[r4](evidence/workflow-shadow-1.13.0/ui-r4/browser.json)底边760px，最终联合界面也通过。未放宽产品准入。

[frozen-r1](evidence/workflow-shadow-1.13.0/frozen-r1-interruption.json)无完整结果，恢复时无进程，原因未知，不能计通过；frozen-r2重新运行完整门。实测试跑之后只改移动端CSS和界面探针：原实测summary和回执保持；当前整包重算如实返回CHANGED。[分范围源码核验](evidence/workflow-shadow-1.13.0/trial-source-review.json)确认其余源码包括生成/核对全部相同，原观察重算不变。因此模型证据限定用于未变动组件，完整最终候选由frozen-r2另行验收，不把两个版本冒充同一整包。

本轮19个源码/测试输入变更，534个源码输入与55个支撑输入冻结；原三职能权责、Task许可、共享预算、知识晋升规则不扩大。原host/work_status.py与JPF预测摘要不变；观察结果不自动写正式知识或业务评分。未来精灵仍应复用原发送/投影，未验证实际精灵入口、多Bot及机器人。原观察器性能预算探针按[机器汇总](evidence/workflow-shadow-1.13.0/verification.json)登记，它不是新增聊天核对的专门延迟测量。[交付检查](evidence/workflow-shadow-1.13.0/delivery-checks.json)区分本轮选定改动与共享树3705条既存格式问题；未以修复无关文件扩大范围。

后续顺序：先用保留集校准合理改写、遗漏、无依据新增和计划冲突；再做带来源位置、冲突及时间状态的自动依据候选；之后用三域独立真实请求接有限返工和结果回流；最后根据可靠验收扩大条件化经验、多Bot责任链与常设委托。当前仅建议保留可选非阻断观察，[采用判断](evidence/workflow-shadow-1.13.0/adoption-review.json)不授权自动改写、结案、评分、知识晋升或部署。

'''
s=s[:start]+section+s[end:]
marker='**1.13影子核对补充：**'
if marker not in s:
    text='\n'+marker+'[本轮限定证据](#workflow-shadow-evidence)覆盖显式用户依据、冻结轮次、原Host交付及同会话修订；保持原执行权责。591项技术回归不是V-TRI-01—12整体签收，通用自改造与自主发布仍待验证。\n'
    i=s.index('\n如果候选破坏硬不变量，',s.index('<a id="trinity-implementation-evidence"'));s=s[:i]+text+s[i:]
s=s.replace('| 评估器校准和多轮成长收益 | 未运行 | 锚点、分母、分歧、累计变化与实际成本 |',
            '| 评估器校准和多轮成长收益 | [1.13逐字观察器15条合成反例](#workflow-shadow-evidence)已测；通用语义校准与多轮成长未运行 | 需独立真实锚点、分母、分歧、累计变化和完整成本，不能借局部校准签收整体 |')
marker='**1.13交付反馈补充：**'
if marker not in s:
    text='\n'+marker+'[当前依据→回复观察→修订](#workflow-shadow-evidence)在同聊天显式输入子集贯通；没有自动事实抽取或返工执行，误报漏报仍在。V-CLC-01—10保持未整体运行，知识收益和全功能助手不因本轮接线而签收。\n'
    i=s.index('\n首批签收只针对明确领域和版本，',s.index('<a id="closure-validation-register"'));s=s[:i]+text+s[i:]
marker='[1.13交付影子核对](#workflow-shadow-evidence)'
if marker not in s:
    i=s.index('\n| 预测／原版本 |',s.index('<a id="forecast-actual-register"'))
    s=s[:i]+'\n'+marker+'追加数据链、合成校准与三域24次模型调用；所有JPF业务收益仍待验证，质量分、成长收益和预测差值没有匹配实测，不补填为零或通过。\n'+s[i:]
save('docs/delivery-validation.md',s)
s=(ROOT/'README.md').read_text('utf-8')
if '**交付影子核对 1.13.0：**' not in s:
    i=s.index('**正文忠实性 1.12.0：**')
    s=s[:i]+'**交付影子核对 1.13.0：**显式事实/计划、依据版本、原回复观察与工作台修订已接通。591项回归、13条浏览器流程、32道门通过；三域24次模型调用完成。15条反例仍有3误报、3漏报，保持可选非阻断，不自动评分或结案。[结论与图表](docs/evidence/workflow-shadow-1.13.0/report.html) · [实施与用法](docs/core-bootstrap.md#workflow-shadow-runtime) · [实测与限制](docs/delivery-validation.md#workflow-shadow-evidence)。尚未证明自动可信提取、真实质量增益或全功能优秀，生产未部署。\n\n'+s[i:]
save('README.md',s)
s=(ROOT/'docs/decisions-review.md').read_text('utf-8')
old='自由语言和真实净收益仍待验证；接下来先补正文与字段一致、事实/推断/建议分离及计划保留，用三域独立真实请求和未见保留题验证，再测误放行、误拒、人工介入及完整成本，接完整费用与有限常设委托、条件化经验候选及多Bot责任链；'
new='自由语言和真实净收益仍待验证。[1.13交付影子核对](core-bootstrap.md#workflow-shadow-runtime)已接显式依据、轮次快照、原回复观察与工作台修订，[实测](delivery-validation.md#workflow-shadow-evidence)确认当前逐字观察仍误报漏报，不能自动评分或结案。接下来依次校准语义观察、提出有来源的自动依据候选、用三域独立真实请求和未见保留题验证有限返工，再测人工介入与完整费用，接条件化经验候选及多Bot责任链；'
if old in s:s=s.replace(old,new)
else:assert new in s
save('docs/decisions-review.md',s)
print('Existing authoritative sections updated from verified evidence.')
