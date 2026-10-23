# 记忆与认知综合方案：架构、选型与场景图解

> 文档版本 **memory-context-2026-10-23-r2** · 2026-10-23 · **proposed**。本章把综合方案组织为可连续阅读的正文；r2 增加单篇入口、图表和场景说明，没有宣称新增运行能力。记忆代码核查基线是 dev.10；dev.11 MCP 的独立交付不等于本章设计已实现。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第三篇 · 智能运行与多设备协同](../README.md#part-runtime) › 第 12 章

**本章导航**

- [1. 目标、范围与阅读方式](#memory-guide-start)
- [2. 整体架构：交流、执行与学习共用可信上下文](#memory-guide-architecture)
- [3. 数据组织：原件、记忆与知识各司其职](#memory-guide-data)
- [4. 运行流程：先获得合适上下文，再交流或执行](#memory-guide-flow)
  - [4.1 从一句话到可靠回答](#memory-guide-read)
  - [4.2 同时陪用户聊天和整理材料](#memory-guide-parallel)
  - [4.3 记忆形成、知识整理与遗忘的共同流程](#memory-guide-learning)
- [5. 框架与模型选型摘要](#memory-guide-selection)
- [6. 特殊情况与设计示例](#memory-guide-cases)
  - [6.1 同一项目的两个分支给出相反答案](#memory-guide-branch-case)
  - [6.2 提取器还在处理，用户已要求忘记](#memory-guide-forget-case)
  - [6.3 一台电脑离线期间，另一台撤回了记忆](#memory-guide-reconnect-case)
  - [6.4 私聊能理解的内容，不能在客厅直接朗读](#memory-guide-private-case)
  - [6.5 技术资料夹带指令，错误又被反复引用](#memory-guide-poison-case)
  - [6.6 情感变化、专业结论、低资源与升级失败](#memory-guide-other-cases)
- [7. 升级、实施与验收怎样连接](#memory-guide-delivery)
- [8. 文档、图源与后续维护](#memory-guide-maintenance)
<!-- book-nav:end -->

<a id="memory-guide-start"></a>
## 1. 目标、范围与阅读方式

Jarvis 需要在普通 PC／Mac 上持续理解用户，同时处理聊天、情感表达、研究、项目工作和多设备协作。推荐以**本地可追溯的数据为基础，按当前问题构建有限上下文，用可替换组件完成检索、学习和执行**。有意义的长期理解来自可纠正的经历与知识，不是把所有历史塞进提示词，也不是让模型生成一段永久有效的“主人总结”。

本章负责综合说明和场景图解；精确字段、完整安全规则、组件比较和验收阈值仍各有唯一权威位置。阅读本章可以了解完整运作方式，实施时再沿每节链接进入细则。图中角色表示职责，不要求分别部署服务。

| 阅读目标 | 本章位置 | 深入实施时的权威章节 |
|---|---|---|
| 先看系统如何组成 | [整体架构](#memory-guide-architecture) | [系统架构](architecture.md#clean-core-architecture) |
| 看记忆、原件、知识之间的关系 | [数据组织](#memory-guide-data) | [记录职责](knowledge-learning.md#memory-context-records) |
| 看聊天、任务、学习如何并行 | [运行流程](#memory-guide-flow) | [能力选择与调度](tasks-agents.md#context-aware-task-selection) |
| 决定采用哪些开源组件 | [选型摘要](#memory-guide-selection) | [桌面端选型](stack-project-layout.md#memory-desktop-selection) |
| 看实际问题怎样处理 | [特殊场景](#memory-guide-cases) | 每个案例下方的规则和验收链接 |
| 看升级、迁移与验证 | [演进与验收](#memory-guide-delivery) | [迁移协议](stack-project-layout.md#memory-context-migration)、[验收清单](delivery-validation.md#memory-context-acceptance) |

本轮核查的 dev.10 记忆已经具有显式事实、来源候选、范围／供应商过滤和撤回；尚无按问题排序的长期召回、语义索引、通用知识编纂、分支记忆、家庭私密库或多设备同步。实际可用范围见[记忆运行说明](knowledge-learning.md#memory-workbench-runtime)与[当前工程入口](../README.md)。下文案例都是**设计示例与待验证行为**，不是运行截图或已通过测试。

<a id="memory-guide-architecture"></a>
## 2. 整体架构：交流、执行与学习共用可信上下文

![图 1 综合上下文与认知架构](diagrams/memory-context-architecture.png)

[放大 SVG](diagrams/memory-context-architecture.svg) · [Mermaid 图源](diagrams/memory-context-architecture.mmd) · [图的权威说明](knowledge-learning.md#memory-context-design)。

输入到来时先确定身份、当前会话、项目／分支、用途和输出目的地。检索器只接触允许的范围，将本次需要的事实和证据交给交流或任务规划。工具结果核验后回到原会话，后台再从允许保留的内容中整理候选记忆。原始资料、事实修订和可重建索引分开管理，方便纠错和替换组件。

| 职责 | 负责什么 | 与其他职责的边界 |
|---|---|---|
| 前台交流 | 理解输入、回应情感、澄清、展示进度 | 不等待整库整理；回复不冒充任务已成功 |
| 上下文服务 | 范围过滤、按需召回、证据与预算 | 检索结果是资料，不授予执行权限 |
| 任务与能力选择 | 选择已有工具／Skill，必要时组织 Agent | 使用任务专属上下文；每次实际执行仍核对权限 |
| 后台记忆整理 | 提取候选、检查来源、去重、编纂知识 | 不直接覆盖事实；不能长期占用数据库写锁 |
| 自身能力目录 | 安装、健康、资源、验证版本 | “声称支持”与“实测可用”分开，过期能力需复查 |
| 同步与维护 | 获准共享、纠错传播、重建、迁移 | 离线仍可本地工作；重连不重复执行现实动作 |

默认采用轻量业务宿主和有界后台 Worker；检索编码器尽量共享、按需加载。模块独立指可测试、可替换的接口边界，不代表每个模块都要一个数据库或微服务。普通设备仍会竞争 CPU、内存、磁盘和 GPU，靠资源预留、短事务、背压和可取消任务控制影响，不能承诺物理上完全互不影响。

<a id="memory-guide-data"></a>
## 3. 数据组织：原件、记忆与知识各司其职

![图 2 原件到记忆与知识的数据关系](diagrams/memory-guide-data.png)

[放大 SVG](diagrams/memory-guide-data.svg) · [Mermaid 图源](diagrams/memory-guide-data.mmd)。箭头表示依赖和读取关系，不表示内容会自动晋升。原件只能证明当时记录了什么，仍需判断陈述是否真实。

| 层次 | 例子 | 主要用途 | 需要避免的问题 |
|---|---|---|---|
| 当前工作记忆 | “把刚才那份报告缩短”中的指代 | 连续对话、未完成步骤、恢复检查点 | 不把临时约束永久化 |
| 原件与情景经历 | 原消息、文档版本、工具回执、附件 | 查证原话、日期、人物与上下文 | 不只保存摘要，也不无限保存未经许可的内容 |
| 事实与条件偏好 | “工作汇报先给结论” | 稳定而可纠正的个人理解 | 不把“今天疲倦”变成永久性格 |
| 共同经历 | 一次完成的旅行计划与后续评价 | 关系连续性、未结话题 | 不虚构共同经历或混入 NPC 台词 |
| 主题知识 | 某接口在版本 v2 下的约束 | 专业研究、复用可查证结论 | 不丢失适用版本、反例与来源 |
| 方法与能力经验 | 某工具在某环境下成功的步骤 | 改进规划，生成候选 Skill | 一次成功不等于通用方法或执行授权 |

知识可以按“领域 → 问题／概念 → 主张与方法 → 来源／实验”组织；个人、项目与共享范围是横向权限维度，不能只靠文件夹名实现隔离。某份原件可以支持多个知识条目，但各条目都记录源修订，原件纠正后能定位受影响内容。

总体认知通过允许读取的“个人目标与偏好、项目目录、未结事项、共同经历、自身能力”动态组装。目录标题也可能泄露秘密，因此先筛范围，再生成总览。数据字段和边界分别见[记录职责](knowledge-learning.md#memory-context-records)、[分支与总览](knowledge-learning.md#memory-branch-context)、[公共记忆契约](contracts.md#memory-view-contract)。

<a id="memory-guide-flow"></a>
## 4. 运行流程：先获得合适上下文，再交流或执行

<a id="memory-guide-read"></a>
### 4.1 从一句话到可靠回答

| 步骤 | 输入／动作 | 输出与失败处理 |
|---|---|---|
| ① 请求快照 | 绑定身份、项目／分支、用途、时间和目的地 | 不明确的敏感范围先澄清，不从文本自称判断身份 |
| ② 按需检索 | 自足问题可直接回答；回忆／任务／专业问题查对应资料 | 低置信度判断采用小预算补查，不永久跳过记忆 |
| ③ 确定性与混合召回 | ID、日期、版本、词项；需要时加语义召回 | 短词、否定和数字保留原意；编码器不可用可回退 |
| ④ 深入证据 | 摘要 → 相关主张 → 原件章节 | 限制轮次和费用；证据不足明确缺口 |
| ⑤ 组装上下文 | 合并近期内容、允许偏好、证据与任务状态 | 保留回答预算，避免无关记忆挤占 |
| ⑥ 回复或规划 | 闲聊／情感／澄清，或任务计划与能力选择 | 出站再复查最新撤销和渠道许可 |

全文规则见[检索与上下文](knowledge-learning.md#memory-context-retrieval)。速度需要测首字、首音频、任务入队和附加检索延迟，不能只用一次 SQL 耗时代表体验。缓存也带身份、范围、修订和目的地，防止同一句问题从其他用户或分支的缓存得到答案。

<a id="memory-guide-parallel"></a>
### 4.2 同时陪用户聊天和整理材料

**示例：**用户说“今天很累，陪我聊聊，顺便整理昨天的项目材料”。这句话同时包含情感交互与工作要求，不能强制只选一种意图。

![图 3 前台交流与后台工作的时序](diagrams/memory-guide-parallel.png)

[放大 SVG](diagrams/memory-guide-parallel.svg) · [Mermaid 图源](diagrams/memory-guide-parallel.mmd)。

前台先回应并受理工作；如果“昨天的材料”能在当前项目唯一定位，就沿用上下文继续。如果不能确定项目，提出一个必要问题，其他交流继续。后台任务独立报告进度和交付结果，记忆整理还可稍后执行。取消材料任务不应结束聊天，聊天结束也不自动撤销用户明确要求继续的任务。

能力选择顺序是先满足实际契约、权限、平台和资源，再考虑质量与费用：现成工具能完成就复用；Skill 组织步骤；适合分解的问题才生成多个 Agent。Agent 数量由预算和可用资源限制，不能把理论可扩展理解成无限并发。规则见[任务选择与调度](tasks-agents.md#context-aware-task-selection)、[伙伴表达与反向提问](interaction-persona.md#companion-context-policy)、[自身能力证据](self-model.md#self-model-context-selection)。

<a id="memory-guide-learning"></a>
### 4.3 记忆形成、知识整理与遗忘的共同流程

![图 4 记忆形成、纠错与迁移流程](diagrams/memory-context-lifecycle.png)

[放大 SVG](diagrams/memory-context-lifecycle.svg) · [Mermaid 图源](diagrams/memory-context-lifecycle.mmd) · [完整生命周期规则](knowledge-learning.md#memory-lifecycle-completion)。

主动学习从已授权目标、重复失败、用户纠正或资料过期等实际缺口出发。每个学习项说明预期收益、证据、资源预算和结束条件；读取网页之后仍要核验，不因为“新”就替换旧知识。先更新可编辑、可删除的知识和经验，再考虑独立的微调实验；默认不把私人记忆训练进模型权重，因为逐条删除数据库不能消除权重中的信息。

<a id="memory-guide-selection"></a>
## 5. 框架与模型选型摘要

以下是对[唯一选型表](stack-project-layout.md#memory-desktop-selection)的阅读摘要，不另立版本或依赖清单。详细许可、版本、平台和采用条件以该表为准。上游研究固定了九个仓库提交，见[研究来源与证据](references.md#memory-context-sources)；没有完成同机跑分，不能按自研或上游宣传预判胜负。

| 位置 | 优先路线 | 对照／升级路线 | 决定因素 |
|---|---|---|---|
| 事实与事务 | SQLite 与单一写入接口 | 完整框架替换也须保留等价语义 | 修订、来源、撤回、迁移和崩溃恢复 |
| 词项检索 | FTS5＋中文预处理 | 短词／标识符补查 | 中文姓名、两字词、数字、代码和否定 |
| 向量索引 | sqlite-vec 先试验 | LanceDB | 过滤准确性、安装负担、召回和重建成本 |
| 本地编码器 | e5-small／BGE-small 作为小模型基线 | EmbeddingGemma-300m、Qwen3-Embedding-0.6B | 相同任务上的质量、CPU 延迟、全部进程内存与许可 |
| 提取与整理 | 最小结构化提取基线 | LangMem、Mem0 | 有依据的候选、错误晋升率、费用和数据接管范围 |
| 知识分层读取 | 可追溯章节与按需读取 | 借鉴 OpenViking／VikingRAG | 原件定位、层次读取、版本和许可 |
| 完整记忆方案 | 与当前方案平等比较 | EverOS、Hindsight | 桌面部署、质量、隐私、同步与全生命周期 |
| 关系与反思 | 简单实体／关系视图与有界整理 | Graphiti、LightMem 方法参考 | 确认有收益后再承担额外抽取和依赖成本 |

费用要拆成初次建库、增量写入、每次检索、知识编纂和最终回答。开源框架本身不决定 API 费用；提取模型、embedding 与回答模型可以分别路由，但每条外发路径都受资料许可约束。私密资料还要覆盖索引、缓存、备份与日志的保护，见[私密存储规则](security-sovereignty.md#memory-private-storage)。

<a id="memory-guide-cases"></a>
## 6. 特殊情况与设计示例

这些案例用于解释边界和指导测试，不是另设一套验收编号。每个案例都需要正例与反例：既验证不该发生的行为被阻止，也验证允许的正常工作仍可完成。

<a id="memory-guide-branch-case"></a>
### 6.1 同一项目的两个分支给出相反答案

**输入：**项目 A 的 main 使用 API v2，feature 正在试验 v3。用户先问 main 的调用方式，随后要求比较两个分支。

![图 5 项目分支记忆的隔离与合并](diagrams/memory-guide-branches.png)

[放大 SVG](diagrams/memory-guide-branches.svg) · [Mermaid 图源](diagrams/memory-guide-branches.mmd)。

| 时点 | 正确的上下文与表现 | 不应发生 |
|---|---|---|
| 询问 main | 读取 main 对应快照，回答 v2 并给出处 | feature 最近写入就覆盖 main |
| 比较差异 | 临时联合读取，标明每项来自哪个分支 | 合成一份混杂的“项目事实” |
| 合并 feature | 对照目标代码、提交与测试，判断哪些知识仍适用 | 合并代码时无条件晋升所有实验笔记 |
| 删除实验分支 | 清理其专属草稿／索引，保留仍被引用的证据 | 连同其他分支引用的原件一起删除 |

完整规则见[分支快照与总体视图](knowledge-learning.md#memory-branch-context)，对应[综合验收](delivery-validation.md#memory-context-acceptance)中的分支冲突场景。

<a id="memory-guide-forget-case"></a>
### 6.2 提取器还在处理，用户已要求忘记

**输入：**某条资料正在形成记忆候选；用户纠正或要求忘记该资料。稍后旧提取结果才返回。

![图 6 遗忘与迟到候选的竞态处理](diagrams/memory-guide-forget-race.png)

[放大 SVG](diagrams/memory-guide-forget-race.svg) · [Mermaid 图源](diagrams/memory-guide-forget-race.mmd)。

关键是先让后续读取和提交看到撤销，再清理派生内容。提交端检查来源修订和撤销状态，不能接受“已经在后台开始了”的旧候选。已在途的回答在发送前再次核查；已经发出的文字无法撤回成“从未发送”。

| 界面状态 | 实际含义 |
|---|---|
| 已停止使用 | 本地后续读取／提交已受撤销约束 |
| 本机清理完成 | 已处理范围内正文、摘要、索引与缓存，并有逐项回执 |
| 等待其他设备 | 离线节点尚未接收撤销；不能显示全网已删除 |
| 备份按保留策略处理 | 说明到期时间和恢复时先应用撤销的规则 |

详细语义见[遗忘与清理](knowledge-learning.md#memory-lifecycle-completion)，不能把逻辑失效、物理清理和远端副本处理都用一个“已删除”表示。

<a id="memory-guide-reconnect-case"></a>
### 6.3 一台电脑离线期间，另一台撤回了记忆

**输入：**设备 B 离线后保留旧记忆；设备 A 上用户要求遗忘。B 之后重连，还带回了旧摘要和新任务回执。

![图 7 离线节点携带旧内容重连](diagrams/memory-guide-reconnect.png)

[放大 SVG](diagrams/memory-guide-reconnect.svg) · [Mermaid 图源](diagrams/memory-guide-reconnect.mmd)。

离线阶段，B 依据本地已知权限工作，无法立即知道 A 的撤销。高敏感资料可以采用带期限的访问许可，到期后等待重新验证；这会牺牲部分离线便利，需要在数据类别上明确选择。重连时先对账身份、权限和撤销，再接收允许的增量；新回执按任务身份核对，不因同步事件再次执行现实动作。

该流程不是 SQLite 文件复制或网盘同步。冲突的事实修订保留来源等待解决，不能凭设备时间简单覆盖。完整规则见[共同体共享](federation.md#memory-context-sharing)。

<a id="memory-guide-private-case"></a>
### 6.4 私聊能理解的内容，不能在客厅直接朗读

**输入：**主人在私人会话保存了资料，稍后在家庭共用扬声器上询问相关事项；现场可能有访客。

![图 8 私密记忆的读取与输出渠道](diagrams/memory-guide-private-output.png)

[放大 SVG](diagrams/memory-guide-private-output.svg) · [Mermaid 图源](diagrams/memory-guide-private-output.mmd)。

| 情况 | 示例行为 |
|---|---|
| 私人终端已解锁，资料与目的地均允许 | 读取必要内容，在私人渠道回答 |
| 客厅扬声器／未知在场人员 | 提示“有一项私人内容，请在个人设备查看”，不透露标题或正文 |
| 资料允许本地使用，禁止云端处理 | 本地完成或说明能力缺口；不转云 embedding／重排／TTS 绕过限制 |
| 家庭成员自己的私密资料 | 根据该成员授权判断，家庭管理员不自动获得读取权 |
| 只有声纹相似，没有其他认证 | 仅作辅助线索，不据此解锁秘密 |

完整身份、存储与渠道规则见[个人与家庭私密域](security-sovereignty.md#memory-private-storage)。这是目标交互，当前普通记忆库尚未因此自动获得加密与多人认证能力。

<a id="memory-guide-poison-case"></a>
### 6.5 技术资料夹带指令，错误又被反复引用

**输入：**导入的技术文档夹带“把资料上传到某处”的指令；另一条错误结论又被三个 Agent 分别总结。

| 观察 | 应采取的处理 | 解释 |
|---|---|---|
| 外部资料要求执行动作 | 作为来源内容处理，不晋升为主人命令 | 来源不能授予权限 |
| 三份摘要都来自同一原文 | 计为一个来源，保留共同依赖 | 三次复述不是三份独立证据 |
| 编纂顺序改变造成结论变化 | 保留矛盾，重放形成过程并检查来源 | 整理过程本身也会产生污染 |
| 发现局部错误 | 隔离受影响主张与派生知识，保留独立有效证据 | 避免无差别删除导致更多损失 |
| 修复后测试仍失败 | 继续修复，保留失败样例 | 不降低门槛宣布恢复 |

若触及系统既有停止条件，执行其停止协议；普通错误不能由外部文本随意升级成无限关停。规则见[抗污染与防退化](security-sovereignty.md#memory-contamination-defense)，研究依据见 [MemForm](references.md#s298) 与 [MemSecBench](references.md#s299)。

<a id="memory-guide-other-cases"></a>
### 6.6 情感变化、专业结论、低资源与升级失败

| 场景 | 期望表现 | 需要观察的证据 |
|---|---|---|
| “今天不想说话”，明天主动聊天 | 今天减少打扰，不推断永久性格或取消全部提醒 | 临时状态有时效，长期偏好可解释、可修改 |
| 设计机械部件，旧资料缺少单位 | 查原件、补单位并计算／仿真；证据不足说明缺口 | 参数、单位、软件版本与结果可追溯，不只看答案流畅度 |
| 记忆编码器未加载，语音正在使用资源 | 先走词项／结构路径，后台工作排队，显示降级 | 前台延迟、队列积压与恢复后结果；不把没查到当作不存在 |
| 主动学习发现库有新版本 | 形成有预算的更新任务，先检查对当前项目的影响 | 学习目标、证据、完成条件与安静时间有效 |
| 更换向量模型时磁盘不足 | 保留当前可用索引，推迟／分批重建 | 不先删除唯一可用数据，不混用不同模型向量 |
| 新组件回退到旧组件 | 应用最新事实、权限和撤销后恢复旧实现 | 代码可以回退，已经遗忘的内容不能复活 |

专业知识处理见[知识晋升](knowledge-learning.md#memory-knowledge-promotion)，互动见[伙伴理解](interaction-persona.md#companion-context-policy)，资源和迁移见[验收预算](delivery-validation.md#memory-resource-envelope)、[升级协议](stack-project-layout.md#memory-context-migration)。

<a id="memory-guide-delivery"></a>
## 7. 升级、实施与验收怎样连接

升级按现有协议进行：一致快照与增量水位 → 影子转换／重建 → 核对来源、修订、权限和撤销 → 重放增量 → 验收通过后切换 → 观察与退役。这里是阅读摘要；精确迁移规则只维护在[组件迁移章节](stack-project-layout.md#memory-context-migration)。不能保证任意数据库格式变更都完全零停机；需要短暂只读时应显示真实状态，不假报保存成功。

| 实施方向 | 要证明什么 | 权威位置 |
|---|---|---|
| 先补当前召回与失效缺陷 | 能从超过固定条数的资料里找到本轮所需内容，纠正不会无差别清空无关背景 | [验收与既有阶段对应](delivery-validation.md#memory-context-acceptance) |
| 接入提取／编纂候选 | 依据完整、错误不自动晋升、后台失败不拖住交流 | [知识晋升](knowledge-learning.md#memory-knowledge-promotion) |
| 比较框架与替换组件 | 同一模型、资料、预算、留出集下比较真实回答和产物 | [桌面选型](stack-project-layout.md#memory-desktop-selection) |
| 家庭、多设备与迁移 | 私密范围正确、撤销传播、不重放动作、旧备份不复活 | [综合验收](delivery-validation.md#memory-context-acceptance) |

K0—K6 仍是唯一实施路线，本章不新增第二套阶段。准确率、延迟、内存、并发、迁移与污染测试沿用[完整验收表](delivery-validation.md#memory-context-acceptance)，不能用本文案例替换或删减原验收。Windows 大内存开发机的结果不能替代真实 Mac 或普通低内存 PC；受限模拟与真实设备证据分别登记。

<a id="memory-guide-maintenance"></a>
## 8. 文档、图源与后续维护

从[工程主入口](../README.md)进入本章，再沿主题链接深入；[全书目录](README.md#book-tree)和[图册](architecture-atlas.md#diagram-index)同步收录。图的 PNG 直接供 Cursor／VS Code 和普通 Markdown 阅读器显示，SVG 供放大，`.mmd` 是唯一可编辑源，避免依赖阅读器的 Mermaid 插件。

维护时优先修改负责该主题的权威章节，本章只更新综合叙述和受影响示例；不要复制整份旧版。增加案例时同步本章导航、manifest 归属、图册和对应验收的覆盖关系。新增图的生成与检查见[本轮图形回执](evidence/memory-guide-render-2026-10-23.json)，文档与目视检查见[本轮交付回执](evidence/memory-guide-document-2026-10-23.json)。完整操作规范见[文档维护](MAINTENANCE.md#change-workflow)。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：记忆、知识库与持续学习](knowledge-learning.md) · [下一章：任务、动作、多 Agent 与资源调度](tasks-agents.md)
<!-- book-footer:end -->
