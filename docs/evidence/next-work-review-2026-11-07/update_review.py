"""Record a source-based follow-up review in the existing authoritative chapter."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
page=ROOT/'docs/decisions-review.md'
text=page.read_text('utf-8')
old_top='**1.4.0 之后的最新优先级：**[先看后续顺序、预期效果和下一次交付](#real-work-followup-analysis)。建议先完成版本交付核对，再验证真实需求与质量，接通常设/单次委托内的低打扰推进和完整预算，随后按净收益扩大经验、多 Bot、自愈与自身改造；陪伴和学习从 K2 同步推进。以下 2026-10-26 诊断保留为历史基线，不代表现在仍未实现交接和局部返工。'
new_top='**2026-11-07最新优先级：**[先看源码复核、施工顺序与下一次交付](#v012-next-work-order)。当前网页精灵共享和受控应用采用已有证据；下一轮优先进程生命周期、可靠要求核对与个人待办/一次性提醒，再沿实际收益扩大委托、经验、多Bot及自愈。原生薄壳可并行小样验证，陪伴与学习继续同步。以下较早诊断与实验按原时间和范围保留，不代表对应机制现在仍未实现。'
assert old_top in text or new_top in text
text=text.replace(old_top,new_top)
start=text.index('<a id="v012-next-work-order"></a>')
end=text.index('<!-- book-footer:start -->',start)
replacement='''<a id="v012-next-work-order"></a>
### 建议下一轮的闭环与原 K 阶段对应

**2026-11-07 源码复核结论：下一次主要交付应是“有依据、可改期、可取消、重启后能接续的个人待办”，同时完成外部进程生命周期加固。** 网页精灵共享与受控应用采用已有实现，不能继续当作未开发项；原生轻量壳可并行做薄层验证，业务优先贯通“用户请求→当前要求→执行回执→独立核对→交付→纠正”。先让一个真实任务少操心，再验证经验和多 Bot 的额外收益。沿原 K0—K6 推进，下面是当前工作队列，不新增第二条阶段路线。

本轮依据开发提交 `efe50c7634a965d167e4ae197ed53dc35347d175`；检查了对话/规划/调度/结案、影子核对、记忆/经验、邮件、跨入口投影、进程启动与应用准入。新跑81项选定离线测试，0失败、0错误、0跳过；架构428个Python文件、20个既有Host导入环模块、0新增错误。未重跑全套回归、浏览器实测、真实模型或日用部署，不继承旧测试数量作为当前全量通过。[范围、源码摘要与检查记录](evidence/next-work-review-2026-11-07/audit.json) · [选定回归](evidence/next-work-review-2026-11-07/selected-tests.log)。后续建议均为proposed，不因文档写出就标为implemented。

**源码实际支持到哪里。**

| 环节 | 当前实现与依据 | 对后续工作的含义 |
|---|---|---|
| 自然交流和目标提案 | [assistant](../host/assistant.py)、[dialogue](../host/dialogue.py)把chat/goal/amend/cancel/resume接到原目标；前台2槽、后台1槽 | 已有入口；明确动作仍须转可核对计划，尚非通用自动委托策略 |
| 任务执行和交付 | [goals](../host/goals.py)、[scheduler](../host/task_scheduler.py)沿原账本与许可执行；[work_closure](../host/work_closure.py)核对当前版本、覆盖及预算 | 可复用；不能只看到SUCCEEDED就说用户目标完成 |
| 核对器的实际范围 | [completion](../modules/task_resource/completion.py)主要为文本/报价检查；[delivery_review](../modules/task_resource/delivery_review.py)为限定摘录或逐字出现检查 | 自由语言合理改写、额外编造与真实业务效果仍不能据此自动签收 |
| 负责人和多Bot | [Works](../modules/task_resource/works.py)已有默认负责人、当前目标版本及返工关联，投影明确是default_projection | 有责任归属种子；没有多Bot运行时、任期、过期负责人防写和接管协议 |
| 记忆和经验 | [retrieval](../modules/context_knowledge/retrieval.py)融合词法与语义；[memory_capture](../host/memory_capture.py)只将明确“记住”请求变成候选；[Episodes](../modules/context_knowledge/episodes.py)复用text-report-v1方法并支持隔离/过期 | 不能把会检索或存在经验表等同于通用自主学习；当前方法不是跨域经验归纳器 |
| 邮件与持续待办 | [mailbox](../host/mailbox.py)已有独立job、审阅、账号代际和未知写入禁止重放；[邮件轻投影](../modules/mail/companion.py)读取缓存，不主动拉取 | 工具可用；邮件→待办/提醒→反馈尚无完整领域执行链，不能靠提示词承诺提醒 |
| 界面与升级 | [companion-shell](../apps/workbench/companion-shell.js)共用聊天、工作和已阅；[participants](../host/runtime_participants.py)已覆盖受管理通道排空 | 原网页业务复用继续保留；原生壳仅负责窗口/托盘/通知，不能另建一套业务核心 |
| 进程与采用 | [application_release](../host/application_release.py)已有独立检查、审阅与代码包交接；Blender/工程Worker仍先Popen后挂Job，Codex候选进程未挂Job | 扩大无人值守前需补进程树约束和异常清理；应用包恢复不等于业务副作用补救 |

**建议按以下依赖顺序交付。** 序号只表示本轮优先级，不是新增K阶段；所有数值门槛均应在实验前冻结，以下效果是待验证假设。

| 顺序 / 原阶段 | 具体施工与复用位置 | 预期效果 | 必须拿到的验收证据 |
|---|---|---|---|
| ① K0/K1：稳定基线和进程边界 | 固化Windows离线核心回归、业务专项、浏览器三层清单，接持续集成；补Blender/工程/学习Worker和Codex进程树生命周期，按平台验证挂Job后才执行或等效原子约束；对现有20模块环按修改面渐进收缩 | 出错可复现，停止/超时/Host崩溃不留下继续工作的子进程 | 取消、超时、父进程强退、孙进程逃逸、Job绑定失败、升级排空；失败时不放行。Job约束不冒充完整沙箱。源码与日用构建摘要可追溯 |
| ② K2：任务要求与可靠核对 | 在原Goal/依据快照上表达事实、推断、计划、禁止项及来源；先提出自动提取候选，以影子模式核对，保留显式填写；针对遗漏、改写、矛盾、新增断言和时间变更分别校准 | 用户不用每次手填核对依据；问题定位到具体要求，减少错误结案 | 三域真实请求和未见样本，逐类报告误报/漏报、弃权与来源引用；生成器不修改隐藏答案。保留1.12/1.13反例；逐字匹配不能直接升级为语义审核门 |
| ③ K2：一条个人助手工作到底 | 首个完整任务域选本地待办/一次性提醒；邮件先提供引用来源，再转待办，既有MailStore仍为邮件事实权威；复用Tasks/Works/Attention/StopGate。保存原时区、绝对到期、来源、版本、状态和回执 | 从“给建议”走到“记下并按时推进”，改期、取消和反馈都能接续 | “明天下午提醒回邮件”先补真正缺失时间；更正邮件→改期→重启→离线/休眠后补交付→取消→迟到反馈。旧版本不能触发；未交付不能写已通知；重放不能再次发信 |
| ④ K2/K3：已有授权内低打扰推进 | 基于原GrantStore和预算增加范围明确的委托配置：动作、目的地、费用、时限、频率及撤回条件；先自动处理约定的本地可逆动作，重要事项与超范围选择再请求用户 | 普通任务不再逐步骤点确认，保留可解释的边界 | 对“原授权内应自动做”和“确实需要决定”都设用例；记录可避免介入、必要决策、撤回后阻断、未知效果对账，不能一律拒绝来获得安全高分 |
| ⑤ K2/K5：知识和经验真实增益 | 分开事实、来源、偏好、承诺、方法；用原修订/条件/墓碑/使用链，给方法增加适用域、反例、版本、有效期、实际采用及结果。先修当前检索质量，再推广方法候选 | 同类请求更准确、更少重复错，条件变化时及时放弃旧方法 | 检索开关/方法开关消融；同类新题、条件反转、过时资料和矛盾资料留出集；核对实际引用、任务质量、token、时延、总费用。记录79/90旧基线但不当本轮复测结果 |
| ⑥ K3/K4：小规模多Bot | 在原Works上补负责人任期和受控交接：一个负责人管理任务，1—2个专家提交有来源的候选；沿原账本统一动作、预算、取消和结果 | 复杂工作可分工，失败能定位到责任与交接，避免各做一份 | 对照单Bot，同一任务质量、成本、时延与介入；测试旧负责人迟到写入、重复派发、交接崩溃、专家矛盾及预算合计。投票或多模型一致不当真值；无净收益不扩大 |
| ⑦ K1/K4/K5：限定自愈与自改造 | 复用调度退避、应用A/B与包回退；增加结构化故障记录和处置范围。先重试读操作/重启卡死通道，再以一个检索或核对模块试候选改造 | 由“报错后人排查”变成有限问题自己恢复，改造可回退且不掩盖业务失败 | 故障注入、重试上限、修复后原目标回接、外部未知效果先对账、停止锁存不被复活；新旧模块同题对照、累计退化检查与状态兼容。恢复代码不能恢复撤回许可或旧知识 |
| ⑧ K2/K6：原生陪伴及长期扩展 | 原生薄壳可与②③并行验证；睡眠/唤醒、多屏、托盘、通知共用当前Host。陪伴/学习从低打扰、会话连续、实际练习和明确反馈开始，语音/跨设备/机器人分别验收 | 接触成本降低、陪伴连续，后续能力沿同一系统扩展 | 原生与网页同任务/设置/状态；断线不误报待命；安静时间与通知撤回。学习用真实作答及延迟复测，情绪支持用用户反馈和打扰情况，不凭热情措辞或知识卡数量加分 |

**下一次交付的最小范围。** 先完成①中与新自动执行直接相关的进程保护及可重复检查，再把②③做成一份可运行候选：本地个人待办/一次性提醒，带当前要求、来源、改期、取消、交付回执和重启恢复。网页工作台/网页精灵共享同一入口，原生薄壳做独立小样；首批邮件数据使用模拟来源，真实账号仍按已有授权与目的地接入。这轮不同时扩成通用日历、多Bot工厂和所有模块自改造。

提醒链必须区分调度受理、通知尝试、实际显示和用户已阅；休眠错过时如何补发、安静时间如何顺延、操作系统通知回执能力有限时如何标未知，都须先定义。采用单一持久任务/版本权威，派发表或通知outbox只保存派生引用与投递状态，不能创建与原任务争夺当前事实的第二套账本。只在主人实际启用后调度；本次研究没有启用提醒或后台监控。

**怎样评估“越用越好”。** 每个任务记录要求版本、执行结果、交付证据、质量维度/未知项、人工介入、模型/工具/知识版本、费用和后续纠正。硬条件得分、主观质量、结构改进性分别报告；没有足够证据时不伪造综合Q。候选改造可以在隔离研发中继续，但采用版须通过原硬不变量和配对业务门；结构更好而真实效果更差时，停止扩大采用、保留失败并定位，不把失败回复或自评直接晋升为知识。自动采用只适用于实际校准并获相应授权的范围，成长不承诺单调上升。

现有WorkBudgets约束的是原账本动作单位，不是全供应商的货币硬限额；聊天、规划、重试、专家调用和返工费用需在各自真实调用记录基础上归集，不能把相同单位直接当美元。扩大常设委托前，补费用预留/结算、未知计费和跨通道额度；收益比较必须包括为了评估、协作和检索新增的开销。核心指标是任务实际完成、可避免介入、重复错误、改期/取消正确率和总费用，而不是调用次数、知识卡数或测试总数。

**三位一体保持。** 定向面维护当前要求、计划和委托范围；协作面沿原任务/执行器推进与交付；观察成长面核对证据、记录故障、提出经验/改造候选。三者共用连续身份、权威数据与控制底座；新增负责人、审核器或原生壳都不替代原权限和任务体系。实际不破坏需按[V-TRI](delivery-validation.md#trinity-preservation-validation)与[V-CLC](delivery-validation.md#closure-validation-register)逐项补运行证据，本次静态审阅不签收全部目标。

**暂缓的扩张。** 原生窗口可以做，但不以外壳替代个人助手闭环；专业3D先处理既有缺陷，不继续占用通用核心的验收目标；不一次性重写Host、引入第二个Agent核心、全面微服务化或扩大机器人权限。应用准入当前使用[sdk/application_policy.py](../sdk/application_policy.py)的固定核心清单，未来增补提醒/来源/经验等领域时应同步增补独立采用门和相关回归，不能把核心清单通过当全部能力通过。

'''
page.write_text(text[:start]+replacement+text[end:],encoding='utf-8',newline='\n')
state=ROOT/'docs/current-state.md'
s=state.read_text('utf-8')
s=s.replace('透明桌面精灵、多 Bot、自愈、通用自身模块替换、多设备共同体和语音都还**只有设计**。','网页精灵已与工作台共用实际能力；原生透明壳、多 Bot运行时、统一自愈流水线、通用自身模块替换、多设备共同体和语音仍未实现，已有局部重试与受控应用恢复。')
s=s.replace('工作流 1.1～1.13 都在合成“报价”任务上验证，台账写明“生产未部署”；','工作流1.1～1.10主要在合成报价/文本任务验证，1.11～1.13另有报价、文档、学习三域合成对照；不能都称为独立真实请求。各版本候选台账仍保留当时“生产未部署”状态；')
old='2. 接原生轻量精灵窗口／多屏及轻量监督，再接邮件待办、日程提醒和记忆纠正这条个人助手工作；优先级和出口见[剩余缺口](decisions-review.md#v012-next-work-order)。\n3. 回到真实日常请求的委托、要求、核验与低打扰推进，按原 K0—K6 路线补齐；3D 等专业侧线先修已有缺陷。'
new='2. 2026-11-07源码复核后，优先固化可重复回归与外部进程生命周期，再做有来源/可改期取消/重启可接续的本地待办和一次性提醒；同步校准当前要求与语义核对。原生薄壳可并行小样验证。[施工顺序、效果与采用条件](decisions-review.md#v012-next-work-order)。\n3. 在上述业务出口可靠后，逐步增加已有授权内低打扰推进、知识/经验收益对照、小规模多Bot责任链与限定自愈/模块改造，继续按原K0—K6验收；3D等专业侧线先修已有缺陷。'
assert old in s or new in s
state.write_text(s.replace(old,new),encoding='utf-8',newline='\n')
sources=['host/assistant.py','host/dialogue.py','host/task_scheduler.py','host/goals.py','host/work_closure.py',
         'host/runtime_participants.py','control/runtime_activity.py','host/background.py','host/mailbox.py',
         'host/memory.py','host/memory_capture.py','host/knowledge.py','host/application_release.py',
         'host/studio3d.py','host/studio3d_learning.py','host/anatomy_engineering.py','adapters/models/codex_cli.py',
         'modules/task_resource/works.py','modules/task_resource/work_budgets.py','modules/task_resource/completion.py',
         'modules/task_resource/delivery_review.py','modules/context_knowledge/retrieval.py',
         'modules/context_knowledge/episodes.py','modules/context_knowledge/conditions.py','modules/mail/companion.py',
         'control/recovery/gate.py','sdk/application_policy.py','apps/workbench/companion-shell.js',
         'apps/workbench/assistant-actions.js']
changelog=ROOT/'CHANGELOG.md'
s=changelog.read_text('utf-8')
entry='2026-11-07 **文档与源码复核（运行版本保持v0.1.3）**：复核当前任务、核验、记忆、负责人、邮件和恢复边界；调整下一轮为进程生命周期加固与有依据的个人待办/提醒闭环，列出后续委托、经验、多Bot和自愈的采用条件。修正状态页对网页精灵、局部恢复及三域合成试验的概括。[分析与实施顺序](docs/decisions-review.md#v012-next-work-order)。\n\n'
assert s.startswith('# 版本记录\n\n')
if entry not in s:changelog.write_text(s.replace('# 版本记录\n\n','# 版本记录\n\n'+entry,1),encoding='utf-8',newline='\n')
audit={'date':'2026-11-07','commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'type':'source-based planning review; implementation proposals are not runtime changes',
       'inspected_source_digests':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},
       'selected_tests':{'run':81,'failures':0,'errors':0,'skipped':0,'log':'selected-tests.log'},
       'full_regression_run':False,'browser_retested':False,'live_models_called':False,'production_inspected':False,
       'production_deployed':False,'checks':{}}
assert 'COUNTS 81 0 0 0' in (HERE/'selected-tests.log').read_text('utf-8')
write=lambda:(HERE/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write()
for name,cmd in [('navigation',[sys.executable,'tools/sync_doc_navigation.py','--root','.']),
                 ('architecture',[sys.executable,'tools/check_architecture.py']),
                 ('documentation',[sys.executable,'tools/check_docs.py','--root','.']),
                 ('selected_diff',['git','diff','--check','--','docs/current-state.md','docs/decisions-review.md','CHANGELOG.md'])]:
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (HERE/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    audit['checks'][name]={'returncode':r.returncode,'output':(r.stdout+r.stderr).strip()}
    write()
    print(name,r.returncode,(r.stdout+r.stderr).strip()[:500])
    assert r.returncode==0
print('Review and current-state corrections saved. No runtime changes.')
