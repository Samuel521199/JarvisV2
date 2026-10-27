# Jarvis 文档目录

[返回工程主入口](../README.md)。根 README 是唯一主入口，本页用于在 docs 内连续阅读。目标与明确规则 accepted，运行设计 proposed；本工程没有继承 H 盘的实现或验收状态。

[主文档中的桌面精灵设计](../README.md#desktop-companion-overview)已合并透明行为、场景呼出、状态动效、参考图和与现有系统的衔接；各章继续维护对应工程细节。

**先读：[当前真实状态](current-state.md)**（一页说明能运行什么、只有设计的部分、证据边界与已知风险）· [版本记录](../CHANGELOG.md)。

当前可运行范围：[模型设置与持久对话](core-bootstrap.md#portable-settings-operation) · [本地数据位置](stack-project-layout.md#portable-data-runtime) · [本工程实际验收](delivery-validation.md#portable-settings-evidence) · [自主研发种子操作](core-bootstrap.md#growth-seed-operation)。

<a id="book-tree"></a>
## 按篇查阅

<!-- book-tree:start -->
<a id="part-product"></a>
### 第一篇 · 产品与体验

| 章节 | 这章回答什么 |
|---|---|
| [产品定义、需求与能力边界](product-requirements.md) | 如何以个人为主、家庭与小团体为辅，自主工作并独立完成任务？ |
| [个人助手体验、工作台与人格形态](interaction-persona.md) | 怎样通过透明精灵按需交流，并把工作台作为特殊补充？ |
| [NPC 小镇与虚拟世界](simulation.md) | 怎样运行 NPC 小镇，并隔离虚拟与现实？ |

<a id="part-foundation"></a>
### 第二篇 · 核心与工程基础

| 章节 | 这章回答什么 |
|---|---|
| [最小核心、初始资产与开发路线](core-bootstrap.md) | 最小核心怎样起步；现有代码如何按 K0—K6 改造并保持三位一体、自愈与持续成长？ |
| [后续方向指南：现状、缺口与优化工作清单](development-guide.md) | 当前版本还缺什么、先优化哪里，原方案的后续工作怎样落到代码与验收？ |
| [系统架构、运行边界与模块职责](architecture.md) | 个人助手核心如何连接记忆、模型、任务与可替换能力？ |
| [主人利益原则、身份授权与停止控制](security-sovereignty.md) | 当前个人使用边界是什么，哪些监督与认证设计已延期？ |
| [公共接口与数据契约](contracts.md) | 模块之间怎样交换任务、事件和记忆数据？ |
| [技术栈、源码目录与运行数据](stack-project-layout.md) | 选哪些技术，代码放哪里，开源组件如何取舍？ |

<a id="part-runtime"></a>
### 第三篇 · 智能运行与多设备协同

| 章节 | 这章回答什么 |
|---|---|
| [模型路由、本地模型与离线生存](models-offline.md) | 用哪些云端和本地模型，怎样切换与离线降级？ |
| [记忆、知识库与持续学习](knowledge-learning.md) | 记住什么，怎样检索、纠正、遗忘和持续学习？ |
| [记忆与认知综合方案：架构、选型与场景图解](memory-cognition-design.md) | 怎样把记忆、知识、聊天、工作、隐私与多设备组成完整方案，并处理特殊情况？ |
| [任务、动作、多 Agent 与资源调度](tasks-agents.md) | 怎样一边交流一边执行任务，如何组织多 Agent？ |
| [离线自治、多设备共同体与重连](federation.md) | 断网怎样独立工作，重连怎样共享记忆与协同？ |

<a id="part-evolution"></a>
### 第四篇 · 自主成长与维护

| 章节 | 这章回答什么 |
|---|---|
| [自主进化、外部编码协作与版本发布](evolution-release.md) | 怎样自编工具、改进模块，并验证和回退？ |
| [火炮类游戏资产制作与经验学习实施手册](studio3d-learning.md) | 怎样把火炮游戏资产经验接成可执行工具、条件方法与可验证的练习闭环？ |
| [开发环境、多语言工具链与构建](toolchains.md) | 怎样准备编译环境，构建和测试不同语言的程序？ |
| [系统健康、防退化与自愈](health-maintenance.md) | 怎样发现故障与结构退化，清理和修复隐患？ |
| [系统自身模型与能力认知](self-model.md) | 如何自动知道当前版本、结构、进程与能力，并为修复和改造提供可靠依据？ |

<a id="part-evidence"></a>
### 第五篇 · 验证与参考

| 章节 | 这章回答什么 |
|---|---|
| [能力验收、故障演练与评估证据](delivery-validation.md) | 哪些能力测过，证据在哪里，下一阶段怎样验收？ |
| [架构决策、批判性评审与评分](decisions-review.md) | 关键架构取舍是否合理；自主助手哪些链条已有基础、哪些交接和长期闭环仍缺证据？ |
| [Grok Bot 功能、界面与运行机制：Jarvis 对比研究（2026-10-26）](grok-bot-comparison.md) | 先看结论、闭环缺口、实施与预测；对比 Grok、多 Bot 与 Harness²，并核对原目标保持和知识收益。 |
| [架构与流程图册](architecture-atlas.md) | 在哪里集中查看架构图和流程图？ |
| [研究资料与证据边界](references.md) | 设计和选型参考了哪些论文与官方资料？ |
| [文档维护规范](MAINTENANCE.md) | 以后怎样归类、更新、检查和清理文档？ |
<!-- book-tree:end -->

<a id="quick-topics"></a>
## 常用专题

| 想查什么 | 文档 |
|---|---|
| 意识、人格和长期伙伴 | [连续身份](architecture.md#continuity-definition) · [人格体验](interaction-persona.md#persona-embodiment) |
| Agent、Bot、Skill、Tool、蓝图和 Runtime | [概念与装配](architecture.md#composition-concepts) |
| 所有核心可替换与恢复 | [核心管理](health-maintenance.md#clean-module-governance) · [升级与交接](evolution-release.md#continuity-upgrade-protocol) |
| 主动工作、任务接续与资源 | [目标循环](tasks-agents.md#proactive-goal-cycle) · [统一资源](tasks-agents.md#resource-scheduling) |
| 个人与工作记忆、知识库 | [分域使用](knowledge-learning.md#memory-scope-model) · [开源取舍](stack-project-layout.md#memory-open-source) |
| Codex、桌面和模型协作研发 | [研发渠道与能力晋升](toolchains.md#autonomous-development-providers) |
| 断网、多设备与统一协作 | [本地能力](models-offline.md#local-survival) · [共同体](federation.md#offline-federation) |
| 全部图表、验证和维护 | [图册](architecture-atlas.md) · [验收](delivery-validation.md) · [维护](MAINTENANCE.md) |
