# 公共接口与数据契约

> 新工程设计基线 · 2026-10-22 · 目标/明确规则 accepted，运行方案 proposed。H 盘版本记录不构成本工程的实现或验收证据。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第二篇 · 核心与工程基础](../README.md#part-foundation) › 第 08 章

**本章导航**

- [实现状态索引（先看这里）](#contracts-implementation-index)
- [个人助手核心接口（设计）](#personal-assistant-contracts)
  - [身份、个人上下文与行动意图的边界](#personal-context-contract)
- [记忆组件的替换契约（proposed）](#memory-provider-contracts)
  - [开源提取器、编纂器与路由的适配要求（proposed）](#memory-extractor-adapter)
  - [MemoryView 与知识候选的必要语义（proposed）](#memory-view-contract)
- [接口与数据契约](#interfaces)
  - [任务与动作分离](#interfaces-2)
  - [事件信封](#interfaces-3)
  - [精灵与工作台共用的呈现契约（proposed）](#desktop-presence-contract)
- [资源租约、本地组件与安全事件契约](#extensions-3)
  - [交流保障与调度决定的增量契约（proposed）](#scheduling-contract)
- [生活助手共用模块与请求上下文](#personal-life-foundation)
- [可组合能力、蓝图与运行契约](#composition-contracts)
  - [能力包与角色蓝图](#composition-package-contract)
  - [一次运行与上下文](#composition-run-contract)
  - [Agent Runtime 一步接口与宿主验证责任](#composition-step-contract)
  - [哪些数据长期保存、哪些只是派生视图](#composition-state-ownership-details)
  - [状态持久性、事件与兼容](#composition-durability-contract)
- [连续身份与核心实现替换的契约草案](#continuity-contracts)
  - [目标委托、行动机会与自主维护策略](#goal-opportunity-contract)
- [独立工程的模块包、管理端口与研发交付契约](#clean-module-contract)
  - [模块清单与可替换端口](#clean-module-manifest)
  - [研发任务和交付物](#development-work-contract)
  - [0.2.0-dev.1 已落地的契约子集](#core-seed-wire-contracts)
- [当前研发、候选与包契约](#growth-seed-contracts)
- [0.2.0-dev.3：本地设置与对话接口](#local-settings-chat-contracts)
- [项目与文字技能的工作台接口](#workbench-project-contracts)
- [目标计划的当前运行契约（dev.8）](#goal-plan-runtime-contract)
- [原目标与研发关联的运行接口（dev.9）](#goal-growth-contract)
- [聊天行动与目标上下文接口（dev.10）](#conversation-contracts)
- [MCP 接入与效果回执契约（dev.11）](#mcp-contracts)
- [项目创建与会话目录契约（dev.12）](#session-folder-contracts)
- [本地文本资料库的运行契约（knowledge-library-1.2.0）](#knowledge-library-contract)
- [记忆连续性、联合范围与提取契约（1.0.0）](#memory-continuity-contract)
- [Gmail 契约与恢复状态（1.0.0）](#gmail-contracts)
- [任务负责、结果评价与经验的增量记录（proposed）](#task-learning-records)
- [三职能、任务负责与成长模块的接入契约（proposed）](#modernization-integration-contracts)
  - [最小端口、数据写入者与故障返回](#modernization-port-map)
  - [关联记录、事务与重复消费](#modernization-durable-projections)
- [闭环交接所需的增量关联（proposed）](#closure-handoff-records)
  - [真实工作诊断对应的最小契约增量（proposed）](#real-work-handoff-contracts)
- [确定性结果评价的运行子集（1.0.0）](#outcome-observer-contract)
- [文本验收、反馈与采用的实际交接契约（1.0.0）](#completion-loop-contract)
- [工作交接 1.1.0 的实际契约](#workflow-handoff-runtime-contract)
- [工作接续 1.2.0 的实际契约](#workflow-rework-contract)
- [工作额度 1.3.0 的实际契约](#workflow-budget-contract)
- [工作闭环 1.4.0 的实际契约](#workflow-closure-contract)
- [领域核验 1.5.0 的实际契约](#workflow-domain-contract)
- [目标要求 1.6.0 的实际契约](#workflow-requirements-contract)
- [聊天来源 1.7.0 的实际契约](#workflow-sources-contract)
- [明确变更 1.8.0 的实际契约](#workflow-changes-contract)
- [返工继承 1.9.0 的实际契约](#workflow-inheritance-contract)
- [来源恢复 1.10.0 的实际契约](#workflow-recovery-contract)
- [三领域对照 1.11.0 的实际契约](#workflow-trials-contract)
- [正文忠实性 1.12.0 的实际契约](#workflow-fidelity-contract)
- [交付影子核对 1.13.0 的实际契约](#workflow-shadow-contract)
<!-- book-nav:end -->

<a id="contracts-implementation-index"></a>
## 实现状态索引（先看这里）

本章前半部分是设计中的概念契约，后半部分是已经有代码的运行子集，两类交错排列。下表按 2026-10-27 的代码核对结果分开列出；“已实现”指仓库里存在对应 schema、接口或校验代码，不代表该能力已在真实使用中验收。

| 状态 | 章节 |
|---|---|
| **已实现（有代码）** | [研发、候选与包](#growth-seed-contracts) · [本地设置与对话](#local-settings-chat-contracts) · [项目与文字技能](#workbench-project-contracts) · [目标计划](#goal-plan-runtime-contract) · [目标关联研发](#goal-growth-contract) · [聊天行动与目标上下文](#conversation-contracts) · [MCP](#mcp-contracts) · [会话目录](#session-folder-contracts) · [本地资料库](#knowledge-library-contract) · [记忆连续性](#memory-continuity-contract) · [Gmail](#gmail-contracts) · [结果评价](#outcome-observer-contract) · [文本验收与反馈](#completion-loop-contract) |
| **已实现，限合成“结构化报价”领域** | 工作流 [1.1 交接](#workflow-handoff-runtime-contract) · [1.2 接续](#workflow-rework-contract) · [1.3 额度](#workflow-budget-contract) · [1.4 闭环](#workflow-closure-contract) · [1.5 领域核验](#workflow-domain-contract) · [1.6 目标要求](#workflow-requirements-contract) · [1.7 聊天来源](#workflow-sources-contract) · [1.8 明确变更](#workflow-changes-contract) · [1.9 返工继承](#workflow-inheritance-contract) · [1.10 来源恢复](#workflow-recovery-contract) · [1.11 三领域对照](#workflow-trials-contract) · [1.12 正文忠实性](#workflow-fidelity-contract) · [1.13 交付影子核对](#workflow-shadow-contract) |
| **部分实现** | [模块包与管理端口](#clean-module-contract)：`module.v1` 等 schema 存在，`describe`/`probe`/`checkpoint` 零散实现，`drain`/`export_state`/`import_state` 尚无代码 |
| **仅设计（代码中尚无对应对象）** | [个人助手核心接口](#personal-assistant-contracts) · [记忆组件替换](#memory-provider-contracts) · [接口与数据契约](#interfaces) · [资源租约与安全事件](#extensions-3) · [生活助手共用模块](#personal-life-foundation) · [组合能力与蓝图](#composition-contracts) · [连续身份](#continuity-contracts) · [任务负责与经验记录](#task-learning-records) · [三职能接入](#modernization-integration-contracts) · [闭环交接关联](#closure-handoff-records) |


<a id="personal-assistant-contracts"></a>
## 个人助手核心接口（设计）

<a id="personal-context-contract"></a>
### 身份、个人上下文与行动意图的边界

**完整接口 proposed。** 服务于[新工程核心](architecture.md#clean-core-architecture)，统一会话、记忆、任务和模型端口；正式实现需版本化机器定义及正反例，不能把概念名当作可调用 API。

| 接口责任 | 最小约束 | 写入与失败语义 |
|---|---|---|
| PersonaProfile 读取/预览/激活 | 稳定主体引用、配置版本、表达/关系设置、作用域；配置不存执行授权 | 激活验证预期旧版本，在轮次边界生效；失败保留原配置；身份与人格表达分开管理 |
| PersonalContext 装配 | 当前会话、人格版本、相关事实/经历引用、作用域与来源版本、上下文预算 | 有界只读视图；模型缓存不成为记忆源；失效、删除、外发禁止的内容排除，不足时明确降级 |
| MemoryIntent 受理 | 明确记住/纠正/遗忘、说话者及来源、作用域、预期修订；引用/推断独立标注 | 交给现有记忆写入者校验；重复意图幂等，冲突返回可解释状态；不能从人格模块直接改事实表 |
| Response / WorkIntent 分流 | 普通交流、记忆意图、建议、具体行动不同类型；带会话和当前请求关联 | 纯交流不创建执行任务；明确行动复用唯一任务受理，能力未开放时说明缺口；不把普通文本响应包装成动作成功 |
| Commitment / Attention 视图 | 约定来源、有效时间/范围、提醒偏好、已撤销状态；实际任务引用 | 约定与执行结果分开；需要定时/外部动作时使用已有受理语义，去重与取消可查；观察不凭自身内容创造新授权 |

<a id="memory-provider-contracts"></a>
## 记忆组件的替换契约（proposed）

下表定义边界，不是已实现的 API；K2 实施时在 `contracts/schemas/` 固定机器定义，避免各框架的私有对象成为跨模块格式。内容语义由[记忆设计](knowledge-learning.md#memory-selection-design)维护，复制语义由[共同体页](federation.md#memory-replication)维护。

| 组件 | 输入与输出 | 不可越过的边界 |
|---|---|---|
| MemoryStore | 原始资料引用、候选事实、修订/撤销关系；返回持久 ID、提交版本和证据 | 唯一事实写入入口；验证来源、作用域、授权及幂等；不让 Worker 或向量库直接决定有效事实 |
| MemoryExtractor | 已授权片段、角色与任务域；返回带来源片段定位的候选事实/摘要 | 模型推断和助手陈述必须标出；无来源、结构错误或不确定输出可拒绝，不能默认晋升 |
| Retriever | 查询、不可放宽的身份/域/版本/时间过滤、预算；返回证据引用、分数类型、索引水位和缺失范围 | 支持关键词、向量、图等实现；返回前重新检查有效性，过期索引不能绕过遗忘或撤权 |
| EmbeddingProvider | 固定模型配置、query/document 用途、文本批次；返回向量及空间标识 | 拒绝维度或空间不匹配；云端处理另行遵循既有数据授权，不能在离线失败后静默外发 |
| SyncTransport | 已授权且版本兼容的事件/对象及缺失范围；返回持久接收游标 | 传输不裁决事实真伪，不授予动作执行权；断线重放须幂等 |
| MemoryViewResolver | 主人、任务与已授权资源范围；返回本次允许的记忆视图 | 应用侧计算范围；模型提出的 project / persona / world ID 不是授权依据 |
| KnowledgeCompiler | 指定项目、源版本、变更集合和资源预算；返回来源明确的候选知识/文档 patch | 不直接修改 MemoryStore、规则或任务表；生成完成不等于知识真实或文档已发布 |

共同记录至少需要：稳定对象 ID、来源与内容摘要、节点及节点实例代次、事件序号与因果前驱、事实有效时间与系统记录时间、修订/撤销关系、现实或模拟域、主体/分享范围、保留策略与证据状态。时间字段不能替代因果关系；来源签名证明发送方，不证明内容真实。

索引版本由源资料修订、切片器/分词器版本、嵌入模型与权重修订、维度、归一化、池化、query/document 前缀和量化配置共同标识。相同维度不代表相同向量空间。检索回执还需标明事实提交水位、已索引水位及结果覆盖范围，不能只返回一段没有来源的自然语言。

记忆事件及其 outbox 在记忆存储的同一事务中持久化，接收端 inbox 去重与事实应用同样原子提交。它们与 `control.db` 的任务/动作事务彼此独立，跨域靠稳定引用与对账；不声称跨数据库的普通写入天然原子。接口升级需提供导出、导入、重放、拒绝不兼容版本和删除传播的兼容证据。

<a id="memory-extractor-adapter"></a>
### 开源提取器、编纂器与路由的适配要求（proposed）

用于 LangMem、Mem0 等候选实现；下面是拟定的替换语义。提取器只提交有来源候选，不能绕过用途许可、事实校验、纠正和遗忘。当前没有安装上述框架。

2026-10-18 新增 **实验工具范围的 LangMem 适配子集**：[父进程适配器（旧工程参考）](references.md#legacy-project)调用独立环境的[单次 Worker（旧工程参考）](references.md#legacy-project)。输入仍先经过本人消息、临时会话、来源版本和不保存/凭据排除检查；输出重新经过原 `SemanticCandidates` 的句位、类别、主体、项目范围校验。框架只接收分句内容和 `has_project`，不接收库路径、密钥、项目真实标识、已有全库事实或确认权限。适配器真实运行 `create_memory_manager`，使用候选批次 schema，关闭更新/删除、存储、embedding 与追踪；`max_steps=1`、Trustcall `max_attempts=1`，父进程另限制每例最多一次网关请求、60 秒模型期限和 90 秒协作期限。取消和异常退出回收实验进程，已发生的用量及 UNKNOWN 保留。

框架实际产生的消息和工具 schema 经管道交回父进程，再通过现有模型网关与核心准入检查发送；当前网关用**文本 JSON 模拟工具回执**，没有新增 SDK 直连或复制上游私有函数。这是受 Jarvis 规则约束的提取实验，不是完整 LangMem 默认配置，也未实现下表全部插件语义。子进程清除继承的供应商/代理/追踪环境变量，安装 Python 网络和子进程审计拒绝；这只能防误用，**不是操作系统安全沙箱**。依赖固定文件、运行测量和复跑方式见[影子对照证据（旧工程参考）](references.md#legacy-project)。生产启动不导入此模块，当前工作台也不把它列为可选提取器。

同日新增 **Mem0 2.2.1 实验子集**：[适配器（旧工程参考）](references.md#legacy-project)与[独立 Worker（旧工程参考）](references.md#legacy-project)使用公开 `Memory.from_config`、`add(infer=True)`、`get_all`、`update`、`delete`、`history`，不复制私有提取函数。每例独立 Qdrant 本地目录与 SQLite 历史；结束后先回收进程再删除临时库。`candidate` 模式让原生 `memory[].text` 承载候选 JSON，再经原来源、分类、项目和修订屏障校验；`sequence` 模式仅用于合成多轮行为观察，其显式更新/删除无权改变 Jarvis 正式事实。二者均不是生产自动建档入口。

Mem0 配置使用受支持的 OpenAI 兼容接口，实际 SDK 只连接 Worker 自己的临时回环端口，使用随机本地令牌；模型消息经管道、序列化文本传输和原网关发送，真实供应商凭据不进入 Worker。原生长提示不通过放宽正式网关的指令上限接入。每个 `add` 至多一次实际模型调用，SDK HTTP 重试关闭；单例候选最多一次、序列最多六次，取消/超时/UNKNOWN 不自动补发；错误 JSON 必须报告失败，不能让 SDK 的宽松解析把错误计为成功弃答。嵌入是本地 256 维字符 n-gram 哈希向量，只用于空库候选和每域不超过十条事实的穷举式小场景，**不作为语义检索质量证据**。遥测关闭，数值库线程限制为一；Python 审计只允许该回环端口，其他网络及子进程拒绝，仍不是 OS 权限隔离。安装、费用、资源与实际边界见[Mem0 实验记录（旧工程参考）](references.md#legacy-project)。

| 边界 | 适配器必须提供什么 |
|---|---|
| 输入快照 | 稳定作业与输入版本、允许的来源集合、说话者/来源类型、作用域、允许的目的 provider、已有相关事实修订、调用/字节/时间预算；只给相关片段，不默认导出全库 |
| 候选结果 | 候选类别、内容、原文或工具回执定位、派生依赖、有效时间、保留理由、冲突/替代建议及提取实现版本；找不到来源或无法确定时返回不足，不能伪造定位 |
| 写入校验 | 应用重新验证作用域、来源是否仍在当前版本及删除/纠正状态；模型输出的 ID、置信度和建议动作不能直接授权写入；向量相似度不作为真实性概率 |
| 幂等与失效 | 区分同一请求重试与更换算法后重新分析；候选必须关联输入修订与提取代次。确认、忽略、撤销和过期结果可对账；被遗忘来源的旧作业不得重新生效 |
| 完成回执 | 分别报告已接受、待确认、忽略、冲突、失效、失败以及实际模型用量；模型生成完毕不等于持久提交成功，失败不能静默丢失待处理输入 |
| 退出和替换 | 可取消，有超时；导出通用候选及来源，不把上游私有对象作为唯一格式。关闭插件后明确事实与既有资料读取仍可运行，实验数据可按其作用域清理 |

提取和知识编纂共用既有模型网关，按任务设置首选、备选、档位与费用预算；每次备选切换重新检查输入外发范围。规则过滤、事实读取和词法检索无需 LLM；语义检索单独经过 EmbeddingProvider。**LLM 任务路由与 embedding 空间管理分工，不新增两个互相绕过策略的云网关。** embedding 不可用时退回词法或等待；换模型须建新索引代次，不能把新模型向量写进旧空间。已准备的离线模型可用则本地处理，否则保留待整理状态，不为完成后台任务自动上传私人内容。

Wiki patch 还需包含所依据的源版本和目标章节版本；发布时源或目标已变化则重新分析/合并，不覆盖用户新修改。插件的自动提示优化、技能生成、联网学习和调度功能默认不由“接入记忆”一并启用；涉及这些能力时仍使用对应模块的既有契约。

<a id="memory-view-contract"></a>
### MemoryView 与知识候选的必要语义（proposed）

这是完整目标，尚未实现；落地须建立独立 schema、兼容版本与正反例，不能把部分联合视图等同完整域、时态及冲突语义。

| 对象 | 需要携带的语义 | 失败行为 |
|---|---|---|
| ScopeContext | owner / task / session 引用、允许的 project 集合、现实或 world 域、persona 配置引用、消费 Agent/工具、查询用途、处理 provider、输出读者/渠道、策略版本 | 未知项目或域不自动扩为全库；更换消费者、用途或目的地重新解析；模型不能自行授予资格 |
| MemoryRecord | 主体 ID 与说话者、信息类别、事实内容或原件引用、适用条件、有效/记录时间、证据类型与状态、修订、分享/外部处理/输出许可引用、来源依赖 | 未知范围保持待归类；缺省不自动共享。密钥不进入普通正文，转述/假设/推断不得伪装核验事实 |
| MemoryView | 本次范围与用途、背景偏好、项目目录引用、选定证据与源修订/策略版本、冲突、事实/索引水位、覆盖范围、字节或 token 预算 | 只返回满足当前使用及输出资格的内容；不足时返回 missing / stale / conflict，不伪造完整性；输出阶段不继承另一用途的完整历史 |
| SharedProjection | 原依赖 ID/修订、分享决定与策略版本、获准的输出字段或片段、目标用途/范围、有效期、晋升状态 | 生成摘要或改标签不扩大许可；依赖变化则复核/重建，无法证明目标范围资格时不放行 |
| KnowledgeCandidate | 源资源 ID/版本、Claim 或摘要、证据类型/说话者、建议作用域、依赖列表、产物状态、编纂器版本、目标章节 | 模型不能自签 verified；源版本变化、缺证据、越域时拒绝晋升或进入待复核 |
| ProjectReference | 全局稳定项目 ID、节点本地位置映射、文档 ID/锚点、提交/工作区版本 | 路径失效只报告无法定位，不能自动扩大扫描到全盘；本机盘符不作为全局 ID |

MemoryView 只授权本次读取与装配，不授予工具执行权限。实际 provider 变化时重新计算 external_processing；将两个项目联合检索不修改它们永久的分享策略。知识候选的来源链包含派生输入，不能只留下摘要而失去限制的继承关系。具体用途与自然交互语义只在[记忆作用域](knowledge-learning.md#memory-scope-model)维护。

切片/事实中的每个来源定位都属于宿主允许的输入集合；多来源混合片段不能因为其中一句可见而返回全文。查询、出站提示、向量化、检索结果与最终产物分别执行当前用途检查。视图缓存键至少关联范围、用途、消费者/实际 provider、输出受众、策略版本及所用依赖修订；旧缓存不能沿用到另一个 Agent、项目、角色或读者。撤销/纠正先使派生视图不再合格，再执行可延后的物理清理；期间返回缺口，不从旧摘要补回内容。

上述 MemoryRecord / SharedProjection 为拟定语义，需要独立验证来源依赖、撤回和受众隔离，组合验收见[个人与工作防串用](delivery-validation.md#memory-domain-validation)。

<a id="interfaces"></a>
## 接口与数据契约

以下是新工程的概念契约设计，不是可直接运行的配置。实施时独立编写正式 schema、校验器与正反例；公共模块清单以[新工程包契约](#clean-module-contract)为唯一规范。

<a id="interfaces-2"></a>
### 任务与动作分离

```yaml
task:
  task_id: task_001
  goal_id: goal_001
  parent_task_id: null
  scope: local
  owner_node_id: node_workstation
  owner_epoch: 7
  workflow_version: "1.2.0"
  skill_version: "2.1.0"
  planning_policy_version: "17"
  authorization_ref: grant_001
  checkpoint_schema: "task.checkpoint.v2"
  budget:
    max_cost_units: 100
    max_runtime_seconds: 1800
    max_attempts: 3
  required_capabilities: ["filesystem.read.v1"]
  cancellation_ref: cancel_001
  status: READY

action:
  action_id: act_001
  intent_id: intent_001
  task_id: task_001
  resource_id: device_workstation_files
  host_instance_id: host_b
  host_epoch: 3
  owner_epoch: 7
  enforcement_policy_version: "18"
  arguments_digest: "sha256:..."
  idempotency_support: receiver_verified
  status: PREPARED
```

task_id 标识工作；intent_id 标识较高层意图，可包含多个具体动作；action_id 标识一个外部动作，同一动作的网络重传、跨节点交接和模型重试必须复用该编号；attempt_id 只区分尝试，不能当作动作幂等键。同一个 action_id 携带不同参数必须拒绝。

动作账本去重记录的保留期必须覆盖允许的重放与离线重连窗口；超过窗口的旧命令拒绝自动重发，先对账或重新规划。第三方去重有效期也必须记录，不能假定永久有效。

执行链：授权 → 持久记录 PREPARED → 持久记录 DISPATCHING → 发出 → 接收并持久化回执 → 对账/验证 → CONFIRMED。恢复时所有没有终态回执的 DISPATCHING 一律按 UNKNOWN 对账；实际未发出的请求也可能被保守归入 UNKNOWN。不能因为缺少“已发出”记录就假定未执行。能够校验幂等键的接收方可用原 action_id 查询或安全重试；不支持幂等的目标保持等待直至消除歧义。[S06](references.md#s06)

<a id="interfaces-3"></a>
### 事件信封

```json
{
  "event_id": "evt_unique",
  "event_type": "task.checkpoint.saved",
  "schema_version": 1,
  "node_id": "node_workstation",
  "community_id": "community_owner",
  "entity_id": "task_001",
  "node_sequence": 1024,
  "causal_parents": ["evt_previous"],
  "occurred_at": "2026-10-15T00:00:00+08:00",
  "policy_version": "17",
  "trace_id": "trace_001",
  "sync_scope": "community",
  "external_processing": "deny",
  "payload_ref": "object:sha256:..."
}
```

事件按至少一次传递设计，消费者去重。消息中间件的确认语义不能替代业务动作幂等。

<a id="desktop-presence-contract"></a>
### 精灵与工作台共用的呈现契约（proposed）

此处落实[统一系统准则](architecture.md#unified-system-principle)，定义[Host 状态投影](architecture.md#desktop-presence-architecture)及相关命令的语义，不声明新 HTTP/IPC 接口已经运行；实现时再冻结 schema、校验器和兼容夹具。精灵、临时卡片、工作台和未来平台入口共用这些对象与受理语义；适配器转换传输和呈现，不在 UI 中创造第二套任务状态机、设置规则或工具执行路径。

| 对象 | 必需语义 | 消费规则 |
|---|---|---|
| 呈现快照 | Host 实例／数据根识别、快照修订、来源范围、采样时间、新鲜期限、最后事件序号；按工作及父子关系引用原 task/goal/conversation/project | 全部已接入来源新鲜且无活跃工作才能表示待命；缺少来源不是零任务，过期记录保留观察时间并标未知 |
| 工作摘要 | 原任务 ID、父工作关系、当前阶段、阻塞原因、实际完成单位／总量（可空）、耗时依据、可用动作和已核验产物引用；调度决定/租约引用、优先级来源、期限、等待资源及预计开始时间（可空） | 按[状态表达](interaction-persona.md#desktop-presence-state)区分运行中、排队中、等待你回答；目标、子任务、工具调用不重复计数，未知排队时长不编造；只渲染来源支持的取消／接续 |
| 待答问题 | question_id、所属任务／原会话、问题修订、问题原因、选项／自由文本、建议与影响、等待依赖、当前未答／已处理／已失效状态 | 持久化由所属业务模块负责；建议不等于授权。“稍后”仅改变呈现，不放行执行；原会话已处理后其他视图必须同步撤下 |
| 回答／取消命令 | 原目标对象、预期修订、幂等请求标识、所选答案或文本、当前调用者及作用域引用 | 由既有受理与权限路径核对。重复请求复用回执，冲突或失效修订刷新后再处理；UI 的“已点击”不等于受理成功，回执未确认先查询，不盲发新效果 |
| 成果与通知引用 | artifact/delivery 原标识、任务／会话关联、核验状态、可读范围、通知去重键、未读与处理修订 | 结果提示与任务完成分开；关闭提示不删除成果。精灵与工作台只展示当前有效引用，不复制私密文件到另一份 UI 数据库 |
| 共享配置引用与更新 | 原配置键／schema 版本、作用域、目标节点（适用时）、有效值与来源、预期修订、更新请求标识及受理结果 | 快捷控件与详细表单走同一设置服务；传播的是获准的值／引用及修订，不向 UI 广播原始凭据。冲突返回实际修订，未受理不得显示保存成功 |
| 呈现偏好／草稿 | 原会话草稿引用及修订、共享主题／免打扰引用、设备／界面作用域的显示器与 DPI 位置、展开和主动隐藏选择 | 沿已有设置／草稿所有权保存；同一作用域保持一致，设备覆盖不改全局值；卡片销毁或切换工作台保留草稿，冲突不静默覆盖。位置与界面关闭不改变任务事实 |
| 能力与节点引用 | 能力稳定标识、契约版本、实际可用状态与原因、执行节点及有效所有权引用、原任务／动作／成果关联 | 两种工作形式从同一能力目录获知能做什么；没有本机硬件时可以显示获准的远端能力。界面设备不冒充执行设备，断线后先核对原请求，不重建一个任务来重发 |
| 面罩表达视图 | 表达类型、状态来源／修订／作用域、双眼／文字／组合模式、短词的类型与语言、提示有效期、实际音频状态引用、外观配置修订 | 按[电子面罩规则](interaction-persona.md#desktop-face-display)由统一渲染器消费声明式数据，不能下发可执行脚本。装饰问候与业务状态分开，过期来源重新仲裁；精灵与工作台形象预览共用定义 |

事件复用[事件信封](#interfaces-3)，按序去重；序号缺口、Host 代际变化或重连先取权威快照，再继续增量。未知业务效果仍按[任务／动作规则](#interfaces-2)核对。输出的状态与文案必须携带可追溯来源，不能因更换前端、模型或原生壳丢失工作归属。此契约不扩大访问所有本机进程、文件、麦克风或其他账号的权限。

<a id="extensions-3"></a>
## 资源租约、本地组件与安全事件契约

```yaml
resource_lease:
  lease_id: resource_001
  root_task_id: task_001
  holder_agent_id: agent_001
  node_id: node_home
  cpu_limit: measured_profile
  memory_limit_mb: 1024
  model_concurrency: 1
  spend_reservation: 10
  budget_account_ref: task_budget
  expiry_ref: lease_expiry
  reclaim_policy: checkpoint_then_sleep
  security_epoch: 12

local_component:
  component_id: speech.stt.local
  kind: stt
  version: "validated-1"
  artifact_hashes: ["sha256:..."]
  source_ref: trusted_registry_entry
  platform_arch: windows-x86_64
  runtime_abi_ref: onnx_compatible_profile
  languages: ["zh"]
  quality_eval_ref: owner_voice_commands_v1
  resource_profile_ref: cpu_survival
  fallback_ref: speech.stt.previous
  offline_verified_at: "2026-10-15"
  status: ready

security_stop_event:
  event_id: stop_unique
  community_id: community_owner
  incident_id: incident_unique
  issuer_node_id: node_home
  issuer_sequence: 1024
  scope: community_business
  reason_code: ROOT_PRINCIPLE_VIOLATION
  evidence_ref: protected_evidence_hash
  signature_ref: supervisor_signature
```

上述额度、日期和编号均为示例，不是已完成验证的记录。真正运行时使用签名来源、实际评估和有效租约。

<a id="scheduling-contract"></a>
### 交流保障与调度决定的增量契约（proposed）

复用原会话、任务、动作、租约、预算和事件标识；不建立第二份任务账本。下表是待冻结的语义要求，不是现有 HTTP 字段或已完成的数据库迁移；实现须补 schema、兼容夹具与并发约束。排序与准入算法只归[资源调度](tasks-agents.md#resource-scheduling)。 当前原型的持久派发意图、优先级修订及工作状态投影见[有界并发实现](tasks-agents.md#bounded-concurrency-runtime)；该子集不代表下表的租约、全局配额与跨模块协议已全部实现。

| 对象 | 需要保存的语义 | 一致性要求 |
|---|---|---|
| 输入受理与命令 | conversation/turn/command ID、原消息引用、接收时间与次序、目标 task/goal/question ID、预期修订、持久受理结果 | 去重不吞同文的新请求；已收、已解析、已建任务、已生效分别记录；控制受理独立于模型完成 |
| 任务调度说明 | 显式优先级及指令来源、期限、重要性/延误影响、推断标记、依赖、排队起点、最长等待/最低进展约定 | 原目标拥有含义与修订；调度器持有派生有效优先级与简短理由，不能改变主人原指令或权限 |
| 步骤资源画像 | CPU份额/内存/显存/I/O/网络需求、模型配额域、估算/实测来源、冲突键、可取消/可检查点能力及最长不可抢占段 | 无观测不标实测；子进程与本地模型驻留纳入，不重复计算共享模型或漏算 KV 缓存 |
| 准入决定与租约 | decision ID、policy/profile revision、owner epoch、任务/步骤/父预算引用、资源保留/上限、到期、实际执行者、检查点引用、授予或等待原因 | 预算与原子认领一致；过期/旧代际不能继续提交新动作；UNKNOWN 与在途请求未核对前不重复授予对应额度 |
| 呈现与观测 | 源状态、采样/新鲜时间、步骤进展、等待原因、控制/回复分段延迟、各模块资源、未知指标 | UI 读取投影；历史数据不是当前状态，运行数与等待数按原工作去重；指标不得包含凭据或完整私人输入 |

调度受理的简短事务与慢模型/工具执行分离，所有权与修订比较失败需重新读取，不自动重复派发。等待问题/资源的状态由原业务拥有，调度器只授予当前可运行步骤的租约；单个任务取消不得清空其他任务、停止常驻服务或释放仍被占用的远端额度。

<a id="personal-life-foundation"></a>
## 生活助手共用模块与请求上下文

目标契约 proposed；复用原核心模块，按端口扩展，不把每个生活场景做成独立 Agent 或服务。首次实施优先本机提醒、定时计划与任务故障隔离；实际交付范围另见版本验收。

| 模块职责 | 服务的同类问题 | 实现方向 |
|---|---|---|
| 身份／授权会话 | 主人、家人、访客、设备、在场者 | Principal、认证强度与时效、资源授权；不让 LLM 决定权限 |
| 资料与记忆视图 | 偏好、关系、学习、工作、私密资料 | 扩展现有 MemoryView，过滤规则见[分域](knowledge-learning.md#personal-life-data-domains) |
| 日程／注意力调度 | 会议、学习、生日、续费、旅行、到期事项 | SQLite 持久规则、一次触发编号、错过执行政策、安静时间、提醒与执行分离 |
| 任务监督 | 分步执行、诊断、重试、替代方案、暂停、接续 | 原计划＋队列＋回执，等待重试释放执行槽，不另建工具运行时 |
| 连接器 | 邮件、日历、媒体、购物、旅行、家居 | 官方 API 优先；明确能力、账号与读写范围，UI 操作仅作受限适配 |
| 凭据代理 | 密码、OAuth 令牌、登录、受保护填写 | 模型获得不可解密引用；私密材料由受保护执行器使用 |
| 外部事务协调 | 发信、下单、续费、预订、取消退款 | 准备→授权→提交→回执→对账；不能把 UNKNOWN 解释为未发生 |
| 资源／审计与通知 | 前台响应、后台公平、预算、结果交付 | 原 Host 租约＋轻量事件，不为状态轮询调用模型 |

逻辑调用链为“已认证主体与受众 → 有范围的资料视图 → 目标／日程 → 授权快照 → 原执行器 → 结果核验 → 私密或公开通知 → 可纠正候选”。请求需关联 principal_id、认证时效、account_id、project_id、用途、输出受众、隐私级别、grant_id、预算、task_id／trigger_id 与幂等标识。身份、条款、资料范围或授权修订改变时重新检查，不能只在第一次对话验证。

普通 PC 采用本机数据库表与按需适配器；调度只在临近到期、事件变化和短周期恢复检查时工作，不常驻大模型。APScheduler 的 misfire/coalesce/max_instances 与 Home Assistant 的 single/queued/parallel 仅作为机制参考（S248—S249），本轮不安装整个框架。秘密不加入一般同步；多设备日程接入时沿原共同体唯一所有权与撤销协议。PC 休眠或关机不能保证准点通知，跨设备推送要另接终端与授权。

<a id="composition-contracts"></a>
## 可组合能力、蓝图与运行契约

**完整契约 proposed，2026-10-22。** 下列字段仍需新工程 schema 和行为测试；语义归[组合框架](architecture.md#composition-concepts)，运行归[装配流程](tasks-agents.md#composition-execution)。身份、任务、动作和预算保持唯一所有者。

<a id="composition-package-contract"></a>
### 能力包与角色蓝图

| 对象 | 必需信息 | 约束 |
|---|---|---|
| CapabilityDescriptor | id、kind、version/content_digest、输入/输出 schema、执行器引用、效果类别、前提、依赖、资源提示、验证引用、来源 | kind 区分方法/工具/工作流/模型/角色；`declared/installed/ready/authorized/verified` 分别表示，不合并成一个 available 布尔值 |
| ToolDescriptor | capability_ref、参数边界、read/write/external_effect、幂等支持与期限、取消能力、结果查询、补偿支持 | 供应商的“只读”标注需本机核对；不支持结果查询/补偿时明确 unsupported，不伪造可回退性 |
| AgentBlueprint | id/version、职责与适用/排除范围、技能/工具依赖、输入输出、上下文选择器、模型策略、评估器、终止条件 | 不携带原始凭据、用户事实正文、活动任务或权限签发代码；依赖可有兼容范围，装配时解析为固定版本 |
| BotBinding | 稳定 id/revision、展示身份、通道/事件触发、blueprint_ref 或 child_binding_refs、有效授权引用、主动性/安静时间、去重及停用状态 | 可选；子绑定是职责引用，完整语义见[Bot 组合](architecture.md#composition-bot-nesting)。不得自行新建工作线程、模型循环或绕过任务准入 |
| TeamPlan | 父目标、子任务依赖、蓝图引用、产物接口、预算分配、合并及验证方式 | 子预算先预留，依赖图无环；动态新增须创建新修订，不让子任务各花整份父预算 |

能力包含不可变清单、方法资料或执行器、兼容要求、测试/证据引用和退役规则。包摘要只证明内容未变，不证明可信作者或无漏洞；签发/来源与独立检查按[准入规则](security-sovereignty.md#personal-life-supply-chain)。第三方 Skill 的 `allowed-tools` 仅作为需求输入，不覆盖宿主许可。

BotBinding 的组合字段仍是概念草案：`child_binding_refs` 引用子绑定的稳定 id，配置修订校验有效目标、唯一组织父节点、无环和宿主规定的容量；不把整棵子树复制进每个记录。单绑定同时具有自身蓝图和子绑定时，应明确触发选择规则，默认不得向全部分支广播。受理时固定所选绑定的修订及触发来源引用，现行撤权和停用约束仍优先；这些字段不属于当前 `composition.run.v1` 的可加载格式。绑定关系不是执行队列，实际子任务及预算继续使用原 Task/TeamPlan 契约。

<a id="composition-run-contract"></a>
### 一次运行与上下文

```yaml
run_spec:
  contract_stage: proposed  # 概念草图；不是 0.1.107 composition.run.v1 的可加载 JSON
  run_id: run_unique
  goal_id: goal_unique
  root_task_id: task_root
  blueprint_ref: research.materials@1
  resolved_packages: [research-guide@2, source-reader@1]
  package_digests_ref: immutable_manifest
  task_graph_ref: graph_revision_1
  input_ref: validated_input
  output_schema_ref: report.materials.v1
  context_view_ref: purpose_limited_view
  model_policy_ref: research_balanced@1
  evaluation_ref: materials_independent_checks@1
  authorization_ref: existing_grant
  budget_reservation_ref: reserved_from_parent
  termination_policy_ref: bounded_research@1
  root_principle_ref: G0

agent_instance:
  id: agent_unique
  run_id: run_unique
  task_id: task_step
  parent_instance_id: null
  deployment_node: node_home
  owner_epoch: 7
  security_epoch: 12
  permission_lease_ref: permission_subset
  resource_lease_ref: current_resource_lease
  checkpoint_ref: validated_checkpoint
  status: admitted
```

RunSpec 固定代码/技能/模型策略与输入来源版本；每次恢复重查现行授权、撤销、网络及来源有效性。固定旧版本不能复活被撤权的数据。实际使用的供应商、模型、档位和备选尝试写入独立调用回执；不把策略引用当作已经调用某个模型。

`RunContext` 统一携带主体/会话/项目或 world_id、purpose、输出受众和目的地、资料引用修订、节点/所有权/停止代际、取消、期限、费用预留及追踪引用。安全字段由 Host 绑定；模型只能建议目标和工具参数。凭据引用仅供执行器解析，不把秘密正文发给 Agent。跨敏感边界新建 ContextView，不复制完整历史。

Agent Runtime 单步返回 `respond / propose_action / propose_subtask / wait / propose_change` 等类型化结果；宿主验证类型、schema、候选范围和适用策略。`respond` 不表示任务已验收，`propose_change` 不表示已发布，模型输出的授权字段必须拒绝或忽略。Runtime 插件不直接获得领域数据库写权限。

<a id="composition-step-contract"></a>
### Agent Runtime 一步接口与宿主验证责任

**以下为新工程接口草案，尚未实现。** Runtime 每次只处理一个有界决策，不持有第二套队列、定时器或自动重试主循环；正式化需兼容版本和独立测试。

建议端口表达为 `step(run_ref, instance_ref, expected_revision, context_view_ref, observation_refs, limits) -> StepProposal`；这是逻辑签名，不是当前 Python/API 已存在的方法。宿主解析所有引用，并提供已核验的最小数据视图。模型仅产生候选内容，不能自行决定输入里的身份、预算、权限或执行代际。

| 内容 | 由谁生成/验证 | 设计要求 |
|---|---|---|
| proposal_id、run/instance/task 引用、expected_revision | 宿主封装；原任务所有者核对 | 绑定本次请求及前序修订；重复候选去重，过期修订不覆盖新结果 |
| kind 与 payload | 模型或确定性策略提议；严格 schema 校验 | 只允许下列联合类型，各类型封闭字段，禁止附带任意命令、路径或权限签发字段 |
| input/context/source 修订 | Context Service 提供；执行与恢复时再验证 | 区分输入版本固定和现行许可有效；旧资料已撤回不能借旧规格恢复使用 |
| rationale_summary 与 evidence_refs | 运行时提供简短可见理由；引用由宿主解析 | 只记录选择依据和可观察证据，不要求获取或保存模型隐含思维链；引用不等于事实已验证 |
| usage_receipt_ref | 模型网关/外部执行器 | 以实际调用记录计费；未知成本单列，模型自报“零成本”不作预算依据 |
| checkpoint_candidate_ref | 运行时建议内容；任务所有者核对后提交 | 不修改动作终态、授权或预算事实；大正文留在领域存储，不全塞控制记录 |

| 返回种类 | payload 的语义 | 宿主后续动作 | 不能被误解为 |
|---|---|---|---|
| respond | 面向主人的文本/产物引用、完整性及证据说明 | 复核输出用途、依赖和验收；可呈现进展或最终结果 | 模型说“已做完”就完成了外部操作 |
| propose_action | 已解析的 tool_ref、schema 内参数、输入引用、前提 | 由原控制链分配/复用 action_id，复核许可和效果，再交领域执行器 | 模型可直接调用任意工具，或换 action_id 规避未知结果 |
| propose_subtask | 子目标、蓝图候选、所需输入、依赖与预计预算 | 工厂核对深度和父额度，绑定父子任务及上下文；不适合拆分则拒绝 | 子 Agent 自动继承所有资料或拥有一整份新的父预算 |
| wait | 等待原因、事件/条件引用、建议期限 | 原调度者登记有界等待，释放能释放的槽位，去重唤醒 | 每隔几秒调用模型判断是否还要等待，或绕过已取消状态 |
| propose_change | 未执行计划/规格的修订建议，或能力改进目标与依据 | 对计划做依赖/权限/预算复核；涉及代码或包交原成长链 | 在途动作被删除、已完成步骤被重新执行，或候选直接上线 |

一次返回不能通过混入第二种隐式指令实现多动作；确有批量操作时应使用已登记的批量工具或显式任务图，并明确其原子性、部分失败与每项回执语义。恶意或格式错误返回在产生副作用前拒绝；纠正格式的重试也占用原预算，达到阈值暂停本任务。

<a id="composition-state-ownership-details"></a>
### 哪些数据长期保存、哪些只是派生视图

| 数据 | 权威写入者 | 保存内容与寿命 | 不能形成的第二权威 |
|---|---|---|---|
| 能力包与蓝图版本 | 原注册/发布控制 | 不可变内容、摘要、来源、兼容及证据引用；按引用退役 | SelfModel 不能自行增加一个可执行能力 |
| BotBinding | 长期职责管理接口，经现有授权规则 | 触发、目标蓝图、安静时间、范围和停用状态；持续到撤销 | 绑定记录不能直接写任务已成功或授予新账号权限 |
| RunSpec | Composer 输出，原受理事务固定 | 原请求、选定版本、范围与策略引用；跟随原回执保留 | 不另建一份可修改的“最新版运行配置”覆盖旧任务 |
| 任务与动作 | 原 Task Runtime / 各领域已明确的任务所有者 | 生命周期、所有权、原动作编号与真实效果证据 | AgentInstance 不能另有一套可独立推进的执行状态 |
| AgentInstance/检查点 | 原任务所有者提交，Runtime 提候选 | 步骤位置、状态引用、可见摘要、来源修订；按任务及恢复要求保留 | 模型对完成与权限的自述不能当权威事实 |
| 个人记忆/项目知识/邮件/世界状态 | 各自领域 API | 保留各自加密、纠正、来源、用途与留存规则 | Runtime 不直接把全部结果写入一个统一向量库 |
| ContextView | 按请求派生 | 最小资料视图及引用；到期/撤销即失效；必要快照按原敏感级别存储 | 不能永久复制一份不再跟随纠正的主人画像 |
| 观察与评估报告 | SelfModel/评估服务 | 来源版本、观察时间、范围和限制 | “观察到某模块”不等于模块健康，更不等于被授权使用 |

这里的“长期”表示跨会话/重启可恢复，不表示永久无条件保留。检查点、候选和缓存均须遵循所属数据的保留与撤回规则；不为 Agent 另建不受遗忘治理的历史库。

<a id="composition-durability-contract"></a>
### 状态持久性、事件与兼容

Task Runtime 拥有任务状态及动作引用；Agent 检查点拥有当前上下文引用、步骤位置、已观察工具结果和运行版本。检查点不保存可重放的权限授予，也不要求保存模型内部思维链。事件包含 event_id、aggregate_id、revision、causation_id、correlation_id、schema_version 与内容引用；敏感正文留在领域存储。

同一控制库中的受理、任务修订、预算预留与 outbox 在短事务中提交；跨领域通过有界 outbox/inbox 和幂等消费协调。先成功提交域结果再发确认，崩溃后按原请求查询和补齐；不宣称跨多个 SQLite 文件全局原子事务或端到端 exactly-once。动作未知及回执保留仍按[动作契约](#interfaces-2)。

旧任务只能由原调度者或完成交接的新调度者执行；迁移标记和映射原子生效。外部编码 SDK、MCP 服务或远程 Agent 不能证明支持取消、幂等或费用统计时，按真实能力标注，不能包装成完整本地控制。

接口与包兼容采用固定 schema、输入/输出契约及组合测试；版本号仅为声明。运行中旧包继续服务到安全检查点或排空，新任务灰度使用新包。有状态迁移必须提供可验证的导入/导出和数据兼容策略；失败时不把未知副作用当作“代码回退即可消失”。

任务修订与检查点提交采用预期修订比较，避免两个 Worker 同时推进同一步。跨库确认仍使用原回执和事件因果引用；“领域动作成功、控制库尚未记录”的故障点通过查询原动作补齐，不用重新执行来修复记录。相同去重键但参数摘要不同必须报冲突，不能静默选任意一份。

暂停、取消、恢复、角色更换和模型备选均是原任务上的受控转换；重试次数、已用成本和未决动作不清零。BotBinding 停用首先阻止后续触发；是否取消已有任务应有独立的明确操作语义，不能在用户只想关闭提醒时终止正在保存的工作。完整任务状态名称继续以[既有状态机](tasks-agents.md#interaction-tasks-3)为准。

<a id="continuity-contracts"></a>
## 连续身份与核心实现替换的契约草案

**proposed；下表不是当前 API 或 `composition.run.v1` 的新增可加载字段。** 对象语义归[连续身份架构](architecture.md#continuity-definition)，迁移流程归[升级协议](evolution-release.md#continuity-upgrade-protocol)。长期资料仍归原领域，控制与恢复仍使用原账本。

| 对象/逻辑端口 | 最小信息或输入输出 | 权威与兼容要求 |
|---|---|---|
| ContinuityRecord | assistant_id、genesis_ref、lineage_revision、owner_relation_ref、charter_ref、domain_head_refs、schema_version | 保存身份来源与领域引用，不带凭据/全量正文；owner 关系不是模型可写字段；领域水位是集合，不伪造跨库全局事务序号 |
| ContinuityView | record_ref、用途/受众/项目/账号、来源修订向量、事实/承诺引用、不确定项、有效期 | 由原领域 API 派生；不是任何角色可永久复制的主人全档案；生成后撤权仍会使其失效 |
| FacetBinding | facet_kind、implementation_ref、blueprint_ref（可选）、input/output schema、context_selector、所需能力 | 三职能可有不同实现；声明能力不授予许可，多个实例不产生新的主体身份 |
| Direction 提案 | goal_ref、意图解释、计划修订、完成条件、所需资料/能力引用、未确定事项 | 提案交原受理；不能传入自批准的 permission、task_owner 或自封完成状态 |
| Engagement 提案 | 原 run/task 引用、回复或 StepProposal、交付/等待依据 | 复用[一步协议](#composition-step-contract)；真实动作通过原准入路径 |
| Reflection 提案 | observation_refs、受影响版本/范围、问题或改进假设、候选验证建议 | 检测事实与模型解释分开；不能覆盖原证据或直接改变 release 状态 |
| ContinuityHandoff | source/target 构建及协议版本、assistant_id、来源水位、任务/动作引用、迁移器摘要、核对结果、expected_generation | 原维护路径核验并提交；密钥/凭据不交给模型，不承诺模型 KV 或私有推理状态可迁移 |

可替换端口至少暴露能力探测、版本协商、一次有界调用、取消、状态导出/导入及结果核验语义。新端口缺少需要的能力时明确拒绝或降级，不能为“兼容未来”忽略未知的安全关键字段。Runtime 的私有优化缓存允许丢弃；可恢复任务的目标、已知结果、未决动作和检查点摘要必须有公开可迁移表达。

同一数据库内的变更使用修订比较和短事务；跨领域固定读取水位并验证，必要时局部暂停或重读，不宣称单次快照能原子覆盖所有 SQLite 库。迁移提交先持久化可恢复意图，再按原运行代际交接，最后确认目标已接管；崩溃在任一阶段只能由可核对的有效所有者继续。过期版本不得重新准入动作，未确认外部效果不得在重放中重复执行。

<a id="goal-opportunity-contract"></a>
### 目标委托、行动机会与自主维护策略

**proposed；新工程目标与维护契约。** 下列对象连接目标输入、个人计划、日程/职责和成长记录，不复制第二套任务调度状态；正文仍按所属资料域保存。

| 对象 | 最小字段组 | 权威与约束 |
|---|---|---|
| GoalMandate（目标委托） | goal_id/revision、owner_instruction_ref、目标/完成条件、优先级/期限、资料域与受众、permission_ref、budget_ref、主动/通知策略、暂停/撤回状态 | 原目标/职责管理接口持有；职责可以持续，但每次动作仍有独立 task/action。推断只能提出修订，不能改 owner_instruction 或授权 |
| OpportunityCandidate（行动机会） | opportunity_id、goal_ref/revision、source_refs/revisions、建议效果与受影响资产、预期收益及不确定性、期限、成本估计、去重键、需要的能力、拒绝/延期依据 | 原计划候选入口持有；尚未准入不是可执行命令。没有有效目标或维护许可时仅可作建议 |
| ImprovementPolicy（自主维护策略） | policy_id/revision、授权对象/变更类别、数据/网络范围、探索与执行预算、测试基线/留出集引用、发布条件、灰度/观察/回退约束、期限与撤销状态 | 原维护控制持有；生成者只能引用，不能自行上调预算、修改放行阈值或扩展变更对象 |
| GoalProgressView（目标进展视图） | goal_ref、原 task/action/承诺引用、已证实结果、未决项、最近证据修订、下一有效唤醒条件 | 从原账本派生，不自行宣称成功，不另建可独立推进的执行状态 |

受理前及产生效果前重新核对目标修订、现行授权、预算预留与来源有效性。目标更新不能通过旧 OpportunityCandidate 继续执行已取消的目的；引用一致但效果参数不同必须冲突处理，不能假借去重静默复用。机会转换为任务时复用原受理事务和因果标识；跨领域依原 outbox/回执对账，不宣称全局原子提交。

持续目标可派生子目标，子目标沿用同一根目标与总预算；模型和 Bot 不能通过生成新 goal_id 取得新额度。改进探索也属于已授权成本，离线期间累计支出与重试不能在重连时清零。是否可自动采用候选由现行 ImprovementPolicy 与独立证据共同决定；“owner_instruction_ref 存在”本身不是权限证明。

<a id="clean-module-contract"></a>
## 独立工程的模块包、管理端口与研发交付契约

**proposed；新工程专用协议草案，不可直接加载到 H 盘 0.1.107。** 格式统一使用 UTF-8、显式 schema 标识与版本。清单采用 JSON，配置采用 TOML，执行事件采用有界 JSONL；精确目录和文件分工只归[文件格式](stack-project-layout.md#clean-file-formats)。未知安全关键字段、主版本和必需能力必须拒绝，不能为“未来兼容”静默忽略。

<a id="clean-module-manifest"></a>
### 模块清单与可替换端口

| 字段组 | 必须描述的内容 | 校验要点 |
|---|---|---|
| 身份与来源 | schema、module_id、version、包摘要、源码/构建来源、许可清单 | 版本号不是完整性证明；固定包内容，不按目录名认领身份 |
| 契约 | provides/requires 的能力/协议及版本区间、输入/输出 schema 引用 | 依赖解析可检查，禁止循环启动与不支持的效果类型；协议兼容需测试 |
| 执行 | 受认可的 runtime_provider_ref、包内入口引用、支持平台、资源估计与硬限额能力 | 清单不嵌任意安装命令或 Python 类导入；不因读取清单而运行代码 |
| 数据与权限 | 自有命名空间、资料用途、需要的效果和权限、凭据引用类型 | 申请不等于授予；无明文密钥，不允许直接读其他模块数据库 |
| 管理 | 支持的探针、取消、排空、检查点、导入导出及重启方式 | 不支持的操作明确返回 unsupported，不虚构可恢复性 |
| 变化与恢复 | 状态 schema、适用迁移器、兼容范围、回退条件、已知风险 | 有较新数据时验证旧实现能否读取；不能只提供旧二进制就宣称可回退 |
| 证据 | 契约/行为/隔离/性能/故障用例及报告引用 | 自带测试可辅助，独立验收不受候选修改；报告绑定实际包摘要 |

核心管理端口统一为 `describe / probe / start / drain / cancel / checkpoint / export_state / import_state / stop`，另有只读状态与指标事件。必须实现的最小集是 describe、probe、start、stop 和真实退出报告；其余按能力声明并由对应验收限制用途。实际调用含 request_id、module/instance_id、expected_revision、deadline、授权/预算引用、因果来源；响应区分成功、失败、拒绝、超时、unsupported 和 unknown，不用一句“OK”概括外部效果。

首期跨进程使用固定版本 JSON 消息和有界 stdio 通道，stdout 只承载协议，stderr 保存脱敏日志；大文件通过产物引用传递。消息的长度、数量、等待和取消均有限额。受控进程映射、实例握手及身份校验不能靠任意本机端口号替代；后续 Named Pipe 或其他传输可替换，不能改变动作语义。现行策略决定操作资格，清单不能自授管理权限。

<a id="development-work-contract"></a>
### 研发任务和交付物

`DevelopmentRequest` 固定根目标、待解决问题、基线、候选工作区、允许资料/网络/工具、预算、截止时间、目标包类型及验收引用。提供者端口至少有 probe、submit、status、cancel、collect；resume 为可选能力。一次派发在本地先登记 request_id 与提供者实例，再关联其 run/thread/turn 标识。提交结果未知时先查询及核对工作区，不能直接换提供者再派相同真实修改。

`CandidateBundle` 包含代码/配方、包清单、公开测试、依赖锁、构建配方、来源与许可、状态迁移/恢复声明、文档和未解决问题。编写者的“已完成”只是候选说明；只有独立构建与实际结果检查才能生成 `EvaluationReport`。报告绑定基线、候选摘要、测试集版本、环境、真实失败/跳过、成本与覆盖边界。

`ReleaseDecision` 引用现行维护策略、报告、预期运行代际、适用范围和回退条件，由发布控制提交。候选、外部 Codex、模型审阅者和普通 Bot 均不能直接构造有效激活记录。评估用例升级与候选修复分开版本化，不能在同一候选里放宽它必须通过的标准。

<a id="core-seed-wire-contracts"></a>
### 0.2.0-dev.1 已落地的契约子集

本节标记实际代码边界，不替代上文完整目标。首版公开 JSON 均有显式版本、类型与尺寸约束，拒绝未知字段、重复键、非有限数、非法 Unicode 和不支持的版本。校验器只支持已使用的 JSON Schema 词汇子集，遇到未支持的 schema 关键字拒绝；不宣称实现整个 JSON Schema 标准。

| 可读取的契约 | 实际用途与限制 |
|---|---|
| [task.v1](../contracts/schemas/task.v1.json) | 有限结构化计划、调用主体／范围／grant、请求幂等与任务限额；input_from 只把前面已确认结果填入报告正文，不能改变路径、身份、权限或能力 |
| [grant.v1](../contracts/schemas/grant.v1.json) | 绑定单一主体、范围、能力列表、有效期与跨任务共享额度；同 ID 不变更内容，撤销后不能由重新添加恢复 |
| [module.v1](../contracts/schemas/module.v1.json) | 仅接受受认可的内置运行提供者、固定代码文件摘要与无状态实现；不支持任意类导入、启动脚本、候选加载和状态迁移 |
| [step-proposal.v1](../contracts/schemas/step-proposal.v1.json) | 模型返回 tool/finish/wait 提案；kind 与效果字段必须相符。当前仅有可注入端口与替身验证，未连接实际模型或自动转成动作 |
| [fact.v1](../contracts/schemas/fact.v1.json) | 主体／范围／键／值／来源；写入与遗忘要求预期修订。当前为显式记录，不含自动抽取或向量召回 |

校验实现见 [sdk/protocol.py](../sdk/protocol.py)，无秘密示例见[文本报告任务](../contracts/examples/text-report.task.json)。动作当前保存在同一 SQLite 控制库，以 PREPARED → DISPATCHING → CONFIRMED／UNKNOWN 表达；正式跨进程 ActionEnvelope、事件总线、研发／发布契约和兼容迁移夹具仍待后续 K0/K1 实现。持久化布局由[SQLite 适配器](../adapters/storage/sqlite.py)的 schema_version 1 管理，未知版本拒绝打开，不自动覆盖或降级数据库。

<a id="growth-seed-contracts"></a>
## 当前研发、候选与包契约

0.2.0-dev.2 在原五种种子 schema 之上增加三种严格 JSON 输入，未知字段与未知版本拒绝。没有把完整目标中的所有草案宣称为已实现。

| 格式 | 本工程文件/事实 | 边界 |
|---|---|---|
| jarvis.development.v1 | `contracts/schemas/development.v1.json` | 固定 request_id、目标、主体/资料域、许可、纯工具能力、公开/独立用例、交付输入、尝试/调用/期限预算 |
| jarvis.development-plan.v1 | `contracts/schemas/development-plan.v1.json` | 模型提议能力、摘要和实现步骤；能力必须等于已受理值；无权限或执行命令字段 |
| jarvis.code-candidate.v1 | `contracts/schemas/code-candidate.v1.json` | 最多 8 个平级 Python 文件，main.py 的 run(text) 返回文本，总源码不超过 60 KB；宿主另校验名字、语法与配方 |
| jarvis.pure-package.v1 | `Packages.stage/get` 的宿主私有落盘格式 | 绑定配方、state_schema=0、内容与验收摘要；不是开放导入任意第三方插件的 API |
| Worker 回执 | `control/worker/runtime.py` | 输出项数/类型/大小匹配输入；Job/令牌/用量证据由宿主取得，候选不能自报隔离 |
| 模型调用账 | SQLite model_calls | provider、phase、输入摘要、额度预留、实际 token、状态、结果；UNKNOWN 不自动变 SUCCEEDED 或免费 |
| 插件结果回执 | `control/receipts.py` | 固定 task/action、参数摘要、实现包与输出摘要，先落盘后确认，恢复只读原回执 |

类型和调用次序由模块所有者验证，schema 成功只是结构检查。编译通过、模型认可或有限样例通过都不能证明任意任务语义正确；当前验收规格来自可信本机操作者，模型不能改写独立期望值。

<a id="local-settings-chat-contracts"></a>
## 0.2.0-dev.3：本地设置与对话接口

这里记录现行工作台接口子集；通用模块协议仍按前文设计完善。所有请求经新工程 JSON 解码、字段/类型/长度约束，再进入对应模块。配置入口不接受任意脚本或执行命令。

| 接口/边界 | 当前格式和效果 |
|---|---|
| GET /api/session、/api/snapshot | 本次页面 nonce/数据根；运行证据及不含凭据的模型投影。公开信息不含完整 credentials 或 credential_id |
| GET /api/chats、/api/chats/{id} | 最近 500 个会话（含恢复登记）、指定会话最近 100 轮；不接受磁盘路径 |
| POST /api/settings | revision、provider、model、reasoning、automatic_fallback、fallback_order；SQLite 比较修订后提交，陈旧修订冲突不覆盖 |
| POST /api/preferences | 栏宽、主题、音效、动画、当前页面的白名单字段；有限范围值 |
| POST /api/chats | 空对象或已登记 project_id 创建本地会话，不调用模型 |
| POST /api/chat/send | chat_id、request_id、text、provider、model、reasoning；dev.4 可附 skill、requirements、attachments，Host 冻结指导；幂等落盘后返回 202，后台获取真实回答 |
| POST /api/chat/cancel | 指定 request_id 取消当前轮次，不清空会话或其他任务 |
| 可信 HTTP 子进程 | 有界 JSON stdin/stdout，选定凭据仅经 stdin；返回 SUCCEEDED/REJECTED/INVALID/UNKNOWN、文本/JSON 和数值 usage |

同一 request_id 和相同内容复用原受理记录，内容变化冲突；每轮冻结模型线路，不被稍后的设置保存改写。对话账和研发账分别归各模块，不混写对方内部表。运行预算、候选及效果授权不会因普通聊天自动生成。对外接口防护归[安全章节](security-sovereignty.md#local-model-vault)，模型切换语义归[模型章节](models-offline.md#portable-model-settings)。

<a id="workbench-project-contracts"></a>
## 项目与文字技能的工作台接口

| 端口 | 格式与职责 |
|---|---|
| GET /api/projects、/api/skills、/api/usage | 项目登记、技能目录及策略、最近 200 条对话调用记录；不读取用户文件正文 |
| POST /api/project/open、/pick | 本机绝对路径与可选 create；或本人使用的 Windows 目录选择器。选择器返回路径，尚不登记项目 |
| POST /api/project/update | id 与 name/description/section/pinned/removed 的白名单 patch |
| POST /api/project/tree、/read | id、相对 path；按层树或文本/原始字节摘要 |
| POST /api/project/write、/mkdir | 写入要求 id/path/text/revision；创建要求 revision=null 且文件不存在；mkdir 只创建单层 |
| POST /api/project/export、/reveal | 无执行字段的工程文本，或打开已登记根目录 |
| POST /api/project/archive | id、archived；Host 调用 dialogue 的公开方法，不跨模块操作内部表 |
| POST /api/chat/update | id 与 title/pinned/archived/removed；正文不删除 |
| POST /api/skill/enable | id、enabled；未知/未就绪技能不能进入运行流程 |

工程文件使用 schema_version=1、folders 单项 path、name、description；前端导入仅取路径并要求用户打开，不执行其他字段。源码技能种子使用 schema_version=1，固定 id/name/category/kind/state/description/output/triggers/guidance；未提供网页安装第三方可执行技能入口。详细输入约束由各模块负责，跨模块关系只在 host/workbench 与 host/dialogue 组合。

<a id="goal-plan-runtime-contract"></a>
## 目标计划的当前运行契约（dev.8）

这是[通用目标/机会设计](#goal-opportunity-contract)的受限实现子集，不替代完整设计。结构源为 `contracts/schemas/goal-plan.v1.json`，行为和资源约束归[运行规则](tasks-agents.md#goal-planning-runtime)。

| 端口/对象 | 当前字段与语义 |
|---|---|
| GET /api/goals | 最近 40 个目标的标题、提案状态、修订和关联任务状态，不触发规划 |
| POST /api/goals，action=create | request 含 request_id、goal、input_text、provider、model、reasoning；相同请求复用原记录，内容变化冲突 |
| POST /api/goals/plan | id、retry_unknown；占用共享后台模型槽，返回受理状态；不执行计划 |
| jarvis.goal-plan.v1 | summary、input_text、steps、questions；每步只含 title、capability、source(input/previous)、expected；额外字段拒绝 |
| POST /api/goals，action=edit | id、revision、proposal；比较修订并检查目录与输入依赖后保存；不会建立执行许可 |
| POST /api/goals，action=approve | id、revision；原子创建受限许可、原 task.v1 和关联；重复同次确认返回相同 task_id |
| POST /api/goals/run | 只能执行已经关联目标的 task_id；不接受任意待办、命令或新的授权 |
| POST /api/goals，detail/cancel/reconcile | id；分别查看、撤销此目标及相关许可、核对原回执；核对不重复效果 |

本版扩展现有 task.v1 的 `input_from` 语义：个人纯文本插件可只传空 arguments，引用前一个已确认插件输出的 text；写产物继续引用前一步结果。运行层再次校验输出类型和长度。v1 结构没有变化，消费此新增语义的执行器必须是 dev.8 或后续兼容版本，不能把新任务交给旧 Host 执行。

所有写接口沿用 loopback Host/Origin、页面 nonce、严格字段、类型和长度检查。公开详情只返回模型 ID/参数，不返回凭据引用或正文。模型契约有效不等于规划业务含义正确，`expected` 不作为自动通过验收的凭据。

<a id="goal-growth-contract"></a>
## 原目标与研发关联的运行接口（dev.9）

行为与限额唯一权威为[目标关联研发](tasks-agents.md#goal-growth-runtime)。接口继续沿用原 loopback、Origin、nonce 和严格 JSON 校验，不直接接受模型代码或宽权限字段。

| 端口/对象 | 当前语义 |
|---|---|
| POST /api/goal-growth，prepare | id、原目标 revision；仅 NEEDS_INPUT 且未执行的首次目标，建立规格请求及模型许可，尚不联网 |
| POST /api/goal-growth/run | id、mode(draft/rejoin)、retry_unknown；复用共享后台模型槽，分别拟订规格或接续返回目标 |
| jarvis.capability-draft.v1 | supported、summary、description、public_cases、evaluation_cases、questions；没有授权、路由、命令和代码字段 |
| POST /api/goal-growth，edit | id、规格 revision、draft；只允许尚未受理研发的可编辑状态，核对两组用例与唯一输入 |
| POST /api/goal-growth，begin | id、规格 revision、routes、limits、acceptance_reviewed；同事务生成限定授权、原 development.v1 和关联；重复同次请求返回同一研发 |
| POST /api/goal-growth，reconcile | id；只核对该目标关联研发样本任务的未知回执，不重新执行 |
| 原 /api/goals detail/cancel | 详情增加 growth 投影；取消原子传播到规格许可、子研发与返回规划许可 |
| 原 /api/development detail | 增加 parent_goal；原批准精确候选、后台运行接口继续生效，不新增竞争发布通路 |

核心 schema 6 追加 goal_growth，goal_plans 增加 planning_round。goal_growth 用 goal_id 作主键、development_id 唯一关联，保存原提案/目录来源、规格、修订、状态和期限；请求文本仍归原 goal_plans。初次规划、规格、研发和返回规划的调用身份分开计量，回到原目标不复用旧提示的缓存。不支持将 schema 6 数据交给仅认识 schema 5 的旧 Host。

<a id="conversation-contracts"></a>
## 聊天行动与目标上下文接口（dev.10）

| 契约/端口 | 当前语义 |
|---|---|
| jarvis.assistant-turn.v1 | reply + action(kind、goal、input_text、target)；严格拒绝额外字段。目标 ID 只能来自当前会话绑定集合 |
| POST /api/chat/send | assistant_mode 布尔选项；旧调用省略时保持普通聊天兼容。前台自然识别与回答使用同一模型请求 |
| POST /api/assistant/action | 只接受 turn_id，宿主重读成功会话、建议、目标修订和域；不能由客户端传入任意执行授权 |
| POST /api/goals create | 可选 context(scope、enabled、chat_id、turn_id)，来源关联需与实际成功消息/路由/记忆相符 |
| POST /api/goals amend | id、revision、goal、input_text；仅未执行的可修订目标，同目标最多 3 代；历史与花费不清空 |
| GET /api/chats/:id | 关联目标状态、已确认的实际输出，以及已应用补充/取消/接续回执 |
| POST /api/memory propose_goal | goal_id；只有成功且背景仍有效的任务证据可形成候选。接受与撤回沿用原记忆接口 |
| POST /api/development retry_rejected | id；显式允许已知拒绝的原路线再尝试，保留原记录和预算，不自动承认 UNKNOWN |
| /api/development detail | 增加脱敏调用状态/模型/用量；没有认证令牌、系统提示或任意命令 |

源语义、状态与预算唯一归[聊天行动](tasks-agents.md#conversation-action-runtime)；schema 7 的增量表结构归[工程目录](stack-project-layout.md#conversation-layout)。

<a id="mcp-contracts"></a>
## MCP 接入与效果回执契约（dev.11）

| 对象 / API | 关键字段与语义 |
|---|---|
| 既有 extensions | id/revision/name/config；编辑或移除使对应旧准入失效 |
| mcp_admissions | extension_id、准入 revision、发现时 extension_revision、冻结工具描述/摘要、selected、enabled；与登记同库存储 |
| 能力引用 | `mcp.<extension-hex>.<tool-name-hash>`；implementation 摘要绑定端点配置、准入修订和完整工具描述摘要 |
| GET /api/connectors | 登记与发现状态、当前可用目录、最近任务；不联网探测 |
| POST /api/connectors/discover | id + 登记 revision；原后台通道执行发现，GET /api/development-runner 读取状态 |
| POST /api/connectors | configure(id,准入 revision,selected,enabled)、submit(request_id,capability,implementation,revision,arguments)、detail/cancel/reconcile(id)；拒绝多余字段 |
| POST /api/connectors/run | 单个 task id；原任务通道，拒绝复跑未知效果 |
| 任务输入 | 将已核对对象序列化为 task.arguments.text，执行适配再严格解码；不通过字符串拼接执行 Shell |
| 结果回执 | text、structured、is_error、source=mcp、端点、工具名、工具摘要、协商协议；外层绑定 task/action/implementation/入参摘要 |

对外协商优先 2025-11-25，接受 2025-06-18 / 2025-03-26 的工具子集。握手后发送 initialized，分页拉取工具；支持 JSON 响应及有限 SSE 消息流。会话标识只留在此次适配对象，不保存为账号凭据。拒绝重定向、错误响应 ID、重复工具名和循环 cursor，不按服务器 instructions 执行动作。

JSON Schema 仅支持显式简单类型、已列 properties/required、简单枚举与数值/长度约束、有界数组。省略 additionalProperties 时本客户端仍只接受已列字段，这是**收窄的客户端输入集合**，不是完整 JSON Schema 默认语义；显式 additionalProperties=true、$ref、组合类型、正则等不支持，工具可显示但不能启用。详情见独立 `sdk/mcp_schema.py`；不忽略未知关键字以放宽输入。

本轮新增状态在 `user-data/config/extensions.sqlite3`，核心 schema 仍为 7。准入修订使旧任务失败关闭，不恢复旧调用权限。完整运行边界归[MCP 通路](tasks-agents.md#mcp-runtime)。

<a id="session-folder-contracts"></a>
## 项目创建与会话目录契约（dev.12）

| 操作 | 输入和输出 | 不变量 |
|---|---|---|
| `POST /api/project/locations` | 空对象 → 当前平台、home、test_root | 只读候选位置，不创建测试目录 |
| `POST /api/project/create` | parent、name、可选 test 布尔值 → 项目登记 | test=true 不接受任意 parent；目标已存在不覆盖；不执行项目内容 |
| `POST /api/project/pick` | 空对象 → path 或取消时 null | 本机系统选择器；没有图形桌面可改用手动路径 |
| `POST /api/chats` | 可选 project_id → 新 chat ID | 工作台创建成功前须分配独立目录；目录失败不返回成功 |
| `POST /api/chat/workspace` | id、action=detail/save/reveal/sync；save 另带 config、revision | 所有动作核对来源和会话存在；save 使用摘要 CAS；归档/移除后拒绝写入 |
| 会话读取 workspace 投影 | path、config、revision、status、delivery_error；异常返回 error | 展示目录状态，不授予模型或文件权限 |

所有写接口复用本机 Host/Origin/nonce 检查。未知字段、链接/重解析点、路径越界和归属不匹配拒绝处理。目录数据格式及领域所有者只维护于[目录归属](stack-project-layout.md#session-folder-ownership)。跨平台使用公开字段与路径适配，不把本机盘符写进可移植的逻辑契约；当前登记的绝对路径仍需在换机时显式重绑定，尚无自动搬迁协议实现。

<a id="knowledge-library-contract"></a>
## 本地文本资料库的运行契约（knowledge-library-1.2.0）

**implemented 子集。** 独立 [knowledge-source.v1.json](../contracts/schemas/knowledge-source.v1.json) 已由运行校验器登记。它只表达用户导入文本，不替代上方完整 MemoryRecord/MemoryView/KnowledgeCandidate 语义。`POST /api/knowledge` 沿用同源 Host/Origin、页面 nonce、JSON 严格字段与请求大小限制；模型不能通过文字建立权限。

| 动作 | 输入 | 结果与失败规则 |
|---|---|---|
| list / detail | scope；detail 另带 id | 当前范围来源元数据 / 完整当前原文；项目已移除则拒绝，已删来源不可读取 |
| save | item、revision；item 严格含 id/scope/title/text/providers/paused | 创建 id 为空、revision=0；更新 CAS 核对修订且不能换域；服务端另校验 UTF-8 字节上限、控制字符、接入方注册和重复许可 |
| delete | scope/id/revision | 清空本模块正文与索引；返回 cleared_chunks 和 historical_outputs_cleared=false，不能伪称全链擦除 |
| rebuild / rebuild_vectors / index_status / cancel_rebuild | 仅 action | 单通道状态 queued/running/succeeded/failed/cancelled、已处理片段数、错误代码和活动索引可用性；取消不删除活动原件；kind 区分 fts/vectors；vectors 含活动空间、数量、水位与可续建 staging |
| export | scope | 返回此范围 jarvis.knowledge-bundle.v1 明文资料包；一致快照，包含墓碑 |
| restore_preview / restore | scope、bundle；restore 另带 token | 预览逐项动作、容量与冲突；恢复用水位 CAS，整包事务，新建/替换项暂停且无接入方许可 |
| cleanup_preview / cleanup | scope、cursor={goals,turns}；cleanup 另带 token | 每类 200 条，返回 counts、targets、next_cursor、has_more、excluded；执行核对预览并返回持久 receipt |
| cleanup_status | scope | 最近 30 条清理回执，state=pending/partial/completed；files 列出回复/产物队列，表示本批受管字段状态 |
| retry_cleanup_files | scope | 幂等处理待清理文件；返回 pending/modified_preserved/cleared/absent 数量，不扫描未知文件 |
| compile / claims / dismiss_claim | scope；compile/dismiss_claim 另带 id/revision | 原文片段候选；compile 核对来源修订、幂等；claims 返回最多 200 条当前范围记录；dismiss 清空候选正文 |
| accept_claim | scope/id/revision/item/fact_revision | item 沿用记忆保存字段；同事务核对源与候选修订、同域及接入方子集；只允许 kind=knowledge；返回 fact ID/修订 |

来源状态为 active ↔ paused → deleted；保存变更产生新 revision，deleted 不允许复活同一 ID。来源文本本身只是参考，可信等级固定 reference_unverified。检索条目 kind=source、id=源 ID、revision=源修订；evidence 包含 source_id/chunk_id/revision/start/end/line_start/line_end/trust。字符区间为 Python Unicode 字符的左闭右开区间，行号从 1 开始；浏览器查看原件按相同码点语义定位。身份/范围/许可先于候选装配，出站前按源修订重新检查。

`POST /api/knowledge-transfer` 是 restore_preview/restore 的专用大包入口，最多 40,000,000 字节；仍校验 Host/Origin/nonce，拒绝重复 JSON 字段、非有限数和非法 Unicode。普通 /api/knowledge 的 200,000 字节及核心消息 262,144 字节上限没有放宽。bundle 严格包含 format、scope、sources、tombstones、checksum；format 固定 jarvis.knowledge-bundle.v1；sources 每项为 id/revision/title/text/providers/paused，tombstones 仅 id/revision。checksum 是除自身外按 sdk.protocol.canonical 编码的 UTF-8 SHA-256，不能作为身份认证。运行结构校验归 modules/context_knowledge/transfer.py，不把大资料包塞进核心任务消息契约。

knowledge_schema 当前为 4；迁移、回滚限制、恢复决策及排除清理范围只在[本地闭环规则](knowledge-learning.md#knowledge-cycle-runtime)维护。FTS 是可丢弃重建的投影。修改/删除与源水位变化同事务提交；FTS 初始构建后最多追赶 3 次来源增量，仍不收敛返回 knowledge_changed，保留当前投影；向量也以当前修订批次和覆盖检查防止迟到旧值进入新空间。普通错误/中断不能生成假成功。未知字段、畸形 ID、过大原文、过期修订、越域/已删除源是必测负例，见[原件证据](delivery-validation.md#knowledge-library-evidence)和[恢复清理证据](delivery-validation.md#knowledge-transfer-evidence)。完整记忆同步、加密备份契约尚未因本接口而完成。

<a id="memory-continuity-contract"></a>
## 记忆连续性、联合范围与提取契约（1.0.0）

这是已实现的有界子集；运行语义与限制只在[连续性规则](knowledge-learning.md#memory-continuity-runtime)维护。核心 user_version=7、knowledge_schema=4、memory_schema=4。新旧进程须协调重载；回退代码须理解新增账本，禁止用旧数据库覆盖当前删除状态。

| 入口 | 动作与关键字段 | 约束 |
|---|---|---|
| POST /api/memory | history(scope/kind/id)、context_recall(scope/provider/enabled/query/selectors)；save 可带 applicability={valid_from,conditions} | kind=fact/source；条件限 channel/activity/language/audience；未知上下文不匹配。历史最多返回最近 100 版，完整包保存所有未遗忘历史 |
| POST /api/memory-domains | list(parent)、create(parent/kind/name/snapshot)、archive(id/revision/archived)；binding(chat_id)、bind(chat_id/scope/revision) | branch/task/world 独立域；最多 100 活动域；禁止嵌套；切换需空闲会话和 CAS |
| 同上 | source(scope/id/revision)、merge_preview(scope)、merge(scope/token/choices) | 历史原文必须是当前分支快照；合并每项明确 branch/parent，已删主条目拒绝，回执重复提交不再修改 |
| POST /api/chat/send · memory_capture | 返回本轮记忆请求保存状态 | 不改变请求原有字段；state 为 not_requested/pending/accepted/dismissed/withdrawn/excluded/unavailable，候选 ID 仅在存在时返回。候选未审阅前不会进入事实背景；回复装配保存 capture_candidate，发送期间重新检查仍为 pending，审阅变化使旧状态说明失效 |
| POST /api/memory · health | scope | 只读当前范围账本计数与关系、全库索引覆盖；返回 issues 与可选修复方向，不含原文；只能使用真实单一范围。修复仍调用既有显式后台构建接口 |
| 联合 scope | joint: 后接 2–4 个去重、明确选择的范围 ID，以逗号分隔 | 禁止嵌套联合范围。每个范围仍检查当前项目/域状态和 provider；不能作为事实、资料或迁移写入目标。会话联合范围必须包含其原始项目或 personal |
| POST /api/memory-domains | source_inherited(scope)、source_fork(scope/id/revision)、source_merge_preview(scope)、source_merge_detail(scope/id)、source_merge(scope/token/choices) | 只限活动项目分支；choices 每项为 parent/branch/combined，重叠或缺起点不能伪造 combined；原文最多 80,000 字节，批次最多 200 份，预览只返回摘要，原文按单份展开 |
| POST /api/memory-transfer | export/export_collection(scope)、preview(scope/bundle)、restore(scope/bundle/token)、origin(scope/id) | 40 MB 严格 JSON；所有冲突先预览，恢复整包事务，目的地许可不随旧包自动恢复 |
| POST /api/knowledge-extraction | start(scope/id/revision/provider/model/reasoning/request_id)、status(scope)、cancel(scope/request_id) | 一条后台提取通道；request_id 幂等，参数不同拒绝复用；每次最多一次模型请求；原文许可和修订在发送前、回调与提交时重验 |

`jarvis.memory-bundle.v1` 顶层为 format/sources/facts/candidates/claims/history/origins/checksum；sources 嵌入现有资料包。`jarvis.memory-collection.v2` 顶层为 format/root/domains/snapshots/bundles/source_branches/checksum；每条 source_branches 为 domain_id/source_id/parent_id/base_revision，必须对应组内分支与父来源，最多 200 条。仍能读取无该字段的 v1；新导出不丢弃依赖。checksum 使用 canonical UTF-8 SHA-256，仅检测损坏，不能认证对端。每组最多 100 域、101 个范围包、100,000 条快照引用；单包对象/历史/来源回执分别最多 10,000 条。精确字段与类型校验由 bundle.py/collection.py 执行，不导入代码、执行许可或活动任务。迁移不会隐式恢复会话绑定。

模型候选输出严格为 `{"claims":[{"key":"标题","quote":"唯一可定位的原文"}]}`，最多 24 条；每条 key 1–120 字符、quote 8–4,000 字符。它只是未核验候选，保持 pending。提取任务保存 queued/running/succeeded/failed/cancelled/unknown 和调用用量；模型原始输出不另行存入调用账。未知调用不能自动重试，重启只标记中断。此契约不保证模型理解否定、条件和专业事实正确，质量按[验收](delivery-validation.md#memory-continuity-evidence)判断。

<a id="gmail-contracts"></a>
## Gmail 契约与恢复状态（1.0.0）

`GET /api/mail` 返回连接状态、真实授权能力、任务/草稿/规则，不返回令牌或 client secret。`POST /api/mail` 严格校验 action：configure、authorize、cancel_authorization、disconnect、job、detail、cancel、resume、draft、review、approve、rule、remove_rule。接口复用 Host/Origin/nonce 与家庭主人门，家庭成员不可访问。

一般 job 只受理 check/list/read/analyze/reconcile；send/remote_draft/change/undo 必须 review 后以 review_id、request_id approve。票据十分钟有效，绑定账号 generation、草稿修订和准确内容；重复确认复用任务，更改草稿需重审。

READY → RUNNING → SUCCEEDED，或 WAITING_AUTH / WAITING_NETWORK / WAITING_SCOPE / WAITING / UNKNOWN / FAILED / CANCELLED。只有明确无远端效果的等待操作可接续；写入效果不明进入 UNKNOWN。重启不重放发送。明确 401/403 的拒绝不当成功，其余网络未知不重复。

重连核对原邮箱；断开改变 generation，晚到的刷新不能恢复旧凭据。回调检查 state/路径，再兑换 code、核对权限和账号；收到回调不等于保存成功。撤回只恢复原操作涉及的标签，后续已改动则冲突停止。

<a id="task-learning-records"></a>
## 任务负责、结果评价与经验的增量记录（proposed）

以下是现有 Task／Action／Artifact、GoalMandate 和 ImprovementPolicy 的关联记录草案。完整记录仍为 proposed；其中 OutcomeAssessment 已有[确定性运行子集](#outcome-observer-contract)，其他草案未因此成为运行 schema。不复制执行状态、权限或费用真相，任务状态机仍由 TaskRuntime 管理。

| 记录 | 最小内容 | 写入与引用约束 |
|---|---|---|
| TaskOwnership | work_ref（goal/task 的类型与 ID）、root_work_ref、task_id（受理执行前可空）、owner_bot_id、owner_epoch、revision、lease_ref、接管原因、前任引用 | 每个 work_ref 只有一个有效负责人；目标形成任务时关联原归属；子任务有自己的 work_ref 并引用原根工作。宿主通过 CAS 转交，旧任期不能新派发；租约过期不证明外部动作失败 |
| Delegation | parent_task_id、child_task_id、目标/完成标准修订、输入/产物引用、权限引用、预算预留、依赖、冲突资源 | 子任务复用原 Task，权限取交集，所有花费计入根预算；同一逻辑动作的幂等键不随重试改变 |
| OutcomeAssessment | task_id、goal_revision、artifact/receipt 引用及摘要、rubric_version、维度得分/缺失项、证据覆盖、硬门结果、评价者、时间、supersedes | 验收模块写入追加修订；模型意见与确定性检查分栏；旧评价不能覆盖新产物 |
| TaskEpisode | task/revision、实际方法/版本、结果与评价引用、纠正差异、失败模式、适用域、隐私/保留规则、状态与失效依赖 | 记忆模块保存经验，不授予权限；删除和纠正使派生检索失效 |
| ImprovementTrial | 问题引用、base/candidate 摘要、允许修改面、固定场景/评估器/环境、探测与成本回执、采用或拒绝理由、发布引用 | 复用改进单及发布事务；不能由候选修改自己的准入标准，经验采用不等于生产发布 |

跨模块沿用[持久性契约](#composition-durability-contract)的提交与 outbox 规则：任务完成后评价失败，可以显示“交付完成／评价待补”，不能回写成任务未执行，也不能重新执行已发生的动作。评价、记忆投影和通知消费分别去重，键包含任务、目标修订及产物版本；重复消费不重复记功。

记录中保存可核查的决策摘要、输入来源和工具效果，不要求收集模型隐藏思维链。个人数据使用引用、范围与失效关系，日志不写凭据。新增字段必须声明默认值、读取兼容与迁移版本；旧版本不理解新调度/所有权语义时，不接管新版在途任务。

<a id="modernization-integration-contracts"></a>
## 三职能、任务负责与成长模块的接入契约（proposed）

本节细化上文增量记录如何接到现有实现。以下端口名和新增记录是待实施接口，**不是当前可调用 API**。不向严格的 `jarvis.task.v1` 塞入未定义字段，不让旧读取器静默忽略所有权或权限语义；先新增版本化关联记录，再按[迁移规则](core-bootstrap.md#modernization-migration-switch)接入支持它们的运行器。

<a id="modernization-port-map"></a>
### 最小端口、数据写入者与故障返回

| 逻辑端口 | 输入 → 输出 | 唯一写入者与调用限制 |
|---|---|---|
| Direction.propose | 当前目标修订、获准上下文、能力目录 → 计划/取舍候选 | 仍由 Goal/Plans 验证并保存；端口本身不签发授权 |
| Engagement.advance | 任务引用、负责人任期、获准计划 → 子任务/动作提案或交流结果 | TaskRuntime/网关接纳；模型不能直接操作任务和动作表 |
| Reflection.observe | 事件水位、结果/评价引用 → 问题、经验或改进候选 | 各领域分别写 assessment、episode、incident、trial；不拥有所有领域数据 |
| Ownership.claim/transfer | 根工作、预期修订、旧任期、理由 → 新任期或 conflict | Task/Host 事务负责；不等同于调度器执行许可，不新增业务权限 |
| Evaluation.assess | 目标修订、产物摘要、回执、量表版本 → 评分/缺失/硬条件结果 | 宿主控制的评价领域追加记录；评价任务本身有预算、截止与取消 |
| Experience.propose/select | 结果/纠正引用 → 候选；当前条件 → 适用方法引用或无匹配 | Context/Knowledge 管候选、采用、版本和撤回；返回引用不授予动作资格 |
| Health.open/route | 原故障证据、对象和基线 → 合并事件/恢复建议 | Health 管故障，执行由原运行器承担；修复和改进共享发布互斥 |

端口统一携带 `request_id / correlation_ref / schema_version / expected_revision / deadline / authority_ref / budget_ref` 的适用子集；不存在的许可不自动生成。返回区分完成、拒绝、过期、冲突、不支持和未知；无新经验或无匹配是正常结果，不制造失败重试。已存在的 Goal、Task、Action、Package 状态枚举保持原语义，评价待补不成为新的 Task 执行状态。

<a id="modernization-durable-projections"></a>
### 关联记录、事务与重复消费

| 接入点 | 具体持久要求 | 失败时的结果 |
|---|---|---|
| 创建工作归属 | 根工作已有 goal 就用 goal 的 work_ref，否则用 task；子任务的 work_ref 是自身 task，并引用原 root_work_ref。绑定 task 时原子核对 principal/scope 与唯一关系；按目标修订保留历史绑定 | 不能因补元数据重复生成工作或覆盖旧绑定；旧未迁移任务明确为 legacy |
| 新动作准入 | 在实际派发检查点核对负责人任期、任务修订、当前授权和资源许可；原 action 幂等键仍由原任务步骤确定 | 过期任期拒绝新派发；迟到效果仍可成为待核对事实，不能丢回执 |
| 结果到评价 | 任务终态事务留下轻量事件；消费以 task/goal_revision/artifact_digest/rubric_version 去重 | 事件重复不重复扣费记功；评价中断可重试评价，不能重做业务动作 |
| 评价到经验 | episode 指向评价和原件；一次修订只追加真实差异；选择记录区分召回、采用和收益 | 旧产物评价不能替新版背书；撤回传播至缓存、候选和在途上下文 |
| 经验到改进 | trial 引用问题、基线及候选，采用时再次比较基线修订 | 自愈已改版本时旧 trial 失效/重验，不覆盖刚恢复的版本 |

现有 `Database.event(tx, ...)` 在业务事务内写事件，可作为接入起点；它尚不等于完整的可靠消费者。实施时补消费者水位、幂等键、失败次数与有界补偿；同一数据库内将投影写入与消费水位提交在一个事务，跨库用原 outbox/幂等消费协议，不能声称跨库天然原子。事件负载只保存引用和必要元数据，敏感原文仍按用途读取。

需要付费模型评价或归纳时，调用前先持久化消费尝试及稳定请求键，关联原模型调用与预算记录；崩溃后复用已取得的结果。请求结果未知时保持未知并核对，不能因为水位没提交就再次付费调用。事务内去重只能保证本地记录，不自动保证外部请求恰好一次；模型回执、用量及不确定账单必须分别记录。

消费者按事件/固定小批次恢复，限制队列、耗时与资源；没有新结果就不启动总结模型。无法消费时暴露积压和最老事件，而非静默漏掉；关键审计持久化失败按控制策略处理，可选成长积压不把整个执行系统卡住。

<a id="closure-handoff-records"></a>
## 闭环交接所需的增量关联（proposed）

以下细化现有对象，不要求每行新增一张表，更不建立新的调度或评分真相。实施时冻结机器 schema、单一写入者、幂等键及迁移夹具；这些字段目前不是已发布 API。

| 原对象／关联 | 需要补足的语义 | 写入与失效规则 |
|---|---|---|
| GoalMandate 的验收条目 | criterion_id、goal_revision、必需性、验证器/量表引用、证据要求、完成与未知处理 | Goal 领域冻结；用户修订形成新版本，不能由执行者事后放宽 |
| GoalProgressView 的结案对账 | 条目→task/action/artifact/assessment 引用、满足/未满足/未知/失效及原因、业务补救引用 | 从原事实派生；不覆盖 Task 状态，不能因下游通知成功而修改质量结论 |
| WaitBinding（等待关联） | work/task/goal 修订、reason、dependency/question_ref、source_watermark、resume_condition、consumer_ref、deadline、最近进展、预算/预留引用、取消代次 | 由对应业务域登记，原调度消费；状态和唤醒分别幂等，重复事件不重复派发 |
| 原成果/通知引用 | 当前产物摘要、获准受众与入口、可访问性、投递回执、未决项摘要、反馈与返工修订 | 交付和用户反馈分开；通知丢失不重做业务，旧入口收到纠正须核对版本 |
| Tool 效果契约／补救关联 | 效果查询能力、幂等/取消/补偿支持及限制、原 action_ref、补救 task/action_ref、实际回执 | 声明不等于能力已验；补偿仍走当前准入，不修改原动作的已发生事实 |
| TaskEpisode／OutcomeAssessment | 观察截至时间、证据成熟程度、后续反馈、实际采用经验版本及使用步骤、反证与 supersedes 引用 | 迟到证据追加修订；经验相关不等于因果责任，先做局部核对 |
| ImprovementTrial／发布引用 | 滚动基线、固定参照基线、实际行为组合、累计变化、观测窗与退出条件 | 仍由原评估/发布领域维护；不能每次改进都清零历史退化和支出 |

WaitBinding 的注册、任务等待交接与源水位须通过同库事务或原跨域 outbox/对账保证可恢复；外部来源先读当前状态再登记仍可能有竞态，需要可恢复游标、重读或有界核对。无法保证的来源明确标记覆盖限制，不以文档字段齐全宣称可靠通知已实现。

所有回接都重新核对工作修订、取消代次、当前权限和已发生效果；领域之间传递事实引用与请求，不互相写完成状态。关于等待、结案和业务补救的完整行为归[任务闭环](tasks-agents.md#goal-outcome-closure)。

<a id="real-work-handoff-contracts"></a>
### 真实工作诊断对应的最小契约增量（proposed）

本节细化上表和[已有 TaskOwnership](#task-learning-records)，是待冻结的字段语义，不是已发布 API/schema。继续由原领域维护唯一事实；不新增一个同时管理授权、队列和评分的总控制器。

| 现有对象／接口 | 最小增量 | 单一写入者、幂等与失效 |
|---|---|---|
| GoalMandate／既有授权引用 | 委托版本、目标/作用域、允许的行为类别、总预算/期限、默认值依据、必要升级条件 | Goal 记录委托，授权域裁决实际许可；撤回/改版不得被旧委托快照覆盖 |
| 目标批准和 Scheduling 入队交接 | 明确区分仅批准与“批准并执行”；持久执行意图引用 goal_revision、task_id、request_id、取消代次 | Goal 与原调度同库事务，或具备幂等消费及恢复对账的交接；队列满保留等待原因，不能丢意图或重复分配许可 |
| GoalMandate 条目／OutcomeAssessment | 必需要求到检查器及证据的映射；缺项、矛盾、未评、已满足分别记录；冻结评价器与覆盖检查版本 | Goal 冻结需求；Evaluation 追加评估。执行者声明 `complete` 只能是待核对输入，不单独授予根目标完成资格 |
| 计划中的 question | 必需性、默认值、依赖的条件/步骤、回答版本及等待引用 | Goal 管问题修订，业务域登记 WaitBinding；回答只唤醒仍有效的依赖，不重新启动全部任务 |
| 目标修订／关联返工 | root_work_ref、base_revision、新修订、变更原因、影响集合、复用产物引用、repair_task_ref | Goal 写关联，Ledger 写 Task；幂等键至少绑定根工作、新修订与修复请求，原执行事实不改写 |
| TaskOwnership／Delegation | 沿用 work_ref、root_work_ref、owner_bot、owner_epoch、revision、lease_until；补齐派发时的对应引用 | 原所有权领域 CAS 转交；动作边界核对当前任期。租约过期不自动证明旧动作已停止；子任务消耗仍归根预算 |
| 经验候选／TaskEpisode | 区分执行观察、已验证业务结论和用户偏好；绑定原条件、评价版本、反例、实际采用步骤 | Context 管候选/方法版本；评价提供可失效证据，不直接把“成功”文字写成事实；迟到纠正沿原引用传播 |

“批准并执行”建议作为显式新操作或有版本的选项，不能默默改变原 `approve` 的调用约定。事务边界内冻结已接受的修订、验收与执行意图；事务外唤醒只是优化，丢失唤醒也可从持久记录恢复。入队后到实际执行前仍检查当前授权、取消、来源和资源。

旧记录不补造要求覆盖或负责人历史。先以扩展关联记录接入，老协议可继续读旧任务；不理解新所有权和修订的运行版本不得接管已采用新协议的任务。机器 schema、错误码和迁移号须在实际实现时核对当前代码后冻结，再用[对应验收](delivery-validation.md#real-work-upgrade-validation)验证，不能用此表替代代码兼容性测试。

<a id="outcome-observer-contract"></a>
## 确定性结果评价的运行子集（1.0.0）

[运行 schema](../contracts/schemas/outcome-assessment.v1.json) 为 `jarvis.outcome-assessment.v1`，通过原严格验证器注册；不向 `jarvis.task.v1` 塞入新字段。[评价模块](../modules/evaluation/outcomes.py) 的检查器版本固定为 `deterministic-1.0.0`。这是上文 OutcomeAssessment 的首个子集，完整多维 Q、GoalMandate 和学习记录仍按各自设计验收。

| 内容 | 当前语义 |
|---|---|
| 绑定 | task_id、task_revision、goal_id/goal_revision、fingerprint、evaluator；指纹覆盖原任务、动作参数/结果、当前目标及实际检查结果 |
| 核对条目 | 原执行是否成功、每步是否有确认回执、文本统计是否对应输入、受管原始文件是否与回执及原内容一致、计算回执完整性、引用依据是否有效 |
| 未知项 | 自然语言目标质量、收件人接受/后续使用效果、缺少语义验证器的工具结果明确 unknown；不因为工具返回成功就补齐 |
| 结果 | PARTIAL 表示有限检查有证据且未发现失败；ISSUES 表示有失败项；INVALIDATED 表示目标/来源/内容撤回使依据失效；三者都不能代表完整目标已验收 |
| 评分 | 该版本 score 必须为 null；coverage 是已知/通过/总条目数，不是质量分，不重新归一化缺失维度 |
| 历史 | 追加评价记录、唯一 current 指针、supersedes；相同当前指纹不重复写入。文件恢复原样也追加恢复记录，不把旧评价重新当作一次新验证 |
| 数据最小化 | 评价只保存引用、摘要、固定原因码和结论；不另存原提示词、文件正文、用户记忆或异常原文 |

[增量存储](../adapters/storage/outcome_schema.py) 在原 core.sqlite3 中独立登记 `outcome_schema=1`，增加 assessments/current/failures/consumers 四张表；不改 core user_version，不重写原身份、任务、动作、授权或事实。两个消费者在 SQLite 写事务内串行竞争同一水位；检查结果、当前指针与消费进度同事务提交。检查中断全部回滚；检查器异常则回滚该次局部写入，保存失败并推进水位，让后续任务继续。

失败尝试持久化，冷却 5×尝试次数秒，最多三次；每轮至多接两项到期重试。手动重试仅清除该任务评价失败计数。关闭观察器不推进水位；重新启用可补评。没有付费模型调用，不运行候选代码，不补写/重建产物，不触碰 UNKNOWN 动作。

每轮最多消费 32 条事件，调用参数最大 64；轮内达到约 50 毫秒后停止接下一项，**不是强实时超时保证**。每个原始文件读取上限 256 KiB，每任务原始文件累计读取预算 2 MiB；路径继续使用原防越界/重解析点检查，回执相对路径必须匹配原 task/action/name。计算回执沿用既有有界读取。SQLite 争用、磁盘或原来源检查仍可能造成等待。

原会话与单目标查看会针对指定任务重新核对。工作状态每次只重新核对最近列表中的四个终态任务，其余历史返回 STALE，提示重新核对；不会把未检查的历史评价冒充当前有效结论。展示外壳的 PENDING、UNAVAILABLE、DISABLED、STALE 不是完整评价记录，不套用已完成评价的 schema。文件访问结论只说明检查时的受管原始文件，不保证会话副本、外部接收或稍后文件状态。

现有 `/api/operations` 增量动作：`outcome_configure(enabled)`、`outcome_retry(id)`、`outcome_history(id)`；复用原本机权限及请求校验。历史最多返回 20 条，提供 current_id，但历史记录自身不授予权限。`assistant.projection`、目标 detail、task_detail 和 work_status 使用同一服务。观察器 schema、检查或来源暂不可用时显式返回不可用/未知，不把旧评价静默当作本次新检查。

<a id="completion-loop-contract"></a>
## 文本验收、反馈与采用的实际交接契约（1.0.0）

[Completion](../modules/task_resource/completion.py) 与 [Host 组合](../host/completion.py)复用原 task/action/goal；[增量存储](../adapters/storage/completion_schema.py)登记 `completion_schema=1`，增加 task_acceptance、completion_feedback、task_completion、experience_methods、experience_sources、experience_uses。评价、结案和方法记录在同库事务内对账；身份、许可、执行事实和 core user_version 不回滚、不另建真相来源。

| 记录／端口 | 实际语义 |
|---|---|
| task_acceptance | 原 task_id、revision、coverage 与最多 16 条 criterion；每条有 id、step_id、check、expected。检查器只支持 text_statistics、纯文本工具的 text_equals/text_contains，不执行任意表达式或模型生成代码 |
| 保存条件 | 仅 READY、无动作且未取消时接受当前 revision；目标 approve 可携带 acceptance，同事务准入。重复批准不能换条件，已有执行后不能事后改答案 |
| task_completion | 绑定当前评价 ID、验收版本、任务修订和检查结果的 fingerprint；WAITING/UNSPECIFIED/WAITING_EVIDENCE/UNAVAILABLE 不算成功；SATISFIED 只满足配方范围，VERIFIED 满足事先声明的完整条件，ACCEPTED 另有当前证据上的用户认可 |
| 条件分数 | condition_score 是已声明条目全部有已知结果时的通过百分比，明确 `declared_conditions_only`；与总质量 Q 和用户满意度分开，未知不计作零分 |
| completion_feedback | task/request 幂等键、证据 fingerprint、accept/reject/withdraw、说明与时间。相同键不同内容冲突；accept 不能覆盖失败检查；withdraw 只撤回纠正，不替代验收、不自动解除方法暂停 |
| experience_uses | 每个实际采用关联 method_id/revision、source_task/source_fingerprint；与新任务入账和调度申请同事务保存。重复请求返回原任务，不增加业务效果 |
| 当前依据检查 | 动作执行前、结果查看与复核时核对原来源、产物、方法版本、期限和许可；采用任务缺少必要关联时关闭该条执行路径，其他任务继续 |

`/api/operations` 新增 completion_detail、acceptance_set、completion_feedback、experience_reuse、experience_review，沿用原本机访问与请求校验。历史反馈最多返回 20 条；规则、反馈长度和字段均有界。方法投影的 review_required 标记暂停或到期，复核成功续期并增加修订，不能让旧采用越过原版本绑定。任意模型文本不能自行调用这些端口获得新权限。条件性方法的范围及重新准入规则唯一归[知识运行节](knowledge-learning.md#conditional-method-runtime)。

结果评价暂不可用时保留未完成核对状态；不会让缺少证据的任务通过，也不会因一次观察器停用把所有已验证方法永久判坏。必需采用依据缺失时，相应任务等待；普通任务不依赖该方法表。原自然语言目标未提供可验证条件时继续显示未约定，不据此生成“整体完成”结论。

已有 TaskRunner 每轮最多对账两个到期的终态任务，单条间隔至少 10 秒；只覆盖有验收记录的任务。这个有界扫描补齐完成回调与重启之间的空隙，不新建系统计划任务。缺失或不可用仍有显式出口；通用跨域通知、远端事件订阅和所有任务类型的可靠唤醒尚未签收。

<a id="workflow-handoff-runtime-contract"></a>
## 工作交接 1.1.0 的实际契约

本节为 implemented 的限定子集；上面的通用交接契约仍为 proposed。源码见[目标准入](../host/goals.py)、[原调度](../modules/task_resource/scheduling.py)、[覆盖核对](../modules/task_resource/coverage.py)与[结案](../modules/task_resource/completion.py)。

| 契约 | 实际字段／结果 | 原子性与失效 |
|---|---|---|
| `POST /api/goals` 新 action `approve_and_run` | `id`、原 `revision`、可选 `acceptance`；返回原 `task_id`、`existing` 与 `dispatch.state/reason` | 与 Task/许可/目标关联同事务；`approve` 不变。幂等重试不重新派发，改变原验收拒绝 |
| 原 `task_dispatch.requested` | 0：没有待执行意图；1：就绪队列；2：已持久受理、等待队列容量 | 原 Runner 通过原 enqueue 晋升 2→1；取消、终态和过期退出等待，UNKNOWN 不重放；真正执行前仍检查当前授权等原控制 |
| `acceptance` 扩展 | 原 `coverage/criteria` 保留；可选 `requirements` 为 1—16 项，每项 `id/text/kind/criterion_ids` | 唯一 ID、文本 1—1000 字、引用必须存在；可空映射表示缺证据；执行前冻结。未提供 requirements 的旧调用仍可执行，但不能单靠 complete 声明完整核验 |
| `kind` 与验证器 | `literal` 仅接受 text_equals；`statistics` 仅接受 text_statistics；`semantic` 当前没有支持的验证器 | 不匹配或缺映射为 unknown，不能用 text_contains 充当语义覆盖。类型由显式要求提供，本版不自动判断该类型是否完整反映自然语言目标 |
| `requirement_coverage` | 核对版本、逐项状态与原因、完整性、`scope=explicitly_declared_requirements`、`semantic_goal_verified=false` | 原执行、产物与来源检查不合格或反馈拒绝时不得宣称完整；condition_score 仍只统计原检查项，不计为总体 Q |
| schema 2 与核对历史 | 既有记录原位保留，新增 completion_history；同一旧结论按摘要去重 | 新核对覆盖当前投影前保存旧体；当前投影最多展示最近 8 条历史，未删其余历史；不改变旧动作、反馈或原验收规则 |

`dispatch.state=NOT_PENDING` 表示原执行意图当前不在队列，可能已结束；不能解释成可以自动重试。等待容量时仍遵守原任务期限，不自动延长许可或预算。达到意图受理上限时抛 task_capacity，整个新受理事务回滚；普通排队的原限制保持。

VERIFIED 现在只用于明确要求在支持范围内全部核对通过；SATISFIED 表示检查已通过但覆盖未证实。ACCEPTED 只记录当前证据下的认可，不把未支持的语义要求改为已证实。历史 1.0.0 的结果保留原版本，复核产生新结论，不能将升级后标准反写为当时已经采用。

<a id="workflow-rework-contract"></a>
## 工作接续 1.2.0 的实际契约

本节限定 implemented 的默认责任投影及纯文本关联返工，不等同于完整 TaskOwnership/Delegation 契约。[实现](core-bootstrap.md#workflow-rework-runtime) · [证据](delivery-validation.md#workflow-rework-evidence)。所有操作仍使用原 `/api/goals` 会话鉴权和字段白名单。

| 操作／投影 | 实际字段与边界 | 原子性、失效与幂等 |
|---|---|---|
| `rework` | `id/revision/work_revision/request_id/kind/note/goal/start_step`；kind 为 correction 或 new_requirement；完整目标 1—4000 字，原因 1—1000 字，request_id 8—80 字母数字/下划线/连字符；start_step 从 1 开始 | 仅当前成功本地 plugin 串行链；源版本/根修订比较；一次事务写新 Goal、上下文引用、版本关系、纠错反馈和当前指针。相同 request_id/载荷只返回原 Goal，不新增许可、Task 或模型调用；异载荷冲突 |
| 新版批准与执行 | 继续使用 approve / approve_and_run、原 revision 及可选 acceptance；新步骤从 step-1 重编号 | 不复制旧验收为新目标的完整证明。每版分别申请有限许可；旧许可不转移，新计划未批准不执行 |
| `review_rework_source` | `id/revision/work_revision/note`；仅当前未受理 REVIEW 草稿，说明前段仍适用的理由 | 来源完整且祖先有效才更新来源摘要；提升 Goal 与工作修订，留旧/新摘要和理由事件；原负反馈保留。已受理、取消或损坏/撤回来源拒绝 |
| `cancel_work` | `id/work_revision`；任何关联版本入口均可定位根工作 | 根取消与当前未完成任务取消/撤权同事务；同一次请求幂等；已完成 Task 保留 SUCCEEDED，根工作禁止新接续 |
| `work` | `schema=jarvis.work.v1`、root_goal/current_goal、assistant_id、owner_bot_id=default、revision、cancelled、registration、versions、spent_cost_units、remaining_followups | ownership_mode=default_projection；没有 owner_epoch/lease/接管。cumulative_budget_enforced=false；成本单位不能当作 token 或货币 |
| 扩展表 | meta.work_schema=1；work_owners 保存单一当前指针；work_revisions 保存序号、父引用、来源摘要和请求幂等信息 | 增量建表；普通启动不补写旧责任。旧工作首次接续 registration=followup_adoption，新受理为 admission；最多原版加 3 个后续版 |

纯文本限定为原计划全部 plugin 能力、首步 input、之后 previous、原 Task SUCCEEDED 且动作 CONFIRMED。复用前段还要求当前工具绑定匹配。检查原背景、来源会话的当前知识域、所有计算回执及最终文件摘要，将原请求/计划/任务/动作/最新反馈摘要固定；根或任一祖先变化会阻止继续。复用文本仍受原 12,000 字上限。原始链含 MCP、UNKNOWN、并行或重新读取 input 的分支时拒绝；不通过改写旧 Task 假装支持。

`work_conflict` 表示版本/当前指针/取消冲突；`work_limit` 表示接续次数上限；`rework_invalid` 表示输入或固定前段约束错误；`rework_unsupported` 表示超出纯文本成功串行子集；`rework_source_changed` 表示来源、反馈、权限或回执失效。效果边界发生变化后保留原 UNKNOWN 对账语义，不自动重放；评价器将失效来源反映到新版评价，但不会因为“存在新版”就否定原版本在原标准下的结果。

<a id="workflow-budget-contract"></a>
## 工作额度 1.3.0 的实际契约

本节补齐 [1.2.0 关联工作](#workflow-rework-contract)的工具动作共享上限，仍不是完整 Delegation 的全部费用预算。[实现与使用](core-bootstrap.md#workflow-budget-runtime) · [验收](delivery-validation.md#workflow-budget-evidence)。

| 契约 | 字段／语义 | 原子性和边界 |
|---|---|---|
| 初版 approve / approve_and_run | 可选整数 budget_limit，1—1000；未给出默认本版 max_cost_units×4，含最终保存 | 仅新根首次受理可设置；与原 Task/grant/验收/Work/预留同事务。初版总额小于所需预留时全回滚；后续版不得用此参数偷偷调额 |
| 重复批准 | 保留原 id/revision 与可选验收比较；给定 budget_limit 时比较本次受理保存的 admission_limit | 后来明确调过总额，不改变原批准回执；同一旧批准不重复预留或扣费 |
| set_work_budget | id、预算 revision（初次为0）、request_id、limit_units、note；ID 8—80 字母数字/下划线/连字符，原因1—1000字 | 预算修订 CAS、请求幂等；低于已用+预留拒绝；改变相同请求载荷冲突。成功只改约束和审计，不变 Task/grant/队列，不解除取消 |
| work.budget | scope=linked_task_action_units、enforced、limit_units、revision、spent_units、reserved_units、committed_units、available_units、unresolved_tasks、integrity | 累计消费来自原 tasks.spent。未接入的旧工作 enforced=false、limit/available=null；不能把空值解释成无限许可 |
| work_schema=2 | 增量 work_budgets、work_allocations、work_budget_changes；allocation 保存 Task、根工作、units、admission_limit | 不改身份/Task/回执，不回填旧总额。旧工作正式设置预算时回填额度引用，已有消费计入；关键预留缺失时拒绝派发，普通调额不得重建缺失证据 |
| 派发与效果边界 | Ledger.dispatch 在原扣费事务检查占用/总额和该 Task 预留；Core checkpoint 在已扣费后再次核对 | 原 grant、停止、取消、当前版本及来源检查全部保留。效果不确定仍按 UNKNOWN 对账，不能以剩余额度为理由重试 |

预留释放规则：Task 非终态，或仍有 UNKNOWN/DISPATCHING 动作时，剩余预留为 max(0, 分配额度−原已用)；只有 SUCCEEDED/FAILED/CANCELLED 且不存在这两类动作时，剩余预留才为0。已用不退款、不因取消归零。原工作最多 3 次关联接续的限制不变，额度增加不能突破它。

work_budget_invalid 表示值域或关键额度引用错误；work_budget_required 表示旧工作新增返工前需要正式接入；work_budget_conflict 表示预算修订或幂等载荷冲突；work_budget_committed 表示尝试低于已经占用的总额；work_budget_exhausted 表示本次受理/派发超出共享上限。后两者不自动扩容。工作根取消仍使用 work_conflict。

升级与降级分别验证：本版 v1→v2 增量升级和旧已受理任务接续有临时数据证据；没有在生产迁移或演练旧二进制降级。不能删除预算表后继续在途工作来规避约束，也不能假定旧代码能理解新预留。

<a id="workflow-closure-contract"></a>
## 工作闭环 1.4.0 的实际契约

[运行入口](core-bootstrap.md#workflow-closure-runtime)限定纯文本串行任务，不改变 1.2/1.3 的来源、接续次数、预留和授权约束。

| 接口／投影 | 字段 | 一致性与失败语义 |
|---|---|---|
| analyze_rework | POST /api/goals：id、revision、work_revision、goal、proposal；proposal 是修改后的完整计划 | 只读分析，不建 Task、许可或版本；源任务须成功且回执可验证，候选非空无未决问题且仅 plugin 串行 |
| 分析结果 | start_step、reused_steps、rerun_steps、reasons、planned_cost_units、analysis_digest；semantic_impact_verified=false、ancestor_prefix_reused | 成本只计候选后段工具数加保存；目标文字/原始输入变化 start=1，其余从首个不同步骤或绑定开始 |
| rework_auto | 在分析输入上加 request_id、kind、note、analysis_digest，使用同 action API | 在原 RunLock、上下文锁和数据库事务内重新分析；摘要不相等拒绝。成功生成完整候选的后段，固定复用输入；纠错反馈与版本/事件一起提交 |
| work.impact_applied 事件 | 新旧 Goal ID、完整候选与目标的规范化摘要、分析结果 | 与草稿同事务，不覆盖旧计划；不复制计划或目标正文，避免新增绕过原清理路径的文本副本，不作为新权限 |
| detail.work_closure | root_goal、current_goal/current_task、state/complete、reasons、completion_state、condition_score、score_scope、requirement_coverage、assessment_fingerprint、spent/reserved_cost_units、quality_score=null | 原 Completion 和 WorkBudgets 的派生读模型。历史入口查看当前版；状态只有 COMPLETE、NEEDS_REVIEW、IN_PROGRESS、NEEDS_EVIDENCE、STOPPED |
| 聊天关联 | linked_goals.id 为当前版，root_goal 保存原关联；历史卡片增加同一 work_closure | 修改/取消/接续建议仍须原确认路径；校验原会话归属、当前版及修订，不能用旧根 ID 或另一个会话绕过 |

结构比较使用步骤所有字段及能力 active/revision；说明 summary 的变化不会产生新执行。追加步骤时，为兼容原可复用前段协议，至少重做原最后一步；删除尾段则至少重做新最后一步并重新交付。此规则有意保守，不声称全局最小语义影响集合。自然语言目标即使只改一个标点也从头开始。

多轮返工沿当前版本的完整计划分析，scope=structural_current_plan_only。若任一祖先曾复用前段，改变目标或输入返回 rework_full_plan_required，不能把当前后段的第一步冒充整条原始流程第一步。目标和输入不变时仍可分析局部步骤变化，且继续核对全部原祖先依据。此时界面解释保留范围；需要改变早期输入的工作应重新制定完整的受审计划。

rework_no_change：未发现执行相关变化，不创建空返工；rework_analysis_changed：候选/来源/工具/反馈已不匹配分析，重新核对。已有 work_conflict、work_limit、rework_source_changed、rework_unsupported、plan_capability 等继续生效。重试同一已提交请求返回原草稿；不能改变载荷，也不会重新授权或执行。

聊天记忆域或祖先来源失效时，不向模型返回目标正文、已确认输出、记忆依赖或详细结案内容。完成仍只指显式列出的支持范围；semantic_goal_verified 保持 false。终态评分、反馈、知识方法和执行事实使用各自原存储，投影不能把成功执行改写成业务认可。

<a id="workflow-domain-contract"></a>
## 领域核验 1.5.0 的实际契约

沿用已有 acceptance.criteria：新增 check=quote_selection，expected 是**审阅输入 UTF-8 原字节的 SHA-256 小写十六进制**，不是正确答案；同样内容换空白后也需重新确认摘要。必须在首次 action 前配置，受原 CAS、许可、工作预算和原子受理约束。输入从冻结 Task 的首步 arguments.text 取得，独立重算，不读取模型的自评分或中间候选名单。

| 对象 | 唯一字段与界限 | 判定 |
|---|---|---|
| 输入 | schema=jarvis.quote-input.v1；currency 为3位大写标识；max_price_minor 为0..10^12整数；max_delivery_days 为0..3650整数；offers 为1..100项 | 输入不超过12000字符；所有对象拒绝未知字段/重复键；布尔、浮点、非有限数不能作为整数；不进行汇率或货币单位换算 |
| 每项报价 | id、price_minor、delivery_days、source；金额/天数沿用以上界限；id 1..80字符且唯一；source 1..300字符 | id/source 不得含控制字符或首尾空白；source 仅为用户提供资料的引用，不联网验证真实性 |
| 输出文本 | JSON：schema=jarvis.quote-result.v1、eligible_ids、selected_id、selected_source；不超过20000字符；拒绝多余字段与重复键 | eligible_ids 为不重复的完整合格集合，不要求排序；selected_id/source 是匹配的字符串或均为 null |
| 合格与选择 | 金额≤预算且天数≤交期；从全部合格项中取最低价 | 并列最低价任选一项；无合格项必须返回空集合及两个 null；与输入来源逐字匹配，不自行补造来源 |
| 执行链 | 首步直接使用冻结 text；后续仅 plugin 串行引用前一步，最终 artifact.write 引用被核验的最后一个 plugin | 不支持 MCP/外部调用或未核验的末尾改写，不额外执行、联网或获取权限 |
| 要求映射 | kind=quote_selection；text 固定为“按冻结报价输入核对预算、交期、完整合格集合、最低价和所选来源引用” | 自由文字不能借此获得语义核对；semantic_goal_verified=false；全部目标要求是否列全仍需独立解决 |

输入样例与正确/错误输出见[固定样本](../tests/fixtures/quote_acceptance_v1.json)；执行器只返回标识与引用，不暗示摘要中的其他叙述已被验证。未知输入条件拒绝受理；错误输出为 failed；冻结来源或链变化为 invalid。source_digest、verifier=quote-selection-1 和 reason 随检查结果进入原 Completion 指纹。原因包括 quote_report_invalid、quote_source_changed、quote_eligible_mismatch、quote_selection_mismatch、quote_source_mismatch；通过区分 quote_verified / quote_no_eligible。

整体结案仍同时依赖原动作事实、产物一致性、来源、反馈和覆盖检查。领域检查通过但产物被改动会沿原观察器成为 NEEDS_CORRECTION；来源授权/上下文失效遵循原 INVALIDATED 规则，不能由领域通过抵消。100% 只表示所列检查通过率，不是业务质量 Q 或全功能能力分数。

<a id="workflow-requirements-contract"></a>
## 目标要求 1.6.0 的实际契约

POST /api/goals新增只读 `review_quote_request`：传id、revision；版本不符拒绝。只接受已有无待决问题的纯文本串行计划。返回逐句审阅与建议acceptance，不批准、不排队、不改变Goal版本。其source_scope=stored_goal_only，范围为当前Goal.request.goal；不宣称匹配聊天全文、附件或先前各轮原话。

| 项目 | 约定 | 失败与限制 |
|---|---|---|
| 目标与分句 | 完整目标1..2000字符；最多32个非空分句；按中英文逗号/分号、中文句号及换行分句；保留start/end/text | start/end为Unicode码点位置，end不含；仅忽略分隔符和首尾空白。全句匹配，不只搜索关键词；过长目标拒绝，不能以截断摘要冒充原文 |
| 预算 | 预算/总预算 + 不超过、不高于、最多、至多、上限(为)、为 + 可选人民币 + 数字 + 元/万元；可前置请 | 数字1..12位、最多2位小数，精确Decimal转人民币分；元×100、万元×1000000；需与CNY输入的max_price_minor一致；无汇率换算 |
| 交期 | 交期/交货期 + 不超过、最多、至多 + 整数天；或“(在)N天内交货/交付/送达”；可前置请 | 整数1..4位；对照max_delivery_days；不解释工作日、实际日期、起算时点或真实履约 |
| 选择及附加明确表达 | 支持“选择最低价报价/方案”“选出最低价方案”“选择符合条件的最低价报价”“在合格报价中选择最低价”；附加“保留/附上来源引用”“保存结果/报告”“比较(以下)报价”“谢谢” | 必须明确识别预算、交期、选择三项；输出仍由1.5独立核验，保存仅指原本机产物流程 |
| issues | missing_*、uncovered_text是待覆盖；duplicate_*、budget_mismatch、delivery_mismatch、currency_mismatch阻止受理 | 重复值相同也不自动合并；保留原文等待核对，不推断优先级 |
| 未支持控制词 | 未覆盖片段出现不要、禁止、不得、不能、不允许、不选、未经、除非、或者、否则、忽略、例外、如果、只有、并非 | unsupported_control阻止受理；词表未出现不等于已理解，只能保持未覆盖并受部分范围约束 |
| 审阅绑定 | version=quote-request-1；binding=digest({parser:version,goal:原文UTF-8 SHA256,input:输入UTF-8 SHA256}) | digest沿SDK规范JSON摘要；Goal/输入/解析版本改变均不得复用。revision还独立保护受理时版本 |

新增criteria.check=quote_request，expected=binding；step_id必须为实际保存结果的末个plugin。requirements.kind=quote_request，text固定为“对照当前目标原文中受支持的报价条件及冻结输入核验结果，未覆盖内容须另行处理”。来源与执行链继续符合[1.5契约](#workflow-domain-contract)，configure和评价重新解析，不信任客户端的ready/coverage声明。超过Task目标字段长度的Goal在首次受理和后设验收入口均拒绝此模式。

正确结果且语法范围全部覆盖时检查可passed；正确结果但仍有未覆盖要求为unknown，整体WAITING_EVIDENCE，不能接受为已核验结果；错误结果仍优先failed/NEEDS_CORRECTION；依据或解析版本改变为invalid/INVALIDATED。检查证据记录解析/核验版本、摘要、范围和未解决数量，不重复写原文片段；审阅响应中的原文仅供显示。semantic_goal_verified始终false，完整业务Q仍不产生。 解析规则发生语义变化时必须更新解析版本并重新取证；不得沿用旧版本标识绕过绑定失效。多个工具步骤若仍有未核验中间结果，整体结案还受原观察器的待证据条件约束，ready仅表示目标片段与输入对照就绪。

<a id="workflow-sources-contract"></a>
## 聊天来源 1.7.0 的实际契约

POST /api/goals新增只读 `review_quote_sources`，传id、revision；要求完整、无待决问题的纯文本串行计划。返回当前Goal逐句结果、sources、issues、source_scope和建议acceptance。审阅不创建Task、许可或模型调用；原文仅在审阅响应显示，新的验收条件、评价与审计不复制原文正文。

| 项目 | 规则 | 未通过处理 |
|---|---|---|
| 来源链 | 根Goal的chat_goals关联；已有Work祖先最多4代；各Goal已接受聊天amend最多3次 | 循环、缺祖先、聊天来源Goal缺关联、request摘要不符、来源行动被清除或聊天归档/移除/分域变化均拒绝；不可降格成直接Goal |
| 版本历史 | 保留最初聊天原话及已接受修订原话；绑定每代Goal完整request、generation及原上下文历史摘要 | revisions_unreviewed保留待核验，不解释覆盖关系或最后一句优先；返工不丢弃初始要求 |
| 读取范围 | 最多16份来源文本、合计32000字符；每段指令沿1.6的2000字符/32句上限 | 超界不截断；指令超界标记阻止受理，整体来源窗口超界直接拒绝 |
| 用户原话与会话要求 | 分别解析；受支持条件与输入核对，并对照Goal的标准化条件；未覆盖片段保留原文位置 | 预算/交期/币种冲突、重复和未支持控制词阻止受理；Goal漏项或未知附加要求保持未核验 |
| 附件 | kind=reference；全文逐字等于本次input_text时status=input_identical，否则unreviewed | 引用资料不作为执行授权；一致不证明外部事实；未核对附件不能完整结案 |
| 其他上下文 | context_count>1或来源轮前已有成功轮、图片、记忆依赖/事实或技能guidance均显式标记未核验 | 不猜测无关、不把后来新聊天自动算成旧任务来源；未保存完整历史依赖，不能声称已绑定所有前文正文 |
| 范围标记 | linked_chat_sources / direct_goal_only | 没有聊天关联的人工Goal只核对自己；不能宣称全部聊天意图已覆盖 |

criteria.check与requirements.kind新增quote_sources，要求文本固定为“对账已关联聊天原话、会话要求与参考资料范围，再核验当前目标的报价结果”。expected是64位摘要：`digest({verifier:quote-sources-1,request:1.6绑定,receipt:来源回执摘要,scope:来源范围})`。回执含Goal祖先及历史摘要、根聊天关联、已关联轮request/action/背景视图摘要、guidance、context_count及是否存在前轮；不含后来无关轮。策略语义修改必须升级source verifier版本。

来源端口由Host提供，Completion在configure和evaluate重新取得；缺端口或绑定变化不能通过。Goal首次受理未关联Task时由Host显式传Goal id；后续只能从原Task找到Goal。完整Goal与Task.goal、本次输入与Task首步文本必须一致，不能核验截断的目标。执行前和原副作用检查点重新验证来源绑定，失败沿现有plan_source_changed进入WAITING，不为核验发新权限。

正确结果且来源ready可passed；仍有未核验内容为unknown/WAITING_EVIDENCE；错误报价仍优先failed/NEEDS_CORRECTION；已确认结果的来源失效为invalid/INVALIDATED。quote_sources_changed / quote_sources_unresolved、版本、绑定、来源数量和未解决数量进入原证据指纹。工作结案仍要求全部原前提，不把ready或条件通过率当业务Q；semantic_goal_verified=false。

检查发生在现有边界，Dialogues与主库没有新增分布式事务。不得据此宣称消除了核验后到实际效果间的所有竞争窗口；已完成动作及交付回执保留原事实，后来失效仅撤销当前可采信结论。历史上下文未决时的部分执行也不等于那些未读取正文已经被完整绑定。

<a id="workflow-changes-contract"></a>
## 明确变更 1.8.0 的实际契约

POST /api/goals新增只读 `review_quote_changes`，传id、revision。只接受已关联聊天的原始Goal及完整纯文本计划；不接受直接Goal、Work子修订或缺少已接受聊天来源的generation。原quote_sources、quote_request与quote_selection契约保持原义，旧任务不自动升级。

| 项目 | 规则 | 拒绝或保留未核验 |
|---|---|---|
| 来源次序 | generation 0来自根聊天；1..N各有唯一已接受amend回执；history顺序完整、N≤3；按generation排序，不按turn_id字典序 | 缺代、重复代、行动goal/input与历史快照不符、时间非递增、原有来源撤回均不能通过 |
| 明确语法 | `新增要求「单条要求」`、`撤销要求「单条原要求」`、`将要求「单条原要求」替换为「单条新要求」`；多条以中英文分号或换行分隔 | 每轮≤2000字符、≤8操作；引号内必须完整单句、无首尾空白；拒绝尾部未解析文字、嵌套引号、礼貌句及多句目标 |
| 有效条件 | 初始用户原话和会话要求形成条目；旧目标须逐字匹配一个active条目；新增不可与有效条目逐字重复 | 不自动合并同义目标、不取最后一句、不再次操作已失效条目；任何操作错误阻止整份审阅受理 |
| 历史 | 条目保留source、id、state；替换/撤销保留changed_by；操作保留generation、原文span、old_id/new_id | 最多56历史条目、32有效条目；有效文本仍受1.6长度上限；不截断历史冒充完整 |
| Goal与输入 | 当前Goal实质条件的标准化多重集合须等于有效条目；预算、交期和选择仍由原解析器与独立报价核验器检查 | 当前Goal漏项或增加未请求条件阻止受理；未知有效要求保持待核验；撤销预算不表示无限预算 |
| 报价资料 | 每代input_text仅可改变max_price_minor/max_delivery_days；其余解析字段必须等于初始输入；计划输入须等于最终接受输入的解析内容 | 不借要求修改替换报价、价格、来源或币种；预算/交期仍须与有效原话一致 |
| 前文范围 | 每个关联轮的成功前轮集合必须正好是已重放轮，context_count须为2×前轮数+1 | 混杂前文、缺失/截断上下文保持未核验；这是有界一致性检查，不补造不存在的逐轮上下文捕获记录 |
| 会话要求与附件 | 初始会话要求一直参与；后续缺省不等于撤销；不同非空会话要求阻止受理。附件只核对本次或当轮输入的逐字一致性 | 明确任务内撤销不修改全局会话设置；图片/其他资料和背景依赖仍待核验，资料不能授予权限 |

新check/kind为quote_changes，固定要求文本为“按已接受原话的明确新增、替换和撤销重放要求，核对当前目标、输入与报价结果”。expected绑定quote-changes-1、当前1.6绑定、原来源回执、generation顺序/前轮ID集合/历史回复摘要及重放结果摘要。策略语义变化必须升级版本。旧quote-sources-1绑定不因新策略版本改变而失效。

审阅响应可包含原文、requirements_history和changes；新的验收存储、结果评价和审计只保存绑定、版本、数量与原因，不复制这些原文。Host为Completion提供独立change_review端口；缺端口不能通过。受理、执行前和原副作用检查点、完成评价均重新计算；绑定变化沿原plan_source_changed停在WAITING，已完成结果失效为quote_changes_changed/INVALIDATED。未知有效条件为quote_changes_unresolved/WAITING_EVIDENCE；错误结果仍优先NEEDS_CORRECTION。

原目标版本、执行许可、共享额度、停止/撤权、真实动作和交付回执保留。撤销一条任务要求不是清除控制底座停止锁存或扩大权限；重新评价也不撤销已发生的动作。Dialogues与主库没有全局原子事务；不能将现有检查点宣传为消除了所有竞争窗口。semantic_goal_verified仍为false，条件通过率不等于完整业务质量。

<a id="workflow-inheritance-contract"></a>
## 返工继承 1.9.0 的实际契约

POST /api/goals新增只读 `review_quote_rework`，字段id、revision；返回requirements_history、changes、rework_versions、issues、ready、binding及建议验收。通过原Goal受理、Completion及效果前来源端口复核；纯核验不调用模型、不执行动作或改变权限。旧规则和旧绑定版本不自动升级。

| 项目 | 契约 |
|---|---|
| 工作祖先 | Work根＋最多3个子版本；ordinal连续、同根、无环；父任务SUCCEEDED，纯文本串行、全部回执和交付可读且摘要一致；不要求父版业务已通过 |
| 验收来源 | 根已冻结quote_changes，父子修订已冻结quote_rework；依据必须匹配父任务完整goal及首步input。历史结果错误可以纠错，但不能抛弃父版本的条件 |
| 重做范围 | 每条边start_step=1；当前完整纯文本计划；子Goal不能再有无法由该Work边解释的amend或history |
| 变更依据 | 复用Work中已记录的kind、note；correction仅接受 `保持全部要求`；new_requirement使用明确引用式新增/替换/撤销；每次最多8条、note沿原1000字限制 |
| 条件与资料 | 有效条件≤32、历史节点≤80、完整目标及有效条件拼接均在原2000字核验界内；保留未知项；资料除预算/交期上限外不变；最终Goal与有效条件归一化多重集相等 |
| 绑定及变化 | quote-rework-1绑定当前完整请求、计划、所有继承边、父冻结验收、父条件绑定和要求历史；原回执/文件/反馈由Work来源摘要核对；变化使冻结验收失效 |
| 详情一致性 | Goal详情的计划、动作、任务、共享预算和评价在同一核心账本事务内组装；观察评价及首次schema初始化参与已有事务，避免旧动作与新完成状态混在同一响应。不是跨数据库或外部文件的全局快照 |
| 新评价 | 固定quote_rework检查及对应需求文本；独立报价判定决定passed/failed；未知项为unknown；缺来源端口或绑定变化为invalid；完整覆盖不等于通用语义理解 |
| 存储 | 原始note只留在既有Work请求/来源展示；新验收和评价存摘要、版本、计数，不额外复制原话；没有新schema或迁移 |

已发生动作与旧交付不重写。检查触发原plan_source_changed或Work错误路径，沿原等待/取消状态处理；不新设重试许可。“重新核对复用依据”仅允许当前尚未受理的返工草案；更新原Work来源摘要后，新审阅绑定也随之变化。已受理版本不就地改签，来源失效后不能靠改绑定继续执行；1.10通过[显式新版本恢复](#workflow-recovery-contract)覆盖可证明的反馈变化；自动诊断和其他来源问题恢复仍未实现。来源撤回、交付损坏、授权或总额度不足不能靠更换核验方式绕过。[实施](core-bootstrap.md#workflow-inheritance-runtime) · [证据](delivery-validation.md#workflow-inheritance-evidence)。

<a id="workflow-recovery-contract"></a>
## 来源恢复 1.10.0 的实际契约

在原POST /api/goals新增以下动作。沿原任务与Work身份，不提供新执行通道。

| 动作 | 请求与结果 | 约束 |
|---|---|---|
| analyze_recovery | id、revision、work_revision；返回来源变化摘要、analysis_digest、保留要求绑定、待停止标记与预算估算 | 只读；持有原上下文锁和账本事务；目标必须为当前负责版本，版本/权限/停止状态仍有效 |
| recover_work | 上述版本字段＋request_id、analysis_digest、note、keep_requirements=true；返回新Goal id | 原执行锁＋上下文锁＋事务；重新分析后摘要必须一致；同请求幂等，不同内容冲突；失败回滚取消、撤权、记录和草案 |
| review_quote_recovery | id、revision；返回要求历史、recoveries、issues、ready、binding、建议验收 | 新quote-recovery-1核验；有恢复边界的全量后续版本也强制使用，不自动升级旧验收 |

证明限定：遍历同根、连续ordinal、全部start_step=1的最多4版本链；当前来源快照除feedback外须与旧绑定一致。仅回看最近17条反馈摘要及无反馈状态；证据不足返回recovery_unprovable，不能扩大窗口后声称原证明成立。已确认纯文本动作核对原计算回执，保存动作核对原文件摘要；预算spent须与完整确认动作前缀一致。

新增work_recoveries表（独立work_recovery_schema=1，原work_schema=2不改），保存摘要保护的不可变恢复边界：父Goal/Task、停止标记、停止前后状态摘要、父验收摘要、此前各边的旧/新来源摘要、要求及分析摘要。反馈正文仍来自原反馈表，恢复记录不复制反馈原话。最新恢复边界只为它及后代记录新观察，不使祖先旧验收重新有效；后续新反馈或其他来源变化再次使该边界失效。

恢复只保留原完整Goal与输入。父链冻结验收的criteria与requirements必须恰好匹配相应来源核验建议；额外自定义条件拒绝恢复，不能悄悄丢弃。未知要求保持unknown，错误结果为failed，来源变化为invalid。固定quote_recovery检查与对应需求文本进入原Completion覆盖校验；缺端口、缺检查、错绑定不能受理或签为通过。

READY／仅来源错误WAITING可在所有动作CONFIRMED时由原取消机制停止，撤销旧执行许可；SUCCEEDED保留执行状态但撤销旧许可。已有任务、动作、验收和交付不覆盖。新草案无Task、无新grant、无派发；下次原受理重新检查权限与预算。释放额度仅为旧任务未用预留，已用成本留在原Ledger；原4版本及整件工作总额不重置。独立取消、停止锁存、RUNNING、未知效果、来源撤回、过期或撤权均拒绝。

来源核验与文件检查沿现有模型；跨数据库、外部文件的并发写入不是全局事务快照，不声称物理隔离或任意外部效果恢复。[实施](core-bootstrap.md#workflow-recovery-runtime) · [实测与未测](delivery-validation.md#workflow-recovery-evidence)。

<a id="workflow-trials-contract"></a>
## 三领域对照 1.11.0 的实际契约

本轮增加离线CLI与纯检查策略，并修订原assistant的协议/仅回复路由提示；不新增生产HTTP动作或数据库表。`tools.work_trials`的--suite读取三领域任务包，--output要求新目录；--run显式发起模型调用；--provider、--model、--reasoning、--max-output-tokens选择并冻结本轮配置，不保存回用户配置。

| 项目 | 契约 |
|---|---|
| 样本 | jarvis.work-trials.v1；3—30个任务，必须覆盖comparison/documents/learning；唯一有界ID、1—3轮/任务、每prompt最多6000字；同内容不能换ID充独立样本；整包最多1MB |
| 来源 | synthetic或user_supplied＋来源说明；用户提供是来源声明，不自动获得独立真实任务认证；隐藏参考仅留在冻结包，不传给模型 |
| 对照 | workflow_off/workflow_on；相同当前代码与模型参数、隔离聊天、记忆关闭、AB/BA顺序、每任务每配置1次；报价none/none是同路径控制，不能算技能收益 |
| 调用边界 | 总调用数为两组全部预定轮次；无回退、无自动重试；每次至多50000输入字节、60秒、128—8192可配置输出上限；连续3次响应失败停止，依赖前轮失败则后轮缺测 |
| 检查 | work-trials-2；严格JSON对象（可有json代码围栏），重复键、非有限数、错误类型拒绝；顺序无关的集合必须无重复；额外文字质量未据此获分 |
| 状态 | 明确交付失败为FAIL但Q未知；UNKNOWN/取消/缺测不填零；一项硬条件失败即该案例失败；仍有缺轮的案例不能算完整配对 |
| 分领域汇总 | 每个领域单列PASS/FAIL/UNMEASURED；只有所有预定轮次可判定才完整；6个任务×2配置×若干轮仍只算6个不同任务，不以调用数充样本量 |
| 文件与审计 | frozen.json先写；turns中started与result分别独占创建；绑定冻结摘要及记录摘要；artifacts保留模型解析前协议输出、原会话回复与document字段的原样派生文件；复制的Markdown证据用.md.txt后缀，原会话.md不变；回读复核摘要与原始观察 |
| 费用 | 沿sdk.pricing使用调用时费率快照估算，各币种分开；缺用量/价格明确未知；人工、本机计算、供应商账单尚未完整对账，full_cost与效率收益保持null |
| 权限与影响 | 原StopGate/NetworkGate有效；只读现有模型凭据并在临时实例执行对话；无生产配置变更、自动新任务受理、发信、定时、知识晋升或正式评分写回 |

摘要与SHA256用于可复核和发现变更，不是对文件持有者的数字签名。一个模型或技能开关的小样本对照不证明评估独立、广泛泛化或因果收益。没有人类学习者的独立作答、延迟复测和主观反馈时，学习增益和情绪质量均不得计算。[实施](core-bootstrap.md#workflow-trials-runtime) · [验收](delivery-validation.md#workflow-trials-evidence)。

<a id="workflow-fidelity-contract"></a>
## 正文忠实性 1.12.0 的实际契约

v1的输入及结果含义保持；新增`jarvis.work-trials.v2`在每轮增加必填`body_evidence`。共同调用、权限、费用与归档规则继续使用[三领域对照契约](#workflow-trials-contract)，没有新生产HTTP接口。

| 对象 | 实际限制 |
|---|---|
| 冻结参考body_evidence | sources为1—30个单行来源摘录，编号1—30个ASCII字母数字/下划线/连字符，文本最多1200字；facts/plans为无重复、互不重叠的当前有效来源编号 |
| 回复evidence | 严格只有facts、plans、suggestions；前两项各最多30项source/quote字符串；suggestions最多5个500字以内非空单行字符串 |
| 来源与计划 | 当前选择集合必须与冻结参考相同且无重复；quote逐字对应来源；失效来源即使原文真实也不能当当前依据；事实更正不能顺带删除计划，显式取消/替换则不得复活旧计划 |
| 正文 | 固定事实、已确认计划、建议（未采纳）三节；与字段渲染完全一致，允许CRLF和一个末尾换行；Markdown特殊字符作文本转义；额外结尾或改变原因/时间/动作均失败 |
| 解释范围 | 核验document三节正文与冻结指定字段；未指定的额外字段不获语义认证。来源摘录格式不是通用语义判官；来源真实性、建议适当性与自由改写质量未认证；条件分不能当Q |
| 版本 | v1仍work-trials-2；v2为work-trials-3/body-evidence-1；冻结原代码摘要及参考；旧证据、失败和原始回复不追改 |

事实/计划原文来自用户材料，不是执行授权。这里只检查选择与表示；模型仍走原chat/Goal通道，任何外部动作受原权限与受理规则控制。试验器对不匹配只记录失败，不自动修复后冒充原答案。[实施](core-bootstrap.md#workflow-fidelity-runtime) · [验收](delivery-validation.md#workflow-fidelity-evidence)。

<a id="workflow-shadow-contract"></a>
## 交付影子核对 1.13.0 的实际契约

复用原`/api/chat/send`，新增可选`delivery_basis`字段；旧请求保持有效。原GET会话投影增加当前依据与逐轮快照/观察，没有新任务受理端口。

| 对象 | 契约与界限 |
|---|---|
| delivery_basis输入 | 严格expected_revision非负整数、facts/plans字符串数组；每组最多15条，每条1—1200字、无换行/空白边界/NUL；两组不重复，合计最多6000字；每条必须逐字存在本次用户消息 |
| 事务 | expected_revision须等于该聊天当前修订；依据快照与新轮次一并提交，失败回滚；同request_id且同内容重试不重复增版；版本冲突返回delivery_basis_conflict，不自动覆盖 |
| 持久化 | 原dialogue.sqlite3增加delivery_bases；turns增加delivery_basis/delivery_review。每次显式更新完整替换当前事实与计划；不提供字段则沿用。空两数组也增版，表示停止后续核对 |
| 来源标识 | 每条保留source_turn、原文起止位置，快照保留source_time_utc与摘要；F1/P1等编号只在该依据版本内有效，引用必须连同依据摘要/修订，不能跨版本仅凭编号认作同一事实 |
| 时间 | 来源时间为消息受理UTC时间；相对时间解析状态UNVERIFIED；保存“明天”等原文不代表已换算正确日期、时区或提醒 |
| 模型上下文 | 只用该轮冻结快照；用户声明不是外部许可或已核实事实。资料更正、清空可改变后续快照，不能改写旧回复原始依据 |
| 影子结果 | delivery-shadow-1；绑定依据摘要、修订和回复摘要，would_block始终false、quality_score为null；有摘录协议时复用body-evidence-1，其他正文只查原文出现 |
| 状态 | EXCERPT_MATCH仅限定摘录格式匹配；PROSE_UNVERIFIED表示原文出现但全文未核实；REVIEW是可能改写或遗漏；NO_BASIS/NOT_APPLICABLE/UNAVAILABLE不能算通过 |
| 变化与异常 | 当前依据摘要或回复摘要不同则投影stale；检查异常不改变成功回复；已有依赖清理同时清除旧观察，避免旧核对冒充当前有效 |
| 隔离与权限 | 仅同聊天依据；不自动读附件、其他聊天或知识库来建真值；不执行计划、不发信、不安排提醒、不写正式知识/业务评分，不额外请求模型 |

工作台的依据编辑草稿复用原会话草稿目录；提交后取消更新勾选，未提交失败时保留。清空当前依据不是删除历史原消息，也不代替正式知识的纠正/遗忘流程。`tools.work_trials --basis-inputs`可加载独立于隐藏答案的用户声明包并冻结，采集真实交付观察；输入声明属于试验条件，不冒充自然语言自动提取成果。[实施](core-bootstrap.md#workflow-shadow-runtime) · [验证](delivery-validation.md#workflow-shadow-evidence)。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：主人利益原则、身份授权与停止控制](security-sovereignty.md) · [下一章：技术栈、源码目录与运行数据](stack-project-layout.md)
<!-- book-footer:end -->
