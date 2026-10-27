# 技术栈、源码目录与运行数据

> 新工程设计基线 · 2026-10-22 · 目标/明确规则 accepted，运行方案 proposed。H 盘版本记录不构成本工程的实现或验收证据。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第二篇 · 核心与工程基础](../README.md#part-foundation) › 第 09 章

**本章导航**

- [技术栈与选型理由](#technology-selection)
  - [语言与运行形态怎样选择](#technology-selection-3)
  - [普通 PC 优先：默认部署与组件准入](#technology-selection-4)
  - [透明桌面壳与补充工作台的技术落点](#desktop-presence-shell)
  - [自有任务状态机、LangGraph 与 Temporal 的取舍](#technology-selection-5)
  - [替换与隔离规则](#technology-selection-6)
  - [选型冻结条件](#technology-selection-7)
- [知识与记忆的开源选型（2026-10-23 更新，proposed）](#memory-open-source)
  - [名称、短长期记忆与比较边界](#memory-candidate-identities)
  - [存储和检索层：不同项目解决不同问题](#section-ee5f9aae063b)
  - [记忆框架：复用算法和接口，不交出数据所有权](#section-31d166a591e4)
  - [整库接入、复用部件还是自己实现](#memory-integration-choice)
    - [综合比较后的推荐方案与替换条件](#memory-recommended-plan)
    - [个人与工作资料怎样分区，为什么这样选](#memory-storage-partition-choice)
  - [推荐组合如何落到独立模块](#memory-module-adoption)
  - [OpenWiki：适合项目知识，不取代整套记忆](#openwiki-adoption)
  - [已核查的依赖负担与默认部署](#memory-dependency-audit)
  - [冻结选型的依据与成本](#section-9f65cb73fb32)
- [项目文件结构与依赖规则](#project-structure)
  - [新工程的推荐源码结构](#project-structure-1)
    - [D 盘目录、技术起点与文档交接](#clean-project-layout)
    - [文件格式、状态与配置的唯一分工](#clean-file-formats)
  - [单个模块模板](#project-structure-2)
  - [新工程的运行数据结构](#project-structure-3)
  - [依赖规则](#project-structure-4)
- [网页与桌面操控选型（2026-10-21）](#browser-desktop-selection)
  - [开源对比与采用方式](#browser-desktop-comparison)
  - [Google 兼容性与能真正减少配置的路径](#google-browser-compatibility)
  - [模块化落地、资源与升级](#browser-desktop-adoption)
- [自主研发种子的新增目录与所有权](#growth-seed-layout)
- [0.2.0-dev.3：工程内的配置与运行数据](#portable-data-runtime)
- [会话专属目录与跨平台项目位置（dev.12）](#session-folder-layout)
  - [目录归属与保存格式](#session-folder-ownership)
  - [新建项目和测试目录策略](#project-location-policy)
  - [模块分工与替换点](#session-folder-components)
- [聊天行动与候选编码的增量结构（dev.10）](#conversation-layout)
- [连接器的独立实现位置（dev.11）](#mcp-layout)
- [PC 与 Mac 的综合记忆技术选型（2026-10-23，proposed）](#memory-desktop-selection)
- [记忆组件升级、索引重建与换机协议（proposed）](#memory-context-migration)
- [本地模型模块与资产归属](#local-model-layout)
- [Gmail 模块与本地数据（1.0.0）](#gmail-layout)
<!-- book-nav:end -->

<a id="technology-selection"></a>
## 技术栈与选型理由



<a id="technology-selection-3"></a>
### 语言与运行形态怎样选择

| 方案 | 更适合的部分 | 需要承担的成本或限制 | 当前判断 |
|---|---|---|---|
| Rust | 小型长期驻留底座、原生桥、性能热点 | 编译链、所有权学习、异步与 FFI 调试；内存安全不等于业务正确 | 保留，缩小首期范围 |
| Python | 推理、工具、评估、迭代快的业务宿主 | 依赖/解释器封装、原生扩展、资源隔离；不能把所有任务塞进一个事件循环 | 首期主业务参考 |
| Go | 服务进程、联网、进程管理 | cgo/原生 SDK 仍增加构建与发布复杂度；AI 生态适配成本需估算 | 底座的有效替代 |
| C# / .NET | Windows 服务、桌面集成、熟悉该生态的团队 | 自包含与 AOT 有不同兼容约束；跨平台能力要按依赖逐项确认 | Windows 优先的有效替代 |
| TypeScript | Web/桌面交互、部分软件集成 | Node 依赖与构建供应链；不承担所有本地模型工作 | UI 和适配器按需引入 |
| C/C++、CUDA 等 | 驱动、既有高性能库与特定设备 | 内存/ABI/驱动兼容风险，编译与硬件验证成本 | 通过受限进程封装复用 |
| WASI 组件 | 可表达为受限接口的轻量工具 | 语言、宿主 API、线程/设备支持需逐项确认 | 可选能力载体，不是全系统唯一底座 |
| JVM、Swift、其他语言 | 领域库或目标平台明确要求的模块 | 增加运行时、缓存、测试矩阵和维护责任 | 按收益准入，不预装所有生态 |

这是定性选型表，不是语言性能排名。对替换需求应比较“完成同一任务的端到端质量、延迟、常驻资源、构建时间、恢复成本、维护负担”。如果 Rust 改成 Go 并未改善这些指标，仅重写代码不计作进化成果。

<a id="technology-selection-4"></a>
### 普通 PC 优先：默认部署与组件准入

此约束按主人 2026-10-15 的要求采纳，适用于 K0—K6 的个人设备产品；不是“第一版轻量、后期必然集群化”。完整功能可以逐步增加，默认安装和常驻开销必须保持受控。以下是后续实现规则，不表示加载、卸载与资源管理均已实现。

| 范围 | 默认实现方向 | 按需扩展边界 |
|---|---|---|
| 主运行形态 | 本机应用：受保护控制底座、一个模块化业务宿主、受限 Worker；当前复用 Python、SQLite 和本地网页，目标日常入口为[透明精灵壳](#desktop-presence-shell) | 按权限与故障隔离拆进程，不按文档中每个模块拆服务；工作台按需打开，不因支持跨平台而立刻重写内核 |
| 持久任务 | 现有账本与有界本机队列，一个后台 Worker 起步 | 按实测资源增加并发；不默认增加 Redis、Celery、Temporal 或消息服务器 |
| 模型与 Agent | 一个路由权威，共用按需启动的推理后端；Agent 是上下文和任务状态 | 不给每个 Agent 单独部署模型、数据库或服务；只有任务确需时生成角色，限制活跃并发 |
| 记忆与检索 | SQLite/FTS5 起步，最多选定一个当前向量后端 | 对照候选用于实验，不能把所有记忆框架和数据库一同装入默认包 |
| 语音、视觉与研发 | 能力包按需安装、加载和释放；编译环境与生产运行分离 | 未启用语音时不常驻 STT/TTS；未使用的模型、SDK 和构建器不自动下载，退役按既有保留规则处理 |
| 多设备 | 完整节点各自能运行，配对后同步领域事件、分配任务 | 加第二台 PC 不要求建立集群、共享数据库或常驻中心服务；协调节点可由现有完整节点承担 |
| 平台支持 | 当前先完成 Windows；平台特权集中在适配器 | 有实际目标设备和测试条件后再支持 Linux/macOS 等；不提前实现所有 OS、GPU 后端、语言和硬件协议 |

**默认安装、启动与升级链路均不引入 Kubernetes、服务网格、Ray 集群、Kafka/NATS 集群或分布式训练基础设施，也不依赖 Docker/WSL 环境。** 隔离需要何种原生机制或按需虚拟机，按实际执行能力验证；不能为了减小体积而允许不可信代码以宿主权限运行。确有服务器规模需求时才独立评估重型适配器，例如耐久消息服务 [S26](references.md#s26)，它不能反过来成为普通 PC 的启动条件。

新增第三方组件或长期支持一个后端前，须记录：当前任务缺口；用标准库/已有组件能否解决；相同任务的收益；下载/安装体积、空闲和峰值资源、常驻进程、更新与许可证成本；失效与卸载路径。只为未来可能使用而增加兼容层，不构成准入理由。同一能力默认只维护一个已验证实现；对照试验和明确使用中的提供商适配除外，统一走原有接口。

较多服务会增加部署、契约版本和分布式故障成本。保留必要权限隔离，其余业务模块先同宿主，再按真实瓶颈拆分；这借鉴模块化起步的工程经验 [S39](references.md#s39)，不是用进程数替代隔离验收。控制循环掌握授权和生命周期，LLM 不能改变组件准入规则或自行扩大资源预算。正式资源目标与检查方法只维护在[验收页](delivery-validation.md#pc-footprint)。

<a id="desktop-presence-shell"></a>
### 透明桌面壳与补充工作台的技术落点

**目标定位 accepted，技术方案 proposed。** 优先验证 Tauri 2/Rust 与 Windows WebView2 组合，复用现有 HTML/CSS/JavaScript 与 Host；这是候选选型，没有在本轮安装或作为已具备依赖登记。版本、原生透明合成、命中测试和窗口生命周期必须实测后才能冻结；[现有来源](references.md#desktop-companion-sources)不代替本机验证。若候选达不到透明性与资源出口，再在同一接口下评估 Windows 原生替代，不同时生产维护多个壳。

原生层负责无边框窗口、逐像素背景透明、有效命中区域、鼠标拖动捕获、非主动激活显示、托盘、热键、普通窗口之上的层级和显示器坐标修正；Web 层负责原 Logo、主题、局部动效及按需卡片。CSS 的 `background: transparent` 只能使网页元素背景透明，不能单独证明操作系统窗口透明；原生层和 Web 层都满足[透明要求](interaction-persona.md#desktop-presence-transparency)才算成立。透明区透传与整体穿透不同，交互主体必须仍可点击／拖动。

按[统一系统准则](architecture.md#unified-system-principle)，同一节点／数据根的两种视图复用已有业务 Host，经[呈现契约](contracts.md#desktop-presence-contract)读取状态与配置、提交动作；未来跨节点通过传输适配访问明确的执行节点，不为入口另建模型循环或业务账本。普通收起、工作台关闭、壳视图重建不得结束 Host；明确退出沿既有控制层处理。精灵与卡片采用紧贴内容的小窗口或等效命中区域，隐藏时停动画、释放非必要视图，不能保留一个覆盖整屏的透明浏览器来截取输入。开机启动作为独立设置留给用户选择，本轮不创建启动项或常驻服务。

源码位置只在[目标目录树](#clean-project-layout)登记：`apps/companion/` 为未来原生壳与卡片前端，`apps/workbench/` 保留详细工作台，平台桥经既有 `adapters/desktop/` 边界接入。目录分开仅组织不同视图与平台代码，共享客户端、数据契约、设置校验、主题和通用控件应抽取复用；新平台不复制整套工作台业务。上述规划项不表示目录或平台功能已经存在。原 Logo 继续引用 `apps/workbench/brand/core.png`，不新做另一套标识；主题和动效遵守[品牌规则](interaction-persona.md#jarvis-brand-icon)。构建依赖按实现时的锁文件登记，不导入 H 盘旧桌面程序。

当前源码核对仅发现网页启动器 `apps/workbench/launch.py`：默认启动／复用本机服务并打开浏览器，`--no-browser` 仅不打开页面，不会启动精灵。`control/bootstrap` 的 Rust 控制 CLI 也不是桌面壳。设计样张位于 docs/evidence，不是产品入口。[核查记录](evidence/desktop-companion-2026-10-25/project-integration-checks.json)与[原生验收](delivery-validation.md#desktop-presence-validation)区分素材、网页预览、源码实现和实机行为。

<a id="technology-selection-5"></a>
### 自有任务状态机、LangGraph 与 Temporal 的取舍

**首期只允许一份权威任务账本、一位外部动作调度者。** LangGraph 若启用，只持有推理过程检查点，工具节点向 Task Runtime 提交意图；历史检查点重放不得直接执行现实动作。LangGraph 的执行便利性不转移 Jarvis 的授权责任。

先验证自有有限状态机是否足够。若出现大量跨周定时、信号、复杂补偿或人工步骤，再比较继续维护的成本与引入成熟工作流引擎的成本。Temporal 是后期共同体工作流候选，不是必须采用的升级目标；采用后仍不要求完整离线节点依赖远端 Temporal 在线。[S12](references.md#s12)

引入另一引擎优先接新任务；既有任务完成或在明确检查点转交唯一所有权。必须记录能力差异与迁移代价，不能只替换 SDK 就宣称工作流语义等价。

<a id="technology-selection-6"></a>
### 替换与隔离规则

模型、语言、数据库和 UI 的替换都通过相同模块生命周期：候选注册 → 契约验证 → 独立评估 → 新任务灰度 → 排空或迁移 → 保留可恢复版本。长任务固定版本，执行时仍检查当前授权。

独立虚拟环境解决依赖冲突，不解决恶意代码隔离。生成代码的构建、测试和执行必须使用适当的受限账户、进程控制、文件/网络白名单，必要时使用虚拟机或适当隔离模式的容器；WSL、容器或子进程名称本身不是安全结论。生产目录和发布凭据不对候选环境开放。

<a id="technology-selection-7"></a>
### 选型冻结条件

K0—K1 在同一目标硬件上比较不超过两个底座候选，先验证确定性停止/恢复、离线准备、账本与资源预留，选定一个首期栈并锁定版本。K2—K4 逐步补齐本地智能、工具构建和版本回退证据；早期用文本与模拟交互负载测资源竞争，真实语音并发在 M2 验收时补齐。持续记录开发维护成本，不同时实现所有替代方案。

只有当一个候选实现通过相同契约和验收，且收益高于迁移/维护成本时，才发起语言或框架迁移。编程语言开放是新增实现的能力，不是允许 Jarvis 因个人偏好不断重写自己。

<a id="memory-open-source"></a>
## 知识与记忆的开源选型（2026-10-23 更新，proposed）

结论是采用 **Jarvis 自有记忆语义与数据接口 + 成熟可替换组件**：本地事实存储、项目知识编纂、选择性长期记忆、检索和同步分别负责。每个完整节点都能独立读取必需资料；稳定主机可以提供更强检索，但不能成为其他完整节点的唯一记忆来源。语义设计见[知识页](knowledge-learning.md#memory-selection-design)，同步取舍见[共同体记忆协议](federation.md#memory-replication)。以下是根据官方代码库与文档作出的工程判断，不是性能跑分；未安装这些候选，也没有把公开基准成绩记为 Jarvis 的成绩。

2026-10-18 的历史调研补充 LLM Wiki、MemPalace、LangMem、LightMem、A-MEM 和 EverOS；2026-10-23 重新固定 9 个项目的提交与可取得的依赖/许可，当前结论见[桌面端选型](#memory-desktop-selection)。**当前最合适的是分工组合，不是挑一个“最强记忆库”替换全部系统。** 日常伙伴需要记住偏好与共同经历，工作时需要准确资料和真实进度；这几类信息的更新、纠正和保留方式不同。推荐落点见[模块映射](#memory-module-adoption)，当前代码缺口见[渐进改造](knowledge-learning.md#memory-selection-design)。

<a id="memory-candidate-identities"></a>
### 名称、短长期记忆与比较边界

| 名称 | 本次比较对象 | 不能混淆的地方 |
|---|---|---|
| LLM Wiki | Karpathy 的 [LLM Wiki 思路稿 S219](references.md#s219) | 是“原始材料 → 持续编纂的关联页面 → 查询与维护”的方法，不是一个已有统一 API、同步协议和性能保证的数据库产品 |
| OpenWiki | 用户先前指定的 `langchain-ai/openwiki` | 是具体工具实现；可借鉴 Claims、来源版本和分节读取，不等同于所有名为 LLM Wiki 的仓库 |
| 记忆宫殿 | 本轮采用 `MemPalace/mempalace` 为具体样本 [S220](references.md#s220) | “记忆宫殿”也是一种组织隐喻，网上存在同名实现；这里的结论不泛指其他项目，也不假定空间隐喻必然提高准确率 |
| LightMem | `zjunlp/LightMem` [S222](references.md#s222) | 比较的是记忆增强研究框架，不是同名 KV cache 项目；节省模型调用不等于安装包或常驻内存小 |
| A-MEM / AgeMem | A-MEM 是动态关联笔记方法 [S223](references.md#s223)；AgeMem 是学习长短期记忆管理策略的研究 [S227](references.md#s227) | 不因名称相近视作同一库；训练策略的论文不能当作接上任意 API 就获得相同表现的插件 |
| EverMemOS / EverOS | 当前官方仓库为 EverOS [S224](references.md#s224) | 本轮看到的是 Markdown + SQLite + LanceDB 的本地路线；旧论文、旧服务栈和新代码的成绩、依赖不可互相套用 |

短期记忆是本轮上下文、近期交流和任务工作状态；长期记忆包括情景经历、可纠正事实与知识、经验证的方法。短期不等于只能放 RAM，长期也不等于一律放向量库。上下文窗口、KV cache、向量检索、知识 Wiki、事件日志各自只解决部分问题；先按[数据职责](knowledge-learning.md#memory-operating-cycle)比较，再按同条件测试选实现。GitHub 星数、项目自报准确率和某个英文数据集总分不构成 Jarvis 的适配评分。

<a id="section-ee5f9aae063b"></a>
### 存储和检索层：不同项目解决不同问题

| 候选与主项目许可 | 已核实的能力 | 对本项目的判断与代价 |
|---|---|---|
| SQLite + FTS5（Public Domain）[S87](references.md#s87)、[S100](references.md#s100) | 本地事务、关系元数据、全文检索；WAL 不是多机器共享数据库协议 | **首期事实与元数据底座。** 延续现有栈；必须补中文检索、事件同步与权限过滤，不能直接同步活跃 DB/WAL 文件 |
| sqlite-vec（MIT / Apache-2.0）[S88](references.md#s88) | C 扩展、Windows 等平台、float/int8/binary 向量；官方仍标 pre-v1 | **轻量向量候选，先试验。** 适合少依赖节点；只放派生索引，固定版本并验证重建/过滤；不把未验证 ANN 能力或演示速度当作规模承诺 |
| LanceDB OSS（Apache-2.0）[S89](references.md#s89) | 嵌入式检索、向量/全文/多模态数据，Lance 格式与版本能力 | **本地向量第二候选。** 在检索规模或多模态需求超过轻量方案时比较；增加原生包和第二种存储格式；数据版本不等于离线多主冲突解决 |
| Qdrant（Apache-2.0）[S90](references.md#s90) | 服务端向量、分片、复制、读写一致性选项；集群元数据使用 Raft | **稳定主机的可选检索服务。** 不让常休眠设备都变成集群节点；官方安装要求和目标 OS/文件系统需验证。分布式索引不替代记忆语义和删除对账 |
| PostgreSQL + pgvector（PostgreSQL License）[S91](references.md#s91) | SQL 与向量，精确/近似搜索、过滤和迭代扫描 | **已有常驻数据库或复杂服务端查询时再采用。** 每台轻节点部署的运维收益不足；近似索引加过滤可能不足 top-k，必须测授权过滤后的召回 |
| Chroma OSS（Apache-2.0）[S92](references.md#s92) | 简单 collection API、本地/服务端模式、文档/向量元数据 | **快速 RAG 对照候选。** 接入容易，但不因此获得事实溯源、离线合并或 Jarvis 的恢复协议；Cloud 功能不能默认算进 OSS |

本轮不为全套候选创建运行依赖。K2 首轮使用 SQLite/FTS5 基线，向量试验只比较 sqlite-vec 与 LanceDB 两个后端，并使用相同嵌入与输入，避免把模型差异误算成数据库优势。暂定 sqlite-vec 为资源较小节点的试验首选；如果版本兼容、权限过滤或规模测试不过，选择 LanceDB，不改变原始资料与事实接口。Qdrant/pgvector 是后续集中检索选项，不能要求完整节点在线才能查自己的记忆。

<a id="section-31d166a591e4"></a>
### 记忆框架：复用算法和接口，不交出数据所有权

| 候选与本次核验状态 | 值得复用的部分 | 准入判断 |
|---|---|---|
| Mem0，Apache-2.0 [S93](references.md#s93) | 记忆提取、个性化召回、混合检索，库/自托管/托管多种形式 | **记忆提取器的优先对照项。** 默认云端 LLM/embedding 必须显式替换或授权；README 明确部分新基准含托管专有优化。其新增记忆与 Agent 陈述处理不能替代我们的证据等级、纠正和遗忘规则 |
| MemOS，Apache-2.0 [S97](references.md#s97) | 本地插件的 SQLite/FTS5、经验整理及独立 core / 宿主 adapters | **备用对照，不进入首批默认安装。** 不要求为 Jarvis 先安装 OpenClaw，但现成插件不能直接视为 Python 模块；Node 与原生依赖需另计。自托管栈与本地插件是不同部署路线 |
| Graphiti，Apache-2.0 [S94](references.md#s94) | 时态实体关系、事实有效期和来源追踪 | **关系/时间问题出现明确收益后接入。** 需要图后端和可靠结构化提取；官方提示小模型可能导致入库失败，并已弃用 Kuzu 后端。图只作可重建关系视图，抽取冲突不能直接裁决主人事实 |
| Cognee，Apache-2.0 [S96](references.md#s96) | 文档、代码与会话转成可检索知识图；当前文档提供本地小模型路径 | **文档理解流水线的备选。** “本地可运行”不等于本机中文准确、依赖已备齐或具备离线复制；单独测解析、图构建和资源成本 |
| Letta / Letta Code，Apache-2.0 [S95](references.md#s95) | 有状态 Agent、记忆块、上下文管理和 MemFS | **借鉴或作为外部工作者，不接管核心。** 原 Letta V1 server 已归档，当前代码在 letta-code；Cloud 默认和 local 后端须区分，不能把云端多机运行当作我们的离线多主共同体 |
| OpenViking，主项目 AGPLv3，部分组件 Apache-2.0 [S98](references.md#s98) | 目录化上下文、L0/L1/L2 分层读取、记忆/资源/技能组织 | **架构参考与后续独立适配候选。** 当前 README 另含整体重写/语言转换限制说明，应核对拟采用版本条款；本轮不将其整库纳入可任意自改底座，也不作许可效力判断 |
| Hindsight，MIT [S157](references.md#s157) | retain / recall / reflect、按 bank 组织记忆、经历与反思检索 | **完整记忆对照候选。** 当前官方提供跨平台嵌入式 pg0 路线，见[本轮复核](#memory-desktop-selection)；默认包是否适用需实测，嵌入式 PostgreSQL 仍有数据库成本 |
| OpenWiki，MIT [S160](references.md#s160) | 有来源的代码知识、Markdown 页面、跨仓库 workspace、按章节检索 | **项目知识模块的优先参考，与 Mem0 互补。** 不能用 Wiki 代替个人情景记忆、任务账本或设备复制协议；具体复用与限制见[OpenWiki 分析](#openwiki-adoption) |
| LangMem，MIT [S221](references.md#s221) | 可接自有存储的提取接口、用户画像、情景记忆与后台整理；`create_memory_manager` 可返回提取结果 | **与 Mem0 同批比较，接口适配优先看它。** 功能边界较适合候选提取，但包依赖仍带 LangChain/LangGraph、模型 SDK 和 LangSmith；不为此迁移主循环或默认开追踪 |
| MemPalace，MIT [S220](references.md#s220) | 保留原文，按人物/项目/主题组织检索；后端可替换 | **借鉴情景档案和检索组织；完整实现作为独立对照。** 默认 Chroma；已有 SQLite exact 等选项，不能因此认为安装依赖已去掉 Chroma。层级不是授权机制，检索命中不等于事实已纠正 |
| LightMem，MIT [S222](references.md#s222) | 分段、短期整理、离开交互关键路径的长期整合 | **借鉴节省重复加工的方法。** 当前研究实现依赖 Torch、Transformers、压缩和 embedding 模型，不整体放进轻量默认包；“sleep-time”指异步整合，不代表计算或费用为零 |
| A-MEM，MIT [S223](references.md#s223) | 类卡片笔记的关联、上下文补充和关联更新 | **关联推荐的后续算法候选。** 模型生成的链接可撤回、可重建；不允许关联传播重写原始证据或主人确认事实，避免错误沿笔记扩散 |
| EverOS，Apache-2.0 [S224](references.md#s224) | 可编辑 Markdown、派生 SQLite/LanceDB 索引、个人/Agent/知识分域与后台整理 | **值得保留的完整系统对照。** 已不应按旧重服务印象排除；但需要 Python ≥ 3.12、Arrow/LanceDB 及多个算法包，与现有事务事实库的权威模型不同，直接替换代价较大 |

这些框架的“记忆”常包含各自的 Agent、模型配置、存储或后台处理。候选必须通过本项目适配器：输出待核验事实/摘要及来源；写入权仍由 MemoryStore 控制。先在同一数据上测增益，允许直接采用通过测试的开源实现，避免重复开发已有算法；但不能因一个库接入成功就同时启用其自动学习、网络连接或技能发布。

<a id="memory-integration-choice"></a>
### 整库接入、复用部件还是自己实现

| 方式 | 得到什么 | 真实代价 | Jarvis 的选择 |
|---|---|---|---|
| 完整框架接管记忆 | 最快获得框架自身的写入、提取、检索闭环 | 双重存储/路由、作用域和删除语义适配；升级可能影响整个闭环 | 保留为隔离对照或稳定主机选项，不作为默认核心 |
| 官方 API / 独立 Worker 适配 | 保留上游升级通道，故障和依赖可隔离 | 要做版本、预算、导入导出及回执映射；服务持有的数据仍需撤回 | **优先复用方式**；按任务启动，仅交付该任务允许的资料 |
| 小范围代码复用或算法借鉴 | 可只引入确有收益的部件，继续共用 Jarvis 路由和存储 | 复制代码后需维护补丁与许可声明；上游私有函数未必是稳定组件 | 用于证据定位、切片、排序等边界清楚的部分；维护来源 SHA 和差异 |
| 全部自己实现 | 完整控制 | 需重新解决解析、检索、性能、迁移和大量边界问题 | 只自持必要语义和协调逻辑，不自造通用数据库、向量算法或密码协议 |

当前推荐、备选和变更条件见[桌面端选型](#memory-desktop-selection)。当前新工程的 [事实检索](knowledge-learning.md#memory-retrieval-runtime) 和 [文本资料库](knowledge-learning.md#knowledge-library-runtime) 已有独立证据；1.2.0 已加入可续建持久向量与片段式知识审阅，完整语义提取/编纂仍待实施，不继承旧工程通过结论。

Mem0 的 `Memory` 对象本身包含模型、embedding、向量后端和历史管理，并非现成的纯 Extractor。第一轮可让完整 SDK 在独立测试存储中输出结果，再转换为候选；若生产仅需提取，优先选择稳定扩展点或小范围实现，不依赖其私有函数。其 user / agent / run 过滤字段可作输入，不能直接等同 Jarvis 的主人、项目、人格和模拟域权限。[S154](references.md#s154)

LangMem 的函数式接口减少了存储接管，但不保证结果天然具有 Jarvis 要求的原文定位、否定语义和撤销关系，仍需外层适配与校验。其示例的 `InMemoryStore` 重启会丢失，不作为持久方案；选择功能接口也不能把整个依赖树称为“零依赖”。两者先在相同已授权片段上输出候选，比较质量、调用数和改造成本；接入任一库都不能同时启用另一套自动写入和后台调度。[S221](references.md#s221)

<a id="memory-recommended-plan"></a>
#### 综合比较后的推荐方案与替换条件

2026-10-23 更新：采用本地事务事实管理与可替换组件的路线，具体默认/备选、费用和替换条件只维护在[桌面端选型](#memory-desktop-selection)。当前 D 盘已有事实有界 E5 和文本资料 FTS5 子集，见[当前实现](knowledge-learning.md#knowledge-library-runtime)；1.2.0 已补持久向量与片段审阅，自动语义提取和通用知识编纂仍未完成，旧工程实验不作为当前通过证据。

保留完整替代路线参加评测：若 EverOS、Hindsight 或其他框架在相同中文、分域、纠正、遗忘、离线和资源预算下显著降低维护成本，应按 ADR 流程重评。自研不会自动获得更高质量评分；完整框架也不能凭上游排行榜继承 Jarvis 的可靠性结论。

<a id="memory-storage-partition-choice"></a>
#### 个人与工作资料怎样分区，为什么这样选

组件选型之外，还要选择数据的组织方式。以下是对当前普通 PC 与个人伙伴目标的工程判断，不是不同数据库的性能跑分；信息分类与完整共享规则只在[知识章](knowledge-learning.md#memory-scope-model)维护。

| 组织方式 | 好处 | 主要问题 | 取舍 |
|---|---|---|---|
| 所有原文和记忆放一个全局向量集合，依靠提示区分 | 原型接入快，跨内容相似搜索直接 | 相似不代表允许使用；主人、客户、NPC、计划与已完成结果容易混淆，提示不能代替过滤 | 不作为权威数据模型 |
| 每个项目一套完全独立的记忆 | 项目隔离直观 | 主人通用习惯反复学习，跨项目统筹困难；复制偏好后纠正和遗忘难以收敛 | 用于确需隔离的敏感项目，不作为所有项目的默认方式 |
| 个人、工作、知识、Agent 各自引入一整套框架 | 各模块可快速使用专用能力 | 重复提取、索引与模型配置，多个写入权威和后台调度增加维护成本 | 保留实验对照，不全部常驻 |
| 单份整体画像文档直接覆盖，再附项目标签 | 画像易读，提示装配简单 | 局部纠正容易误改其他属性，情境例外和出处容易丢失 | 只把画像文档作为派生阅读视图，不作为唯一事实原件 |
| **统一接口，按主体/用途/项目/世界分域；共享用引用与晋升；敏感域可物理隔离** | 保留同一助手的连续性；局部可纠正、可迁移；适合单机与后续事件复制 | 必须实现严格的用途视图、依赖撤销和后端过滤契约；逻辑分域不能替代操作系统隔离 | **推荐**：延续原件、事实、账本、配置的现有物理落点，增量补语义，不要求合成一个巨型 DB |

首期仍由原 Python Host 管理 SQLite 与原件引用，MemoryStore 管事实，MemoryViewResolver 管一次使用资格；不是每种记忆各起一个服务。FTS/向量/关系索引只存派生数据，同一 embedding 执行后端供多个获准任务复用，但不得跨域混装提示、缓存或检索结果。真正敏感的资料可单独库、目录和受限进程；普通域共享连接/缓存不等于共享读取权限。

这种选择保持[原文—事实—知识—经验的流程](knowledge-learning.md#memory-operating-cycle)，以及[先回复后整理、按需召回、独立节点与升级](#memory-recommended-plan)。实现前先固定用途字段和混合消息正反例，再对比提取器；若产品规则尚未表达清楚，换更强的提取库也只能更快地产生难以纠正的数据。资源上限继续使用[既有预算](delivery-validation.md#memory-resource-envelope)，没有为每个域额外分配一份模型或进程预算。

<a id="memory-module-adoption"></a>
### 推荐组合如何落到独立模块

| 职责端口 | 新工程实现要求 | 替换边界 |
|---|---|---|
| MemoryExtractor | 确定性规则与按需模型提取产生来源候选，可对照 Mem0/LangMem | 不直接写长期事实，不改变授权 |
| CandidateReview | 比较重复、冲突、差异及来源，接受主人纠正 | 相似度不能自动改写画像 |
| FactStore | 统一事实写入、修订、撤回和用途管理 | 原始事实不依赖向量引擎 |
| EvidenceResolver / KnowledgeCompiler | 资料版本、引用和知识编纂，可借鉴 OpenWiki | 知识是可更新投影，不覆盖来源 |
| ContextAssembler | 按个人/项目/模拟世界和本次用途组合上下文 | 不因同属一个助手而无限共享 |
| IndexProvider | SQLite 全文起步，按需可替换向量索引 | 索引可重建，不承担身份和权限 |

所有端口在新工程独立实现或经许可适配成熟第三方库；旧项目文件名和实验适配器不作为代码依赖。首批不同时安装所有候选框架，按同任务质量、资源和维护成本对照。

<a id="openwiki-adoption"></a>
### OpenWiki：适合项目知识，不取代整套记忆

核验对象是用户指定的 `langchain-ai/openwiki`，固定到 `7c469e59584bfac3f97f5c32a67604de46805999`（package 0.7.2）。本次静态读码未执行它的安装、生成、插件注册或定时任务。与个人记忆框架相比，它更直接覆盖“Jarvis 理解多个项目、代码变化后知识不过时”。

| 已核查机制 | 借鉴到哪个独立模块 | 必须调整的边界 |
|---|---|---|
| Claim 的稳定 ID、来源 resource/version、增补/确认/修订/撤回；代码行范围哈希定位 [S161](references.md#s161) | 项目知识的 EvidenceResolver / KnowledgeCompiler | 版本匹配只说明来源未变，不能证明模型理解正确；增加 proposed/implemented/verified 状态与测试回执，不能把设计说明当现有能力 |
| 先给紧凑搜索结果，再按页面/章节读取；多 Wiki 保留来源身份 [S162](references.md#s162) | ProjectCatalog 与 Retriever 的分节读取 | 由 Jarvis 提供已允许的项目集合；workspace 关联是组织功能，不等于访问授权；不能默认带入所有私人项目 |
| 每页保存进度、保留未变化的 Claims、处理中断可续接 [S160](references.md#s160) | 可取消、可恢复的知识编纂任务 | 复用 Jarvis 任务账本和模型网关，不增加第二个后台调度器；更新按来源增量触发，不每轮聊天重写全书 |
| Markdown / 可视化知识图 | 知识浏览与可读导出 | 阅读视图和派生解释可以重建；权威文档仍按本仓库 manifest / 章节树维护，不额外生成一个竞争的 `openwiki/` 总设计 |

**两个实质限制：**当前 `searchWiki` 读取所选 Wiki 页面，`rankSearchUnits` 每次建立内存 SQLite FTS5，再使用 `porter unicode61` 排序；这避免持久索引陈旧，但工作量随所选页面增长。代码中的 camelCase / 路径拆词不等于中文分词，不能直接保证中文两字词召回。Jarvis 大量、多项目的日常查询应复用有源版本水位的持久增量索引，并对中文进行独立验证。[S162](references.md#s162)

现成 CLI 需要 Node ≥ 22.22.0，包含 DeepAgents / LangChain、多个供应商 SDK、MCP 等依赖；检索实现使用 `node:sqlite`，但完整依赖链仍涉及 checkpoint SQLite 原生组件。Windows 安装遇到无匹配二进制时可能需要构建工具，不能把“Markdown 文件”误认为零运行环境。生成/更新会用模型；只读 search/read 自身不调用模型。宿主集成当前支持代码 Wiki，不能把独立 CLI 的 personal brain 能力全算进宿主集成。[S160](references.md#s160)

首期采用它的边界和机制，不整体复制运行时。如果后续希望直接使用完整 OpenWiki，通过可选 KnowledgeCompiler Worker 在受限临时输出目录运行，产出**带来源的候选 patch**，经 Jarvis 文档检查后更新对应权威章节；兼容现有章节格式和目录的改造成本必须纳入对照。集成不能自动修改本仓库 AGENTS、安装全局插件、注册 cron 或启用自动合并。

2026-10-18 又读取了快照 `6c14bff27830034bfd70c15bde46825d7686ec60` 的 README、package 和检索文件 [S226](references.md#s226)。上文机制分析明确基于 10 月 16 日固定版本，不把新 HEAD 当成已完成兼容审计的升级包；正式适配前应对所选发布版本重新核对 Claims 路径、依赖和章节 patch 行为。

<a id="memory-dependency-audit"></a>
### 已核查的依赖负担与默认部署

以下是 2026-10-16 固定源码的直接依赖声明，**不是完整依赖闭包、安装体积或内存跑分**；不同语言/拆包方式的数量不能直接排序。快照、文件摘要和解析结果见[静态证据（旧工程参考）](references.md#legacy-project)。

| 候选 | 静态核查结果 | 对普通 PC 的影响 |
|---|---|---|
| Mem0 Python | 8 项基础声明，含 qdrant-client、SQLAlchemy、模型 SDK 与 PostHog；Qdrant adapter 支持本地 path [S154](references.md#s154) | 无需因此强制 Docker / Qdrant 服务；仍需模型/embedding 和依赖适配。默认遥测需显式关闭并验证网络行为 |
| MemOS local plugin | 8 项 JS 声明，Node ≥ 20，含 better-sqlite3、Transformers.js [S155](references.md#s155) | 增加 Node / 原生轮子 / 可选推理资源；不要与其完整服务部署混算 |
| Graphiti | 7 项基础声明，含 Neo4j driver、NumPy、模型 SDK；另有 FalkorDBLite 等 extras [S156](references.md#s156) | 不能笼统称“必须远端图服务”；嵌入式选项也需要单独验证 Windows、资源回收和图维护成本 |
| Hindsight API slim | 53 项基础声明；上层 API 依赖 slim[all]，extras 可带入本地 ML、ONNX、pg0 [S157](references.md#s157) | `slim` 名称不代表适合轻节点；先作为稳定主机服务评估。pg0 仍是 PostgreSQL 方案 |
| Cognee | 55 项基础声明，含 LanceDB、图后端、FastEmbed/ONNX、文档解析及服务组件 [S158](references.md#s158) | 文档处理能力完整，但不应为少量偏好记忆默认安装整套；按具体解析缺口评估 |
| OpenWiki | 27 项 JS 运行依赖声明；Node ≥ 22.22.0，独立生成与只读检索有不同成本 [S160](references.md#s160) | 适合按需编纂工具；可借鉴机制而不增加常驻 Node / 第二模型配置面 |
| Letta Code | Node ≥ 22.19、另声明 Bun 工具链，含终端/Agent 运行组件 [S159](references.md#s159) | 属于编码工作者，不因记忆需求引入第二个完整 Agent 主循环 |

2026-10-18 补充读取下列固定源码声明，完整 URL 与文件摘要见[本轮静态复核（旧工程参考）](references.md#legacy-project)。这是部署取舍依据，尚未测安装后的依赖闭包、内存、速度或中文质量。

| 新增候选 | 本轮静态观察 | 本地部署判断 |
|---|---|---|
| LangMem [S221](references.md#s221) | Python ≥ 3.10；基础依赖包含 LangChain、LangGraph、模型 SDK、Trustcall、LangSmith | 接口便于适配不等于包小；先在独立环境调用函数式提取，核查追踪/网络配置 |
| MemPalace [S220](references.md#s220) | Python ≥ 3.9；默认依赖 Chroma、NumPy、tokenizers、Hugging Face Hub；另有 GPU、DirectML、多模态等 extras | 首次 embedding 可能下载模型；离线前要备齐。选 SQLite 后端不自动移除默认包依赖，extras 不全装 |
| LightMem [S222](references.md#s222) | 当前声明 Python ≥ 3.10 且 < 3.12；固定 Torch、Transformers、sentence-transformers、LLMLingua、Qdrant client 等版本 | 研究复现环境独立；不把默认依赖合并进 Jarvis 基础环境，借鉴批处理可不引入整个训练/推理栈 |
| A-MEM [S223](references.md#s223) | sentence-transformers、Chroma、scikit-learn、LiteLLM 等 | 先验证关联是否有收益；已有 embedding 和网关应复用，避免再常驻一套模型 |
| EverOS [S224](references.md#s224) | Python ≥ 3.12；LanceDB/Arrow、SQLite、Web 服务组件及多个 everalgo 包；可选多模态 | 与 LightMem 的当前 Python 约束不能直接共用一个解析环境；本地无外部数据库不代表无运行时、模型或后台开销 |

Graphiti、Hindsight、MemOS 与 OpenViking 的本轮 README/依赖快照记录于 [S225](references.md#s225)，用于核查候选仍在变化；这里保留旧版数量的日期，不把旧直接依赖数写成当前安装体积。OpenViking 当前仍有分组件许可与 README 附加说明，实际复用须按固定文件核对，不能据名称推断所有代码都可无条件改写再分发。

默认运行仍使用已有 Python + SQLite，不新增 Postgres、Redis、Neo4j、Docker、WSL、K8s 或常驻 Node。已存在的文档渲染 Node 是开发工具，不因此变成终端用户的运行依赖。语义检索启用后只选择一个 embedding 执行后端；不同时引入 PyTorch、ONNX、Transformers.js 三条推理栈。多个 Agent、项目和人格共用模型进程，不各加载一套权重。

候选运行实验中，Mem0 使用 `MEM0_TELEMETRY=false`，OpenWiki 使用 `OPENWIKI_TELEMETRY_DISABLED=1`（或其支持的 `DO_NOT_TRACK=1`），并另核对网络行为；不能把关闭遥测等同禁止业务模型调用，也不能仅凭文档说明证明没有其他网络请求。最初静态调研未安装这些框架；后续 Mem0 的独立环境与回环限制已在[实验记录（旧工程参考）](references.md#legacy-project)单列，正式运行环境仍不安装 Mem0，OpenWiki 未因此进入运行流程。[S154](references.md#s154)、[S160](references.md#s160)

后台提取、索引和知识编纂走现有有界队列；默认一个后台作业、批量合并变更、互动优先、取消可恢复。小库先按需更新，后续若启用维护也只处理 dirty sources；不做无限网上学习、每次对话全量反思或重复嵌入。冷启动、空闲/峰值内存、安装和退役预算统一见[资源设计与验收](delivery-validation.md#memory-resource-envelope)。

<a id="section-9f65cb73fb32"></a>
### 冻结选型的依据与成本

先过硬门：本机离线、可导出原件和事件、纠正/遗忘完整、权限与模拟域隔离、兼容恢复、无未声明外发、许可和依赖可固定；任何一项失败不能靠高召回抵消。再比较中文召回与时间问答、错误记忆率、延迟/CPU/RAM/磁盘、后台入库的模型费用、同步字节量和迁移工作量。未测项目写“未知”，不填主观 95 分。

依赖成本包含模型文件、分词器、原生轮子、运行时和可离线重建材料；不能只比较 Python 包大小。常驻服务、重排模型和图提取均按需启用。升级触发器为冻结任务集上的可重复缺口，而不是固定“超过几万条就必须换数据库”。模型候选见[嵌入模型](models-offline.md#embedding-candidates)，实验入口见[记忆选型验收](delivery-validation.md#memory-selection-evaluation)。

<a id="project-structure"></a>
## 项目文件结构与依赖规则

本页是新工程源码和运行数据目录的唯一权威。下面是逐步实施的目标树；当前已有核心、网页工作台及分项能力源码，实际范围见本页后续增量与[当前验收](delivery-validation.md#session-folder-evidence)。目标目录不等于已经创建，尤其不能把规划中的桌面壳视为当前运行入口。

<a id="project-structure-1"></a>
### 新工程的推荐源码结构

**2026-10-22：D 盘独立工程路线 accepted，目录与栈 proposed。** 本节替代先前含大量预建适配器的目标树；H 盘各版本实际结构留在旧工程参考文档。新工程不依赖旧 Python 包、旧服务、旧数据库或旧环境。

<a id="clean-project-layout"></a>
#### D 盘目录、技术起点与文档交接

新工程已创建于 `D:/Jarvis/`，D 盘为 NTFS。2026-10-22 已独立实现[确定性核心与受限自主研发种子](core-bootstrap.md#growth-seed-operation)，使用 Rust 标准库原生控制、Python 标准库 Host 与 SQLite；没有引入第三方运行依赖、初始化 Git 或复制旧环境。Worker 使用从本机解释器单独准备的标准运行包；身份、控制库、能力包与交付均在本工程 user-data 下。下列树仍是逐步实施的目标结构；当前工作台使用原生 HTML/CSS/JavaScript，完整 TypeScript 前端与通用 Windows 桌面适配尚未实现，实际目录归[当前增量](#growth-seed-layout)。语言是初期实现选择，外部契约不依赖 Python/Rust 内存对象。编译器在开发包按需加载，生产启动不编译。

具体解释器、编译器、库和模型版本在首次实现前按受支持版本、目标机兼容和供应链核验锁定；不从 H 盘复制依赖锁或虚拟环境，也不自动安装 latest。首期不要求 K8s、Redis、RabbitMQ、独立向量服务或每 Bot 一进程。基础知识先用本地结构化记录/全文检索，向量、语音及大型模型按真实需求扩展。

```text
D:/Jarvis/
├── README.md / AGENTS.md
├── docs/                         # 新工程启用后的唯一当前设计与验收文档
│   ├── README.md / MAINTENANCE.md / manifest.json
│   └── diagrams/                 # 唯一图源与生成物，继续原章节规范
├── contracts/
│   ├── schemas/                  # module / task / action / development / release
│   ├── compatibility/            # 协议兼容夹具，不复制业务逻辑
│   └── examples/                 # 无秘密的格式示例
├── control/                      # 最小启动、停止、策略、恢复实现
│   ├── bootstrap/
│   ├── policy/
│   └── recovery/
├── host/                         # 通用装载与 IPC，不写领域特例
├── modules/                      # 首批核心，逐个具备清单和生命周期
│   ├── continuity/
│   ├── task_resource/
│   ├── personal_core/
│   ├── registry_composer/
│   ├── agent_runtime/
│   ├── context_knowledge/
│   ├── model_gateway/
│   ├── self_model_health/
│   ├── development/
│   └── evaluation_release/
├── adapters/                     # 仅在选中并实现时创建对应子目录
│   ├── models/
│   ├── development/              # Codex CLI / SDK / 桌面 / 模型补丁
│   ├── desktop/
│   ├── storage/
│   └── toolchains/
├── apps/
│   ├── cli/                      # 现有命令行与维护入口
│   ├── workbench/                # 现有网页；目标为主动打开的特殊补充
│   └── companion/                # proposed：日常透明精灵壳与按需卡片，共用 Host
├── sdk/                          # 首个已支持语言的薄协议封装
├── seed/                         # 无私人数据、无凭据的首次启动种子
│   ├── charter/                  # G0 的构建引用与策略版本
│   ├── skills/                   # 最小诊断、构建、测试与恢复方法
│   └── blueprints/               # 通用编写、审阅、研究等受限配方
├── config/                       # 默认配置与策略样例，不含有效账号秘密
├── tests/                        # 契约、集成、故障、升级、隔离、端到端
├── evals/                        # 公开样例与独立验收引用
├── tools/                        # 独立编写的开发、文档与发布工具
├── packaging/                    # 平台构建、离线依赖、启动与恢复包
├── research/                     # 仅来源索引与提炼笔记，不复制旧源码树
└── user-data/                    # 不进入源码版本管理，见运行数据节
```

树表示职责规划，脚手架只创建会实际验证的部分。每个核心目录使用下节同一包规范；轻量可信模块可在 Host 内运行，需要独立更新/故障隔离的实现用 Worker。源码模块边界与部署进程边界分别声明。

首版实际落点：`control/bootstrap` 为 Rust 启动／停止程序；`control/policy` 与 `control/recovery` 为 Python 确定性控制；`host/core.py` 负责装配；`modules/continuity、task_resource、context_knowledge、model_gateway、registry_composer` 为已用到的职责。内置能力清单在 `modules/registry_composer/manifests/`，入口在 `apps/cli/main.py`；JSON 契约在 contracts，种子在 seed，行为测试在 tests，固定文本评估夹具在 evals。Python 包目录使用下划线，协议 module_id 使用连字符；它们不必同名。当前核心随一个可信 Host 源包运行，只有两个内置能力登记管理清单，不冒称每个核心职责已能独立升级。

apps 和领域能力依赖公共端口/Host，再经明确控制接口执行；领域包只依赖 contracts/薄 SDK 和获准能力，不能反向导入其他领域内部代码。控制层不导入生成插件；候选不写控制器、激活包、凭据或独立验收。构建时检查依赖，运行时核对许可，目录名字不构成隔离。

当前设计已交接至本工程，根 README 是主入口，docs/manifest.json 管理章节。保留已有 R/N/K/M/V/H/ADR/S 编号；H 盘保留旧实现与历史证据，不再维护新工程设计。来源与去向记录见 references.md 的旧工程参考节及 docs/provenance.json。文档工具重新编写；旧代码、环境和用户业务库不迁移。主人于 2026-10-22 另行授权的模型设置和模型凭据迁移见[本地数据布局](#portable-data-runtime)。

<a id="clean-file-formats"></a>
#### 文件格式、状态与配置的唯一分工

| 格式 | 位置和用途 | 约束 |
|---|---|---|
| Markdown + 稳定锚点 | 可读规则、职责、说明与验收；manifest 管理章节 | 文案不能直接授予运行权限 |
| JSON + JSON Schema | 模块、能力、任务、动作、研发与发布契约 | 显式版本，不嵌任意安装脚本，不接受未知关键字段 |
| TOML | 配置与策略参数，由对应校验器核对 | 不存明文 Key，不能改 G0；候选不能自改生效配置 |
| JSONL | 有界执行事件及外部提供者事件适配 | 不作任意重放命令，不保存无限日志或秘密正文 |
| SQLite | 单机事务状态及分域数据 | 明确每张表的写入权威，不宣称跨库原子事务 |
| 不可变文件 + 摘要/来源清单 | 候选、正式包、测试、证据和必要恢复材料 | 哈希不证明安全，恢复不能覆盖新动作事实 |
| 平台秘密存储/加密文件 | 凭据、私密资料及受控引用 | 不进入 Git、模型提示、构建环境或通用日志 |
| 生态原生锁文件 | Python/Rust/Node 等实际构建依赖 | 每个依赖集合只有一个权威，不从旧环境盲拷 |

固定的是语义和变更流程，不是所有字段永远不变。字段变更通过 schema 协商和迁移，未知主版本不运行。

<a id="project-structure-2"></a>
### 单个模块模板

```text
module-name/
├── module.json              # 唯一包清单；JSON Schema 校验
├── README.md                # 职责、边界、使用、失败与恢复
├── CHANGELOG.md
├── src/                     # 独立实现
├── tests/                   # 公开行为、契约与故障测试
├── migrations/              # 自有状态迁移器；执行前隔离验证
├── compatibility/           # 邻近版本/替代实现的兼容夹具
└── build/                   # 构建配方及本模块生态锁文件
```

字段与生命周期只维护于[模块包契约](contracts.md#clean-module-contract)。根 contracts 定义通用消息，模块可提供业务 schema，由总清单引用。构建产物进入候选/包存储，不在 src 堆 release-old、final2 目录。独立验收标准不能由候选自带 tests 替代。

同进程可信模块可随 Host 包发布；要求独立停用、隔离崩溃或不同环境的实现通过相同端口运行在 Worker。缺少可用替代时停用核心会让相应服务不可用，不能声称任意拔除都无影响。

<a id="project-structure-3"></a>
### 新工程的运行数据结构

便携模式默认 `D:/Jarvis/user-data/`，数据与源码/程序分目录；安装到只读位置时由配置选择可写数据根，不要求管理员运行。新工程数据独立于 H 盘，未经显式导入验证不共享数据库、令牌、活动队列或发布槽。

```text
user-data/
├── identity/                # 连续身份与来源引用，不内嵌秘密
├── config/                  # 生效配置、修订与安全恢复引用
├── state/                   # 控制账本和按域保存的数据
├── private/                 # 平台加密秘密与访问代理数据
├── artifacts/               # 内部产物/证据；业务交付按主人指定位置
├── packages/                # 已发布、内容固定的能力包
├── candidates/              # 待验候选，不在生产进程导入
├── workspaces/              # 每项研发独立工作区
├── quarantine/              # 不可信资料或不合格候选
├── checkpoints/             # 带版本的恢复引用与摘要
├── recovery/                # 必要可用包与恢复证据，按引用留存
├── models/                  # 按需模型与许可
├── toolchains/              # 按需构建环境，非日常启动依赖
├── indexes/                 # 可重建检索缓存
└── logs/                    # 有界、脱敏、轮替
```

根控制记录和普通资料使用不同权限域；同属一个目录仍需实际 ACL/受限身份或相应平台机制。磁盘不支持所需能力时，隔离执行与恢复使用可配置受保护位置；未测试不能仅凭 NTFS 宣称隔离有效。隔离构建使用单独临时空间，不能获得生产写权。

开发实例使用测试身份与合成资料。正式接续前须核对旧经历、纠正、撤权和未决任务，建立继承映射；导入失败保留旧系统独立可用，不能靠模型编造共同经历。

<a id="project-structure-4"></a>
### 依赖规则

1. contracts 只定义协议与数据结构，不依赖业务实现。
2. modules 仅通过公开接口依赖其他模块。
3. adapters 依赖端口与 SDK；领域模块不导入适配器内部。
4. runtime 组合模块并管理生命周期，不承载全部业务逻辑。
5. apps 通过 API 操作系统，不能直接修改任务数据库。
6. 恢复代码不依赖 Python 智能框架或云模型。
7. 部分智能模块可自主生成，但受同样的接口、测试和发布约束。
8. 编译依赖和强制启动依赖不得成环；跨模块写表、生产运行中直接覆盖源码属于架构违规，CI 检查。运行时反馈循环按超时、去重与预算约束处理。

<a id="browser-desktop-selection"></a>
## 网页与桌面操控选型（2026-10-21）

**结论：Jarvis 内置工作面板，复用系统浏览器；API → DOM／可访问控件 → Windows UIA → 有界视觉补充。** 不默认嵌入另一套 Chromium，不把通用 Agent 的全部工具直接交给模型。对 Gmail，重点是正常浏览器登录、选定标签页接管、配置后使用正式 API。第三方框架的功能表不是 Google 放行承诺，也不是 Jarvis 的实测结果。以下为源码／官方文档审查，没有在同一机器上运行这些开源项目的完整基准。

<a id="browser-desktop-comparison"></a>
### 开源对比与采用方式

| 方案 | 适用性与可借鉴部分 | 代价与不足 | 对本项目的决定 |
|---|---|---|---|
| 现有 Playwright + Edge | 已有 Python 环境和有界动作底座；无需下载第二套浏览器 | 新上下文缺登录状态；固定成功条件覆盖有限；无桌面 UIA | 保留为隔离网页执行器，补专用已登录标签页适配 |
| Playwright MCP／扩展 | 可访问树、真实标签页、复用登录会话；开源 Apache-2.0 | MCP 本身不是安全边界；通用工具比 Gmail 所需权限更大；上游安装／版本仍需管理 | 借鉴标签页授予与适配接口。当前用最小专用扩展，不为单一配置任务安装整套 MCP 服务 |
| Stagehand（MIT） | 结构化观察与动作、页面变化恢复、缓存思路；适合多网站重复工作流 | SDK／浏览器版本变化快，旧 v3 与当前主分支 API 不能混用；使用模型会产生费用并涉及页面数据外发 | 通用网页规划的优先候选。当前借鉴“确定性执行＋验证后的定位适配”，不直接引入云端浏览器 |
| browser-use（MIT） | Python 生态、开放任务规划、模型选择、本地／远程浏览器 | 通用 Agent 引入自己的依赖与执行循环；行为和成本随模型、页面、步数变化；不能保证登录或验证码成功 | 可作为以后独立规划适配候选，不取代 Host 权限、预算和任务账本 |
| BrowserOS（AGPL-3.0 等） | 完整浏览器产品、MCP、多标签工作、可视化过程 | 整体引入会重复浏览器／Agent／设置体系；Chromium 分叉需持续补丁和发布。官方约 100 GB 源码、16 GB+ RAM 是**构建要求，不是用户运行内存**；分发前需单独核对各部分许可证 | 适合外部可选浏览器，不适合当前 PC 默认核心；不复制 Chromium 分叉 |
| Third Hand（MIT） | 应用 @ 定位、任务接续、先规划、候选控件筛选、执行后检查；失败才重规划，具有步数和请求大小约束 | 当前 Swift/macOS 14+/Apple Silicon；AX、Apple Vision、Keychain、arc-cua 不能直接变成 Windows UIA。使用云端规划／决策；终端命令按用户权限运行，非隔离执行 | 借鉴交互与执行循环，不整体移植或继承其命令权限；不把后台操作宣传推广到任意 Windows 软件 |
| Microsoft UFO（MIT） | Windows UIA／Win32／COM、视觉与 API 混合、应用专用执行器 | 全栈 AgentOS／Galaxy 会重复现有编排；原生 GUI 在当前用户桌面上有广泛影响；视觉与依赖开销须按选定子集实测 | Windows 驱动与应用适配的主要参考，不整套引入 Galaxy |

Third Hand 的本地感知不代表资料全部留本机：其说明将请求、应用名、控件标签／值和结果交给云端规划，歧义候选交给决策服务。Jarvis 应先按任务裁剪并排除凭据；Gmail 固定配置当前不需调用模型。

若按“当前 Gmail 配置、PC 增量成本、与现有模块复用、权限可收敛程度”做**工程适配判断**：现有底座加受限扩展最合适；Stagehand 适合后续通用网页规划；UFO 的 UIA 混合思想适合 Windows 桌面；Third Hand 适合学习计划和交互。没有同机任务成功率、时延、峰值内存数据，因此不编造百分比或综合高分。当前自研方案也有明显弱项：定位覆盖窄、安装扩展需一次手动操作、真实 Google 尚待联调、未知改版不能无人处理。

<a id="google-browser-compatibility"></a>
### Google 兼容性与能真正减少配置的路径

Google 明确禁止将 OAuth 授权请求导向开发者控制的嵌入式 user-agent；帮助文档也说明自动控制、嵌入式或不安全扩展浏览器可能被阻止登录。因此“把网页嵌入 Jarvis”“换成另一个 Chromium”“改用屏幕鼠标”均不能保证通过。不得使用隐藏自动化、复制 Cookie、验证码绕过或伪装设备作为兼容策略。

当前采用正常 Chrome／Edge：本人登录 → 点击扩展授予当前 Google Cloud 标签页 → 限定配置 → 下载桌面客户端 JSON → 现有连接器在系统浏览器执行 OAuth。扩展不申请 accounts.google.com、Cookie、debugger、全部网站权限；正常跨站导航会撤销 activeTab 临时权限。授权结束后，后续读取通过 Gmail API，无需反复操作邮箱网页。

**产品最终更简洁的方案是 Jarvis 提供已配置好的官方 OAuth 客户端**，用户只需“连接 Gmail → 登录／同意”。这需要项目维护者管理应用、域名、隐私政策以及 Google 对所用范围／发布方式的审核，不是换浏览器就能省掉。本机个人开发版暂保留自己的桌面客户端；服务账号／模型 Key 不能代替 Gmail 用户授权。独立模块保留以后替换成产品级 OAuth 的位置，不让每个用户永远承担 Cloud Console 配置。

<a id="browser-desktop-adoption"></a>
### 模块化落地、资源与升级

本轮新增 `account_setup.py`（任务、配对和有界回执）、`account_setup_recipe.py`（固定语义）、`adapters/gmail-setup-extension/`（选中标签页动作）、`account_setup_routes.py / gmail-setup.js`（内置面板）。它们与原 `mail_auth / mail_accounts` 分离：配置网页完成不等于账号已连接，最终状态以连接器实际取得的邮箱身份为准。源码自主实现，仅借鉴机制；没有复制或安装 Third Hand、Stagehand、BrowserOS、browser-use、UFO 的代码／依赖。

普通 PC 空闲时无常驻新浏览器、视觉模型、数据库服务器或网络爬虫；任务使用已有浏览器标签页，SQLite 按首次操作建立。每次步骤分配现有后台资源通道，保留前台聊天；估算 64 MiB 仅为本机桥接准入数，**不是已测量的浏览器总内存或操作系统内存上限**。动作超时释放通道并留下待核对状态。内置规则不消耗 LLM token，打开面板的本地进度查询不等于查询 Google。

后续通用桌面优化顺序：应用 API 适配 → 窗口绑定 UIA 驱动 → 控件失效重观察 → 必要时局部截图／OCR → 有界视觉动作。借鉴 Third Hand 的候选集合约束和失败重规划，借鉴 UFO 的原生 API 优先。须验证高 DPI／多屏、遮挡、自绘控件、用户抢占、UAC、权限变化与取消延迟；不能因为 UIA 能后台调用就保证任何应用不抢焦点。此部分仍 proposed，不写成 Gmail 增量已经交付的桌面能力。

来源与固定提交见[操控选型来源](references.md#browser-desktop-sources)，配置流程归[任务章](tasks-agents.md#mail-management-plan)，权限归[安全章](security-sovereignty.md#identity-authorization)。

<a id="growth-seed-layout"></a>
## 自主研发种子的新增目录与所有权

0.2.0-dev.2 的真实增量如下；后续本地设置/对话增量见[数据布局](#portable-data-runtime)。这是该版实现定位，不替代前文完整目标目录。

| 路径 | 职责/维护者 | 能否由生成候选修改 |
|---|---|---|
| control/worker/ | Win32 绑定、LPAC 启动、运行包与孤儿恢复；可信控制层 | 否 |
| control/atomic.py、control/receipts.py | 原子控制记录与插件计算回执 | 否 |
| adapters/models/ | HTTPS JSON 模型传输；仅提供者适配 | 否 |
| modules/model_gateway/routed.py | 线路/预算/调用回执与 UNKNOWN 语义 | 否 |
| modules/autonomous_development/ | 研发状态与有界修复；注入其他模块端口 | 否 |
| modules/release_recovery/ | 候选检查、不可变包、指针、观察与回退 | 否 |
| seed/skills/pure-tool-development.json | 当前编程方法与配方 | 候选不得自行改放行配方 |
| config/model-routes.json | 模型/端点/环境变量引用/限额；无密钥 | 本机配置者维护 |
| apps/workbench/ | 新只读本机 UI；独立 JS/CSS，品牌静态图像原字节复用 | 否 |
| packaging/reference-map.json | 旧参考文件定位、借鉴点与品牌摘要 | 来源信息，不运行加载 |
| user-data/worker-runtime/ | 从本机可信 CPython 准备的独立约 20 MB 运行包 | 只读 |
| user-data/worker-runs/ | 每次 Worker 临时源码/输入；执行结束清理 | 本次只读 |
| user-data/state/worker-leases/ | 暂存 SID/profile 租约；崩溃后恢复 | 否 |
| user-data/packages/ | 摘要命名的不可变源码包 | 否；新版本形成新包 |
| user-data/state/receipts/ | 原 task/action 的计算结果回执 | 否；代码回滚不覆盖 |
| docs/evidence/ | 新版本的测试、真实模型与界面证据 | 验证者维护 |

没有运行依赖 H 盘路径，没有初始化新 Git 或引入 pip/Rust 第三方依赖。旧品牌图像来源文本会出现在 reference-map 中，不是硬编码运行根。安装打包、各平台 Worker、加密资料和受保护恢复底座仍待后续实现。

<a id="portable-data-runtime"></a>
## 0.2.0-dev.3：工程内的配置与运行数据

**dev.9 增量：**`modules/task_resource/growth.py` 维护原目标与一次受限研发的关联、规格修订及来源；`host/goal_growth.py` 组合既有模块完成返回目标；`apps/workbench/goal-growth.js` 承担成长卡和用例编辑，候选审阅复用 development.js。schema 5 → 6 仅追加 `goal_growth` 和 goal_plans.planning_round；原目标、任务、身份和记忆不重建。原目标取消事务传播到子研发，原研发受理改为同事务提交授权/任务/审阅控制，避免中途失败留下孤立权限。无新增依赖、服务或线程池。旧 dev.8 Host 不识别 schema 6；能力回退不能覆盖数据版本或撤权记录。运行规则归[目标关联研发](tasks-agents.md#goal-growth-runtime)。

**dev.8 增量：**`modules/task_resource/plans.py` 维护可修改提案，`host/goals.py` 组合模型/目录与原任务；`apps/workbench/goals.js` 复用于工作台和设置。`host/background.py` 将规划与原编码工作共用一个后台模型槽，未增加线程池数量或第三方环境。核心 schema 4 → 5 仅事务追加 `goal_plans` 表，保存目标、冻结目录/路线、提案修订、取消及任务关联；任务和产物继续使用原表/目录，原身份、记忆和许可不重建。schema 5 不能交给仅支持 schema 4 的 dev.7 Host；能力包回退不回滚数据 schema 或撤销记录。详细运行规则归[目标计划](tasks-agents.md#goal-planning-runtime)。

**dev.7 增量：**`host/tools.py` 组合发布目录与持久任务，`apps/workbench/tools.js` 复用于设置页和工作台右侧。未新增存储 schema；仍为核心 schema 4，工具调用使用现有 tasks/actions/grants/release_slots。结果落在 `user-data/artifacts/<task_id>/<action_id>/result.json`；任务账本保留本次输入与结果。没有新增依赖、线程池或常驻服务；运行规则归[工具复用](tasks-agents.md#published-tool-runtime)。

**dev.6 增量：**核心数据库以事务追加升级到 schema 4，新增 `memory_usage`、`memory_candidates`、`development_controls` 与记忆代次；既有身份、授权、任务和事实不重建。对话库追加记忆引用与开关字段。新代码分别位于 `modules/context_knowledge/memory.py`、`host/memory.py`、`host/development.py` 和独立的前端 `memory.js`、`development.js`。数据仍只留本工程 user-data，未增加外部服务或数据库。schema 4 不能直接交给仅识别 schema 3 的旧 Host；纯能力包回退不回滚记忆、撤销或数据库版本。使用语义以[记忆](knowledge-learning.md#memory-workbench-runtime)、[研发](toolchains.md#development-workbench-runtime)为准。


默认数据根由程序所在工程定位到 `user-data/`，当前实际为 `D:/Jarvis/user-data/`，不依赖启动时的工作目录，也不隐式写入旧工程或用户主目录。源码与可替换程序、可变数据仍分开；安装到不可写目录时必须显式指定可写 `--data-root`，不能悄悄回退或要求管理员启动。

| 当前实际位置（相对数据根） | 内容和所有者 | 保存方式 |
|---|---|---|
| config/settings.sqlite3 | 模型目录、全局默认、备选顺序、档位、Codex 选择参数、栏目宽度、六主题和音效/动画偏好；preferences 模块 | SQLite 事务与修订比较；不存明文 Key |
| private/model-credentials.dpapi | 授权迁入的模型 API Key 和 Vertex 服务账号凭据；受信任凭据适配器 | Windows 当前用户 DPAPI 加密 |
| config/model-migration.json | 来源修订、数量、摘要与核对结果 | 无明文凭据的 JSON |
| config/model-probes.json | 本轮有限连接验收结果、时间与 token 回执 | 静态验收记录，不是后台探测开关 |
| state/dialogue.sqlite3 | 会话、项目绑定、归档/置顶/移除状态、用户/模型消息、技能快照/要求/附件、尝试回执；dialogue 模块 | SQLite 增量迁移，不重建旧正文；当前未加密 |
| state/workspace.sqlite3 | 项目路径、名称、说明、分区、置顶/移除登记；workspace 模块 | 文件内容仍留用户选定目录，不复制整个项目 |
| config/network.sqlite3 | 模型通道联网限制及修订；control 网络策略 | SQLite CAS；不修改系统网络 |
| config/extensions.sqlite3 | 本地技能/MCP 声明登记、修订与文件摘要；registry_composer | 不保存凭据正文，不执行扩展 |
| config/skills.sqlite3 | 文字技能全局启用策略；skills 模块 | 源方法登记在 seed/skills/conversation.json，不存执行代码 |
| state/、artifacts/、packages/ | 原核心身份/任务/发布账本、交付与不可变能力包 | 沿用既有控制模块的事务和恢复规则 |
| worker-runtime/、worker-runs/、temp/ | 独立 Worker 运行包、受限执行暂存、可信模型子进程临时目录 | 只在工程数据根分配；生成代码无凭据访问权 |

当前增加 `modules/preferences/`、`modules/dialogue/`、`host/dialogue.py`、`control/credentials.py` 和 `adapters/models/native*.py`；分别负责设置、会话、前台调度、凭据和供应商协议。dev.4 增加 `modules/workspace/`（项目/有界文本）、`modules/skills/`（文字指导）、`host/workbench.py`（应用组合）及 `adapters/desktop/folder_picker.py`（本人打开本机选择器）。前端拆为 app/ui/projects/model-picker/settings/brand，模块之间不直接操作对方数据库；只有 Host 组合公开方法。它们不会把旧工程模块导入进来。公开 UI 只读安全设置投影，完整凭据规则归[本地模型凭据边界](security-sovereignty.md#local-model-vault)。

dev.5 新增设置命令组合 `host/settings_operations.py`、目录编辑 `modules/preferences/management.py`、扩展登记 `modules/registry_composer/extensions.py`、费用计算 `sdk/pricing.py`、系统计数器 `adapters/desktop/resources.py` 和 `control/network.py`。核心 SQLite schema 从 2 增量到 3，仅为 model_calls 增加模型/计价快照字段；对话 attempts 增加快照列。原消息、身份、任务和发布数据不重建，旧记录缺值继续为未知。旧 dev.4 Host 不支持 core schema 3，不能直接换回旧程序读取现库；恢复应使用适配该 schema 的程序，不能覆盖数据回到旧库。

“数据在工程内”不表示 Windows 的 DPAPI 主密钥、系统日志、Python 开发工具和浏览器本身也搬到 D 盘。DPAPI 文件通常只能由同一 Windows 用户/机器解密，直接复制工程到另一台电脑不等于凭据可用。跨账户迁移、加密导出和整套备份恢复尚待实现；不得通过备份旧数据库恢复已撤回权限。应用设置及会话不用浏览器 localStorage 作为唯一存储。

<a id="session-folder-layout"></a>
## 会话专属目录与跨平台项目位置（dev.12）

**目标 accepted，代码 implemented；Windows 实测与平台模拟范围以[本次验收](delivery-validation.md#session-folder-evidence)为准。** Jarvis 面向 Windows、macOS 和 Linux 等个人电脑，不能把 D 盘、Windows Shell 或 DPAPI 当成公共模块契约。当前完整受限 Worker 与模型凭据仍依赖 Windows 适配器；新增通用目录策略不代表整套应用已通过其他系统验收。

<a id="session-folder-ownership"></a>
### 目录归属与保存格式

| 数据 | 唯一权威或实际落点 | 管理边界 |
|---|---|---|
| 项目会话文件夹 | `<项目根>/.jarvis/sessions/<chat-id>/` | 每个会话有独立稳定 ID；改项目显示名称、归档、移除不改变目录 |
| 独立会话、Jarvis 自身源码项目的会话 | `<数据根>/sessions/<chat-id>/` | 不把助手自身工作稿写进待发布源码；默认数据根仍为工程 `user-data` |
| 目录所有权 | 会话目录 `owner.json`，schema_version / chat_id / project_id | 与 workspace 登记核对；不能借外部同名目录接管另一会话 |
| 会话配置与草稿 | 会话目录 `config.json` | JSON；保存草稿、会话要求、模型 ID/档位、技能选择、记忆开关、显式文本附件。摘要比较与原子替换；冲突保留页面草稿 |
| 自然回答 | 会话目录 `replies/<request-id>.md` | 已成功生成的文本逐轮保存；文件名不取用户题目，不覆盖用户后来编辑的版本 |
| 目标任务交付 | 会话目录 `artifacts/<task-id>/<action-id>/<文件名>` | 从已确认回执核对摘要后保存；同名相同内容可重复核对，内容不同停止覆盖 |
| 会话与项目登记 | 数据根 `state/dialogue.sqlite3`、`state/workspace.sqlite3` | 前者仍是聊天和模型调用的权威记录；后者新增目录绑定与交付异常登记 |
| 任务回执、能力包、权限、密钥 | 原控制/凭据模块的位置 | 不随会话复制；原交付副本继续供中断核对，生成 Worker 不获得任意项目写入权 |

目录是组织与交付单位，不是身份认证或操作系统沙箱。`.jarvis` 不在普通项目资源树中编辑，避免编辑器误改归属；会话有独立入口查看和打开目录。选择项目不会递归读取资料、默认上传文件或将配置当作系统指令。

旧会话在进入或继续时补建目录，不批量移动原件。缺失原目录、盘未挂载或所有权变化会报错，不在另一位置悄悄新建。已成功回答/任务的集中账本仍保留；“补齐交付文件”只从已有结果恢复文件，不重新调用模型或执行工具。当前手动补齐回答覆盖会话 API 最近 100 轮；更早历史仍在数据库，完整归档导出需另行扩展。尚未提供物理删除、目录搬迁或跨设备会话目录合并。

<a id="project-location-policy"></a>
### 新建项目和测试目录策略

普通项目由主人选择父目录和新文件夹名称，或打开已有目录；不猜测工作项目应放在测试区。新建目标已存在则提示选择其他名称或打开原项目。文件夹名称使用可跨平台的受限字符集，拒绝路径跳转、驱动器语法、Windows 保留名和末尾点/空格。

| 平台 | 测试项目默认根目录 | 选择窗口与打开目录 |
|---|---|---|
| Windows | 优先已有本地固定非系统 D 盘；没有 D 则另一固定非系统盘；没有非系统固定盘才选系统盘的 `jarvisTest` | 原生 Shell 文件夹窗口，允许创建目录；系统文件管理器 |
| macOS | 优先已识别为内部可写的非系统挂载卷；没有则 `~/jarvisTest` | 系统 `choose folder`，`open` 打开目录 |
| Linux | 优先 `/media`、`/run/media`、`/mnt` 下识别为本地文件系统的可写数据挂载；没有则 `~/jarvisTest` | 已安装 Zenity 或 KDialog；`xdg-open`；无桌面时手动填写路径 |

`jarvisTest` 在选择“新建测试项目”并提交时才建立，不在启动时遍历磁盘、批量建目录或下载 GUI 工具。非系统盘存在但无法创建时报告失败，不未经说明回退系统盘。系统盘根目录无写权限时也不提权；可改用普通新建项目选择可写目录。Unix 的 `/` 不是 Windows 盘符，不能硬套 `D:` 路径；显示的是服务实际运行主机的路径。远程浏览器上的文件夹窗口属于 Host 所在机器，不是浏览器所在设备。

<a id="session-folder-components"></a>
### 模块分工与替换点

| 实现 | 职责 |
|---|---|
| `adapters/desktop/locations.py`、`folder_picker.py` | 平台位置策略、系统选择器和目录展示；可替换，不依赖对话或任务领域 |
| `modules/workspace/store.py`、`sessions.py` | 项目登记、独立目录归属、配置 CAS 和不可覆盖的交付保存 |
| `modules/dialogue/store.py` | 消息和调用记录，不导入 workspace 内部实现 |
| `host/session_workspace.py` | 组合项目、对话、已确认任务与目录；配置写入不授予执行权限 |
| `apps/workbench/projects.js`、`session-folders.js` | 项目创建窗口、会话目录面板、每会话草稿保存队列 |

依赖仍是 Python 标准库、SQLite 与当前系统已有桌面工具，没有引入常驻数据库、向量服务或浏览器自动化框架。项目移除和会话移除都只改变登记状态，恢复复用相同目录；未来增加物理删除必须先检查所有权、活动任务、引用与恢复材料，不能把“移除”扩大为递归删除。

<a id="conversation-layout"></a>
## 聊天行动与候选编码的增量结构（dev.10）

| 新增位置 | 唯一职责 | 复用原有能力 |
|---|---|---|
| `contracts/schemas/assistant-turn.v1.json` | 自然回复与有限行动建议的协议 | SDK 严格契约校验 |
| `host/assistant.py` | 聊天、目标关联及真实结果投影 | Dialogues、Goals、任务账本 |
| `host/goal_context.py` | 目标记忆视图、失效检查、同目标修订 | Memory、Grants、Plans |
| `adapters/models/codex_cli.py` | 冻结外部 CLI 的候选响应适配 | RoutedModels、原研发/发布器 |
| `apps/workbench/assistant-actions.js` | 会话里的目标、补充、取消与交付卡片 | 原右侧目标面板和记忆面板 |

core.sqlite3 schema 6 → 7：追加 goal_context、chat_goals、assistant_operations；goal_plans 追加 generation。聊天库追加 assistant_action 字段。关联目标/补充/取消与对应操作回执保持事务一致；聊天成功回复和建议同条 SQL 落盘。宿主重启不创建另一套目标或重复既有动作。

旧 schema 6 Host 不识别 schema 7，不可用旧 Host 配新数据强行回退。能力包回退仍沿用原发布器，不回退身份、撤权和记忆修订。没有新增 Python 包、Rust crate、外部数据库、常驻服务或线程池。所有本地状态仍在本工程 user-data；临时 Codex 目录位于 user-data/temp。

运行规则分别归[聊天行动](tasks-agents.md#conversation-action-runtime)、[目标记忆](knowledge-learning.md#goal-memory-runtime)和[候选编码](toolchains.md#codex-candidate-runtime)。

<a id="mcp-layout"></a>
## 连接器的独立实现位置（dev.11）

| 路径 | 职责与替换边界 |
|---|---|
| `adapters/mcp/http.py` | MCP HTTP/JSON/SSE 协议及有界传输；不写任务与许可 |
| `sdk/mcp_schema.py` | 明确声明的输入结构子集；不导入业务模块 |
| `modules/registry_composer/connectors.py` | 发现快照、工具选择、准入修订和 Registry 执行端口 |
| `host/connectors.py` | 工作台命令组合、具体调用任务、回执查看；复用原 Core/TaskRunner |
| `host/capabilities.py` | 组合已发布纯工具与获准 MCP 目录，核对固定版本 |
| `apps/workbench/connectors.js` | 选择工具、核对参数、调用和接续界面；复用原样式与弹窗 |
| `tests/mcp_fixture.py` | 无账号、无外网、无业务读写的模拟服务器，只用于验收，不随 Host 自启动 |

没有新增第三方包、容器、服务进程或独立调度线程池。底层 HTTP 适配使用按次线程，具体资源边界见[MCP 运行规则](tasks-agents.md#mcp-runtime)。更换协议适配不能绕过原任务许可和发布/恢复边界。

<a id="memory-desktop-selection"></a>
## PC 与 Mac 的综合记忆技术选型（2026-10-23，proposed）

记忆核查基线 0.2.0-dev.10：Python 标准库 sqlite3 与自有 Memory/Facts；[依赖锁](../packaging/runtime-lock.json)没有新增记忆框架包。本轮读取上游文档并固定 9 个仓库提交、已取得文件的摘要和依赖元数据，见[研究证据](evidence/memory-context-research-2026-10-23.json)。研究期间的 dev.11 MCP 交付有独立证据，未因此重跑记忆框架比较。未执行第三方框架、没有本机性能排名；包元数据版本不等于已发布稳定版本，缺失文件不是零依赖。

| 位置 | 首选 / 备选及依据 | 采用条件与代价 |
|---|---|---|
| 事实、来源、修订与队列 | SQLite；普通资料沿现有库，私密域用独立加密库 | 保留事务与单一写入 API；后台短事务，容量与忙锁单独测；无 Docker/K8s/Redis 前置 |
| 中文词项 | SQLite FTS5＋统一分词/词项预处理＋短词/标识符补查 [S87](references.md#s87) | 默认 unicode61 与 trigram 各有中文盲区；固定预处理版本，以姓名、两字词、代码、否定和数字对照 |
| 小型语义检索 | sqlite-vec 首选试验；LanceDB 为主要替代 [S306](references.md#s306) | 前者纯 C、跨平台但 pre-v1；后者嵌入式并有混合检索，但增加原生包/存储格式；只管理可重建索引。**当前实现**未引入两者，见 [ADR-031](decisions-review.md#adr-031) |
| 本地 embedding | multilingual-e5-small 作为多语基线，中文专用 BGE-small 作为中文轨对照 [S303](references.md#s303) | 仅预选，不宣称最新最强；统一切片和维度比较。固定模型 revision，验证查询前缀/池化/量化；CPU 为共同基线，ONNX 可作为运行时候选 |
| 提取/合并候选 | 最小结构化提取基线，对照 LangMem 0.0.30 与 Mem0 源码声明 2.2.1 [S307](references.md#s307) | LangMem 核心可独立于存储，但依赖 LangChain/LangGraph/模型 SDK；Mem0 整理流水线更完整，包含向量/历史管理。都须转成带原件引用候选，不直接接管事实 |
| 知识章节与按需读 | 自有小型编纂器，借鉴既有 LLM Wiki/OpenWiki 与 OpenViking L0/L1/L2 [S305](references.md#s305) | 保留证据与版本；采用思想和正式引入代码分别审查。OpenViking 主项目 AGPLv3/部分组件不同，按拟采用文件与分发方式核对许可，不默认可整体复制 |
| 完整本地替代 | EverOS 1.5.1 [S296](references.md#s296) | 当前 Markdown 原件＋SQLite＋LanceDB；Python ≥3.12，Arrow/ORM 等依赖较多。可读性好，但会改变 Jarvis 数据权威模型，需实际转换与撤销测试 |
| 完整学习/反思替代 | Hindsight 当前提交 [S297](references.md#s297) | 官方已列 Windows、Apple Silicon 与 Intel Mac 的嵌入式 pg0 路线，Intel 有包差异；不能再按“必须外置服务器”排除。仍需计入其实际进程、数据库、索引、模型与额外反思开销 |
| 后台整合与事件组织 | 借鉴 LightMem/StructMem 的分批、事件绑定 [S301](references.md#s301) | 当前 LightMem 元数据要求 Python ≥3.10,<3.12，含固定 torch 等大依赖，与本工程 Python 3.13 不同；只参考方法，隔离环境比较后才决定适配 |
| 时态关系 | 先 SQLite 实体/关系表，复杂关联失败后比较 Graphiti [S94](references.md#s94) | 图后端和可靠抽取增加成本，Kuzu 后端已弃用；关系图只是派生视图，不能裁决互相矛盾的主人事实 |
| 密钥与加密 | Windows 系统保护 / macOS Keychain；SQLCipher 或成熟对象加密 [S302](references.md#s302) | 同平台原生包、加密索引、备份与密钥恢复需验证；SQLCipher 社区源代码与商业预编译发行分别核对，不能把下载包都算免费 |

较新的编码器也进入升级对照 [S303](references.md#s303)：**EmbeddingGemma-300m** 面向设备端，官方列出 100 多种语言、2,048 token 输入、768/512/256/128 维输出；使用 Gemma 许可，下载需接受对应条款，不能归作 Apache/MIT 许可模型。**Qwen3-Embedding-0.6B** 使用 Apache 2.0 许可，支持多语/代码、32K 输入与 32—1,024 维输出，适合比较专业语义和代码召回。两者都先与小模型基线在相同短片段上比较，再测长文；长上下文上限不表示可免费处理长文。只有质量收益和实际 CPU 延迟、全部进程内存都满足既定门槛才替换主选。参数量、权重文件大小与运行内存不同，量化格式、算子支持、批量与精度须实测；EmbeddingGemma 官方特别说明激活不支持 float16，不能套用统一的半精度装载脚本。未下载或测试这些模型，不给未经测量的 RAM/显存数值。

MemPalace、A-MEM、MemOS、Cognee、Letta 保留在前面的分工表作为原文组织、关联、宿主集成或外部 Agent 对照；本轮不为“覆盖所有框架”同时接入。OpenViking 的桌面助手不等于已证明整个本地引擎在本机资源预算下运行；Hindsight 的嵌入式 API 也不等于单进程零数据库负担。先确认发行包和目标平台，再用同一负载测量。

费用拆开计算：原件/事实读写与词项检索没有模型 token；语义检索有查询编码成本；写入候选有提取/合并成本；知识编纂和反思另计；最终回答还要计实际注入上下文。框架本身的开源许可不决定运行费用。比较统一模型、重试与提取频率，区分一次建库、增量写入、每次检索和每次回答；本地模型无 API 账单也有内存、电量与延迟成本。主回答模型、提取模型与 embedding 可分别路由，外发许可覆盖全部三者。

默认只运行一个业务 Host 与必要控制入口，空闲等待事件；一个低优先级可退出的记忆 Worker 共享解析/编码资源。每类生产实现只启用一个，基准用的对照框架不常驻。模块拆分是可替换代码与进程边界，不要求每个概念都部署微服务。设备资源与延迟目标只在[验收预算](delivery-validation.md#memory-resource-envelope)维护。

<a id="memory-context-migration"></a>
## 记忆组件升级、索引重建与换机协议（proposed）

沿用[模块端口](#memory-module-adoption)与既有发布协议。数据 schema、提取器、模型权重、embedding 维度、分词器、检索融合、知识编纂器和权限策略分别版本化；运行版本不能隐式决定全部语义。

迁移步骤：冻结导出范围/依赖清单 → 生成一致快照和 outbox 水位 → 新版本在影子目录转换与建索引 → 校验记录计数/内容摘要/来源/权限/墓碑/查询结果 → 重放迁移期间增量 → 达到水位并通过保留集 → 原子切换索引清单 → 有界观察 → 退役旧索引。新旧事实管理器不能各自独立接受写入；使用唯一权威与版本化 API。磁盘不足则分批迁移或推迟，不能先删唯一可用索引/原件再赌重建成功。

旧检索器回退仍读取最新事实与撤销，不能恢复旧权限或遗忘内容。向量重算失败回到词项路径；重建去重键包含源修订和编码器版本。SQL 数据迁移采用可兼容的扩展/收缩，真正不可逆变更需可审阅维护方案和恢复材料；跨版本零停机并非任何 schema 都能保证，若需短暂只读必须明示，聊天可降级但不假报写入成功。

导出使用版本化 JSONL＋原件清单/摘要＋源映射＋必要撤销与权限；Markdown 供人阅读，不独自承担事务修订。向量可选导出但可丢弃重建。加密私密域按[恢复规则](security-sovereignty.md#memory-private-storage)另封装；默认排除模型凭据、邮箱令牌与不在范围的成员数据。

PC/Mac 共用逻辑契约，分别打包 SQLite 扩展/编码器和系统密钥适配器。Windows x64、Apple Silicon、Intel Mac 分别验证安装/冷启动/睡眠唤醒/取消/恢复；同步使用稳定逻辑 ID，由节点映射路径，不传绝对盘符作为事实身份。真实 Mac 证据缺失时标未验证，不能拿 Windows 测试替代。

<a id="local-model-layout"></a>
## 本地模型模块与资产归属

模型评价配置 `modules/local_models/assessments.json`、评分器 `assessments.py`、固定合成评测集 `retrieval-suite.json` 和执行器 `benchmark.py` 独立维护；持久测量与资源校准存于原模型状态库，权重仍不进入源码。

本地模型管理以宿主编排、领域清单、下载/推理适配三层独立组成，不添加 Kubernetes 或常驻容器集群。其运行规则只在[本地模型中心](models-offline.md#local-model-manager-runtime)维护。

```text
modules/local_models/
  catalog.json        公开来源、修订、许可证、语言/维度与文件摘要
  catalog.py          清单校验、向量空间标识
  runtime.json/.py    可选依赖锁定与只读就绪检查
  descriptor.json    组件版本、契约、状态、测试与替换边界
  assessments.json/.py  官方来源、资源规划与评分规则
  retrieval-suite.json / benchmark.py  固定多语回归集与执行器
host/local_models.py  独立管理通道、状态机与 Worker 生命周期
adapters/models/
  local_download.py          有界断点下载与摘要校验
  local_embedding_worker.py  本地 CPU 编码进程
apps/workbench/settings-local-models.js
  设置中的模型生命周期、资源与清单视图
tools/local_models.py         同一状态契约的离线恢复 CLI
tools/probe_local_models.py   真实模型、合成样本的可重复探针
tools/probe_local_model_assessments.py  校准、评测、重启保留探针
user-data/                   Git 忽略的本机运行资料
  config/local-models.sqlite3 目录、状态、修订、恢复指针、操作与分域测量记录
  local-models/<model-id>/    不可变版本对应的文件与 .part
```

下载包与推理环境分别计量。模型清单不内嵌凭据；公开源模型无需账号令牌。GitHub 分发源码、元数据、许可证链接与下载工具，权重由本机管理器取得；这是本项目分发策略，不是 GitHub 绝对不能承载任何模型。`.gitignore` 同时忽略运行目录和常见权重后缀，发布仍应检查实际暂存文件。

可选原生 Python 库只允许指定 Worker 导入；核心与 Host 保持标准库通路。`tools/check_architecture.py` 对该固定路径按依赖声明检查，不放开所有模块的任意第三方导入。管理器只使用自身独立 SQLite 状态，不耦合记忆正文表；未来有状态迁移必须保留模型指纹和恢复引用，按[自身实现替换](evolution-release.md#local-model-foundation-evolution)验证。

<a id="gmail-layout"></a>
## Gmail 模块与本地数据（1.0.0）

| 层 | 位置与职责 |
|---|---|
| 协议与纯函数 | `sdk/mail.py`：scope、有限动作、MIME、文本化、分类 |
| Google 适配器 | `adapters/mail/google.py`、`oauth.py`：固定 HTTPS、有限响应、系统浏览器 PKCE |
| 邮箱领域 | `modules/mail/store.py`：加密账号、客户端、缓存、草稿、规则、审阅与任务回执 |
| Host | `host/mailbox.py`：队列、代际核对、接续与回执；`host/mail_ai.py`：明确发起的单封分析 |
| HTTP/UI | `apps/workbench/mail_http.py`、`mailbox.js`、`mail.css`；复用身份、来源和 nonce |
| 一次迁移 | `apps/cli/migrate_gmail.py --source <旧连接库路径>`；仅在明确授权后使用 |
| 数据 | `<数据根>/private/mail.sqlite3`；默认工程 `user-data/private/mail.sqlite3`，不依赖旧项目运行 |

SQLite 仅明文索引对象 ID、种类、修订；内容、地址、令牌、client secret、草稿及请求/结果正文均经 Windows 当前用户 DPAPI 加密，独立于模型凭据、家庭私密库与知识库。原 OAuth JSON 不自动删除。

无新增第三方 Python 包或常驻数据库。读取与写入按需联网，展示与本地分类不消耗 token，明确 AI 分析才调用模型。当前加密仅 Windows verified；其他系统不降级明文，后续需平台密钥适配与真机验收。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：公共接口与数据契约](contracts.md) · [下一章：模型路由、本地模型与离线生存](models-offline.md)
<!-- book-footer:end -->
