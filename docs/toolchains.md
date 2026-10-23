# 开发环境、多语言工具链与构建

> 新工程设计基线 · 2026-10-22 · 目标/明确规则 accepted，运行方案 proposed。H 盘版本记录不构成本工程的实现或验收证据。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第四篇 · 自主成长与维护](../README.md#part-evolution) › 第 16 章

**本章导航**

- [自带开发环境与多语言自我开发平台](#development-platform)
  - [需求定义与交付形态](#development-platform-1)
  - [三环境与职责](#development-platform-2)
  - [图 E：从自编源码到正式运行](#development-platform-3)
  - [开放接口：ToolchainProvider 与 RuntimeProvider](#development-platform-4)
  - [开发包内容与初期选择](#development-platform-5)
  - [构建清单示例](#development-platform-6)
  - [真正离线与可复现](#development-platform-7)
  - [跨平台并非一个编译开关](#development-platform-8)
  - [来源证据与发布权](#development-platform-9)
  - [工具链本身的更新与退役](#development-platform-10)
- [新工程自主研发：Codex、模型与编写检查协作](#autonomous-development-providers)
  - [三种研发方式及如何选择](#development-channel-choice)
  - [桌面操作的定位、互斥与接续](#development-desktop-protocol)
  - [从需求到自有能力的完整闭环](#development-capability-loop)
- [当前自主研发实现与旧工程借鉴](#growth-development-runtime)
- [受限研发工作台与候选审阅（dev.6）](#development-workbench-runtime)
- [外部 Codex 候选生成端口（dev.10）](#codex-candidate-runtime)
<!-- book-nav:end -->

<a id="development-platform"></a>
## 自带开发环境与多语言自我开发平台



<a id="development-platform-1"></a>
### 需求定义与交付形态

**完整研发节点必须能够在断开互联网和共同体后，使用已安装开发包修改、构建、测试当前获支持的 Jarvis 实现及技能。** 新语言、新平台和新依赖可以由 Jarvis 自主选择并准备，但必须先具备对应工具链、许可、存储、目标验证条件和已有授权。它不等于所有设备预装所有编译器，也不等于网络中断时可以凭空获得缺失 SDK。

| 安装形态 | 包含内容 | 承诺 |
|---|---|---|
| 运行节点 | 已发布程序、运行时、本地模型/语音包及恢复材料 | 离线执行已支持能力；按节点等级配置 |
| 研发节点 | 运行节点 + 工具链、构建器、验证器、候选源码 | 可为已准备生态自主开发 |
| 离线研发节点 | 研发节点 + 指定版本完整依赖闭包、SDK、测试资源与离线重建记录 | 在验收矩阵内断网开发与重建 |
| 轻节点 | 交互和少量本地能力 | 不宣称拥有完整离线研发能力 |

普通 Windows PC 默认从运行节点安装开始；当前开发机可继续承担研发验证，但不代表所有用户都要安装离线研发包。进入 K3 时先为当前实现与技能准备一个所需生态，再按具体任务增加其他语言。完整离线研发能力仍须准备对应依赖闭包并验收，不能仅靠远端工具声称实现。开发包的安装成本、缓存、内存峰值和构建时间与[离线模型包](models-offline.md#local-survival)一起测量；极低资源时保留恢复、交互和已发布工具，暂停构建。部署准入遵守[普通 PC 优先规则](stack-project-layout.md#technology-selection-4)。

<a id="development-platform-2"></a>
### 三环境与职责

| 环境 | 能访问的资源 | 禁止拥有的能力 |
|---|---|---|
| 生产运行 | 已发布包、声明的运行依赖、限定业务能力 | 任意候选脚本、可写编译器目录、共享开发账户凭据 |
| 隔离构建 | 候选源码快照、只读工具链、只读缓存、有限临时空间 | 生产凭据、任意主人目录、真实设备控制、发布私钥 |
| 独立验收 | 候选产物、受保护测试、模拟或专用测试设备 | 修改通过标准、直接替换生产、自签发布权限 |

下载准备与执行构建进一步分离：受控下载器按清单和来源策略准备材料，构建环境默认无网络。编译器插件、构建后端、安装钩子和代码生成器都可以执行程序，必须从准备阶段就视为待约束工作负载。可信构建缓存只接受来源已验证的不可变对象；候选过程不能把任意文件写回可信公共缓存。

<a id="development-platform-3"></a>
### 图 E：从自编源码到正式运行

![build-and-release](diagrams/build-and-release.png)

[矢量图](diagrams/build-and-release.svg) · [可编辑图源](diagrams/build-and-release.mmd)


图中的逻辑角色可由少数服务实现，不新增一套与任务账本竞争的调度系统。BuildRequest 本身是持久任务，重试有预算；Artifact 是不可变产物。生产启动无需编译器在线，构建器损坏也不能阻止停止和恢复。

<a id="development-platform-4"></a>
### 开放接口：ToolchainProvider 与 RuntimeProvider

`ToolchainProvider` 提供：`ProbeHost`、`DescribeTargets`、`ResolvePlan`、`PrepareOfflineClosure`、`Build`、`Test`、`Package`、`ExportEvidence`。方法返回结构化状态、产物和诊断，不只返回自由文本日志。

`RuntimeProvider` 提供：`ProbeArtifact`、`Start`、`Health`、`Drain`、`Stop`、`Checkpoint`（如支持）。它负责运行已发布产物，不兼任生成源码、安装依赖或自我授权。程序不支持检查点时必须如实声明，不能自动序列化任意进程内存。

可支持的产物类型包括原生独立进程、Python/Node 包、.NET/JVM 产物、适用的 WASI 组件和 OCI 镜像。通用“命令配方”适配器负责常规生态，主力语言再增加更严格的专用适配器。选择接口兼容的实现不要求 Jarvis 本身迁移到相同语言。

加入一种新语言的准入步骤：

1. 检查工具链、目标平台、许可和系统需求，生成版本固定的工具链包提案。
2. 准备安装源与依赖闭包，在隔离环境安装；系统级安装通过受保护的有限安装接口，不将管理员权限交给研发 Agent。
3. 编译或封装最小契约样例，验证输入输出、取消、超时、日志和资源边界。
4. 在目标运行环境验收，记录支持矩阵后启用。
5. 在预算内逐步用于真实任务；失败可撤回新包，保留原有能力。

不能因为模型能生成某语言的文本，就把该语言显示为“可构建且可运行”。

<a id="development-platform-5"></a>
### 开发包内容与初期选择

| 开发包 | 随当前参考实现准备的材料 | 独立升级注意事项 |
|---|---|---|
| Rust | 锁定编译器、Cargo、目标标准库、依赖源、链接所需材料 | 版本并存；只升级编译器不会自动更新全部系统 SDK |
| Windows Native | 所需 MSVC Build Tools、Windows SDK、链接器与目标库 | 按组件布局固定；部分组件需安装或管理员服务，不能假设都可便携解压 |
| Python | 固定解释器、uv、目标平台 wheels、必要源码构建依赖 | 生产环境不使用 editable 安装，不在启动时自动改锁文件 [S50](references.md#s50) |
| Node/TypeScript | 固定 Node、pnpm、锁文件对应包、前端构建资源 | 若首期没有前端源码则可后装；当前完整构建配方需要时必须预装 |
| 通用工具 | Git、契约生成器、按需 CMake/Ninja、测试与打包工具 | 不要求每个配方都依赖全部工具 |
| 扩展生态 | Go、.NET、JDK、C/C++、Swift、其他领域语言等 | 有任务需要再准备对应包，不扩大基础常驻体积 |

优先复用各生态原有构建器。Jarvis 不自研通用编译器，也不在第一版重造 Bazel/Nix/通用包管理器。统一的是输入快照、工具链身份、执行隔离、证据和运行契约。将来需要更复杂构建缓存或远程执行时，再通过构建提供者接入成熟系统。

<a id="development-platform-6"></a>
### 构建清单示例

以下 YAML 说明字段关系；摘要为占位值，实际准入要求真实且可校验的摘要。参数以数组传递，默认不经 shell 拼接。必须使用 shell 时，配方需明确解释器、固定脚本和受控变量。

```yaml
api_version: jarvis.build/v1
build_id: build-example-001
task_ref: task-example-001
source:
  snapshot_digest: "sha256:<immutable-source-tree>"
  repository_commit: "<commit-if-available>"
  patch_digest: "sha256:<patch-or-empty-object>"
toolchain:
  provider: python
  bundle_digest: "sha256:<toolchain-bundle>"
  recipe_digest: "sha256:<reviewed-build-recipe>"
environment:
  template_digest: "sha256:<isolated-environment>"
  host: windows-x86_64
  target: windows-x86_64
  network: denied
  readable_mounts: [source, toolchain, dependency-store]
  writable_mounts: [scratch, output]
dependencies:
  lock_digest: "sha256:<lockfile>"
  closure_digest: "sha256:<all-build-and-runtime-inputs>"
  missing_policy: fail
steps:
  - executable_ref: toolchain.python
    argv: ["-m", "build", "--no-isolation", "--wheel"]
artifact:
  kind: python-wheel
  runtime_profile: python-windows-x86_64-v1
  contract_ref: jarvis.capability/v1
verification:
  targets: [windows-x86_64]
  suite_ref: capability-contract-and-heldout-v1
limits:
  cpu_cores: 2
  memory_mib: 2048
  scratch_mib: 4096
  wall_seconds: 600
authorization:
  grant_ref: maintenance-budget-example
  publication_scope: candidate-only
```

该例选择 `--no-isolation` 是在**已有外层隔离且预置构建依赖**的环境里避免隐式创建和下载依赖，不表示关闭 OS 隔离。这些资源数字只是一个小工具配方示例，不是编译完整 Jarvis 的硬件承诺。旧配方中的未锁定“最新版本”不得进入生产构建。

<a id="development-platform-7"></a>
### 真正离线与可复现

离线闭包包含：源码、补丁、锁文件、直接与传递依赖、构建期依赖、目标 SDK/sysroot、运行时、打包器、代码生成输入和测试素材。预下载模型包与编译包分别登记，不能混称“已有离线缓存”。

Cargo vendoring 可保留依赖源 [S49](references.md#s49)；pnpm fetch 可用于准备依赖，但本地 `file:` 依赖仍需另行包含 [S44](references.md#s44)；VS 离线布局只有选定组件，缺项不能在封网构建中回源补齐 [S43](references.md#s43)。因此验收必须在干净候选工作区、屏蔽宿主全局 PATH、关闭网络的环境重建。缺项返回 `MISSING_OFFLINE_DEPENDENCY`，不悄悄联网、放宽锁文件或借用生产全局安装。

区分三个结论：

- **来源可追溯：**能说明输入、构建者和输出分别是什么。
- **过程可重做：**同一配方和材料可以再次完成构建。
- **字节可复现：**独立构建得到完全相同输出摘要。

前两项不自动证明第三项。时间戳、绝对路径、签名封装和构建器行为都可能影响字节；不满足字节复现时报告差异及验证方式。发布签名可作用于已记录摘要，不用修改来源信息来“凑”一致。



<a id="development-platform-8"></a>
### 跨平台并非一个编译开关

| 构建与运行形态 | 适合 | 必须额外验证 |
|---|---|---|
| Windows 原生 | 桌面桥、服务、Windows SDK 集成 | 实际 OS/CPU、会话权限、安装与卸载 |
| Linux 原生或隔离 VM | 后端、部分模型服务、工具构建 | 内核/运行库、设备映射、模型驱动 |
| 交叉编译 | 明确目标的程序与嵌入式工具 | 目标头文件、库、链接器、ABI，以及目标设备执行 [S42](references.md#s42) |
| macOS/iOS | Apple 原生模块 | 匹配的 Mac/Xcode/SDK、目标系统与必要签名条件 [S48](references.md#s48) |
| WASI 组件 | 受限计算、格式处理、明确接口的插件 | 语言/运行时支持及宿主能力，不默认支持桌面、GPU和所有原生库 [S45](references.md#s45)[S46](references.md#s46) |
| OCI 镜像 | 可隔离打包的服务和构建环境 | 宿主平台、内核/镜像兼容、实际隔离模式；不是万能跨 OS 包 [S47](references.md#s47) |

分别记录 `built`、`contract-tested`、`target-validated`、`release-admitted`。仅交叉编译成功不能提升为“目标平台支持”。缺目标设备时保存候选并等待，不把仿真或模拟器的结果冒充实机结论。

Windows 首期优先一个明确配置的本地构建 VM 或等效隔离方案；复用快照但每次工作区隔离。Windows Sandbox 的网络、共享和映射目录选项需要明确配置，不能直接沿用默认值并宣称安全。[S51](references.md#s51) WSL 可用于便利开发，但“在 WSL 里”本身不是足以隔离恶意候选代码的判据。

<a id="development-platform-9"></a>
### 来源证据与发布权

内容哈希识别文件，构建证明说明来源，发布签名授予生产准入；三者不能互相代替。证据至少关联源码快照、工具链/环境摘要、配方、依赖闭包、构建日志、产物摘要、运行依赖清单、目标验收与测试集版本。

可借用 SLSA 的 `buildDefinition`、`resolvedDependencies`、`builder.id`、`runDetails` 和产物 subject 表达来源；使用该格式不意味着自动达到任何 SLSA 安全等级，也不证明代码无缺陷。[S41](references.md#s41)

来源记录由候选环境外的构建控制器采集，独立验收服务签发测试结果，发布控制器核对一致的产物摘要。研发 Agent 不获得发布私钥，也不能自己修改保留测试后签发“通过”。远端构建节点按授权收到必要源码；私人源码是否离机由资料策略决定。离线本地发布采用预登记信任材料，不强制联网验签；在线后再接收新撤销信息。

<a id="development-platform-10"></a>
### 工具链本身的更新与退役

生命周期：发现 → 隔离准备 → 来源/完整性验证 → 离线重建与目标验收 → 可用 → 弃用 → 撤销或删除。

每个构建固定工具链和环境摘要；新版注册不改变正在执行的构建。新旧包并存，先对同一源码建立基线对照；收益包括质量、速度、空间或支持范围，不能仅因为版本号较新而替换。

删除前检查运行时引用、未完成构建、存量任务和回退版本；不得删除最后可用的恢复或开发包。共享磁盘不足时先暂停新实验、按引用回收缓存，保留明确的恢复空间。工具链更新失败只影响候选研发，不应停止已发布业务。

工具链维护服从[主人利益最高原则、独立监督与锁存关停](security-sovereignty.md#sovereignty-shutdown)锁存。安全停机后不能以“只是在编译修复补丁”为由继续自主活动；主人授权的独立维护流程另行处理。

<a id="autonomous-development-providers"></a>
## 新工程自主研发：Codex、模型与编写检查协作

**目标 accepted，多渠道适配仍 proposed；真实模型通道的受限闭环已局部实现，见[当前研发实现](#growth-development-runtime)。** Development Orchestrator 使用统一研发提供者端口，按任务选择渠道。H 盘现有适配器只作行为与故障参考，不在 D 盘导入、复制或运行。

![自主研发渠道与能力晋升流程](diagrams/autonomous-development.png)

[SVG 放大](diagrams/autonomous-development.svg) · [唯一图源](diagrams/autonomous-development.mmd)。各渠道只交付候选，不直接批准生产部署。

<a id="development-channel-choice"></a>
### 三种研发方式及如何选择

| 渠道 | 实现方式与用途 | 结果与边界 |
|---|---|---|
| 程序化编码工具 | 独立适配 Codex CLI 或经过锁定验证的 SDK，其他编码工具按同一端口接入 | 固定候选目录，读取进度/差异/退出及提供者任务 ID；仍须独立构建验证 |
| PC 桌面操作编码工具 | Desktop Adapter 启动或识别 Codex/IDE，确认窗口与工作区，输入任务、观察进度、收集文件 | 真实桌面路径；UI 改版、焦点错误、用户输入冲突时暂停相关动作，不盲按坐标 |
| 直接调用模型 | Model Gateway 选择适合代码/上下文/多模态需要的模型，输出结构化补丁或文件清单 | 宿主校验路径、差异和依赖，再交隔离构建器；不在运行目录试跑 |
| 混合协作 | 一方分析/编写，另一方审阅，确定性工具构建/测试；原编写者修复或有界换方法 | 同一根任务、预算和证据链；多个模型一致不替代实际结果 |

选择时先筛数据许可、范围、真实工具能力、可恢复性和预算，再比较任务质量证据、费用、延迟和失败记录。主选/备选按角色和用途设置，“最合适”不固定为某型号或最大参数量。换模型重新核对用途、剩余额度和未知执行状态，不把所有可连模型每次都调用一遍。

官方已有 `codex exec` 的非交互执行、JSONL 事件与结构化输出，以及 SDK 的线程控制/恢复，可作为程序化编码通道。[S282](references.md#s282)[S283](references.md#s283) 它们不等于接管桌面 App 当前对话。GUI 专有能力或需要观察的操作仍通过桌面适配器完成。

本次查阅中，旧 `codex mcp-server` 已移除，App Server 使用自己的 JSON-RPC；集成页仍标注实验性且不支持生产负载，SDK 页则把 Python SDK 描述为 stable。必须区分具体 SDK 锁定运行时和裸 app-server 接口：首个最小适配优先固定 CLI，SDK/App Server 经独立兼容验证再采用，不笼统承诺稳定。[S284](references.md#s284) 本轮没有安装或实测新接口。

<a id="development-desktop-protocol"></a>
### 桌面操作的定位、互斥与接续

桌面通道使用有时限的输入租约，核对程序、窗口身份、工作区及输入位置；优先可访问性/UI Automation 控件，必要时截图视觉定位，每次操作前后核验。用户正在操作、锁屏、窗口变化或状态不明时等待，不抢夺输入。操作经过动作网关，目标是 Codex 不代表取得全桌面权限。

每项研发有独立候选工作区与任务关联；任务说明携带目标、范围和验收引用，但提示词不替代实际访问限制。收集代码差异、文件和真实测试结果，不以“写好了”的聊天或动画判成功。提交后中断先查询原任务/产物，不盲目换渠道重复提交。

本人登录、验证码、UAC 和服务强制授权可能仍需本人完成；Jarvis 负责导航和接续，不绕过验证。凭据留在授权代理，不能粘贴进提示或源码。GUI 只能可靠控制一个窗口时串行该通道，其他任务和直接模型可继续。UI 适配器升级同样经过隔离测试，不让未知页面自行扩大权限。

<a id="development-capability-loop"></a>
### 从需求到自有能力的完整闭环

1. **明确缺口。** 关联主人目标，查询已有能力，能组合就不另造插件。
2. **固定交付。** 明确输入输出、验收、预算、范围和未知事项；缺少业务判据时先研究/原型，不凭模型猜测签收。
3. **选择渠道。** 生成、审阅和构建分别选工具/模型；简单任务可以单一生成者配独立确定性检查。
4. **隔离编写。** 输出实现、公开测试、清单、依赖锁、文档与恢复说明；第三方代码和安装钩子遵守原供应链准入。
5. **独立检查。** 按效果类型做构建、契约、行为、回归、权限、资源、兼容与故障测试；失败返回反例，有界修复，候选不能改放行标准。
6. **发布观察。** 有效维护许可覆盖时自动准入/灰度；失败拒绝，退化按兼容条件恢复，新的事实与真实动作不回退。
7. **泛化或结束。** 有复用价值且通过其他独立场景后，移除用户/路径/账号特例，形成能力包；一次性交付可以结束而不永久安装。
8. **继续完善。** 反馈进入 SelfModel、知识与目标，替代完成后按引用退役旧能力。

| 资产类型 | 何时形成 |
|---|---|
| 知识/案例 | 有用事实、解释和失败经验，无需执行入口 |
| Skill | 可复用方法、步骤和判断条件，使用已有工具 |
| Tool / Connector | 确实缺少可观察动作或服务协议适配 |
| Workflow / 角色蓝图 | 已有能力组成稳定步骤或角色配方，无须新增执行器 |
| BotBinding | 有长期职责、通道或获准触发，不是一项临时研发任务 |
| 核心模块候选 | 需改变公共运行、状态或控制语义，走自身改造及交接条件 |

完整机制减少逐步人工指挥，但不保证任意业务都能自主实现。缺模型、工具、权限、物理条件或可靠结果检查时保留现有能力并说明缺口；有限研发失败不阻塞无关工作。隔离执行尚不可信时，只做生成与静态检查，不能以普通用户全权限试跑未知候选。关键请求/交付字段归[研发契约](contracts.md#development-work-contract)。

<a id="growth-development-runtime"></a>
## 当前自主研发实现与旧工程借鉴

**0.2.0-dev.2 implemented，范围内验证见[当前验收](delivery-validation.md#growth-seed-evidence)。** 上方架构图继续表示完整目标；本节记录其中已经接通的通道。原运行代码没有导入新工程。

| 环节 | 当前实现与实际作用 | 权威边界 |
|---|---|---|
| 规划 | `modules/model_gateway/routed.py` 经模型适配器取得严格 JSON 开发计划 | 计划描述本次纯工具的实现步骤，供编码者使用；不能扩大能力编号或宿主既定执行流程 |
| 编写与有界修复 | `modules/autonomous_development/service.py` 调用模型输出最多 8 个 Python 文件；失败返回类型摘要后最多按规格再试 | 真实生成而非预写样板；不自动安装依赖，不开放任意仓库编辑 |
| Skill 方法 | `seed/skills/pure-tool-development.json` 提供配方、可用库、接口与输出规范 | Skill 不是执行器、授权方或验收器 |
| 独立验证 | 宿主持有冻结的验收输入/期望值，Worker 返回实际输出，宿主逐项比较 | 不采纳模型自报通过；没有调用第二个模型也可构成独立确定性检查，不能宣称独立语义审稿 |
| 执行器 | Windows LPAC + Job，一次有界调用，多文件候选只在此处导入 | 不是普通 subprocess/提示词充当沙箱；平台隔离限制见安全章节 |
| 发布与交付 | 不可变包 → 检查 → 切换指针 → 灰度 → 原任务使用 → 保存结果 | 发布权仍在宿主有效维护许可内；恢复不恢复旧权限/记忆 |
| Codex / 桌面 | 核对了本机 CLI 0.142.1 和当前官方非交互文档 | dev.2 时尚无执行器；dev.10 已接原生 CLI 候选端口，桌面仍未接入 |

**主备与预算。** dev.2 示例线路使用 Qwen 主选与 Qwen 备选，真实首例由主选完成；dev.3 迁入后使用[本地模型设置](models-offline.md#portable-model-settings)的默认与备选，测试替身另行验证明确拒绝后的备选、UNKNOWN 后不自动重发和持久调用预算。每次调用有输入字节上限、输出 token 上限、墙钟期限与调用次数上限；保存供应商实际 token 回执。reservation 是保守额度记录，cost_units 是本地动作/调用次数，均不是人民币金额。缺少价格和确定用量时记录未知，不声称已实现硬货币上限。

**借鉴清单。**

| 旧来源，只读参考 | 采用的经验 | 在新工程中的改进 |
|---|---|---|
| 旧 coding_workflow 与编码 Skill 方法 | 固定入口/样例、生成者不能修改验收、失败有界修复 | 研发状态、模型调用回执、包发布各自独立模块；不把领域工作流直接塞进宿主 |
| 旧 coding_codex | 编码工具只提供候选；版本、工具事件、未知回执必须核查 | 新模型适配器不读取 Codex 私有 token、不复制旧账号；dev.10 已实现 Codex CLI 候选端口 |
| 旧 Windows Worker 与准备工具 | LPAC、Job、匿名管道、只读 staging、无网络、GUI Python 入口避免控制台子进程 | 新 Win32 绑定独立实现，新增本工程孤儿租约恢复；实际隔离按新反例重新验证 |
| 旧发布/任务故障经验 | 先记录、再动作；未知结果不盲重发；代码回退不恢复业务资料 | 包指针与提交记录同一 SQLite 事务，保留修订比较、固定任务绑定与旧包引用检查 |
| 旧工作台和品牌 | 认可的机器人 J 星图像、侧栏切换、右区、顶栏图标、状态动画 | 视觉资产与业务运行依赖分开，采用[新工作台映射](interaction-persona.md#workbench-reference-implementation) |

源文件定位及品牌摘要登记在 `packaging/reference-map.json`，只作来源信息，不是运行加载路径。本版没有引入旧 Skill 的第三方许可证代码或把其整套依赖搬入。当前独立实现仍需持续安全审查；本轮测试不能证明不存在漏洞或病毒。


<a id="development-workbench-runtime"></a>
## 受限研发工作台与候选审阅（dev.6）

0.2.0-dev.6 以新 Host/API 连接已实现的受限研发模块，独立重写旧工作台的交互语义。新入口在“编码协作”和“成长中心 → 进化”，同一模块负责两处显示，不复制研发状态机。dev.9 另提供[目标缺口到关联研发](tasks-agents.md#goal-growth-runtime)：规格与用例可先由模型建议，核对后冻结，并复用本节执行和候选审阅通路；样本交付后自动返回原目标重新规划。独立用例对后续编码模型不可见，不表示其最初从未由规格模型生成。

| 步骤 | 确定性行为 | 模型参与与边界 |
|---|---|---|
| 冻结需求 | 填写目标、plugin 能力名、行为契约、公开示例、独立案例和实际输入 | 独立案例只留本机；UI 不假设模型能替主人确定任意需求的正确标准 |
| 限定授权 | 明确提交表单时，为本次能力建立有限时效与次数的授权；创建尚不调用模型 | 仅模型生成、受限构建、此能力发布和结果产物；不授予桌面、任意文件、Shell 或依赖安装 |
| 用途路由 | 规划与编码各选首选/一个备选、模型与档位，冻结在本次记录 | 已知拒绝/无效可尝试备选，远端未知结果不自动重发；费用快照继续沿用模型章 |
| 开始 | 一个研发线程，独立于两个聊天线程和任务批次 | 使用明确开始时的网络许可，同时受核心停止、模型网络开关、授权撤销及预算控制 |
| 候选与检查 | 支持多个 Python 文件；固定契约与独立输入由 LPAC Worker 执行 | 不将候选导入 Host；不存在“模型说通过就通过” |
| 待审阅 | 已验证包保持 VERIFIED，尚不切换活动能力 | 页面展示规划、各文件源码和回执；批准绑定精确包摘要，变更包不能继承旧批准 |
| 发布与交付 | 批准后继续原任务，启用灰度包、执行实际输入并保存结果文件 | 仍核对范围、时限及授权；已完成任务重复继续不重复生成或交付 |
| 停止与接续 | 取消同时撤销本次授权；等待可继续，未知调用需明确承认可能重复计费后重试 | 关闭页面不取消后台任务；服务中断不把未知远端结果当失败后自动重放 |
| 回退与停用 | 发布管理沿用版本 CAS、灰度探测、失败隔离、旧版本回退和引用阻止退役 | 这里管理的是已验证纯文本能力包，不是任意核心、模型或有状态数据库的热替换 |

本次限额为最多 1–3 轮候选、2–8 次模型调用、30–1,800 秒（包含人工审阅等待）。共享授权预算按模型调用、验证与执行保留单位，不是美元或人民币硬上限。失败/时限不会重置已花预算。模型路由配置及输入冻结在任务中；已发出请求仍可能计费。

**范围仍为纯文本能力。** 发布后的能力可由已有任务契约调用；dev.6 页面提供首次输入的实际交付与回执；dev.7 已补[本地工具目录与新输入调用](tasks-agents.md#published-tool-runtime)，它不等同于把任意代码自动认定为文字 Skill。dev.10 已接[外部 Codex 候选生成](#codex-candidate-runtime)；桌面研发、任意业务软件构建、主动选题和自动判断业务验收标准仍未接通，不把旧偏好存在当作执行器存在。

研发成功后的代码复用由[已发布工具任务](tasks-agents.md#published-tool-runtime)承接，不复用或延长研发许可，也不重复创建执行注册表。

<a id="codex-candidate-runtime"></a>
## 外部 Codex 候选生成端口（dev.10）

**implemented：0.2.0-dev.10。** `adapters/models/codex_cli.py` 实现与原生模型相同的候选生成端口，只可作为研发的“编码”路线；规划仍使用已配置模型。默认沿用已迁入的 Codex 模型/档位偏好，真实账号认证由已安装的 Codex CLI 自己管理，不复制 H 盘旧桥接器或读取、转存其私有登录令牌。

| 环节 | 实现 | 边界 |
|---|---|---|
| 发现 | 查找本机原生 codex.exe，核对版本并冻结二进制 SHA-256 | 缺失/升级后不能静默使用未冻结的新程序；不自动下载安装 |
| 调用 | 非交互 exec、JSONL 回执、严格输出 schema、临时目录、临时会话 | 不控制用户正在操作的桌面，也不修改 Jarvis 工程 |
| 权限 | read-only、approval_policy=never；忽略用户配置和规则；禁用 Shell、统一执行、浏览器、图像读取/生成、MCP 来源的插件/应用、子 Agent 与 hooks | 提示词不是隔离证明；CLI 是被信任的外部程序，这不等同于给整个 CLI 提供已验证的 OS 文件读取沙箱 |
| 回执 | 只接受最终候选 JSON；若出现命令、写文件、MCP、搜索、协作工具事件则拒绝候选 | 事后事件检查不能撤销外部程序已经造成的效果，不因此宣称能安全运行恶意 CLI |
| 预算 | 每次启动纳入既有 model_calls；独立保留输入/输出 token 用量 | Codex 账号订阅/额度不同于 API 余额；当前金额无可靠计价时不编造费用 |
| 停止与恢复 | 超时、撤权、应用离线检查点终止本机子进程；候选等待上限 180 秒 | 远端结果/费用可能未知；未知不自动换模型重发 |
| 已知拒绝重试 | 修复本机登录或启动问题后，可显式允许原路线再次尝试 | 旧调用记录保留，仍消耗原总预算；不能拿重试扩大权限或重置次数 |
| 后处理 | 候选经过既有静态准入、LPAC Worker 公共/留出用例、精确版本审阅、灰度与交付 | Codex 没有发布权，所有编码渠道经过同一发布器 |

当前验证本机原生 CLI 为 0.163.0-alpha.11.1；旧记录中的 npm CLI 0.142.1 是另一可执行入口，不能混用其支持参数。真实联调曾因 `tools.view_image` 配置键不被此版本接受而拒绝启动，现按实际 CLI 使用 `view_image` 功能开关，并保留失败账本。参数设计参考 [官方 exec 文档](https://learn.chatgpt.com/docs/developer-commands#codex-exec)；实际可用字段以冻结二进制的帮助与真实结果核对。

本轮一次成功的 Codex 调用报告输入 12,172、输出 368 token；CLI 自身上下文也有开销，不能把短提示长度当作账单或宣称必定比直接模型 API 便宜。当前由用户选择编码路线，不把所有简单工作自动交给它。

外部 CLI 随需启动，结束后清理本轮临时目录，不增加第三方 Python 包、数据库、服务或常驻模型。桌面 Codex 操控、任意仓库改写、自动依赖安装、供应链签名更新仍未由本端口实现。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：自主进化、外部编码协作与版本发布](evolution-release.md) · [下一章：系统健康、防退化与自愈](health-maintenance.md)
<!-- book-footer:end -->
