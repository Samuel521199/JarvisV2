# 研究资料与证据边界

> 新工程设计基线 · 2026-10-22 · 目标/明确规则 accepted，运行方案 proposed。H 盘版本记录不构成本工程的实现或验收证据。

<!-- book-nav:start -->
[工程主入口](../README.md) › [第五篇 · 验证与参考](../README.md#part-evidence) › 第 24 章

**本章导航**

- [研究资料与证据边界](#references)
- [论文与研究文章](#references-1)
- [官方工程资料](#references-2)
- [证据使用说明](#references-3)
- [架构评审、构建与自维护依据](#references-4)
- [0.1.0 实施选型依据（2026-10-15）](#implementation-sources)
- [0.1.1 提供商错误处理依据](#chat-error-sources)
- [0.1.2 模型目录与参数迁移依据（2026-10-15 核验）](#model-catalog-sources)
- [0.1.3 推理级别依据（2026-10-15 核验）](#reasoning-control-sources)
- [0.1.4 Google Pro 与主流型号依据（2026-10-15 核验）](#google-catalog-sources)
- [知识与记忆开源选型依据（2026-10-15 核验）](#memory-selection-sources)
- [运行预检与控制实现的官方依据（2026-10-15 核验）](#preflight-sources)
- [Eachlabs Claude 小额调用依据（2026-10-16 核验）](#eachlabs-claude-sources)
- [模型后台价格依据（2026-10-16 核验）](#model-billing-sources)
- [Codex 工作台与交互参考（2026-10-15 核验）](#codex-workbench-sources)
- [宿主上下文与模型回答完整性（2026-10-16 核验）](#runtime-context-sources)
- [Grok Build 源码评审依据（2026-10-16 核验）](#grok-build-sources)
- [记忆组件与 OpenWiki 源码复核（2026-10-16）](#memory-component-audit-sources)
- [扩展接入格式依据（2026-10-16 查阅）](#extension-interface-sources)
- [本地运行与结构化规划依据（2026-10-16 查阅）](#local-runtime-sources)
- [进程资源计数依据（2026-10-17 查阅）](#process-metric-sources)
- [工作台布局参考（2026-10-16 查阅）](#workbench-layout-sources)
- [编码技能与模型选择依据（2026-10-17 查阅）](#coding-skill-sources)
- [科普动画与机械拆解的固定源码依据（2026-10-17）](#anatomy-sources)
- [常用 MCP 来源（2026-10-17 查阅）](#mcp-server-sources)
- [当前架构审计的补充依据（2026-10-17 查阅）](#current-audit-sources)
- [语音主选与候补的来源（2026-10-18 查阅）](#voice-selection-sources)
- [记忆与 Wiki 方法扩展复核（2026-10-18）](#memory-pattern-review-sources)
- [REA 软件解析来源（2026-10-18）](#rea-sources)
- [对话、语音与任务分离的工程依据（2026-10-18 查阅）](#conversation-isolation-sources)
- [编码协作与离线工具包依据（2026-10-19）](#codex-coding-sources)
- [生活助手身份、凭据与轻量调度参考（2026-10-21）](#personal-life-sources)
- [邮件与日历文件处理依据（2026-10-21）](#correspondence-sources)
- [QQ 与 Gmail 连接依据（2026-10-21）](#mail-account-sources)
- [网页与桌面操控选型来源（2026-10-21）](#browser-desktop-sources)
- [邮件管家权限、同步与草稿依据（2026-10-21）](#mail-management-sources)
- [可组合 Agent 框架的工程依据（2026-10-22）](#composition-sources)
- [连续身份与可替换实现的设计依据（2026-10-22）](#continuity-sources)
- [自主研发与 Codex 程序化接入依据（2026-10-22）](#autonomous-development-sources)
- [旧工程资料与交接边界](#legacy-project)
- [受限自主研发实现参考（2026-10-22）](#growth-runtime-sources)
- [本地凭据与原生模型协议依据（2026-10-22）](#native-model-sources)
- [MCP 子集实现依据（2026-10-23）](#mcp-runtime-sources)
- [综合记忆与桌面端选型复核（2026-10-23）](#memory-context-sources)
- [Charakuru 工作流与 Blender 适配来源（2026-10-28）](#charakuru-blender-sources)
- [3D 查看与资产检查来源（2026-10-23）](#studio3d-viewer-sources)
- [Gmail 官方接口与授权依据（2026-10-25）](#gmail-sources)
- [桌面常驻伙伴参考（2026-10-25）](#desktop-companion-sources)
- [Grok Bot 功能、界面与运行机制研究（2026-10-26）](#grok-bot-research-sources)
- [Harness² 与多机器人主脑研究来源（2026-10-26）](#harness2-research-sources)
- [经验成长、知识治理与退化控制的研究依据（2026-10-26）](#learning-compounding-sources)
- [微信通道与桌面协作来源（2026-10-30）](#weixin-integration-sources)
- [单机开发、共享与 A/B 更新来源（2026-10-30）](#single-pc-development-sources)
<!-- book-nav:end -->

<a id="references"></a>
## 研究资料与证据边界

资料核查日期：2026-10-15。论文用于支持具体机制，官方文档用于核对组件和平台约束。本设计没有将任何论文基准成绩等同于 Jarvis 的实测能力。

<a id="references-1"></a>
## 论文与研究文章

| 编号 | 来源 | 本文使用范围 |
|---|---|---|
| <a id="s01"></a>[S01](https://www.inkandswitch.com/essay/local-first/) | Kleppmann 等，Local-first software: You own your data, in spite of the cloud，2019 | 本地数据所有权、离线工作与多设备协作原则 |
| <a id="s02"></a>[S02](https://dsf.berkeley.edu/cs286/papers/crdt-tr2011.pdf) | Shapiro 等，A comprehensive study of Convergent and Commutative Replicated Data Types，2011 | 可收敛复制数据结构及其适用条件 |
| <a id="s03"></a>[S03](https://www.comp.nus.edu.sg/~gilbert/pubs/BrewersConjecture-SigAct.pdf) | Gilbert、Lynch，Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services，2002 | 网络分区时强一致与可用性的限制 |
| <a id="s04"></a>[S04](https://raft.github.io/raft.pdf) | Ongaro、Ousterhout，In Search of an Understandable Consensus Algorithm，2014，扩展版 | 领导者、日志复制和多数派 |
| <a id="s05"></a>[S05](https://static.usenix.org/events/osdi06/tech/full_papers/burrows/burrows_html/) | Burrows，The Chubby lock service for loosely-coupled distributed systems，2006 | 锁、租约和执行端 sequencer 验证 |
| <a id="s07"></a>[S07](https://arxiv.org/abs/2305.16291) | Wang 等，Voyager: An Open-Ended Embodied Agent with Large Language Models，2023 | 自动课程、代码技能库与执行反馈；限于论文环境 |
| <a id="s08"></a>[S08](https://arxiv.org/abs/2303.11366) | Shinn 等，Reflexion: Language Agents with Verbal Reinforcement Learning，2023 | 通过语言反馈与记忆改进尝试，无需权重更新 |
| <a id="s09"></a>[S09](https://arxiv.org/abs/2405.15793) | Yang 等，SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering，2024 | Agent 工具界面与软件工程任务 |
| <a id="s10"></a>[S10](https://www.anthropic.com/engineering/multi-agent-research-system) | Anthropic，How we built our multi-agent research system，2025 | 协调、分工、上下文、产物与多 Agent 成本取舍 |
| <a id="s28"></a>[S28](https://arxiv.org/abs/2304.03442) | Park 等，Generative Agents: Interactive Simulacra of Human Behavior，2023 | 角色记忆、反思、计划与小镇模拟，不能证明无限扩展 |
| <a id="s31"></a>[S31](https://arxiv.org/abs/2310.08560) | Packer 等，MemGPT: Towards LLMs as Operating Systems，2023 | 分层记忆与有限上下文管理 |
| <a id="s32"></a>[S32](https://arxiv.org/abs/2507.03724) | MemOS: A Memory OS for AI System，2025 | 记忆资源、来源、版本和生命周期的研究框架 |
| <a id="s34"></a>[S34](https://www.anthropic.com/research/prompt-injection-defenses) | Anthropic，Mitigating the risk of prompt injections in browser use，2025 | 外部内容风险、分层防御与未解决边界 |
| <a id="s36"></a>[S36](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html) | Saltzer、Schroeder，The Protection of Information in Computer Systems，1975，基本原则部分 | 默认拒绝、逐次检查、最小权限等设计原则 |

<a id="references-2"></a>
## 官方工程资料

| 编号 | 来源 | 本文使用范围 |
|---|---|---|
| <a id="s06"></a>[S06](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | AWS Builders' Library：Making retries safe with idempotent APIs | 意图编号、参数匹配与安全重试 |
| <a id="s11"></a>[S11](https://docs.langchain.com/oss/python/langgraph/persistence) | LangGraph：Persistence | 线程检查点与长期存储区分 |
| <a id="s12"></a>[S12](https://docs.temporal.io/worker-versioning) | Temporal：Worker Versioning | 工作流版本绑定与新旧 Worker 并存 |
| <a id="s13"></a>[S13](https://protobuf.dev/programming-guides/proto3/#updating) | Protocol Buffers：Updating a Message Type | 协议演进和字段兼容规则 |
| <a id="s14"></a>[S14](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) | Kubernetes：Deployments | 滚动更新、就绪、历史和回滚边界；不是首期必选技术 |
| <a id="s15"></a>[S15](https://docs.litellm.ai/docs/routing) | LiteLLM：Router | 路由、重试、冷却和 fallback |
| <a id="s16"></a>[S16](https://modelcontextprotocol.io/specification/2026-07-28) | MCP Specification，2026-07-28 | 工具互操作协议；实施时固定版本 |
| <a id="s17"></a>[S17](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | llama.cpp server README | 本地模型服务能力及部署接口 |
| <a id="s18"></a>[S18](https://k2-fsa.github.io/sherpa/onnx/index.html) | sherpa-onnx 官方文档 | 本地语音能力与平台支持 |
| <a id="s19"></a>[S19](https://docs.livekit.io/agents/logic/turns/) | LiveKit：Turns overview | 轮次检测和打断机制 |
| <a id="s20"></a>[S20](https://tauri.app/concept/process-model/) | Tauri：Process Model | 桌面界面进程边界 |
| <a id="s21"></a>[S21](https://www.sqlite.org/wal.html) | SQLite：Write-Ahead Logging | 本机事务、持久性和网络文件系统限制 |
| <a id="s22"></a>[S22](https://learn.microsoft.com/en-us/windows/desktop/services/interactive-services) | Microsoft：Interactive Services | Windows 服务与交互桌面的限制 |
| <a id="s23"></a>[S23](https://developer.apple.com/documentation/backgroundtasks/choosing-background-strategies-for-your-app) | Apple：Choosing Background Strategies for Your App | 移动端后台运行约束 |
| <a id="s24"></a>[S24](https://developer.android.com/about/versions/oreo/background) | Android：Background Execution Limits | 移动端后台运行约束；具体当前版本另行实测 |
| <a id="s25"></a>[S25](https://developers.home-assistant.io/docs/api/websocket/) | Home Assistant：WebSocket API | 设备状态事件与服务调用 |
| <a id="s26"></a>[S26](https://docs.nats.io/concepts/jetstream) | NATS：JetStream | 可选持久消息基础设施 |
| <a id="s27"></a>[S27](https://opentelemetry.io/docs/what-is-opentelemetry/) | OpenTelemetry：What is OpenTelemetry? | 追踪、指标与日志互操作 |
| <a id="s29"></a>[S29](https://docs.ray.io/en/latest/ray-core/scheduling/resources.html) | Ray：Resources | 逻辑资源调度与物理隔离的区别 |
| <a id="s30"></a>[S30](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) | Kubernetes：Horizontal Pod Autoscaling | 依据指标扩缩副本；不自动提供任务语义和预算控制 |
| <a id="s33"></a>[S33](https://microsoft.github.io/graphrag/index/overview/) | Microsoft GraphRAG：Indexing Overview | 可配置索引、实体关系与派生摘要 |
| <a id="s35"></a>[S35](https://www.openpolicyagent.org/docs) | Open Policy Agent：Documentation | 策略决策和执行分离，不构成语义安全证明 |
| <a id="s37"></a>[S37](https://design.ros2.org/articles/node_lifecycle.html) | ROS 2：Managed Nodes | 外部监督下的生命周期，不等于物理安全认证 |

<a id="references-3"></a>
## 证据使用说明

Local-first 和 CRDT 支持数据组织思路，不能证明共享记忆产生真实意识。
- 多 Agent 与自动编程论文说明特定任务中的有效机制，不能保证所有任务或任意自主代码正确。
- 框架文档说明功能接口，不能代替在目标硬件上的兼容、性能和故障测试。
- 本文关于双路径恢复、模块拆分、版本治理和阶段目标是结合这些依据形成的工程建议。
- 最终是否达标，以[验收标准与故障演练](delivery-validation.md#acceptance)规定的真实场景和故障验收为准。

<a id="references-4"></a>
## 架构评审、构建与自维护依据

<a id="s38"></a>[S38](https://c4model.com/diagrams) C4 架构视图。
- <a id="s39"></a>[S39](https://martinfowler.com/bliki/MonolithFirst.html) Martin Fowler：Monolith First。
- <a id="s40"></a>[S40](https://sei.cmu.edu/documents/196/1998_019_001_29711.pdf) CMU SEI：Architecture Tradeoff Analysis Method。
- <a id="s41"></a>[S41](https://slsa.dev/spec/v1.2/build-provenance) SLSA v1.2：Build Provenance。
- <a id="s42"></a>[S42](https://clang.llvm.org/docs/CrossCompilation.html) Clang：Cross-compilation。
- <a id="s43"></a>[S43](https://learn.microsoft.com/en-us/visualstudio/install/install-vs-inconsistent-quality-network) Microsoft：Visual Studio 离线安装布局。
- <a id="s44"></a>[S44](https://pnpm.io/cli/fetch) pnpm：fetch。
- <a id="s45"></a>[S45](https://docs.wasmtime.dev/security.html) Wasmtime：Security。
- <a id="s46"></a>[S46](https://component-model.bytecodealliance.org/language-support.html) WebAssembly Component Model：语言支持。
- <a id="s47"></a>[S47](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/version-compatibility) Microsoft：Windows 容器版本兼容。
- <a id="s48"></a>[S48](https://developer.apple.com/xcode/system-requirements) Apple：Xcode 系统与 SDK 要求。
- <a id="s49"></a>[S49](https://doc.rust-lang.org/cargo/commands/cargo-vendor.html) Cargo：vendor。
- <a id="s50"></a>[S50](https://docs.astral.sh/uv/concepts/projects/sync/) uv：锁定与同步。
- <a id="s51"></a>[S51](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file) Microsoft：Windows Sandbox 配置。
- <a id="s52"></a>[S52](https://www.erlang.org/doc/system/sup_princ.html) Erlang/OTP：Supervisor Behaviour。
- <a id="s53"></a>[S53](https://docs.temporal.io/workflow-definition) Temporal：Workflow Definition。

- <a id="s54"></a>[S54](https://learn.chatgpt.com/docs/non-interactive-mode) OpenAI：Codex 非交互模式。
- <a id="s55"></a>[S55](https://learn.chatgpt.com/docs/codex-sdk) OpenAI：Codex SDK。
- <a id="s56"></a>[S56](https://evolutionaryarchitecture.com/precis.html) Building Evolutionary Architectures：作者概要。
- <a id="s57"></a>[S57](https://github.com/seddonym/import-linter/blob/main/docs/contract_types/layers.md) Import Linter：Layers 合约。

<a id="implementation-sources"></a>
## 0.1.0 实施选型依据（2026-10-15）

以下是本次接口与模型选型的官方依据。精确本地文件版本、许可指针、大小和 SHA-256 由 [模型清单（旧工程参考）](references.md#legacy-project)维护；来源说明能力或接口，不证明本机准确率、生产隔离或所有商业使用权。

| 编号 | 来源 | 本次使用范围 |
|---|---|---|
| <a id="s58"></a>[S58](https://developers.openai.com/api/docs/guides/text) | OpenAI Text generation | Responses 接口、输出项解析 |
| <a id="s59"></a>[S59](https://developers.openai.com/api/docs/models/gpt-5.6-luna) | OpenAI gpt-5.6-luna | 成本敏感的文本探测候选；账户列表可见不等于生成已成功 |
| <a id="s60"></a>[S60](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-flash-lite) | Google Gemini 3.1 Flash-Lite | 模型 ID、global 支持、MINIMAL thinking |
| <a id="s61"></a>[S61](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) | 阿里百炼 OpenAI 兼容 | Chat Completions、模型和区域配置；基址另见[官方说明](https://help.aliyun.com/zh/model-studio/base-url) |
| <a id="s62"></a>[S62](https://docs.x.ai/developers/rest-api-reference/inference/chat) | xAI Chat REST | 请求与响应格式 |
| <a id="s63"></a>[S63](https://x.ai/news/grok-4-1-fast) | xAI Grok 4.1 Fast | non-reasoning 模型选择 |
| <a id="s64"></a>[S64](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a) | Qwen 官方 GGUF | 0.6B Q8_0 与固定发布文件 |
| <a id="s65"></a>[S65](https://huggingface.co/FunAudioLLM/SenseVoiceSmall/tree/3847d57b6bdf2dd8875cb1508d2af43d80a16bf7) | FunAudioLLM SenseVoiceSmall | 原始模型能力、模型许可；转换版另由清单固定 |
| <a id="s66"></a>[S66](https://huggingface.co/csukuangfj/icefall-tts-aishell3-vits-low-2024-04-06/tree/57345c004e13ed640e408c4c29ab56187b18f065) | sherpa 发布者 AISHELL3 VITS low | 小型中文预置声音合成模型 |
| <a id="s67"></a>[S67](https://modelscope.cn/models/iic/speech_campplus_sv_zh-cn_16k-common) | ModelScope CAM++ 中文声纹模型 | 说话人特征；不提供主人身份授权结论 |
| <a id="s68"></a>[S68](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) | Microsoft CryptProtectData | 当前 Windows 用户 DPAPI 加密与适用边界 |
| <a id="s69"></a>[S69](https://github.com/ggml-org/llama.cpp/releases/tag/b11617) | llama.cpp b11617 | 固定 CPU 运行包、发布摘要；不追随 latest |
| <a id="s70"></a>[S70](https://github.com/snakers4/silero-vad) | Silero VAD 官方仓库 | 语音活动检测；实际 ONNX 文件与摘要见清单 |

<a id="chat-error-sources"></a>
## 0.1.1 提供商错误处理依据

| 编号 | 来源 | 本次使用范围 |
|---|---|---|
| <a id="s71"></a>[S71](https://developers.openai.com/api/docs/guides/error-codes) | OpenAI Error codes | 区分余额/账单额度、429 限流、认证及服务错误；不能把所有 429 当余额耗尽 |
| <a id="s72"></a>[S72](https://help.aliyun.com/zh/model-studio/error-code) | 百炼错误码 | Arrearage 等账户异常与参数/限流错误 |
| <a id="s73"></a>[S73](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/api-errors) | Google API errors | RESOURCE_EXHAUSTED 可表示配额或共享容量不足，响应本身不等于余额证明 |

<a id="model-catalog-sources"></a>
## 0.1.2 模型目录与参数迁移依据（2026-10-15 核验）

| 编号 | 来源 | 使用范围 |
|---|---|---|
| <a id="s74"></a>[S74](https://developers.openai.com/api/docs/models) | OpenAI API model catalog | GPT-6 Astra、6.1 Sol、6 Luna 和 6 Sol 的官方 ID；账户生成状态另看本地实测 |
| <a id="s75"></a>[S75](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart) | OpenAI GPT-6 migration | Astra/6.1 Sol 不支持 none；Responses、推理参数兼容；未启用供应商内置工具 |
| <a id="s76"></a>[S76](https://docs.x.ai/developers/models/grok-4.7) | xAI Grok 4.7 | 精确 ID、low/medium/high/xhigh 推理档位 |
| <a id="s77"></a>[S77](https://help.aliyun.com/zh/model-studio/text-generation-model) | 百炼文本模型 | Qwen3.8 Max/Flash、Qwen3.7 Plus、思考开关；区域和账户状态需实测 |
| <a id="s78"></a>[S78](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash) | Google Gemini 3.8 Flash 迁移 | global、LOW/MEDIUM/HIGH、移除 candidateCount 与 MINIMAL |
| <a id="s79"></a>[S79](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/4-argon) | Google Gemini 4 Argon | 模型 ID、global 和思考档位；本原型只接文字能力 |

<a id="reasoning-control-sources"></a>
## 0.1.3 推理级别依据（2026-10-15 核验）

| 编号 | 来源 | 使用范围 |
|---|---|---|
| <a id="s80"></a>[S80](https://help.aliyun.com/zh/model-studio/deep-thinking) | 百炼深度思考 | Qwen 混合思考的 enable_thinking 开关；商业模型支持非流式，输出与 reasoning_content 区分 |
| <a id="s81"></a>[S81](https://developers.openai.com/api/docs/models/gpt-6-astra) | OpenAI 模型页 | Astra 的 low 至 max；另核对 [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)、[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol)、[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) 的各自枚举；GPT-5.6 Luna 见 S59 |

<a id="google-catalog-sources"></a>
## 0.1.4 Google Pro 与主流型号依据（2026-10-15 核验）

| 编号 | 来源 | 使用范围 |
|---|---|---|
| <a id="s82"></a>[S82](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-pro) | Gemini 3.1 Pro | 精确 preview ID、global、发布阶段和中等思考档位 |
| <a id="s83"></a>[S83](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite) | Gemini 3.5 Flash-Lite | 当前 Lite 选型、模型 ID、GA、四个 thinking 档位 |
| <a id="s84"></a>[S84](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/migrate) | Google 当前模型迁移表 | Argon、Pro、各 Flash 分支的阶段和能力比较，不是本机质量测试 |
| <a id="s85"></a>[S85](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) | Google Cloud 模型生命周期 | Vertex 的 2.5 系列及 3.6/3.7 Flash 退役时间；不混用 Developer API 日期 |
| <a id="s86"></a>[S86](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking) | Google Thinking | 按模型支持的级别与 thought signature 限制；当前仅验证纯文字聊天 |

<a id="memory-selection-sources"></a>
## 知识与记忆开源选型依据（2026-10-15 核验）

本组依据官方仓库、文档和模型卡；主分支和许可证会变化，表中是本次网页核验，不是已安装的版本锁。正式接入前固定 tag/commit、依赖与模型 revision；选型结论是本项目工程判断，不是这些项目对 Jarvis 的背书。未采用商业托管成绩作为开源实现或本机效果证据。

| 来源 | 核验范围 | 使用限制 |
|---|---|---|
| <a id="s87"></a>[S87](https://www.sqlite.org/fts5.html) | SQLite FTS5 的 unicode61、trigram、MATCH 与 LIKE/GLOB 限制 | 用于解释本地中文探测；不是中文语义召回基准 |
| <a id="s88"></a>[S88](https://github.com/asg017/sqlite-vec) | C 扩展、向量类型、部署形式、MIT/Apache-2.0、pre-v1 提示 | 不推断未测索引能力、吞吐或跨节点复制 |
| <a id="s89"></a>[S89](https://github.com/lancedb/lancedb) | LanceDB OSS 嵌入式检索、Lance 数据层、Apache-2.0 | 区分 OSS、Cloud 与 Enterprise，不把数据版本当多主语义 |
| <a id="s90"></a>[S90](https://qdrant.tech/documentation/distributed_deployment/) | Qdrant 分片/复制、集群元数据与读写语义；另见[安装约束](https://qdrant.tech/documentation/installation/)和[许可](https://github.com/qdrant/qdrant/blob/master/LICENSE) | 稳定集群不等于经常离线的个人设备网络 |
| <a id="s91"></a>[S91](https://github.com/pgvector/pgvector) | pgvector 精确/近似检索、过滤与迭代扫描、PostgreSQL License | 需测过滤后的召回和服务运维成本 |
| <a id="s92"></a>[S92](https://github.com/chroma-core/chroma) | Chroma OSS 本地/服务端接口与 Apache-2.0 | collection 接口本身不提供主人事实的修订和同步规则 |
| <a id="s93"></a>[S93](https://github.com/mem0ai/mem0) | Mem0 记忆库、自托管与托管区分、默认模型配置、Apache-2.0 | README 将部分新基准归于托管专有优化；不移植其成绩 |
| <a id="s94"></a>[S94](https://github.com/getzep/graphiti) | 时态关系、图后端要求、Kuzu 弃用、小模型结构输出限制、Apache-2.0 | 图关系提取仍需核验；不提供事实真伪保证 |
| <a id="s95"></a>[S95](https://github.com/letta-ai/letta) | Letta V1 server 归档与[Letta Code](https://github.com/letta-ai/letta-code) 当前路径、记忆块/文件系统与本地后端、Apache-2.0 | 不沿用旧服务端架构假设，不把 Cloud 多机等同离线共同体 |
| <a id="s96"></a>[S96](https://github.com/topoteretes/cognee) | Cognee 文档/代码/对话知识处理、本地模型路线、Apache-2.0 | 本地运行声明不证明本机中文效果或多主复制 |
| <a id="s97"></a>[S97](https://github.com/MemTensor/MemOS) | MemOS 自托管、Cloud 和 Agent 本地插件的不同入口、Apache-2.0 | 资源比较需选同一部署形态；插件不等于通用 Jarvis 模块 |
| <a id="s98"></a>[S98](https://github.com/volcengine/OpenViking) | 目录式上下文、L0/L1/L2、[当前主许可](https://github.com/volcengine/OpenViking/blob/main/LICENSE) AGPLv3 与 README 的分组件/改写说明 | 不作许可效力判断；选用前核对具体版本与组件，不能沿用旧 Apache-only 假设 |
| <a id="s99"></a>[S99](https://automerge.org/docs/hello/) | Automerge 离线合并与同步；[代码库](https://github.com/automerge/automerge)为 MIT | CRDT 收敛不替代权限、独占行动或矛盾事实判断 |
| <a id="s100"></a>[S100](https://www.sqlite.org/wal.html) | SQLite WAL 的同主机共享内存限制；[Public Domain 声明](https://www.sqlite.org/copyright.html) | 不支持把活跃 WAL 文件直接交由云盘多机同步 |
| <a id="s101"></a>[S101](https://docs.couchdb.org/en/stable/replication/conflicts.html) | CouchDB 复制冲突、winning revision 与应用解决冲突责任 | 可见修订不是事实裁决；没有免除应用冲突处理 |
| <a id="s102"></a>[S102](https://huggingface.co/BAAI/bge-small-zh-v1.5) | BGE 中文小嵌入模型、参数/维度、MIT | 官方模型卡不是量化后本机中文/代码测试 |
| <a id="s103"></a>[S103](https://huggingface.co/intfloat/multilingual-e5-small) | E5 多语言小模型、384 维、512 token、用途前缀、MIT；核验[原始模型卡](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md) | 运行包和分词/截断配置需另行固定 |
| <a id="s104"></a>[S104](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Qwen 嵌入模型维度可调、上下文、多语言、Apache-2.0 | 输出降维不等于权重按比例缩小；不是当前聊天模型 |
| <a id="s105"></a>[S105](https://github.com/xiaowu0162/LongMemEval) | LongMemEval 长期记忆问答评估；[论文](https://arxiv.org/abs/2410.10813) | 不能代替中文、权限、离线复制与故障注入测试 |
| <a id="s106"></a>[S106](https://github.com/snap-research/locomo) | LoCoMo 长对话记忆数据和任务；[论文](https://arxiv.org/abs/2402.17753) | 不将单轮公开成绩或模型裁判评分当整个系统可靠性 |

<a id="preflight-sources"></a>
## 运行预检与控制实现的官方依据（2026-10-15 核验）

| 来源 | 核验范围 | 使用限制 |
|---|---|---|
| <a id="s107"></a>[S107](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls) | `icacls` 显示 DACL 与授权操作 | 预检只读；0.1.7 Worker 仅对自己创建的运行包/暂存授予只读执行权限，不改用户输入目录 ACL |
| <a id="s108"></a>[S108](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/whoami) | `whoami /user` 的当前账户及 SID 查询 | 只代表调用进程身份，不推断其他服务或 Worker 身份 |
| <a id="s109"></a>[S109](https://cryptography.io/en/46.0.4/hazmat/primitives/asymmetric/ed25519/) | Ed25519 生成、签名、验证和密钥序列化 API | 0.1.6 历史恢复实现参考；0.1.14 已移除恢复密钥/签名流程。依赖仍由模型认证组件使用，不能据此声称当前有恢复认证 |
| <a id="s110"></a>[S110](https://www.sqlite.org/lang_attach.html) | ATTACH 多库事务在 WAL 模式下的原子性边界 | 当前控制库独立提交，业务注释允许随后对账；不声称两个 WAL 数据库有跨库原子提交 |
| <a id="s111"></a>[S111](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer) | LPAC 创建、profile、能力与注册表初始化要求 | 原生机制依据，不替代本机有效权限试验或完整沙箱审计 |
| <a id="s112"></a>[S112](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | Job 进程组和关闭终止；[限额定义](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information) | 本机 CPU 自动终止没有得到预期证据，改用 Host 主动计时；Job 不保护 Host 自身 |
| <a id="s113"></a>[S113](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) | Windows 进程 user/kernel CPU 计时 | 主动轮询需要 Host 响应，不是独立实时监督 |
| <a id="s114"></a>[S114](https://developers.openai.com/api/docs/guides/tools-computer-use) | OpenAI Computer Use：模型、结构化动作、代码工具、截图反馈与应用负责执行 | 官方接法不证明 Jarvis 已接入；Codex 产品内部实现不由此推断 |
| <a id="s115"></a>[S115](https://ai.google.dev/gemini-api/docs/computer-use) | Gemini 3.8 Flash 的 Computer Use 与浏览器/桌面接口 | Gemini API 示例不等于已有 Vertex 服务账号已验证可用 |
| <a id="s116"></a>[S116](https://github.com/QwenLM/Qwen3-VL) | Qwen3-VL 模型规格与 GUI agent/computer-use 示例 | 小型离线候选尚未下载和在本机验收 |
| <a id="s117"></a>[S117](https://github.com/QwenLM/open-computer-use/blob/main/README.md) | 开源 MCP 电脑操作服务与 Windows UI Automation 实现 | 可借鉴的适配器，不是 Jarvis 的权限边界或已安装功能 |
| <a id="s118"></a>[S118](https://playwright.dev/python/docs/browsers) | Playwright 系统 Edge channel、浏览器 sandbox；[网络路由](https://playwright.dev/python/docs/network)、[Route API](https://playwright.dev/python/docs/api/class-route) 的重定向行为 | 本项目锁定 1.64.0；路由不是 OS 防火墙，重定向拒绝和生命周期仍须真实测试 |
| <a id="s128"></a>[S128](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex) | Windows 物理可用内存和当前进程提交余量；[读取 API](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex)、[进程计数](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex) | 快照易变；不能视为实际预留、浏览器限额或其他进程峰值 |
| <a id="s129"></a>[S129](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule?view=windowsserver2022-ps) | Windows 防火墙 Program、Outbound、Block 与配置文件范围 | 本机探测只为临时包的 4 个可执行文件设规则，实测阻断并清理；不是整机断网或 Host 安全隔离 |
| <a id="s130"></a>[S130](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1) | Start-Process 的 RunAs、WindowStyle 与参数传递 | 通过正常 UAC 提权固定防火墙脚本；不能根据桌面应用身份推定工具子进程已有管理员权限 |
| <a id="s131"></a>[S131](https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.notifyicon) | Windows Forms NotifyIcon 的图标、悬浮文字、右键菜单、双击与释放 | 0.1.18 使用系统组件实现轻量托盘；图标所在的常显/隐藏区域由 Windows 设置决定，不等同于完整桌面壳 |
| <a id="s132"></a>[S132](https://learn.microsoft.com/en-us/dotnet/api/system.threading.eventwaithandle.openexisting) | 打开已存在的命名事件 | 本实例桌面退出信号；命名对象不代表对同一 OS 用户代码的安全隔离，也不新增密码或恢复认证 |

<a id="eachlabs-claude-sources"></a>
## Eachlabs Claude 小额调用依据（2026-10-16 核验）

| 来源 | 核验范围 | 使用限制 |
|---|---|---|
| <a id="s133"></a>[S133](https://platform.claude.com/docs/en/models/overview) | Anthropic 当前 Opus/Sonnet/Haiku 5.5、Fable 5.1 与原生模型 ID | 官方可用不等于中转或本账号已成功调用 |
| <a id="s134"></a>[S134](https://docs.eachlabs.ai/llm-router/models) | Eachlabs 模型 ID、每百万 token 标价与 5.5% 平台费；结合[实际上游目录](https://openrouter.ai/api/v1/models) | 静态价格是估计依据，最终以逐笔结算为准 |
| <a id="s135"></a>[S135](https://docs.eachlabs.ai/llm-router/quickstart) | Eachlabs Bearer Key、`https://api.eachlabs.ai/v1`、Chat Completions 和 SSE usage | 兼容协议不代表所有参数、工具和停止语义已通过 |
| <a id="s136"></a>[S136](https://docs.eachlabs.ai/llm-router/model-catalog) | 精选目录及 canonical provider/target；[实际目录](https://api.eachlabs.ai/v1/llm-router/model-catalog) | 非精选 OpenRouter 模型按文档可请求；目录与返回型号不是上游权重证明 |
| <a id="s137"></a>[S137](https://docs.eachlabs.ai/openapi_specs/models.json) | 聊天响应、按时间/模型查询 `/v2/executions`；[余额说明](https://docs.eachlabs.ai/llms.txt) | 余额可能延迟；执行 `success` 不等于返回了有效文本；本轮分别检查正文、结束原因、usage 与成本 |

<a id="model-billing-sources"></a>
## 模型后台价格依据（2026-10-16 核验）

| 来源 | 使用范围 | 限制 |
|---|---|---|
| <a id="s138"></a>[S138](https://developers.openai.com/api/docs/pricing) | OpenAI Standard 输入、输出、缓存读写与 272K 档位 | 不套用 Codex 订阅积分或 Fast/Batch 价格 |
| <a id="s139"></a>[S139](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing) | Google 全局文本调用、推理 Token、限期价格和返还说明 | Vertex 与 Developer API 分开；返还不作为即时扣款 |
| <a id="s140"></a>[S140](https://help.aliyun.com/zh/model-studio/model-pricing) | 百炼北京文本原价和输入阶梯 | 缓存价格、地区与账户优惠需分别核对 |
| <a id="s141"></a>[S141](https://docs.x.ai/developers/pricing) | Grok 4.7 短上下文输入、缓存和输出 | 其他型号没有借用此价格，区域加价不默认套用 |
| <a id="s142"></a>[S142](https://platform.claude.com/docs/en/about-claude/pricing) | Claude 原生价格和缓存项 | Eachlabs 附加费与路由由 [S134](#s134) 及真实小额探测约束 |

<a id="codex-workbench-sources"></a>
## Codex 工作台与交互参考（2026-10-15 核验）

本组用于[Jarvis 工作台设计](interaction-persona.md#desktop-workbench)。已搜索并阅读官方原页；界面布局同时参考用户本轮提供的 Windows Codex 新会话截图，截图只支持对可见区域的描述。表中资料不能证明 Jarvis 已实现这些能力，也不证明用户安装的 Codex 已启用官方列出的每项功能。官网包含 ChatGPT 桌面、Codex、Work、网页、CLI 等不同 surface，引用时按原页适用范围解释。

| 编号 | 官方资料 | 使用范围与限制 |
|---|---|---|
| <a id="s119"></a>[S119](https://learn.chatgpt.com/docs/projects) | Projects and chats | 本地文件夹、主目录、附属目录、会话组织和搜索；项目同步不等于完整目录上传 |
| <a id="s120"></a>[S120](https://learn.chatgpt.com/docs/environments/git-worktrees) | Worktrees | 新会话工作树、分支与交接；以已有 Git 为条件，不推导为打开普通文件夹必须初始化 Git |
| <a id="s121"></a>[S121](https://learn.chatgpt.com/docs/features) | Features | 发现插件、语音、浏览器、长任务、计划任务和 dots 等能力范围；目录存在不等于全部可在本机使用 |
| <a id="s122"></a>[S122](https://learn.chatgpt.com/docs/reference/settings) | Settings | 发送键、跟进方式、外观、快捷键、通知、隐私入口与记忆；不据此推断未公开的内部实现 |
| <a id="s123"></a>[S123](https://learn.chatgpt.com/docs/reference/commands) | Commands | Windows 打开文件夹、新聊天、文件树/搜索、模型、终端与布局快捷入口；部分命令要求对应功能可用 |
| <a id="s124"></a>[S124](https://learn.chatgpt.com/docs/reference/slash-commands) | Slash commands | 输入区命令发现与技能入口；Jarvis 的候选命令须由自己的能力注册决定 |
| <a id="s125"></a>[S125](https://learn.chatgpt.com/docs/artifacts-viewer) | Work with files | 文件产物预览、标注和修订；格式支持与宿主有关 |
| <a id="s126"></a>[S126](https://learn.chatgpt.com/docs/code-review) | Code review | PR 的描述、差异、检查和评审流程；查看评审不等于已经发布评论或合并 |
| <a id="s127"></a>[S127](https://learn.chatgpt.com/docs/browser) | Browser | 内置浏览器、标签分屏、批注、配置与网站权限；浏览器访问不等于网页内容可信 |

Jarvis 专属入口来自本项目的需求和领域设计，不通过缺少竞品文档来证明竞品没有相应功能。后续实施前应重新核对官方页面和实际安装行为；本组是调研时点的参考，不能作为永久功能清单。

<a id="runtime-context-sources"></a>
## 宿主上下文与模型回答完整性（2026-10-16 核验）

| 来源 | 核验范围 | 使用限制 |
|---|---|---|
| <a id="s143"></a>[S143](https://developers.openai.com/api/docs/guides/text) | Responses 的 instructions；[推理与输出预算](https://developers.openai.com/api/docs/guides/reasoning)中 incomplete / max_output_tokens | 上下文提示不保证遵从；没有正文也可能有用量 |
| <a id="s144"></a>[S144](https://ai.google.dev/api/generate-content) | 原生 systemInstruction、候选 finishReason | Vertex 的本机服务账户连通性另以本轮实测为证 |
| <a id="s145"></a>[S145](https://platform.claude.com/docs/en/api/messages/create) | Messages 的 system 和 stop_reason | 当前原生字段仅回归覆盖；不据此声称本轮对 Anthropic 原生接口做了真实调用 |

<a id="grok-build-sources"></a>
## Grok Build 源码评审依据（2026-10-16 核验）

所有链接固定到用户指定 fork 的同一提交；完整对照与统计方法见[技术栈章（旧工程参考）](references.md#legacy-project)。这是源码审阅证据，不是上游运行测评或 Jarvis 接入完成证明。

| 来源 | 固定版本源码 | 使用范围与限制 |
|---|---|---|
| <a id="s146"></a>S146 | [快照 README](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/README.md)、[SOURCE_REV](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/SOURCE_REV)、[Cargo workspace](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/Cargo.toml)、[依赖锁](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/Cargo.lock)、[Rust 工具链](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/rust-toolchain.toml)；[LICENSE](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/LICENSE)、[第三方声明](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/THIRD-PARTY-NOTICES)、[工具来源](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-tools/THIRD_PARTY_NOTICES.md) | 核对版本、源码构建平台、静态依赖范围与复用声明；计数来自本地解析，不是运行性能，未执行安装/构建。 |
| <a id="s147"></a>S147 | [SessionActor](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/acp_session.rs)、[工具流接口](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/common/xai-tool-runtime/src/tool.rs)、[并行派发](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs)、[路径锁](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_dispatch.rs)、[压缩](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/compaction.rs)、[子 Agent 深度](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-tools/src/implementations/grok_build/task/mod.rs)、[角色/人格](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-subagent-resolution/src/config.rs)、[派发测试](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/acp_session_tests/parallel_dispatch_tests.rs) | 会话/工具/角色及有界子任务的实现参考；未运行测试，路径锁的局部机制不代表完整并发/跨平台安全审计。 |
| <a id="s148"></a>S148 | [文件状态](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-workspace/src/session/file_state.rs)、[检查点](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-workspace/src/session/checkpoint_store.rs)、[Workspace 依赖](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-workspace/Cargo.toml)、[沙箱 apply](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-sandbox/src/lib.rs) | 检查点持久开关、缓存恢复和平台降级；源码明确 tracker 重建尚未接线，不能称完整重启回退已验证；非 Unix 分支不应用该沙箱。 |
| <a id="s149"></a>S149 | [实验记忆模块](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/lib.rs)、[混合检索](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/search.rs)、[Backend](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/backend.rs)、[Schema](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/schema.rs)、[Embedding](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/embedding.rs)、[Dream](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/src/dream.rs)、[依赖](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-memory/Cargo.toml) | FTS5/向量降级、MMR/衰减、整理门槛和依赖边界；未证明中文质量、离线嵌入、事实纠正或共同体同步。 |
| <a id="s150"></a>S150 | [headless 指南](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md)、[ACP Agent 实现](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/agent/mvp_agent/acp_agent.rs) | 结构化输出、恢复、轮数、工具筛选与 ACP；allowlist 不自动移除 MCP meta-tools；账号/模型权限及本机执行须另验。 |
| <a id="s151"></a>S151 | [技能发现](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-agent/src/prompt/skills.rs)、[插件信任](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-agent/src/plugins/trust.rs)、[Hook 旧信任迁移](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-hooks/src/trust.rs) | 多来源发现、元数据/执行分离、可信目录迁移；外部仓库文件是待解析数据，不因此成为 Jarvis 的授权规则。 |
| <a id="s152"></a>S152 | [Sampling 无 I/O 类型层](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-sampling-types/src/lib.rs)、[API backend 枚举](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-sampling-types/src/types.rs)、[Sampler 配置](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-sampler/src/config.rs) | 请求/协议/认证解耦参考；支持协议不证明所有供应商、模型与计费都已可用，不证明已有 Jarvis Key 能登录此产品。 |
| <a id="s153"></a>S153 | [本机 Leader](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/leader/mod.rs)、[Remote sandbox](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/remote/agent.rs)、[会话存储](https://github.com/Samuel521199/grok-build-fork/blob/8adf9013a0929e5c7f1d4e849492d2387837a28d/crates/codegen/xai-grok-shell/src/session/storage/mod.rs) | 本机多客户端、远端执行和会话回放的范围；不能据此证明多主离线事实合并、撤回传播或现实任务所有权。 |

<a id="memory-component-audit-sources"></a>
## 记忆组件与 OpenWiki 源码复核（2026-10-16）

本组固定到所读提交，不把未来默认分支变化当成本次证据。许可栏和依赖声明用于筛选；集成时仍需检查实际分发包、传递依赖及 NOTICE。静态文件摘要与解析结果见 [memory-source-audit-2026-10-16.json（旧工程参考）](references.md#legacy-project)，未运行候选框架。

| 来源 | 固定源码或原始论文 | 支持的结论与限制 |
|---|---|---|
| <a id="s154"></a>S154 | Mem0 `0724291b`：[依赖](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/pyproject.toml)、[Memory 实现](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py)、[原生提示](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/configs/prompts.py)、[Qdrant adapter](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/vector_stores/qdrant.py)、[遥测](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/telemetry.py)；[PyPI 2.2.1](https://pypi.org/project/mem0ai/2.2.1/)、[官方配置](https://docs.mem0.ai/open-source/configuration) | SDK 组合职责、V3 ADD-only 主路径、过滤参数、local path 与默认遥测；本机固定 wheel 的实验另见[实测记录（旧工程参考）](references.md#legacy-project)。托管分数边界见 [S93](#s93)，不据源码直接证明准确率 |
| <a id="s155"></a>S155 | MemOS `a7367d07`：[本地插件](https://github.com/MemTensor/MemOS/blob/a7367d07e55db61099f7b4e2c1108bc5831a24f3/apps/memos-local-plugin/README.md)、[依赖](https://github.com/MemTensor/MemOS/blob/a7367d07e55db61099f7b4e2c1108bc5831a24f3/apps/memos-local-plugin/package.json) | Node、本地 core / adapter、原生 SQLite 与推理依赖；与完整服务路线区分 |
| <a id="s156"></a>S156 | Graphiti `d50741d1`：[依赖与 extras](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/pyproject.toml)、[说明](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/README.md) | 图后端选择、小模型结构化提取限制；不把 FalkorDBLite 列为已经在本机通过 |
| <a id="s157"></a>S157 | Hindsight `3234aca5`：[README](https://github.com/vectorize-io/hindsight/blob/3234aca57d93d4cac9743b96ef5f7a4677d4389a/README.md)、[API slim 依赖](https://github.com/vectorize-io/hindsight/blob/3234aca57d93d4cac9743b96ef5f7a4677d4389a/hindsight-api-slim/pyproject.toml)、[API 包](https://github.com/vectorize-io/hindsight/blob/3234aca57d93d4cac9743b96ef5f7a4677d4389a/hindsight-api/pyproject.toml)、[官方存储说明](https://hindsight.vectorize.io/developer/storage) | retain/recall/reflect 方向与 PostgreSQL / pg0、扩展依赖；官方不提供可任意换后端的通用存储抽象，不能宣称 SQLite 可直接替换 |
| <a id="s158"></a>S158 | Cognee `f154b32a`：[依赖](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/pyproject.toml) | 广泛的解析/图/向量/推理依赖；声明数不代表实际内存 |
| <a id="s159"></a>S159 | Letta Code `1297870b`：[依赖](https://github.com/letta-ai/letta-code/blob/1297870b0aa6662d6c70729d273f5073c1bcbdea/package.json)、[说明](https://github.com/letta-ai/letta-code/blob/1297870b0aa6662d6c70729d273f5073c1bcbdea/README.md) | Agent 运行环境与记忆能力应区分；不是 Jarvis 的轻型记忆存储依赖 |
| <a id="s160"></a>S160 | OpenWiki `7c469e59`：[README](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/README.md)、[package](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/package.json)、[MIT LICENSE](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/LICENSE) | Node / 宿主集成 / 独立 CLI 的能力边界；只读检索与模型生成区别，默认遥测可关闭。不把安装说明作为 Windows 实测 |
| <a id="s161"></a>S161 | 同一 OpenWiki 提交：[Claim 类型](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/claims/core/types.ts)、[版本解析器](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/claims/evidence/repository/resolver.ts)、[持久化](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/claims/brains/code/store.ts) | 带版本证据、行范围定位和声明修订；来源未变不代表声明含义已被独立证明 |
| <a id="s162"></a>S162 | 同一 OpenWiki 提交：[检索](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/retrieval/wiki.ts)、[workspace 关联](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/linking/wiki-workspaces.ts)、[检索工具](https://github.com/langchain-ai/openwiki/blob/7c469e59584bfac3f97f5c32a67604de46805999/src/integrations/core/retrieval-tools.ts) | 调用内 FTS5、章节渐进读取、跨 Wiki 发现；不等于多设备同步、中文召回或隔离验收 |
| <a id="s163"></a>S163 | [EverMemBench：Evaluating Long-Horizon Memory for Multi-Party Collaborative Dialogues](https://arxiv.org/abs/2602.01313)，核验 v3，2026-03-11 | 多参与者、多组长期协作记忆评测方向；补足只看单人问答的局限，不能直接套作 Jarvis 跑分 |

<a id="extension-interface-sources"></a>
## 扩展接入格式依据（2026-10-16 查阅）

| 来源 | 官方规范 | 本次使用范围与限制 |
|---|---|---|
| <a id="s164"></a>S164 | [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | 采用 stdio 与 Streamable HTTP 两种连接描述；该版本的 HTTP 传输取代旧 HTTP+SSE。登记与后续受限 Context7 适配依据；实际支持子集和验证范围见文档工具契约 |
| <a id="s165"></a>S165 | [Agent Skills Specification](https://agentskills.io/specification) | 技能源以含 SKILL.md 的目录管理，支持日后按需读取关联资源；当前未实现完整 frontmatter 校验、脚本执行或技能自动选择 |

<a id="local-runtime-sources"></a>
## 本地运行与结构化规划依据（2026-10-16 查阅）

| 来源 | 官方资料 | 使用范围与限制 |
|---|---|---|
| <a id="s168"></a>S168 | [llama.cpp b11617 server](https://github.com/ggml-org/llama.cpp/blob/b11617/tools/server/README.md) | 固定版本的 --offline、CPU/上下文/序列参数及 schema-constrained response_format；应用/引擎选项不是 OS 外联隔离，JSON 形状也不保证意图分类正确 |
| <a id="s169"></a>S169 | [Windows UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)、[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | PROC_THREAD_ATTRIBUTE_JOB_LIST 在创建时绑定 Job；生命周期回收不等同于 AppContainer 或权限隔离 |

<a id="process-metric-sources"></a>
## 进程资源计数依据（2026-10-17 查阅）

| 来源 | 官方资料 | 使用范围与限制 |
|---|---|---|
| <a id="s170"></a>S170 | [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)、[GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) | 读取已知进程的工作集/私有提交与内核/用户 CPU 时间，使用 QUERY_LIMITED_INFORMATION；接口不提供 Jarvis 整个进程树用量，也不证明机器性能达到目标 |

<a id="workbench-layout-sources"></a>
## 工作台布局参考（2026-10-16 查阅）

| 来源 | 官方资料 | 使用范围与限制 |
|---|---|---|
| <a id="s166"></a>S166 | [VS Code Custom Layout](https://code.visualstudio.com/docs/configure/custom-layout) | 独立主/副侧栏、视图切换、显隐与布局恢复作为交互依据；未复制其实现或声称 Jarvis 具有完整停靠、编辑器分组能力 |
| <a id="s167"></a>S167 | [Codex Commands — Keyboard shortcuts](https://learn.chatgpt.com/docs/reference/commands#keyboard-shortcuts) | 文件树切换、聊天/标签切换、full/split/hidden 视图作为产品参考；Jarvis 快捷键兼顾浏览器宿主，不承诺与 Codex 每项相同 |

<a id="coding-skill-sources"></a>
## 编码技能与模型选择依据（2026-10-17 查阅）

| 来源 | 原始资料 | 使用范围与限制 |
|---|---|---|
| <a id="s171"></a>S171 | Matt Pocock 固定提交 `49dd158d` 的[插件清单](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/.claude-plugin/plugin.json)、[MIT 许可](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/LICENSE)、[实验目录说明](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/in-progress/README.md) | 插件 27 项与全树 38 项的分发范围；许可与静态文件统计，不证明运行质量 |
| <a id="s172"></a>S172 | 同一提交的[TDD](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/tdd/SKILL.md)、[排错](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/diagnosing-bugs/SKILL.md)、[代码审阅](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/code-review/SKILL.md)、[整规格实现](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/implement-spec/SKILL.md)、[初始化](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/setup-matt-pocock-skills/SKILL.md) | 工作流、测试确认、并行 Agent、Git 和文档前提；本轮未调用这些技能 |
| <a id="s173"></a>S173 | OpenAI [Build skills](https://learn.chatgpt.com/docs/build-skills) | 元数据发现、按需正文/参考读取、repo scope 与调用策略；Codex 支持不等于 Jarvis 已支持 |
| <a id="s174"></a>S174 | OpenAI [模型选择](https://learn.chatgpt.com/docs/models#recommended-models)、[推理档位与工具协议](https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort) | Sol/Astra/Luna 工作定位与 Responses 工具要求；不能代替当前账户访问及实际编码对照 |
| <a id="s175"></a>S175 | Eachlabs [模型与价表](https://docs.eachlabs.ai/llm-router/models) | 所读页面中的 Sonnet/Opus 5.5 ID 与公布 Token 价格；未证明所有兼容参数可用、实时余额或旧型号继续可用 |

<a id="anatomy-sources"></a>
## 科普动画与机械拆解的固定源码依据（2026-10-17）

| 来源 | 原始资料 | 使用范围与限制 |
|---|---|---|
| <a id="s176"></a>S176 | Anatomy 固定提交 `e9488296a44211c42701ff71705b7901470ec78f` 的 [README](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/README.md)、[Skill](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/SKILL.md)、[MIT LICENSE](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/LICENSE) | 包内容、ESM/HTML 与可选 React、按需依赖、许可和创作方法；支持现有 Agent 格式不等于 Jarvis 已支持 |
| <a id="s177"></a>S177 | 同一提交的 [3D 指南](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/references/3d.md)、[3D 构建](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/kit/turn-build.mjs)、[几何审计](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/kit/audit.mjs) | 凸形部件、运动/投影与采样审计限制；不构成 CAD/CAE、机械性能或科学真实性证明 |
| <a id="s178"></a>S178 | 同一提交的 [capture](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/scripts/capture.mjs)、[drive](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/scripts/drive.mjs)、[turn-check](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/scripts/turn-check.mjs)、[CI](https://github.com/wheresryan22/anatomy/blob/e9488296a44211c42701ff71705b7901470ec78f/.github/workflows/ci.yml) | 浏览器检查、失败判定和上游 CI 范围；本机试跑及异常退出码实证只在[验收章（旧工程参考）](references.md#legacy-project)维护，不当作 Jarvis 集成通过 |

<a id="mcp-server-sources"></a>
## 常用 MCP 来源（2026-10-17 查阅）

来源修订、维护/归档状态和许可元数据保存在[评估记录（旧工程参考）](references.md#legacy-project)。下列资料只支持用途与配置选型，不证明本机安装、账户可用或真实调用成功。

| 来源 | 维护者资料 | 使用范围与限制 |
|---|---|---|
| <a id="s179"></a>S179 | [Upstash Context7](https://github.com/upstash/context7) | 库匹配与版本文档查询、HTTP 端点及 Key 建议；后端服务并非全部开源 |
| <a id="s180"></a>S180 | [GitHub MCP](https://github.com/github/github-mcp-server) | 远程仓库工具与认证；实际账户/仓库权限另验 |
| <a id="s181"></a>S181 | [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) | 浏览器工具、Node 和浏览器依赖；本身不代替宿主隔离 |
| <a id="s182"></a>S182 | [Brave Search MCP](https://github.com/brave/brave-search-mcp-server) | 维护方服务器、stdio 与 API Key 配置；服务限额另查 |
| <a id="s183"></a>S183 | [Tavily MCP](https://github.com/tavily-ai/tavily-mcp) | 搜索、提取与 OAuth 入口；Jarvis 不采用 URL 直接放 Key 的示例 |
| <a id="s184"></a>S184 | [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) | 网页提取与采集、Key 和自托管依赖；采集范围与额度另验 |
| <a id="s185"></a>S185 | [Microsoft MarkItDown](https://github.com/microsoft/markitdown) | 文件文字转换及 markitdown-mcp；不是版式编辑或高精度 OCR 保证 |
| <a id="s186"></a>S186 | [MCP Reference Servers](https://github.com/modelcontextprotocol/servers) | Filesystem/Git 参考实现与归档列表；官方说明为教学参考，并非直接生产质量保证 |
| <a id="s187"></a>S187 | [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) | 原 blender-mcp 已重定向；社区 Blender 插件与 uvx 包，非 Blender 基金会官方工具 |

<a id="current-audit-sources"></a>
## 当前架构审计的补充依据（2026-10-17 查阅）

| 来源 | 原始资料 | 使用范围与限制 |
|---|---|---|
| <a id="s188"></a>S188 | [SQLite：Appropriate Uses For SQLite](https://www.sqlite.org/whentouse.html) | 本机应用、低写并发和独立设备的适用范围；单写者与网络文件共享的限制。不证明 Jarvis 当前负载、数据迁移或同步已达标 |

本轮同时复核既有 [S11](#s11) LangGraph 检查点/存储、[S39](#s39) 模块化起步讨论、[S52](#s52) OTP 监督树。它们支持设计取舍，不提供本项目实测评分；Fowler 的讨论属于作者工程经验，不是普遍性能定律。

<a id="voice-selection-sources"></a>
## 语音主选与候补的来源（2026-10-18 查阅）

| 来源 | 维护方资料 | 使用范围与限制 |
|---|---|---|
| <a id="s189"></a>S189 | [sherpa-onnx ZipVoice](https://k2-fsa.github.io/sherpa/onnx/tts/zipvoice.html) | 中英双语零样本克隆、参考音频/文字与 Vocos；本机速度和任意情绪指令未验证 |
| <a id="s190"></a>S190 | [sherpa-onnx Speaker Diarization](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html) | 分段/声纹/聚类接口；不等于已登记身份或重叠波形分离 |
| <a id="s191"></a>S191 | [CosyVoice 官方仓库](https://github.com/QwenAudio/CosyVoice) | 原 FunAudioLLM 仓库重定向后的维护方；Fun-CosyVoice3-0.5B、多语克隆和指令控制；上游时延不是 Windows/AMD 本机实测 |
| <a id="s192"></a>S192 | [Qwen3-ASR 官方仓库](https://github.com/QwenLM/Qwen3-ASR) | 0.6B/1.7B、多语与方言；不把高并发吞吐数字换成本机单会话延迟 |
| <a id="s193"></a>S193 | [Google Gemini TTS](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview) | 3.8 Flash/Lite Preview、声音复刻/设计与专用请求；项目准入和声音权利另核 |
| <a id="s194"></a>S194 | [Google Gemini 3.5 Transcribe](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-transcribe) | 文件/live 模型、语种和分段差别；文件的实验性说话人标签不能转称直播身份识别 |
| <a id="s195"></a>S195 | [Google Gemini Live API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api) | 当前 3.8 Live 与实时会话能力；不证明 Jarvis 已接通或总成本更低 |
| <a id="s196"></a>S196 | [百炼 CosyVoice-v3.5-Flash](https://help.aliyun.com/zh/model-studio/cosyvoice-v3-5-flash) | 克隆/设计/指令与北京 0.8 元/万字符公开原价；实际账单和创建声线费用另计 |
| <a id="s197"></a>S197 | [百炼 ASR 模型目录](https://help.aliyun.com/en/model-studio/asr-model) | 录音/实时模型、格式与语种；声纹登记不是转写附带能力 |
| <a id="s198"></a>S198 | [百炼模型公开价格](https://help.aliyun.com/zh/model-studio/model-pricing) | Qwen ASR/CosyVoice 等按地域、秒/字符/token 区分；只采用查阅日价格，不假定免费配额 |
| <a id="s199"></a>S199 | [百炼 Qwen-Audio-3.1-TTS-Flash](https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-tts-flash) | 新一代流式/表达控制候选；不混用旧 Qwen3-TTS 价格和接口 |
| <a id="s200"></a>S200 | [xAI Voice APIs](https://docs.x.ai/developers/model-capabilities/audio/voice) | STT/TTS/实时接口及公开费用；转写主模型为 grok-voice-transcribe-2.0 |
| <a id="s201"></a>S201 | [xAI Custom Voices](https://docs.x.ai/developers/model-capabilities/audio/custom-voices) | 当前美国地域限制与创建 API 的 Enterprise 条件；普通 Key 不代表能在国内创建克隆 |
| <a id="s202"></a>S202 | [OpenAI Audio and voice](https://developers.openai.com/api/docs/guides/audio) | 新 GPT-Live、级联语音和各专用接口；文字旗舰名称不能代替语音能力档案 |
| <a id="s203"></a>S203 | [OpenAI Custom voices](https://developers.openai.com/api/docs/guides/custom-voices) | 从录音创建的准入/同意要求与 prompt-to-voice 的不同；不保证现有账户已获克隆能力 |
| <a id="s204"></a>S204 | [OpenAI File transcription](https://developers.openai.com/api/docs/guides/speech-to-text) | 当前 gpt-transcribe 与文件/实时路径；账户可用性和费用另测 |
| <a id="s205"></a>S205 | [WeSep 官方仓库](https://github.com/wenet-e2e/wesep) | 目标说话人提取研究候选；不代表轻量 CPU 中文重叠分离已验收 |
| <a id="s206"></a>S206 | [SpeechBrain SepFormer-WHAMR 模型卡](https://huggingface.co/speechbrain/sepformer-whamr) | 双人混合分离候选；数据域与语言泛化、运行依赖和延迟必须实测 |
| <a id="s207"></a>S207 | [sherpa-onnx Source separation](https://k2-fsa.github.io/sherpa/onnx/source-separation/index.html) | Spleeter/UVR 等声源路径；不能自动等同多说话人身份分离 |
| <a id="s208"></a>S208 | [Google Agent Platform 价格](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing?hl=en) | 3.8 Flash-Lite TTS 到 2026 年底及 2027-01-01 后的两档 token 价格；不是无限免费或账户实付 |
| <a id="s209"></a>S209 | [sherpa-onnx 说话人识别预训练模型](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models) | ERes2Net base/large/v2 为不同资产；Release API 核对 base 3dspeaker ONNX 为 39,593,761 字节，不能当作运行内存 |
| <a id="s210"></a>S210 | [pyannote speaker-diarization-community-1 模型卡](https://huggingface.co/pyannote/speaker-diarization-community-1) | 完整流水线的具体预算对象、CPU 默认/CUDA 可选与离线使用；不为本项目预留 GiB 数字提供实测依据 |
| <a id="s211"></a>S211 | [sherpa-onnx Kokoro](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html) | int8 multi-lang v1_1 与固定音色配置；量化资产大小不是 RAM 峰值 |
| <a id="s212"></a>S212 | [sherpa-onnx PocketTTS](https://k2-fsa.github.io/sherpa/onnx/tts/pocket.html) | 2026-01-26 int8 资产、参考音频和推理配置；本机运行占用仍待测 |
| <a id="s213"></a>S213 | [ZipVoice 官方推理说明](https://github.com/k2-fsa/ZipVoice) | 参考音频/文字、速度与 INT8 质量取舍；特殊 token 不代表支持任意情绪文字指令 |
| <a id="s214"></a>S214 | CosyVoice 官方[加载与模式入口](https://github.com/QwenAudio/CosyVoice/blob/main/cosyvoice/cli/cosyvoice.py)、[前端](https://github.com/QwenAudio/CosyVoice/blob/main/cosyvoice/cli/frontend.py)、[示例](https://github.com/QwenAudio/CosyVoice/blob/main/example.py)、[支持指令](https://github.com/QwenAudio/CosyVoice/blob/main/cosyvoice/utils/common.py) | 同一模型的克隆/跨语种/指令复用、参考声音与指令同时输入、CPU 关闭 fp16；源码审阅不是本机内存或效果实测 |
| <a id="s215"></a>S215 | [Fun-CosyVoice3-0.5B-2512 官方资产快照](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4e8d000f4bcd70751be16fa94bf3d85a18) | 五项原生路径主要资产的静态字节核算；排除替代/RL/重复导出格式，不把文件合计当运行 RAM |
| <a id="s216"></a>S216 | [网易 EmotiVoice 官方仓库](https://github.com/netease-youdao/EmotiVoice)、[原生推理](https://github.com/netease-youdao/EmotiVoice/blob/59f0f36de4db12825f4705dd4e0780d79dd6bb01/inference_am_vocoder_joint.py) | 中英、情绪提示与多音色；CPU 分支不能替代本机速度、内存或主观听感验证，原始训练检查点大小不等于运行 RAM |
| <a id="s217"></a>S217 | [Qwen3-TTS 官方模型表与用法](https://github.com/QwenLM/Qwen3-TTS) | 1.7B CustomVoice 的 9 预设音色和指令控制；0.6B 官方能力表未列指令控制，不把上游低延迟或 CUDA 示例当作当前 Windows/AMD 本机已验证 |
| <a id="s218"></a>S218 | speech.cpp 0.8.10 的 [Qwen3-TTS 后端](https://github.com/nyosegawa/speech.cpp/blob/v0.8.10/docs/models/qwen3-tts.md)、[固定模型摘要](https://github.com/nyosegawa/speech.cpp/blob/v0.8.10/tools/catalog/catalog.json)、[Worker 协议](https://github.com/nyosegawa/speech.cpp/blob/v0.8.10/docs/worker.md) | 第三方原生流式量化运行时；上游在 M5/RTX 2080 的测量不冒充当前 Windows/AMD 的内存与速度 |

模型资料支持候选能力描述，不替代真实人声、普通 PC 性能与当前账户的验证。完整选型只维护在[模型章](models-offline.md#local-survival-2)，本轮实测与未验证项见[验收章（旧工程参考）](references.md#legacy-project)。

<a id="memory-pattern-review-sources"></a>
## 记忆与 Wiki 方法扩展复核（2026-10-18）

本轮关注与现有 Jarvis 的适配，不按热度排名。固定源码文件摘要与依赖声明见 [memory-selection-review-2026-10-18.json（旧工程参考）](references.md#legacy-project)；未安装候选或运行上游基准。下列 commit 是观察快照，不代表推荐直接部署 HEAD。概念稿与论文、源码声明、本机运行证据分别使用。

| 编号 | 一手来源 | 本次用途与限制 |
|---|---|---|
| <a id="s219"></a>S219 | [Karpathy：LLM Wiki 原始思路稿](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | 原材料、关联知识页、摄取/查询/维护的模式；网页阅读，未取得固定版本摘要；不视为开源软件实现或零成本保证 |
| <a id="s220"></a>S220 | [MemPalace README](https://github.com/MemPalace/mempalace/blob/74df9fabab2db96e53400465a23f475665f8871a/README.md)、[依赖与可选后端](https://github.com/MemPalace/mempalace/blob/74df9fabab2db96e53400465a23f475665f8871a/pyproject.toml) | 原文保存、可替换检索、R@5 指标范围；默认 Chroma 与可选运行时；上游成绩未在 Jarvis 复现 |
| <a id="s221"></a>S221 | [LangMem 文档](https://langchain-ai.github.io/langmem/)、[提取实现](https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/knowledge/extraction.py)、[依赖](https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/pyproject.toml) | 函数式记忆管理与自有存储适配；公共接口不等于无依赖，不继承示例的云端默认配置；实验另固定 [PyPI 0.0.30](https://pypi.org/project/langmem/0.0.30/) 与 [wheel 哈希锁（旧工程参考）](references.md#legacy-project)，见[对照证据（旧工程参考）](references.md#legacy-project) |
| <a id="s222"></a>S222 | [LightMem 论文](https://arxiv.org/abs/2510.18866)、[官方实现](https://github.com/zjunlp/LightMem/blob/8449d574df6bae1bdf3314a1564da65e2f37e046/README.md)、[依赖](https://github.com/zjunlp/LightMem/blob/8449d574df6bae1bdf3314a1564da65e2f37e046/pyproject.toml) | 分段、短期整理与异步长期整合；固定研究依赖和 Python 版本，节省调用与环境轻量分别评估 |
| <a id="s223"></a>S223 | [A-MEM 论文](https://arxiv.org/abs/2502.12110)、[官方实现](https://github.com/agiresearch/A-mem/blob/ceffb860f0712bbae97b184d440df62bc910ca8d/README.md)、[依赖](https://github.com/agiresearch/A-mem/blob/ceffb860f0712bbae97b184d440df62bc910ca8d/pyproject.toml) | 动态关联笔记、更新关联上下文；作为可重建关联候选，不据此宣称事实或纠正语义可靠 |
| <a id="s224"></a>S224 | [EverOS 当前实现](https://github.com/EverMind-AI/EverOS/blob/736b82103557cc7d5886ae86c4fd0161e69983cd/README.md)、[存储与一致性说明](https://github.com/EverMind-AI/EverOS/blob/736b82103557cc7d5886ae86c4fd0161e69983cd/docs/how-memory-works.md)、[依赖](https://github.com/EverMind-AI/EverOS/blob/736b82103557cc7d5886ae86c4fd0161e69983cd/pyproject.toml) | EverMemOS 当前仓库路线：Markdown 权威、SQLite/LanceDB 派生；不能与旧服务依赖和旧论文成绩混算 |
| <a id="s225"></a>S225 | [MemOS](https://github.com/MemTensor/MemOS/blob/a7367d07e55db61099f7b4e2c1108bc5831a24f3/README.md)、[Graphiti](https://github.com/getzep/graphiti/blob/417c3a125ae3ac53c19b8e53fffaccf3e665a88e/README.md)、[Hindsight](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/README.md)、[OpenViking](https://github.com/volcengine/OpenViking/blob/8d28ffcdbb646a2f8cc1d8176d37d3c0185bc596/README.md) | 2026-10-18 版本/声明更新抽查；全文件 URL、摘要和依赖清单见静态证据，不替代安装和运行测试 |
| <a id="s226"></a>S226 | [OpenWiki 新快照](https://github.com/langchain-ai/openwiki/blob/6c14bff27830034bfd70c15bde46825d7686ec60/README.md)、[package](https://github.com/langchain-ai/openwiki/blob/6c14bff27830034bfd70c15bde46825d7686ec60/package.json)、[检索实现](https://github.com/langchain-ai/openwiki/blob/6c14bff27830034bfd70c15bde46825d7686ec60/src/retrieval/wiki.ts) | 补充读取当前快照；10 月 16 日 Claims 深度分析仍按当日固定版本，不宣称新快照全部兼容 |
| <a id="s227"></a>S227 | [AgeMem：Agentic Memory 论文](https://arxiv.org/abs/2601.01885) | 学习统一长短期记忆管理策略的研究；本轮仅核对摘要方向，不作为即插即用适配器或本地可运行证据 |
| <a id="s232"></a>S232 | [LangChain：Memory overview](https://docs.langchain.com/oss/python/concepts/memory)、[LangMem：User Profiles](https://langchain-ai.github.io/langmem/guides/manage_user_profile/) | 2026-10-18 查阅；短长期记忆、事实/经历、整体画像与集合的取舍。用于建模比较，不代表 Jarvis 已安装框架或自动画像已经实现 |
| <a id="s233"></a>S233 | [Mem0 OSS：Enhanced Metadata Filtering](https://docs.mem0.ai/open-source/features/metadata-filtering) | 2026-10-18 查阅；过滤运算符和后端支持不同，不能把 SDK 参数名当作权限保障。需用拟部署版本做契约测试，不冒称本机已复现各后端行为 |

选择结论只维护于[技术栈章](stack-project-layout.md#memory-open-source)，个人记忆和知识的共同流程见[知识章](knowledge-learning.md#memory-operating-cycle)，未运行的比较项目见[验证章](delivery-validation.md#memory-comparison-tracks)。

<a id="rea-sources"></a>
## REA 软件解析来源（2026-10-18）

| 编号 | 一手来源 | 本次用途与限制 |
|---|---|---|
| <a id="s228"></a>S228 | [morluto/rea](https://github.com/morluto/rea)、[固定 package.json](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/package.json)、[npm 6.5.0 元数据](https://registry.npmjs.org/rea-agents/6.5.0) | 身份、热度观察、引擎范围与依赖；star 不作为有效性，源码快照与发布包分别记录 |
| <a id="s229"></a>S229 | [上游技能](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/.agents/skills/reverse-engineer-anything/SKILL.md)、[静态分析服务](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/src/application/javascript/JavaScriptApplicationService.ts)、[CLI 入口](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/src/cli/javascriptApplicationAnalysis.ts)、[Evidence 契约](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/src/domain/evidence.ts) | 技能与执行分工、按需资料、共用服务与证据；只读上游文件不表示将其指令应用为当前宿主规则 |
| <a id="s230"></a>S230 | [Windows Ghidra P0](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/docs/windows-ghidra-p0.md)、[JS 工作流](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/.agents/skills/reverse-engineer-anything/references/javascript-applications.md) | Windows/provider、资源与分页边界；上游验证声明不冒充 Jarvis 验收 |
| <a id="s231"></a>S231 | [MIT](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/LICENSE)、[第三方清单](https://github.com/morluto/rea/blob/47d3c6b1a15c166091b47666c9cac6dbd882454c/THIRD_PARTY_NOTICES.md) | 主仓库许可与可选依赖分开；不推定商业分析器授权或目标软件的使用权 |
| <a id="s234"></a>S234 | [Electron 官方：ASAR Archives](https://www.electronjs.org/docs/latest/tutorial/asar-archives)、[@electron/asar 格式与打包器](https://github.com/electron/asar) | 发布格式、pickle/JSON 索引、成员偏移与 unpacked 目录；本机 4.2.0 官方打包器生成自有夹具，Jarvis 验证范围另见验收章 |

选型结论见[技术栈章（旧工程参考）](references.md#legacy-project)，真实探测与未测项见[验收章（旧工程参考）](references.md#legacy-project)。

<a id="conversation-isolation-sources"></a>
## 对话、语音与任务分离的工程依据（2026-10-18 查阅）

| 编号 | 一手资料 | 采用范围与限制 |
|---|---|---|
| <a id="s235"></a>S235 | [Microsoft Bulkhead pattern](https://learn.microsoft.com/en-gb/azure/architecture/patterns/bulkhead) | 按用途隔离池、队列和并发，防止慢依赖耗尽全部容量；本项目采用本地实现，不照搬文章的云服务/Kubernetes 示例 |
| <a id="s236"></a>S236 | [Pipecat Pipeline & Frame Processing](https://docs.pipecat.ai/pipecat/learn/pipeline) | 类型化媒体帧、控制优先、模块适配与有序流；借鉴机制，不等于选定或安装完整框架 |
| S19（复核） | [LiveKit Turns overview](https://docs.livekit.io/agents/logic/turns/)、[Turn-taking tuning](https://docs.livekit.io/agents/logic/turns/tuning/) | VAD、语义轮次、附和/插话、实际播放与历史一致性；框架能力不能当作 Jarvis 已实现或本机性能证据 |
| S18（具体接口） | [sherpa-onnx SenseVoice Python API](https://k2-fsa.github.io/sherpa/onnx/sense-voice/python-api.html) | 非流式识别器结合 VAD 处理麦克风切段；区分持续采集、伪实时切段与原生流式识别 |
| <a id="s237"></a>S237 | [Silero VAD 官方仓库](https://github.com/snakers4/silero-vad) | 小型本地 VAD 的实现参考；上游速度和模型文件大小不当作本项目完整 STT/轮次检测的 RAM 或延迟实测 |
| S21（复核） | [SQLite WAL](https://www.sqlite.org/wal.html) | 读写并行边界、单写入者和检查点；不能借 WAL 声称数据库写入完全不会等待 |
| <a id="s238"></a>S238 | [Microsoft NtQuerySystemInformation](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation)、[System Informer 原始结构定义](https://github.com/winsiderss/phnt/blob/master/ntexapi.h) | 2026-10-19 查阅；仅用于 Windows 验收采样器的进程身份/创建时间与父子关系核对，修复父 PID 复用误归属；不扩大进程权限，不给运行产品新增原生依赖。内部结构可能随 Windows 版本变化，布局和真实进程时间不符即失败 |

[架构选择](architecture.md#clean-core-architecture)、[调度](tasks-agents.md#conversation-resource-isolation)和[验收预算](delivery-validation.md#conversation-separation-validation)是针对现有代码的工程判断，性能目标并非引用资料的实验结果。本轮未试装 Pipecat/LiveKit，未复测真实麦克风。

<a id="codex-coding-sources"></a>
## 编码协作与离线工具包依据（2026-10-19）

| 编号 | 官方来源 | 本项目使用与局限 |
|---|---|---|
| <a id="s239"></a>S239 | [Codex 非交互执行](https://learn.chatgpt.com/docs/non-interactive-mode) | exec、JSONL、结构化输出、临时会话；实际参数按本机固定 CLI 核对 |
| <a id="s240"></a>S240 | [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference) | 功能关闭、模型档案、配置隔离；工具声明与可执行性不同，必须做拒绝探针 |
| <a id="s241"></a>S241 | [Codex 权限档案](https://learn.chatgpt.com/docs/permissions) | 禁止工具文件访问，不能与旧 sandbox 参数混用；CLI 的应用策略不等于候选 LPAC 或独立 OS 隔离 CLI |
| <a id="s242"></a>S242 | [Python zipapp](https://docs.python.org/3/library/zipapp.html) · [runpy](https://docs.python.org/3/library/runpy.html) | 标准 PYZ 格式与入口运行；runpy 本身不是沙箱，实际复验仍由 Windows LPAC 承担。源码工具包要求已有兼容 Python，不声称原生 EXE |

<a id="personal-life-sources"></a>
## 生活助手身份、凭据与轻量调度参考（2026-10-21）

| 编号 | 一手来源 | 使用与限制 |
|---|---|---|
| <a id="s243"></a>S243 | [NIST SP 800-63B-4 §3.2.3](https://pages.nist.gov/800-63-4/sp800-63b.html#biometrics) | 生物识别局限、物理认证器和备用认证；不声称 Jarvis 获得符合性认证 |
| <a id="s244"></a>S244 | [Microsoft Handling Passwords](https://learn.microsoft.com/en-us/windows/win32/secbp/handling-passwords) | Windows 凭据保护和不记录秘密；不是同账户恶意进程的完整隔离证明 |
| <a id="s245"></a>S245 | [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2) | 按需授权、授予范围与令牌；没有因此连接主人账号 |
| <a id="s246"></a>S246 | [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) | 读取、发送与管理的作用域；验证要求取决于实际产品／发布方式 |
| <a id="s247"></a>S247 | [KeePassXC 用户指南](https://keepassxc.org/docs/KeePassXC_UserGuide)、[入门指南](https://keepassxc.org/docs/KeePassXC_GettingStarted) | 独立密码库与浏览器确认访问机制；仅参考，未安装、集成或验证兼容性 |
| <a id="s248"></a>S248 | [APScheduler 3.x 用户指南](https://apscheduler.readthedocs.io/en/3.x/userguide.html) | 错过执行、合并和并发上限；不混用 master 的下一代 API，本轮不新增依赖 |
| <a id="s249"></a>S249 | [Home Assistant automation modes](https://www.home-assistant.io/docs/automation/modes/) | 单实例、排队和并发的显式选择；借鉴机制，不整体引入家庭自动化服务 |
| <a id="s250"></a>S250 | [Microsoft 桌面 UserConsentVerifierInterop](https://learn.microsoft.com/en-us/windows/win32/api/userconsentverifierinterop/nf-userconsentverifierinterop-iuserconsentverifierinterop-requestverificationforwindowasync) | 窗口句柄与异步系统用户验证；文档最低 Windows build 22000，只有 Verified 才放行 |
| <a id="s251"></a>S251 | [Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) | 当前用户保护与完整性；不使用机器范围，不等于抗同账户恶意软件或便携备份 |
| <a id="s252"></a>S252 | [Microsoft SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity) | 公开系统捕获 API 的尽力排除，官方明确不能保证内容绝不被获取 |

<a id="correspondence-sources"></a>
## 邮件与日历文件处理依据（2026-10-21）

| 编号 | 一手来源 | 使用与局限 |
|---|---|---|
| <a id="s253"></a>S253 | [RFC 5545：iCalendar](https://www.rfc-editor.org/rfc/rfc5545) | 内容行折叠、VEVENT、时间与重复规则的定义。当前只实现有界读取子集，不宣称完整标准兼容；重复和不确定时区人工核对 |
| <a id="s254"></a>S254 | [RFC 5322：Internet Message Format](https://www.rfc-editor.org/rfc/rfc5322) | 邮件头与消息格式；显示 From 不等于经过身份验证，导出文件不等于发送成功 |
| <a id="s255"></a>S255 | [Python EmailMessage 官方接口](https://docs.python.org/3/library/email.message.html) | 使用现有运行时标准库解析 MIME、选纯文本正文及生成未发送邮件；在线默认文档版本与本机 Python 3.13 的兼容范围通过本机测试核对，不引入解析插件 |

本轮参考公开格式和现有标准库接口，未复制第三方项目代码、安装新包或下载模型。自主生成的解析和协调代码仍按[供应链准入](security-sovereignty.md#personal-life-supply-chain)进行边界审阅与合成故障测试；不能把该范围推断为病毒扫描认证。

<a id="mail-account-sources"></a>
## QQ 与 Gmail 连接依据（2026-10-21）

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s256"></a>S256 | [Google Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) | Gmail API、OAuth 同意和 Desktop app 准备；借鉴配置流程，不复制示例的明文 token 文件，也不安装示例依赖 |
| <a id="s257"></a>S257 | [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) | 系统浏览器、loopback、PKCE；桌面客户端无法保证 client secret 保密。当前做 state 和 S256 校验，真实 Google 授权待验 |
| <a id="s258"></a>S258 | [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) · [messages.get](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get) | gmail.readonly 与 metadata/raw；仅用户选信后取正文，不申请发送／修改范围 |
| <a id="s259"></a>S259 | [腾讯云企业集成服务文档，第 7、33 页](https://main.qcloudimg.com/raw/document/product/pdf/1270_46586_cn.pdf) | 官方资料记录客户端授权码及 QQ IMAP 主机、993 端口；文档为旧版，不能当作当前账户菜单／权限可用性的验证，真实 QQ 仍待联调 |
| <a id="s260"></a>S260 | [Python 3.13 imaplib](https://docs.python.org/3.13/library/imaplib.html) | SSL、readonly 选择与原生 IMAP 操作；本机在其上限制读取量和命令，不引入第三方客户端 |
| <a id="s261"></a>S261 | [Google OAuth 撤销语义](https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke) | 撤销可能使同项目其他客户端／范围失效。因此本版只实现本机断开与官方撤销入口，不静默调用远端撤销 |

本轮参考协议与官方配置，不下载执行外部脚本，不新增 Python／npm 依赖；本机原生程序由现有工具链编译并记录摘要。按[供应链规则](security-sovereignty.md#personal-life-supply-chain)检查请求边界、凭据流向、TLS、只读命令、取消和版本回退；完整漏洞扫描、恶意邮件解析隔离与真实账号测试尚未完成。

<a id="browser-desktop-sources"></a>
## 网页与桌面操控选型来源（2026-10-21）

| 编号 | 一手来源／审查版本 | 范围 |
|---|---|---|
| <a id="s262"></a>S262 | [Third Hand](https://github.com/shhivv/third-hand/tree/412fbb8b546487fd2a5a3161efe900c2dcb5a187) | README、Package.swift、TaskRunner、ArcDriver、JevClient、PlanStep、CDPClient 静态抽查；非 macOS 实机基准。MIT；不复制源码 |
| <a id="s263"></a>S263 | [Playwright MCP](https://github.com/microsoft/playwright-mcp/tree/ab6d67cbf8b619338f096980806fdbe29432cc4d) · [扩展连接](https://playwright.dev/mcp/configuration/browser-extension) | 登录标签页与可访问树；上游明确 MCP 不是安全边界，Apache-2.0 |
| <a id="s264"></a>S264 | [Stagehand](https://github.com/browserbase/stagehand/tree/d16562dafc402893a65e0fe83e16eacddacb4c58) | 当前 SDK、观察／动作／恢复机制，MIT；不得混用旧版本示例或将云服务能力都写成本地免费能力 |
| <a id="s265"></a>S265 | [browser-use](https://github.com/browser-use/browser-use/tree/aa093a843da5edbf323c0b4145c9b6a0db3ecde8) | README、依赖清单与本地／云端区分，MIT；未安装全栈 |
| <a id="s266"></a>S266 | [BrowserOS](https://github.com/browseros-ai/BrowserOS/tree/6e7e97a086ce852c7e51cd8ebe51a6d7a884393b) · [贡献／构建说明](https://github.com/browseros-ai/BrowserOS/blob/6e7e97a086ce852c7e51cd8ebe51a6d7a884393b/CONTRIBUTING.md) | AGPL-3.0 与 Chromium 等许可证分别核对；构建要求不可当作用户运行占用 |
| <a id="s267"></a>S267 | [Microsoft UFO](https://github.com/microsoft/UFO/tree/eae3c0a8d168c47cb10df0652e293e092eda1078) · [UFO² 论文](https://arxiv.org/abs/2504.14603) | Windows UIA／COM／API 与视觉混合，MIT；论文分数不等于本机可靠率 |
| <a id="s268"></a>S268 | [Google OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies) · [支持的浏览器](https://support.google.com/accounts/answer/7675428?hl=en) | 嵌入式 user-agent 禁止与自动控制浏览器可能被拒；不承诺扩展或 UIA 绕过限制 |
| <a id="s269"></a>S269 | [Chrome activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab) · [跨源网络请求](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests) | 用户触发的标签页临时权限、跨站撤销及扩展 host 权限；不把 Origin 或扩展名称当作身份认证 |

以上仅静态审查与设计依据。没有下载运行远端安装脚本，没有导入 Cookie，也没有证明开源项目不存在漏洞。Jarvis 自身增量的验证在[配置技能证据（旧工程参考）](references.md#legacy-project)维护。

<a id="mail-management-sources"></a>
## 邮件管家权限、同步与草稿依据（2026-10-21）

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s270"></a>S270 | [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) | readonly 不提供写入；compose 可管理草稿且能发送；modify 也含发送但不含绕过垃圾箱的永久删除；labels 权限不能当成给邮件修改标签的权限。后续扩大 scope 仍需本机动作白名单 |
| <a id="s271"></a>S271 | [Synchronize clients with Gmail](https://developers.google.com/workspace/gmail/api/guides/sync) | 首次有界缓存、historyId 增量、游标过旧 404 需重建；历史保留时长不能保证固定一周。方案不把当前最近 10 封列表冒充全量同步 |
| <a id="s272"></a>S272 | [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push) | 官方仍建议用户设备采用轮询同步；watch 需要 Cloud Pub/Sub、至少每七天续订且建议每日续订，通知可能延迟／丢失。watch 续订与 OAuth 重授权不同 |
| <a id="s273"></a>S273 | [Create and send draft emails](https://developers.google.com/workspace/gmail/api/guides/drafts) | 远端 draft 容器 id 稳定但更新时内部 message id 可变，发送后 draft 删除并产生新 SENT message；本地保存 EML 不等于 Gmail 远端草稿或投递成功 |
| <a id="s274"></a>S274 | [Google：检查邮件身份验证](https://support.google.com/mail/answer/180707?hl=en) · [Google：SPF 故障与转发](https://support.google.com/a/answer/10685928?hl=en) | 身份验证与邮件安全不能等同；转发／发件基础设施配置可能导致合法邮件认证失败。用于多信号风险设计，不表示 Jarvis 已验证认证链、接入信誉服务或达到反钓鱼准确率 |

以上只借鉴协议与设计，无新依赖、第三方 MCP 安装或远端脚本执行。个人分类质量、普通 PC 资源开销和后续远端写能力需独立验收，官方 API 支持不等于 Jarvis 已实现。现有实测见[邮件读写证据（旧工程参考）](references.md#legacy-project)。

<a id="composition-sources"></a>
## 可组合 Agent 框架的工程依据（2026-10-22）

只借鉴职责、契约和评估方法；本轮未安装或执行第三方 Agent 框架。公开效果不替代本项目相同任务、预算与机器上的实测。

| 编号 | 官方来源 | 采用范围与证据边界 |
|---|---|---|
| <a id="s275"></a>S275 | [Agent Skills specification](https://agentskills.io/specification) | 技能包、元数据、脚本及参考的组织；不将 allowed-tools 当作本机授权，也不把 SKILL.md 当作完整运行系统 |
| <a id="s276"></a>S276 | [LangChain Skills](https://docs.langchain.com/oss/python/langchain/multi-agent/skills) · [Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) | 按需技能与隔离子上下文两种组合方式；按需求选择，不由“专业角色”名称推导必须多 Agent |
| <a id="s277"></a>S277 | [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 检查点与跨会话存储职责分离；原 durable-execution 地址本次跳转此页。可恢复推理状态不等于外部动作能安全重放 |
| <a id="s278"></a>S278 | [MCP Tools，2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | 工具 schema、发现及调用；用作后续协议对照，本轮不改变现有锁定版本，不把工具声明当隔离或信任证明 |

多 Agent 的质量/费用取舍继续引用 [S10](#s10)，普通 PC 及模块化选型继续引用 [S39](#s39)；无需为相同来源建立第二个编号。

<a id="continuity-sources"></a>
## 连续身份与可替换实现的设计依据（2026-10-22）

| 编号 | 一手来源 | 采用范围与限制 |
|---|---|---|
| <a id="s279"></a>S279 | [Microsoft：Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) | 仅为需要追溯的身份/承诺变更借鉴事件与派生视图；注意并发、迁移、删除和复杂度。原领域不整体迁到新日志库，不要求消息中间件 |
| <a id="s280"></a>S280 | [Anthropic：Constitutional AI: Harmlessness from AI Feedback](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback)，2022 | 原则引导的训练、反馈与修订方法；该研究不提供 Jarvis 三角色协作的绝对忠诚证明。模型层原则与宿主权限/发布门禁分开设计 |
| <a id="s281"></a>S281 | [Microsoft：Strangler Fig pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)；2026-10-22 查阅 | 借鉴逐边界迁移、入口切换与依赖解除后退役；过渡层也有成本和瓶颈风险。本项目据此推导本机渐进替换，不要求引入云基础设施，也不由该模式证明 Jarvis 自主成长有效 |

检查点与跨会话资料继续采用 [S277](#s277) 的职责区分参考，确定性控制与最小权限继续参考 [S36](#s36)。三职能划分、连续身份契约及 PC 轻量落地是本项目的设计推导，不声称由这些来源证明存在机器主观意识或无需人工判断的通用自进化。

<a id="autonomous-development-sources"></a>
## 自主研发与 Codex 程序化接入依据（2026-10-22）

通过 OpenAI Docs 搜索并读取官方页面；仅核对接口定位，未安装、登录或调用编码任务。来源说明支持的接口方向，不替代固定版本和本机行为测试。

| 编号 | 官方来源 | 采用与限制 |
|---|---|---|
| <a id="s282"></a>S282 | [Codex Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) | `codex exec`、JSONL、结构化结果和指定会话接续，适合独立候选工作区；保留 Jarvis 自己的任务关联、权限和验证 |
| <a id="s283"></a>S283 | [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) | TypeScript/Python 程序化线程及恢复；页面将 Python SDK 标为 stable 并说明锁定运行时。具体版本/平台/权限需重新实测，不等于桌面 App 远程控制 |
| <a id="s284"></a>S284 | [Codex MCP server removal](https://learn.chatgpt.com/docs/mcp-server) | 原 Codex MCP server 已移除；App Server 为独立 JSON-RPC，页面标注实验性及生产限制。不能把 SDK 状态推导为全部裸接口稳定，也不依赖旧 MCP 命令 |

<a id="legacy-project"></a>
## 旧工程资料与交接边界

旧来源工程是 `H:/Jarvis`，历史运行版本为 0.1.x。新工程参考其有效设计、需求和故障经验，第一方运行代码独立编写；旧运行代码、环境、用户业务数据库、产品运行包和旧测试结果未迁入。0.2.0-dev.2 按主人要求复用两张既有 Logo 静态图像并登记摘要；0.2.0-dev.3 按主人新授权迁入实际模型配置、模型凭据密文和编码偏好，范围归[模型迁入说明](models-offline.md#portable-model-settings)。这两类例外不扩展至旧业务代码或其他账号。旧记录仍在原目录，本工程阅读与检查不依赖其在线。

迁入章节保留稳定编号，未迁的旧运行/测试章节和引用去向登记在 [provenance.json](provenance.json)。其中的 source_path/source_target 是只读来源信息，不是新工程依赖。历史报告只证明原版本原环境；资料中的核验日期不表示本轮重新核验外部产品、模型或价格。

旧代码路径、旧服务入口及旧证据链接统一指向本节，并在交接记录保留原定位。完整设计的当前解释以本工程权威主题为准；技术迁移应遵守新模块契约，不能运行旧命令来“启动新工程”。

<a id="growth-runtime-sources"></a>
## 受限自主研发实现参考（2026-10-22）

| 编号 | 一手来源 | 使用与实测边界 |
|---|---|---|
| <a id="s285"></a>S285 | [Microsoft CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile) | profile/SID 生命周期接口依据；具体本机限制另通过 D 盘 Worker 反例测试 |
| <a id="s286"></a>S286 | [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | 进程组、资源上限和 kill-on-close 设计依据；Job 自身不替代文件/网络访问控制 |
| <a id="s287"></a>S287 | [Alibaba Cloud Structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output) | JSON Object/Schema 与模型差异；本实现另做严格宿主 schema 校验，实测仅登记线路 |

本轮也重新读取 [S282](#s282) 的 Codex 非交互官方文档并核对本机 CLI 帮助。官方文档与本机版本存在时差，不能直接把较新页面的全部参数当成本机可用；本版仅完成接口评估，未启动 Codex 候选生成。旧参考路径、采用点和未复制边界见 [reference-map.json](../packaging/reference-map.json)。

<a id="native-model-sources"></a>
## 本地凭据与原生模型协议依据（2026-10-22）

| 编号 | 官方来源 | 采用与边界 |
|---|---|---|
| <a id="s288"></a>S288 | [OpenAI Structured Outputs / JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs#json-mode) | Responses 的 text.format 与 JSON 指令；JSON mode 仍需宿主校验 schema、完整性和业务结果 |
| <a id="s289"></a>S289 | [Google OAuth service accounts](https://developers.google.com/identity/protocols/oauth2/service-account) | 服务账号 JWT/RS256 和官方令牌交换；不同于 Gmail 本人授权，本轮仅访问原模型项目 |
| <a id="s290"></a>S290 | [Vertex controlled JSON generation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/generativeaionvertexai-gemini-controlled-generation-response-mime-type) | generateContent 的 responseMimeType；本轮真实验证默认 Flash，不据此声称全部目录模型已验证 |
| <a id="s291"></a>S291 | [Microsoft NCryptImportKey](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptimportkey) | 不指定密钥名称的临时 PKCS#8 导入，使用 Windows 密码提供程序，不自行编写 RSA |
| <a id="s292"></a>S292 | [Microsoft NCryptSignHash](https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptsignhash) | SHA-256/PKCS#1 签名及返回检查；实际 Vertex 调用证明本机互操作，不等于独立密码安全审计 |

DPAPI 的范围与同账户限制继续引用 [S244](#s244)，不重复建立来源编号。本轮没有新安装供应商 SDK；官方文档只用于新适配器接口核对，真实调用和失败记录见[验收](delivery-validation.md#portable-settings-evidence)。

<a id="mcp-runtime-sources"></a>
## MCP 子集实现依据（2026-10-23）

| 编号 | 官方来源 | 采用与限制 |
|---|---|---|
| <a id="s321"></a>S321 | [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | Streamable HTTP、JSON/SSE、会话头及 POST；stdio 保留登记但本版不运行 |
| <a id="s322"></a>S322 | [MCP 2025-11-25 Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | tools/list 分页、tools/call、错误结果；工具描述不是主人许可，实际效果需要领域验收 |
| <a id="s323"></a>S323 | [MCP 2025-11-25 Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) | 初始化、协商与 initialized；不声明实现该版所有能力 |

本轮实际读取以上一手规范，独立编写标准库适配，未下载 SDK 或第三方服务代码。规范不是所有服务器互操作性的证明，实测范围仅登记于[验收](delivery-validation.md#mcp-evidence)。

<a id="memory-context-sources"></a>
## 综合记忆与桌面端选型复核（2026-10-23）

本轮只读官方文档、论文摘要与仓库元数据；九个项目的固定 commit、已取得文件摘要/依赖与缺失文件登记见[研究记录](evidence/memory-context-research-2026-10-23.json)。未安装或执行这些框架，未复现上游基准；论文未逐一进行全文方法/统计复核，摘要结果只用于提出设计与测试方向。后续引入代码仍按供应链规则，README 的平台声明不替代目标机测试。

| 编号 | 一手来源 | 采用点与证据限制 |
|---|---|---|
| <a id="s305"></a>S305 | [OpenViking](https://github.com/volcengine/OpenViking)、[上下文层](https://docs.openviking.ai/en/concepts/03-context-layers) | 目录/范围先行、L0/L1/L2 按需读；当前主项目 AGPLv3、桌面 Beta；未测试全本地链路或其同步语义 |
| <a id="s306"></a>S306 | [sqlite-vec](https://github.com/asg017/sqlite-vec)、[LanceDB 混合检索](https://docs.lancedb.com/search/hybrid-search)、[SQLite FTS5](https://www.sqlite.org/fts5.html) | 轻量本地/嵌入式检索对照；pre-v1、过滤、中文短词和实际存储负担需测试 |
| <a id="s307"></a>S307 | [LangMem 核心概念](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)、[Mem0 OSS](https://docs.mem0.ai/open-source/overview) | 核心提取接口与完整记忆流水线不同；默认 LLM/embedding、依赖和存储接管必须显式配置 |
| <a id="s296"></a>S296 | [EverOS 存储](https://github.com/EverMind-AI/EverOS/blob/main/docs/how-memory-works.md)、[依赖](https://github.com/EverMind-AI/EverOS/blob/main/pyproject.toml) | Markdown 原件/派生 SQLite/LanceDB；完整替代候选，不继承旧 EverMemOS 的依赖或成绩 |
| <a id="s297"></a>S297 | [Hindsight README](https://github.com/vectorize-io/hindsight) | 当前官方列出 Windows/macOS 和嵌入式 pg0 路线；Intel Mac 包差异、实际占用和维护成本未验证，主项目 MIT |
| <a id="s298"></a>S298 | [MemForm v1，2026-10-10](https://arxiv.org/abs/2610.14431v1) | 内容、证据、范围、选择与形成顺序的污染反例；预印本方法方向，不泛化其攻防成绩 |
| <a id="s299"></a>S299 | [MemSecBench，2026-07-29](https://arxiv.org/abs/2607.27080) | 形成/执行/选择性修复生命周期评测；不直接套用成功率，不代表本项目已通过 |
| <a id="s300"></a>S300 | [VikingRAG，2026-09-10](https://arxiv.org/abs/2609.11390) | 结构文档逐层取证与有界追加检索；预印本，不能直接推出个人伙伴记忆质量或本机时延 |
| <a id="s301"></a>S301 | [LightMem](https://github.com/zjunlp/LightMem)、[LightMem 论文](https://arxiv.org/abs/2510.18866) | 批次整理、短长期组织与事件绑定参考；包依赖固定 torch 且 Python 范围不同，轻量调用不等于轻量安装 |
| <a id="s302"></a>S302 | [SQLCipher](https://www.zetetic.net/sqlcipher/)、[Apple Keychain](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web) | 本地加密与密钥封装候选；Windows 继续用 S244；跨机恢复、明文副本和私密索引保护需独立验证 |
| <a id="s331"></a>S331 | [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[Microsoft DPAPI 示例与边界](https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata) | 2026-10-24 核对 PBKDF2-HMAC-SHA256 600,000 次及 DPAPI 的同用户/同设备默认边界；本工程 stdlib 首版选择 PBKDF2，不声称优于 Argon2id；DPAPI 不等于独立成员密钥或跨机恢复 |
| <a id="s303"></a>S303 | [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)、[BGE-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)、[EmbeddingGemma-300m](https://huggingface.co/google/embeddinggemma-300m)、[Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)、[ONNX Runtime 安装](https://onnxruntime.ai/docs/install/) | 前两项作为小模型基线，后两项作为升级候选；许可、输入上限、维度和精度分别核对。未下载、量化或测试，不宣称最新最强或 RAM 实测值 |
| <a id="s304"></a>S304 | [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[LongMemEval](https://arxiv.org/abs/2410.10813) | 有限上下文、按需读取、压缩与跨会话评测；工程经验与公开数据需本地中文/业务任务复核 |
| <a id="s330"></a>S330 | [DeepMind XQuAD 官方数据](https://github.com/google-deepmind/xquad)、[固定修订](https://github.com/google-deepmind/xquad/tree/7d30520c717524000f0d9d2f9c10a069acd9d285) | CC BY-SA 4.0；本机使用英、中、西、德、阿、泰六语 JSON，按原文章及全部翻译分隔开发/留出；不是官方排行榜分数，没有无答案样本；原件摘要、划分与限制见连续性验收 |

本轮方案正文见[综合入口](knowledge-learning.md#memory-context-design)，组件比较归[技术选型](stack-project-layout.md#memory-desktop-selection)，测试与资源阈值归[验收](delivery-validation.md#memory-context-acceptance)。所有“推荐”是基于职责与部署约束的工程判断，缺少同条件测量的指标保持未测。

<a id="charakuru-blender-sources"></a>
## Charakuru 工作流与 Blender 适配来源（2026-10-28）

[非官方 charakuru-claude-code](https://github.com/kokushin/charakuru-claude-code/tree/28eddac5fe4bcb8f78f0d375fd7aedc824d7becb) 固定提交 `28eddac5fe4bcb8f78f0d375fd7aedc824d7becb`，MIT。已阅读中文说明、Skill、阶段/设置笔记及若干关键脚本：原流程以 Claude 编排、Codex 出图、Tripo 生成与处理网格、Blender 整理角色及导出。它不是独立的三维生成模型。Jarvis 只借鉴分阶段、保持原版、查明朝向/姿态原因和真实渲染比较的做法，执行代码独立编写。

原始 [Nano / Charakuru 1.1.0](https://github.com/nanocle/Charakuru/releases/tag/v1.1.0) 使用单独的 Source-Available License；本工程未包含套件或素体，也未将其许可改称 MIT。`ea_run.py` 的任意片段执行和 `codex_img.sh` 的外部代理/覆盖输出行为未作为 Jarvis 运行入口。准确阅读范围、Git blob 摘要及未验证项保留于[来源核查](evidence/blender-workflow-1.0.0/source-review.json)。本地核心引擎继续使用 [Blender](https://www.blender.org/)；[实现与限制](tasks-agents.md#blender-workflow-runtime)。

<a id="studio3d-viewer-sources"></a>
## 3D 查看与资产检查来源（2026-10-23）

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s324"></a>S324 | [Three.js](https://github.com/mrdoob/three.js)、[r186发布](https://github.com/mrdoob/three.js/releases/tag/r186) | 使用0.186.0官方包的本地模块、GLTFLoader、OrbitControls和摄影棚环境，MIT；固定来源和摘要，不使用CDN |
| <a id="s325"></a>S325 | [Khronos glTF-Validator](https://github.com/KhronosGroup/glTF-Validator) | 使用2.0.0-dev.3.10固定包，Apache-2.0；检查文件格式，不证明拓扑、视觉或3A质量 |
| <a id="s326"></a>S326 | [three-gltf-viewer](https://github.com/donmccurdy/three-gltf-viewer) | MIT的交互glTF查看参考；未整包复制或运行，Jarvis交互/验收代码自行实现 |
| <a id="s327"></a>S327 | [glTF-Sample-Viewer](https://github.com/KhronosGroup/glTF-Sample-Viewer) | Apache-2.0的官方PBR参考查看器；本轮只用于选型，不宣称渲染一致性已对照验收 |
| <a id="s328"></a>S328 | [Khronos 3D Formats Guidelines](https://github.com/KhronosGroup/3D-Formats-Guidelines) | 资产制作/交付的一般参考；具体预算以项目和目标平台为准，不能推导通用3A阈值 |
| <a id="s329"></a>S329 | [The Tank Museum · Panzer II](https://tankmuseum.org/tank-nuts/tank-collection/panzer-ii/) | 核对Ausf. F车型身份；本轮AI参考板与独立建模，未复制馆藏照片，不声明博物馆精确测绘或授权复刻 |

实际引入、许可、SHA512/SHA256和未完成审计范围见[本轮来源记录](evidence/studio3d-viewer-2026-10-23/source-review.json)。固定依赖不表示任意外来GLB安全；输入、进程与浏览器边界归[工作室边界](security-sovereignty.md#studio3d-viewer-boundary)。

<a id="gmail-sources"></a>
## Gmail 官方接口与授权依据（2026-10-25）

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s350"></a>S350 | [Google 桌面 OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) | 系统浏览器、loopback、state、PKCE 与离线令牌；固定端点，不采用上传 JSON 中的任意 URL |
| <a id="s351"></a>S351 | [Gmail scope](https://developers.google.com/workspace/gmail/api/auth/scopes)、[发送邮件](https://developers.google.com/workspace/gmail/api/guides/sending) | 实际权限与 MIME/base64url；应用另限制具体审阅动作 |
| <a id="s352"></a>S352 | [OAuth 令牌失效](https://developers.google.com/identity/protocols/oauth2#expiration) | 自动刷新非永不过期；测试状态、撤销、账号变化等可能要求重新授权 |

参考协议与旧工程经验，新代码独立实现；未安装第三方 Gmail SDK，未将令牌写入公开证据。

<a id="desktop-companion-sources"></a>
## 桌面常驻伙伴参考（2026-10-25）

只读官方页面与项目 README，没有安装运行、复现宣传指标或完成源码/依赖审计。用于[桌面入口设计](interaction-persona.md#desktop-presence-design)的职责与交互参考，不是替换 Jarvis 核心的授权。许可证以下为仓库当前声明，真正引入代码时另固定版本和核查。

| 编号 | 来源 | 采用点与边界 |
|---|---|---|
| <a id="s353"></a>S353 | [Grok Bot 产品页](https://x.ai/bot)、[发布介绍](https://x.ai/news/introducing-grok-bot) | 官方描述云端电脑、并行任务、上下文延续与需要判断时回问；采用交办体验。未据此证明整体产品已开源，云端持续执行不适用于本机睡眠 |
| <a id="s354"></a>S354 | [OpenMausBot](https://github.com/milind-soni/OpenMausBot) | Apache-2.0；README 的桌面端、统一事件流、问题卡与模型选择有参考价值。云端电脑和连接器依赖另有成本，不整包迁入 |
| <a id="s355"></a>S355 | [OpenClaw](https://github.com/openclaw/openclaw)、[Gateway](https://docs.openclaw.ai/gateway) | MIT；网关服务多个交互端、状态与事件分离、缺口后刷新快照。Jarvis 保留自己既有 Host 和任务记录，不再运行第二个编排核心 |
| <a id="s356"></a>S356 | [OpenBot](https://github.com/ob-f/OpenBot) | MIT；此同名项目是以手机为核心的实体机器人，非本次桌面常驻壳。不能假定它就是主人所指仓库 |
| <a id="s357"></a>S357 | [Tauri 托盘](https://v2.tauri.app/learn/system-tray/)、[全局快捷键](https://v2.tauri.app/plugin/global-shortcut/)、[窗口接口](https://v2.tauri.app/reference/javascript/api/namespacewindow/) | 本地壳候选；托盘、拖动、热键与窗口行为的官方 API 依据。透明窗口不自动保证逐像素穿透，多屏/命中/省电须验证 |
| <a id="s358"></a>S358 | [Microsoft WebView2 API](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/overview-features-apis) | 系统 WebView 与原生应用通信、窗口及浏览器能力参考；不据 API 存在承诺内存或功耗 |

<a id="grok-bot-research-sources"></a>
## Grok Bot 功能、界面与运行机制研究（2026-10-26）

对应完整研究为[Grok Bot 与 Jarvis 对比](grok-bot-comparison.md#grok-comparison-scope)。本次使用官方网页与本工程源码/既有证据，未登录或运行 Grok Bot；公开能力与真实效果分开，借鉴建议为 proposed。产品页和首发介绍沿用 [S353](#s353)，当前版本、权限与套餐优先核对下表具体页面。检索摘要可能落后于正文，尤其是发送审批和 Vault。

| 编号 | 官方来源 | 本次使用范围与边界 |
|---|---|---|
| <a id="s359"></a>S359 | [Grok Bot 总览](https://docs.x.ai/grok-bot/overview) | 产品对象、持久职责和任务交办；不是内部实现审计 |
| <a id="s360"></a>S360 | [创建与管理 Bot](https://docs.x.ai/grok-bot/bots) | 职责、分区与隐藏；隐藏不等于暂停 |
| <a id="s361"></a>S361 | [消息与协作](https://docs.x.ai/grok-bot/chat-and-collaboration) | 工具活动、语音、群聊、异步交接及群内卡片限制；未实测性能 |
| <a id="s362"></a>S362 | [电脑与应用](https://docs.x.ai/grok-bot/computer-and-apps) | 账号共享云电脑、独立屏幕、连接器与本机执行边界；不按 Bot 声称安全隔离 |
| <a id="s363"></a>S363 | [技能、示教与例行流程](https://docs.x.ai/grok-bot/skills-routines-and-automations) | 技能草案、示教限制、方法与触发分离；不推断权重训练 |
| <a id="s364"></a>S364 | [文件、成果与 Pages](https://docs.x.ai/grok-bot/files-and-results) | 预览卡片、持续页面与成果入口；不证明格式还原质量 |
| <a id="s365"></a>S365 | [设置与通知](https://docs.x.ai/grok-bot/settings-and-notifications) | 主题、语言、关注状态；设置列表需结合后续版本 Vault |
| <a id="s366"></a>S366 | [审批、安全与隐私](https://docs.x.ai/grok-bot/approvals-security-and-privacy) | Auto Review、规则优先级与本机控制；后续发送语义结合 S374/S376 |
| <a id="s367"></a>S367 | [Team Bots](https://docs.x.ai/grok-bot/team-bots) | 团队/个人记忆、执行位置与个人例行流程；不同渠道不可套同一身份假设 |
| <a id="s368"></a>S368 | [移动端](https://docs.x.ai/grok-bot/mobile) | 同一工作与手机接续；不等于桌面所有控制均可用 |
| <a id="s369"></a>S369 | [Bot 记忆](https://cursor.com/help/grok-bot/memory) | 自动保存、对话式纠错、群聊使用与删除范围；无质量排名 |
| <a id="s370"></a>S370 | [模型选择](https://cursor.com/help/grok-bot/models) | 后台第一/第三方路由、无用户模型选择与逐请求型号；不能假定固定 Grok 模型 |
| <a id="s371"></a>S371 | [企业安全与数据路径](https://prod.cursor.com/docs/grok-bot/security) | 模型/连接器/云电脑、控制层及套餐差别；不是绝对安全或全量零保留承诺 |
| <a id="s372"></a>S372 | [计划与计费](https://prod.cursor.com/help/grok-bot/plans) | 新旧账号接入、共享周额度、超额路径与绑定不叠加 |
| <a id="s373"></a>S373 | [当前价格](https://x.ai/pricing)、[X Subscription 价格说明](https://docs.x.ai/x-subscription/pricing) | 查询日月付标价与 Bot 资格；税、实际账号与后续变价另核对 |
| <a id="s374"></a>S374 | [Grok Bot 更新日志](https://x.ai/changelog/bot) | 本次最新列项 v0.75.5（2026-10-23）；Vault 与主动请求/后台发送差别 |
| <a id="s375"></a>S375 | [Vault 与安全秘密输入](https://cursor.com/help/grok-bot/secrets) | 0.75.2 起的账号级 Vault、秘密值不可见与卡片使用规则；保密不等于动作逐次批准 |
| <a id="s376"></a>S376 | [Bot 邮箱](https://cursor.com/help/grok-bot/agent-email) | 账号地址、事件处理与当前发送语义；搜索摘要曾滞后 |
| <a id="s377"></a>S377 | [Routine 帮助](https://cursor.com/help/grok-bot/routines) | 触发、运行、限流、200 仅受理与实际用量；不承诺持续必达 |
| <a id="s378"></a>S378 | [排障与恢复](https://docs.x.ai/grok-bot/troubleshooting) | 软件/电脑恢复顺序及数据保存边界；未执行故障实验 |
| <a id="s379"></a>S379 | [X 的 @bot 任务入口](https://docs.x.ai/grok-bot/tag-on-x) | 入口接回原 Bot、地区与账号限制；不混同公开 @Grok 回复 |

本地只读核查、版本、文件摘要、文档检查与未验证项记录于[研究回执](evidence/grok-bot-research-2026-10-26.json)。没有安装外部代码、搬用旧工程实现、改变运行权限或创建自动化。

<a id="harness2-research-sources"></a>
## Harness² 与多机器人主脑研究来源（2026-10-26）

用于[Grok 对比后的设计深化](grok-bot-comparison.md#jarvis-autonomy-deepening)。只读网络与仓库文件；没有安装、运行、移植或全面审计该项目。GitHub 固定提交为 `1cfe254e8d25b15f37048c3730134686abe60335`（2026-10-14）；论文版本和产品文档的日期独立记录，不能当作同一产品发布。

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s380"></a>S380 | [Harness² 论文](https://arxiv.org/abs/2610.14224)、[HTML v1](https://arxiv.org/html/2610.14224v1) | 固定模型权重、任务内探测组合与跨任务改进库；作者基准结果未由 Jarvis 复现 |
| <a id="s381"></a>S381 | [Google Research 固定版 README](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/README.md) | 项目身份、八类可编辑组件、执行/评价入口；研究代码非通用长期助手产品，第三方组件另有许可 |
| <a id="s382"></a>S382 | [固定版实验说明](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/EXPERIMENTS.md) | 有界并行/顺序模式、按域经验、复现条件、网络/评分泄漏和关闭沙箱的实验限制；不照搬运行边界 |
| <a id="s383"></a>S383 | [经验库源码](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/library.py)、[递归源码](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/recursion.py) | 条件化经验、方法树、版本化索引、4k 执行/3k 改进阶段；仅核查相关片段，未做依赖或全仓安全审计 |
| <a id="s384"></a>S384 | [Google Robotics ER 官方文档](https://ai.google.dev/gemini-api/docs/robotics-overview) | 感知推理、任务编排与机器人 API 的分层参考；预览产品不证明本工程实机能力或物理安全 |

Jarvis 的确定性权限、根预算、任务所有权和发布约束继续以本工程主题页为准；外部论文、代码注释和模型建议都不能扩大其运行权限。

<a id="learning-compounding-sources"></a>
## 经验成长、知识治理与退化控制的研究依据（2026-10-26）

本轮只读论文和官方资料，未安装、运行或复现其中系统。以下来源支持研究方向，不证明 Jarvis 已取得相同效果；本项目的条件化经验、发布与验收规则为 proposed。

| 编号 | 一手来源 | 借鉴与边界 |
|---|---|---|
| <a id="s385"></a>S385 | [ReasoningBank 论文](https://arxiv.org/abs/2509.25140)、[Google Research 介绍](https://www.research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/) | 从成功与失败提炼可迁移方法；原研究含模型自评，官方介绍说明其简单追加经验、更复杂整合仍有研究空间，不能当作本项目独立验收或整库治理已完成 |
| <a id="s386"></a>S386 | [ACE 论文 v1](https://arxiv.org/html/2510.04618v1) | 条目化、生成/反思/整理分工与局部增量，减少整体重写丢失细节；本文指 Agentic Context Engineering，不是其他同名 ACE，原基准结果不外推 |
| <a id="s387"></a>S387 | [Self-RAG](https://arxiv.org/abs/2310.11511) | 按需检索、相关性与支持度检查；原方法训练反思 token，Jarvis 的宿主策略借鉴不等于已训练或复现 Self-RAG |
| <a id="s388"></a>S388 | [Lost in the Middle，ACL/TACL](https://aclanthology.org/2024.tacl-1.9/) | 提醒检验长上下文中的相关信息位置与使用效果；其特定模型/任务实验不能用于断言所有当前模型具有相同退化幅度 |
| <a id="s389"></a>S389 | [Google SRE：Canarying Releases](https://sre.google/workbook/canarying-releases/) | 有限范围/时间的变更评估与对照污染风险；借鉴发布方法，不据此宣称本地候选、经验和数据库已实现隔离 |

本轮结论、适用范围和检查见[成长与知识治理记录](evidence/learning-knowledge-strategy-2026-10-26.json)。隐私/污染边界仍归安全主题，不能借“学习更聪明”扩大资料用途或运行权限。

<a id="weixin-integration-sources"></a>
## 微信通道与桌面协作来源（2026-10-30）

用于[微信接入评估](tasks-agents.md#weixin-integration-plan)。只读文档、仓库 README、公开 npm 元数据及本工程相关代码；未安装、运行、绑定或发送，未完成依赖链安全审计。检索未命中不等于功能不存在；当前账号权限与跨平台表现待实测。

| 编号 | 一手来源 | 支撑与边界 |
|---|---|---|
| <a id="s390"></a>S390 | [OpenAI Computer Use](https://learn.chatgpt.com/docs/computer-use) | Windows／macOS 可视桌面控制、Windows 前台限制与结构化接口优先；未找到 Codex 官方 WeChat 专用条目 |
| <a id="s391"></a>S391 | [腾讯 ClawBot 接入指南](https://cloud.tencent.com/document/product/1831/137450) | 扫码绑定、手机向电脑助手发任务及接收结果；这是 CodeBuddy 产品路径，不等于 Jarvis 已接通 |
| <a id="s392"></a>S392 | [Weixin channel npm](https://www.npmjs.com/package/%40tencent-weixin/openclaw-weixin?activeTab=code)、[公开版本元数据](https://registry.npmjs.org/@tencent-weixin%2fopenclaw-weixin/latest) | 核查为 2.4.10、MIT、Node >=22.13.0、peer OpenClaw >=2026.5.12；npm 页面直接打开 403，版本与依赖由 registry 读取确认；不是独立 Python SDK 或服务端永久契约 |
| <a id="s393"></a>S393 | [wxauto 当前安装与兼容文档](https://docs.wxauto.org/docs/install.html) | Windows 微信 4.1；免费 wxauto4 为 Python 3.9–3.12、当次客户端上限 4.1.8.107，Plus 3.9–3.13；声明非本机实测 |
| <a id="s394"></a>S394 | [wxauto 仓库 README](https://github.com/cluic/wxauto/blob/main/README.md) | 旧公开仓库的 3.9 客户端与使用说明；不能与新发行版的许可、收费、支持范围混为一谈 |
| <a id="s395"></a>S395 | [WeChat-MCP README](https://github.com/BiboyQG/WeChat-MCP/blob/master/README.md) | macOS Accessibility、近期消息／回复工具、Codex 配置及可选 HTTP 传输；未做安全审计，不用于证明 Windows 可运行 |
| <a id="s396"></a>S396 | [腾讯企微机器人说明](https://cloud.tencent.com.cn/document/product/1759/121473) | 长连接免公网入口、@机器人／私聊、单机器人连接范围；不是普通个人微信聊天读取接口 |
| <a id="s397"></a>S397 | [Wechaty README](https://github.com/wechaty/wechaty/blob/main/README.md) | 多 Puppet 与 Mock 抽象；各后端不同能力与依赖，不对其服务作统一稳定性保证 |
| <a id="s398"></a>S398 | [hermes-wxauto README](https://github.com/doingSthing/hermes-wxauto) | 作者记录新版 Qt Quick／QML 控件树兼容问题；仅作为探测与视觉兜底研究线索，未独立复现或引入代码 |
| <a id="s399"></a>S399 | [wxauto 可接受使用政策](https://docs.wxauto.org/legal/acceptable-use.html) | 本人设备与指定会话的低频辅助、目标核验、记录与停止；非腾讯授权或无风险保证 |
| <a id="s400"></a>S400 | [GPT-6.1 Terra 官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-terra) | 模型 ID、文本／图片、computer_use 与 Responses 工具调用要求；不证明本机账号已可调用 |
| <a id="s401"></a>S401 | [OpenAI Computer use 指南](https://developers.openai.com/api/docs/guides/tools-computer-use) | SDK Toolset＋应用 driver，以及原生 computer_call／截图回传循环；本次只读文档，不安装 SDK 或执行示例 |
| <a id="s402"></a>S402 | [GPT-6 指南中的 Terra](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-gpt-61-terra) | 视觉与操作用途、medium 起步与代表性比较；档位建议不等于质量或费用实测 |


| <a id="s403"></a>S403 | [RungePei README](https://github.com/RungePei/wechat-mcp/blob/main/README.md)、[项目清单](https://github.com/RungePei/wechat-mcp/blob/main/pyproject.toml)、[工具注册源码](https://github.com/RungePei/wechat-mcp/blob/main/src/wechat_mcp/server.py) | 1.0.0、微信 4.1+ UIA、Python、HTTP／stdio、14 类工具；作者 mock 测试和本机实测需区分 |
| <a id="s404"></a>S404 | [wxauto-mcp README](https://github.com/cluic/wxauto-mcp/blob/main/README.md)、[项目清单](https://github.com/cluic/wxauto-mcp/blob/main/pyproject.toml) | 1.0.2、Python >=3.11、wxautox4 激活依赖、stdio／HTTP 入口；封装与底层许可分别核查 |
| <a id="s405"></a>S405 | [iLink 型 wechat-mcp README](https://github.com/jimingyuan7/wechat-mcp/blob/main/README.md)、[项目清单](https://github.com/jimingyuan7/wechat-mcp/blob/main/package.json) | 第三方 0.2.0 移植、Node >=20、stdio、扫码与 bot 消息／媒体；未核验官方独立服务契约或完整凭据实现 |
| <a id="s406"></a>S406 | [sbroenne Windows MCP README](https://github.com/sbroenne/mcp-windows/blob/main/README.md) | .NET 自带运行时发行包、通用控件优先及截图／输入／CLI；作者任务与 token 比较未在 Jarvis 复现 |
| <a id="s407"></a>S407 | [desk-mcp README](https://github.com/DigitalDog1/desk-mcp/blob/main/README.md) | Node＋PowerShell、UIA／MSAA／OCR／CDP、stdio；作者的性能与后台操作范围不能推为微信保证 |
| <a id="s408"></a>S408 | [CursorTouch Windows-MCP](https://github.com/CursorTouch/Windows-MCP)、[项目清单](https://github.com/CursorTouch/Windows-MCP/blob/main/pyproject.toml)、[发行与安全修复](https://github.com/CursorTouch/Windows-MCP/releases) | 0.8.8、Python >=3.14、传输／工具控制，历史 CORS／DNS rebinding 修复；不安装旧教程任意版本 |
| <a id="s409"></a>S409 | [Microsoft Playwright MCP README](https://github.com/microsoft/playwright-mcp/blob/main/README.md) | 网页可访问性与浏览器工具、Node >=18；不是个人微信桌面执行器 |

| <a id="s410"></a>S410 | [Gemini API 函数调用与 Remote MCP](https://ai.google.dev/gemini-api/docs/function-calling) | 工具调用／返回与 Interactions Remote MCP；远程仅 Streamable HTTP，不能据此让云端连接本机 localhost |
| <a id="s411"></a>S411 | [Google Cloud 函数调用](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tools/function-calling) | 模型产生 functionCall，应用执行并返回 functionResponse；映射调用与结果、保留必要回合信息 |

<a id="single-pc-development-sources"></a>
## 单机开发、共享与 A/B 更新来源（2026-10-30）

支撑[单机环境布局](stack-project-layout.md#single-pc-development)与[单机版本接续](evolution-release.md#single-pc-ab-upgrade)。本次只读核查启动器、数据根、执行锁、Git 状态及监听端口；没有建立 worktree、移动正式数据、下载更新器或重启服务。

| 编号 | 一手来源 | 采用与边界 |
|---|---|---|
| <a id="s412"></a>S412 | [Git worktree](https://git-scm.com/docs/git-worktree) | 同仓库多个工作树、共享对象和独立检出；不是未提交内容迁移工具或运行沙箱 |
| <a id="s413"></a>S413 | [SQLite Online Backup API](https://sqlite.org/backup.html) | 在线单库一致备份；不自动提供多库、附件、授权和外部动作的一致回退 |
| <a id="s414"></a>S414 | [MCP 2025-11-25 生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) | 初始化／能力协商／运行／关闭；不把连接协议解释为发布、热更新或任务恢复框架 |
| <a id="s415"></a>S415 | [TUF 概览](https://theupdateframework.io/docs/overview/) | 包分发元数据、签名／哈希、过期与版本防护；安装及业务接续由应用负责，未安装或实现 |
| <a id="s416"></a>S416 | [Tauri updater](https://v2.tauri.app/plugin/updater/) | 条件性原生壳更新候选；不是当前 Python Host 已采用，也不提供业务任务的自动正确恢复 |

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：架构与流程图册](architecture-atlas.md) · [下一章：文档维护规范](MAINTENANCE.md)
<!-- book-footer:end -->
