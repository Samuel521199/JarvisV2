# 后续方向指南：现状、缺口与优化工作清单

> 新工程 · 2026-10-22 · 实施计划 proposed。已交付确定性核心种子，完整能力仍按逐项证据判断。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第二篇 · 核心与工程基础](../README.md#part-foundation) › 第 05 章

**本章导航**

- [当前状态与下一步](#direction-start)
- [工作项与权威章节](#direction-work)
- [交付要求](#direction-evidence)
<!-- book-nav:end -->

<a id="direction-start"></a>
## 当前状态与下一步

**2026-10-27 优先级更新：**[1.4.0 固定候选已通过本地纯文本闭环验收](delivery-validation.md#workflow-closure-evidence)，共享工作树与生产加载状态仍分别核对。后续先做“真实委托→完整要求→独立核验→已有授权内自动推进”，再验证经验和多 Bot 的净收益，随后扩大自愈、自身模块替换及设备；陪伴/学习与 K2 主链同步。[顺序、预期效果与采用条件](decisions-review.md#real-work-followup-analysis) · [下一次具体交付](decisions-review.md#post-closure-next-delivery)。下面的 dev 版本说明和 F 索引保留各自范围，不将较早建议当作尚未完成的重复开发任务。

**本轮改造的具体施工入口：**[保持三位一体的增量工作包](core-bootstrap.md#core-modernization-plan)。包括现有源码落点、结果评价首个切面、负责人/经验/自愈接线、迁移与退出，沿原 K0—K6 和当前工作队列推进；[V-TRI 联合验收](delivery-validation.md#trinity-preservation-validation)检查原目标是否保留。这是 proposed 实施分解，不替代下文已验证状态或其他尚未完成的阶段门。

前一批 **0.2.0-dev.10** 在原目标关联研发基础上接通[聊天到交付](core-bootstrap.md#conversation-operation)：自然表达形成可核对目标；同会话补充、取消、接续；按域和目的地读取有效记忆；外部 Codex 只生成候选；真实结果返回原消息，并形成待核对经验。真实范围与失败修复记录见[聊天交付验收](delivery-validation.md#conversation-evidence)。

随后 **0.2.0-dev.11** 已接[受控 HTTP MCP](tasks-agents.md#mcp-runtime)，使用既有任务账本和目标计划，覆盖调用回执、取消、版本变化阻断及持久回执恢复。实测范围见[当前验收](delivery-validation.md#mcp-evidence)。

2026-10-26 新增优先事项：先补齐“聊天持续可用、多个任务真实并行”的核心能力，再扩大业务负载。沿既有 K0/K1/K2 补调度契约与原账本认领、统一工作状态、输入/控制/回复资源隔离；迁出占用前台槽的后台规划，再由单槽扩到经过验证的多个执行槽，按[并行响应门槛](delivery-validation.md#conversation-separation-validation)阶梯压测。只增加线程、窗口或 Agent 数量不能算完成；已实现[有界并发 1.0.0](tasks-agents.md#bounded-concurrency-runtime)的两路通用执行、专用聊天池、持久输入、原任务优先级和统一工作状态；[实测证据](delivery-validation.md#bounded-concurrency-evidence)区分首轮失败、优化与复测。后续 F02 优先补全跨模块供应商额度和 GPU／进程资源约束、自然语言控制及尚未接入的状态来源；[资源准入](tasks-agents.md#resource-admission-loop)完整目标仍待逐项验收。

日程/提醒继续作为后续单一完整任务域（本地计划与日程资料、明确启用的调度、取消和交付）。Gmail 已有[独立邮件助手基线](tasks-agents.md#gmail-runtime)，QQ 连接器、周期拉取与主动邮件提醒尚待实现；OAuth、凭据目的地约束与远端对账不能由通用 MCP 冒充。随后补主动跟进、安静时间和额度。不要同时再建平行 Agent 核心。项目域生成能力包的发布隔离、所有派生记忆正文的清理、大规模持久语义索引仍需补齐。规格模型提出的测试期望需要独立核对；本轮闭环不代表任意业务标准自动正确或完整无人值守助手。

私密人员验证、设备共同体、知识编纂和自动学习继续分模块推进。K0—K6 尚缺的受保护控制、签名更新/有状态交接及普通低资源 PC 长期验收仍需完成。所有旧能力采用参考后独立实现；2026-10-25 主人另行明确授权一次迁入已有 Gmail 连接，仅保留原权限并重新加密，不迁入旧邮件缓存、旧记忆或旧环境，详见[迁移与安全边界](security-sovereignty.md#gmail-boundary)。

本轮记忆工作按[综合方案](knowledge-learning.md#memory-context-design)推进：[检索 1.0.0](knowledge-learning.md#memory-retrieval-runtime) 已接已核对事实的按问题召回、有界本地 E5 与引用依赖失效。[资料库 1.2.0](knowledge-learning.md#knowledge-cycle-runtime) 已接通文本原件、FTS/持久向量、来源知识审阅、资料包恢复/墓碑，以及事实/来源依赖的聊天、终态任务和受管文件清理。下一步扩完整记忆对象迁移、独立质量样本、分支与时态语义，再进行框架适配/检索对照；完整工作包、资源目标与尚未具备的实机条件见[验收](delivery-validation.md#memory-context-acceptance)。这与既有连接器/任务领域扩展共用核心接口，不新建第二个助手主循环。

K0—K6 的完整定义只归[核心起步](core-bootstrap.md#bootstrap-5)。下面保留 F 编号作为跨主题工作索引，不构成第二条开发时间线，也不因列出工作项就创建任务或授予执行权限。

2026-10-26 已将[精灵与工作台作为同一系统两种工作形式](architecture.md#unified-system-principle)纳入项目级准则：精灵侧重日常自动化与简洁交互，工作台按需详细展示、设置和控制。后续先盘点并复用现有能力、受理、设置与主题组件，再补平台壳和视图，避免分别开发业务。当前原生壳仍未实现；按既有 K0/K1 的状态与契约准备、K2 的两种形式接续闭环推进，后续平台与远程设备继续沿[核心路线](core-bootstrap.md#bootstrap-5)扩展适配。[场景与参考图](interaction-persona.md#desktop-presence-scenarios)、[原生技术落点](stack-project-layout.md#desktop-presence-shell)、[验收范围](delivery-validation.md#desktop-presence-validation)共同约束后续实现。原网页入口在原生验收前继续可用。

<a id="direction-work"></a>
## 工作项与权威章节

| 编号 | 必须逐步补齐的能力 | 权威位置 |
|---|---|---|
| F01 | 自然对话与真实行动统一受理，闲聊不强制建任务 | [运行循环](tasks-agents.md#continuity-operating-cycle) |
| F02 | 聊天/控制独立受理与资源保障；多个任务真实并行，可解释优先级、统一状态、冲突互斥与本机资源反馈 | [资源调度](tasks-agents.md#resource-scheduling) · [响应验收](delivery-validation.md#conversation-separation-validation) |
| F03 | 事实、来源、纠正、遗忘与撤回传播 | [记忆生命周期](knowledge-learning.md#memory-data) |
| F04 | 检索结果实际改善回答，不能只测找到片段 | [记忆验收](delivery-validation.md#memory-selection-evaluation) |
| F05 | 按需语音、打断、多人场景与主人验证分离 | [交互](interaction-persona.md#interaction-tasks) |
| F06 | 人格连续、未结事项、安静时间；透明精灵按需呼出，工作台仅特殊补充；以个人为主兼顾家庭和小团体，自主规划、执行、核验与交付 | [桌面体验](interaction-persona.md#desktop-presence-design) · [服务范围](product-requirements.md#personal-service-scope) · [目标循环](tasks-agents.md#proactive-goal-cycle) |
| F07 | Codex、桌面和模型的开发协作 | [研发渠道](toolchains.md#autonomous-development-providers) |
| F08 | 分开自检、自愈、进化，独立评估真实收益 | [成长治理](evolution-release.md#growth-governance) |
| F09 | 离线、迁移恢复和普通 PC 资源验收 | [验收环境](delivery-validation.md#acceptance) |
| F10 | 主备模型与用途路由、费用和未知结果 | [模型路由](models-offline.md#model-routing) |
| F11 | 核心与能力模块都可观察、停用、升级和恢复 | [模块管理](health-maintenance.md#clean-module-governance) |
| F12 | 防止依赖、旧包、文档、知识和调试产物污染 | [系统健康](health-maintenance.md#system-health) |
| F13 | 学习与主人目标相关的新知识和技术 | [持续学习](knowledge-learning.md#continuous-learning) |
| F14 | 电脑、软件、设备和可编辑交付物按需接入；精灵与补充工作台共用任务、成果和原会话 | [能力边界](product-requirements.md#capability-boundaries) · [呈现架构](architecture.md#desktop-presence-architecture) |
| F15 | 离线自治、分域共享与重连不重复执行 | [共同体](federation.md#offline-federation) |
| F16 | 动态 Agent、NPC 与表达形态受资源约束 | [Agent 工厂](tasks-agents.md#agent-factory) · [NPC 世界](simulation.md#npc-world) |

<a id="direction-evidence"></a>
## 交付要求

每项变更说明：服务哪个主人目标、有哪些输入与效果、原能力是否退化、如何取消或恢复、真实测试覆盖什么。生成代码不代表已发布，模型一致不代表正确；必须使用[统一验收](delivery-validation.md)和[模块契约](contracts.md#clean-module-contract)。

自主工作能力以[独立完成任务的终态](product-requirements.md#personal-life-autonomous-outcomes)衡量：检查从目标到实际结果的全流程，分别报告独立完成、必要人工介入、部分完成与失败；家庭和小团体场景还需验证成员资料与共享边界，不能只展示计划或工具调用次数。

普通 PC 默认一个模块化业务 Host，按需工具/模型与独立恢复入口；不为上述每个工作项单建常驻服务。正式业务代码从零实现，已有优秀概念在对应端口重新验证。

当前 Gmail 已完成[独立连接与受审阅收发基线](tasks-agents.md#gmail-runtime)，后续邮箱工作优先增量同步、主动提醒和 QQ；旧 Gmail 令牌仅按 2026-10-25 主人明确授权独立迁入，不代表搬入旧环境或旧记忆。上文邮箱完整目标继续按分项验收判断。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：最小核心、初始资产与开发路线](core-bootstrap.md) · [下一章：系统架构、运行边界与模块职责](architecture.md)
<!-- book-footer:end -->
