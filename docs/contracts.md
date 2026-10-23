# 公共接口与数据契约

> 新工程设计基线 · 2026-10-22 · 目标/明确规则 accepted，运行方案 proposed。H 盘版本记录不构成本工程的实现或验收证据。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第二篇 · 核心与工程基础](../README.md#part-foundation) › 第 08 章

**本章导航**

- [个人助手核心接口（设计）](#personal-assistant-contracts)
  - [身份、个人上下文与行动意图的边界](#personal-context-contract)
- [记忆组件的替换契约（proposed）](#memory-provider-contracts)
  - [开源提取器、编纂器与路由的适配要求（proposed）](#memory-extractor-adapter)
  - [MemoryView 与知识候选的必要语义（proposed）](#memory-view-contract)
- [接口与数据契约](#interfaces)
  - [任务与动作分离](#interfaces-2)
  - [事件信封](#interfaces-3)
- [资源租约、本地组件与安全事件契约](#extensions-3)
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
<!-- book-nav:end -->

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

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：主人利益原则、身份授权与停止控制](security-sovereignty.md) · [下一章：技术栈、源码目录与运行数据](stack-project-layout.md)
<!-- book-footer:end -->
