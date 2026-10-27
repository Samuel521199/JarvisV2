# 版本记录

<a id="changelog-rules"></a>
## 版本号规则

- **`VERSION` 是唯一发布号**，同时写入 `packaging/runtime-lock.json` 与 `docs/manifest.json` 的 `runtime_version`。每次发布在本文件追加一节，并在 Git 打同名标签（如 `v0.1.1`）。
- 文档中的 `0.2.0-dev.1`～`dev.12` 是 v0.1.0 发布前的**历史开发编号**（编号比发布号大是早期命名遗留，不代表更新的版本），保留原编号只为让旧证据可追溯。
- 功能模块自带的版本（如“记忆检索 1.0.0”“3D 工作室 1.6.0”“工作流 1.13.0”）只描述该模块自己的契约或验收批次，不是整个 Jarvis 的版本。
- 旧 H 盘工程的版本号（如 0.1.64、0.1.105）只作来源引用，不构成本工程证据。
- 当前真实能力与限制以[当前真实状态](docs/current-state.md)为准；逐项证据见[能力验收](docs/delivery-validation.md)。

<a id="v0-1-1"></a>
## v0.1.1 · 2026-10-27 · 安全与可靠性修复

本版只修复缺陷和整理工程，不新增业务能力。在 Linux 容器（Python 3.13.17）上全量回归 1,065 项：新增 24 项全部通过，没有出现基线之外的新失败；需要 Windows LPAC/DPAPI 的 303 项随后在本机 Windows 11 上复测：全量 1,085 项，首轮 1,075 项通过，另 10 项因 1 处改错的运行时检查报错，撤回后复测通过。证据见[本轮验收记录](docs/delivery-validation.md#maintenance-0-1-1-evidence)。

**安全**

- 本机访问钥匙：未启用家庭登录时，工作台以前会把写操作 token 发给任何本机程序（含其他 Windows 账户），从而可替换模型密钥、用 Gmail 发信或抢先设置家庭主人密码。现在每个数据根生成一把按当前 OS 用户加密保存的访问钥匙，启动器在网址片段（`#access=…`，不会经网络发送）中交给浏览器，换取 HttpOnly 会话 Cookie；没有会话的数据与控制接口返回 401。直接运行 `server.py` 时窗口会打印完整链接。会话按使用顺延 12 小时；失效时页面顶部提示而不清空未发送的草稿。Cookie 改为手工按名读取，其他本机程序写入的无法解析 Cookie 不会把主人挡在门外。仅供一次性测试数据使用的 `--insecure-no-access-key` 保留旧行为。
- 自写工具静态检查：堵住 `vars()`、单下划线属性、`statistics.sys`、`json.codecs.builtins`、`string.Formatter`（含子类覆写钩子）等取得 `os`/`sys` 的途径（namedtuple 的 `_asdict` 等仍可用）；“模块属性指向另一个模块”的名字改为按当前解释器自动计算。LPAC Worker 仍是实际隔离边界。
- POST 请求先完成身份检查再读取请求体（最大 40 MB）；处理线程设置 30 秒套接字超时。

**可靠性**

- 后台有任务执行时，批准目标、提交工具/连接器调用、创建返工或恢复草稿、继续等待中的任务不再报 `busy`：同进程执行组已持有执行锁时，这些“受理”操作在自身数据库事务内进行，仍排除其他进程。
- 已成功写入的回复和已计费的模型调用记录，不会再被后续清理步骤的异常改写为 UNKNOWN（聊天与图片生成都受益）。
- 任务调度线程异常后自动记录日志并退避重启（10 分钟内最多 8 次），不再静默停止。
- 新增诊断日志 `user-data/logs/jarvis.log`（2 MB × 5 轮转）：记录写请求、错误响应、未处理异常、调度与规划失败；不记录凭据、提示词、回复或资料正文。未处理异常统一返回 `internal_error` JSON。
- 本地嵌入模型单次超时不再被卸载：请求带编号，迟到的旧回复被丢弃；连续 3 次超时视为卡死并重启。短事实向量按模型缓存，不再每轮重编码 64 条。
- 语义检索：向量在后台一次性校验并载入内存，之后查询直接计算（换载时元数据与向量作为一个整体替换）；装有 numpy（本地嵌入运行环境自带）时用矩阵运算。15,194 个窗口单次查询约 255 ms → 23 ms（无 numpy 约 90 ms）。
- 长资料候选提取按自然段分批调用，每批严格低于模型输入上限并各有调用记录，引文只在该批范围内匹配；中途失败时如实记录已提交的候选数；本地拒绝不再被记成“可能已计费”的 UNKNOWN。
- 3D 任务状态只由拥有该任务的服务进程在启动时标记中断，其他进程读取状态不再写库。
- 修复：邮件任务异常路径的未绑定变量；`Core` 初始化中途失败时泄漏数据库连接。
- 前端：服务重启后第一次提交自动用新 token 重试一次；非 JSON 错误响应不再显示解析错误。

**工程整理**

- `.gitignore` 排除 3D 资产（`*.blend`、`*.glb`、`3DModels/` 等）、压缩包、日志，以及 `docs/evidence` 下的截图/渲染 PNG 和 CAD 导出（约 200 MB；验收报告 HTML/JSON 仍入库，v0.1.1 之前已提交的 PNG 保留在历史中。克隆后这些截图链接会失效，需要时改用 GitHub Release 附件发布）；新增 `python tools/check_repo_size.py` 在提交前列出超过 50 MB 警告 / 100 MB 上限的文件。
- 模型回退顺序只在 `modules/preferences/store.py:fallback_routes` 维护一处（规划仍刻意最多回退一次）。
- `tools/check_architecture.py` 新增：`host` 不得依赖 `apps`；host 层导入环（含函数内导入）只能缩小不能扩大，基线记录在 `tools/architecture-baseline.json`；numpy 只允许以可选加速方式出现在向量索引中。
- 未接入运行路径的 `Core.models`（`ModelGateway` 空实例）已移除；`ModelGateway` 类保留为有测试的提案端口并注明用途。

<a id="v0-1-0-workspace"></a>
## v0.1.0 之后的工作区增量（2026-10-23～27，未单独发版）

以下条目原在根 README 首页，按原文迁入；其中多项注明“生产未部署”，以各自验收记录为准。

**会话目录与跨平台项目创建：**每个项目会话有专属目录，独立会话留在 Jarvis 数据根；新增项目位置窗口、集中测试目录、配置/草稿保存和交付补齐。[目录与平台策略](docs/stack-project-layout.md#session-folder-layout) · [交互入口](docs/interaction-persona.md#session-folder-interface) · [验收范围](docs/delivery-validation.md#session-folder-evidence)。

**机械科普与参数化组装：**Anatomy 5.2.0 增加 72 件赛车的两级传动、分件车壳和本地 GPU 检视；保留 32 件电动车的单件/子总成/分批同步组装、装后理想运动学运转；保留实体零件/端口约束、19 件轴系示例、真实剖面、静态与插入采样干涉、装配步骤建议及 STEP/STL/DXF/BOM；提供限定机电、热力、化学与流动计算，保留 4.0 发动机/引擎等教学组合。来源和许可随产物保存；源码、实际进程加载和未验证范围分别记录。[使用与边界](docs/tasks-agents.md#anatomy-engineering-runtime) · [检查与模型评分](docs/delivery-validation.md#anatomy-engineering-evidence)。

**3D 工作室 1.6.0：**增加果皮底色贴图、旋转曲面UV和逐级独立烘焙；苹果高模120148三角面，低模990/472/228三角面，主低模采用规则环网格，修复本轮观察到的漏射黑斑和果窝暗缝。参考还原与AAA美术验收仍未通过。[识图与贴图](docs/tasks-agents.md#studio3d-image-workflow) · [苹果实测](docs/delivery-validation.md#studio3d-apple-evidence) · [生产流程](docs/tasks-agents.md#studio3d-production-workflow)。

**英语与日志工作流 1.0.0：**文字英语练习、纠错和学习卡；生活/学习/研发日志整理、纠正与复盘。默认可用，实际测试覆盖短文本场景，定时提醒与自动新闻订阅未接入。[使用方式](docs/tasks-agents.md#personal-workflows-runtime) · [真实对话验收](docs/delivery-validation.md#personal-workflows-evidence)。

**图片与图形设计 1.1.0：**六类设计流程、最高4K规格、持久模型切换/启停、分项费用估算、手工账单对账、人工清单验收与父图编辑链。已有1K真实出图；本轮2K/4K受Google网络超时阻塞，主服务仍待正常重启加载。[版本与费用](docs/models-offline.md#nano-banana-models) · [使用流程](docs/tasks-agents.md#image-studio-workflow) · [实际验收](docs/delivery-validation.md#nano-banana-evidence)。

**综合记忆与认知方案 · r5：**[单篇完整阅读：架构、选型与场景图解](docs/memory-cognition-design.md#memory-guide-start)。包含 8 张架构／流程／时序示意图，以及分支冲突、遗忘竞态、离线重连、家庭隐私和抗污染等案例；[详细技术选型](docs/stack-project-layout.md#memory-desktop-selection) · [验收与实施次序](docs/delivery-validation.md#memory-context-acceptance)。方案为 proposed；记忆缺口依据 dev.10 核查基线，后续运行版本按各自验收记录判断。

**记忆检索 1.0.0：**已核对记忆可按当前问题召回，支持本地 E5 有界补充、关键词降级，以及聊天/任务的引用依赖失效；工作台记忆面板可预览实际检索结果。[使用与边界](docs/knowledge-learning.md#memory-retrieval-runtime) · [验证证据](docs/delivery-validation.md#memory-retrieval-evidence)。[本地资料库 1.2.0](docs/knowledge-learning.md#knowledge-cycle-runtime) 接通原文导入、持久全文/语义检索、来源知识审阅、资料包恢复，以及失效记忆的聊天/终态任务/受管文件清理。[记忆连续性 1.0.0](docs/knowledge-learning.md#memory-continuity-runtime) 增加修订、生效条件、分支快照、显式事实合并、联合检索、模型引用候选、整组迁移、健康检查和明确“记住”请求的本地候选保存，正在集成验收。[家庭私密空间 1.0.0](docs/knowledge-learning.md#family-private-runtime) 已实现可选登录、加密资料/聊天与成员隔离。完整语义编纂、私密跨机恢复、多设备和质量达标仍按缺口清单推进。

**Gmail 邮件助手 1.0.0：**已有连接可迁入，支持自动续期、失效重连、有限读信、分类规则、加密草稿和审阅后的发送/整理；未知写入先核对。[运行能力](docs/tasks-agents.md#gmail-runtime) · [界面入口](docs/interaction-persona.md#gmail-workbench) · [验收边界](docs/delivery-validation.md#gmail-evidence)。

**Grok Bot 对比研究 · 2026-10-26：**[功能、界面、运行机制与 Jarvis 深度比较](docs/grok-bot-comparison.md#grok-comparison-scope)，含当前源码/验收边界、双方取舍与借鉴建议；研究建议为 proposed。

**自主助手设计深化：**[先看结论、改进效果图与预测／实测看板](docs/grok-bot-comparison.md#grok-research-recommendation)，再查多 Bot、任务评分、经验成长、Harness² 和多机器人方案。新增[怎样越用越聪明、处理改造退化与发挥知识库价值](docs/grok-bot-comparison.md#jarvis-learning-deepening)。主人目标 accepted，新增机制和效果 proposed；[实测登记](docs/delivery-validation.md#forecast-actual-register)保留原预测与以后验证的差距。

**具体改造与原目标保持：**[从现有源码到实施工作包](docs/core-bootstrap.md#core-modernization-plan)，补三位一体、自愈、自评估、自改造、模块独立和持续成长的接线、迁移及退出；[逐目标影响评估与 V-TRI 验收](docs/delivery-validation.md#trinity-preservation-validation)区分设计兼容与尚待证明的运行结果。

**闭环审查：**[主链、十个交接缺口与源码依据](docs/decisions-review.md#closed-loop-audit)。重点补目标结案、持久唤醒、迟到纠正、业务补救、自愈回接和累计退化；规则补齐不等于运行闭环通过，[V-CLC 状态](docs/delivery-validation.md#closure-validation-register)保留未测边界。

**结果评价 1.0.0：**已为原任务增加独立的结果核对、持久评价、重复事件去重、故障降级及旧依据失效；原会话、目标详情和工作状态共用同一结果。综合质量缺证据时不生成总分。[运行与开关](docs/core-bootstrap.md#outcome-observer-runtime) · [功能、性能和界面实测](docs/delivery-validation.md#outcome-observer-evidence)。

**本地文本闭环 1.0.0：**已接通事前验收条件、迟到反馈、条件方法的实际采用与暂停、新证据复核，以及模块恢复后按原申请接续任务。158 项相关回归及实际界面流程通过；通用多 Bot、自改造和长期学习收益仍待验证。[如何使用](docs/core-bootstrap.md#completion-loop-runtime) · [实测、预测差距与剩余边界](docs/delivery-validation.md#completion-loop-evidence)。本轮源码尚未部署到正在运行的生产服务。

**怎样验收：**[可重复运行的验收入口、真实任务对照与逐目标签收条件](docs/delivery-validation.md#completion-acceptance-runbook)。[首轮报告](docs/evidence/completion-acceptance-v1/2026-10-26-r1/report.html)中 170 项测试、界面及原开销门槛通过；缺测、跳过、源码变化或失败均不放行，实际收益与完整产品另列证据。

**验收后深查：**[结论、改进效果及原设计相容性](docs/decisions-review.md#real-work-deep-audit)。12 项离线观察暴露了要求覆盖、批准到入队、局部返工和报告方法复用的交接缺口；已整理[具体实施切面](docs/core-bootstrap.md#modernization-next-implementation)及[复现和后续验收](docs/delivery-validation.md#real-work-diagnostic-evidence)。本轮交付诊断与方案，运行改造和真实业务收益待验证。

**目标要求 1.6.0：**增加当前目标原文的有限表达提取、输入对照和未覆盖内容保留；冲突或未支持的控制表达阻止受理，部分成功不能自动结案。382项不同用例、八条浏览器流程和22道验收门通过。[结论与预测对照](docs/evidence/workflow-requirements-1.6.0/report.html) · [使用与边界](docs/core-bootstrap.md#workflow-requirements-runtime) · [验收](docs/delivery-validation.md#workflow-requirements-evidence)。该方式只核对保存的Goal，聊天来源核对见后续1.7。

**聊天来源 1.7.0：**新增原话、会话要求、Goal与附件传入一致性对账；漏项保持待核验，明确冲突拒绝受理，来源变化会停止后续动作或使旧结论失效。414项不同用例、九条浏览器流程及24道验收门通过。[结论、流程与实测](docs/evidence/workflow-sources-1.7.0/report.html) · [实施与三职能边界](docs/core-bootstrap.md#workflow-sources-runtime) · [验收与失败记录](docs/delivery-validation.md#workflow-sources-evidence)。只适用于新核验方式；前文/修订语义、真实工作收益、长期成长与生产部署仍未验证。

**明确变更 1.8.0：**新增按已接受原话重放要求的新增、替换与撤销；保留历史去向和未被点名的有效条件，模型漏项或擅改报价资料阻止受理。451项不同用例、十条浏览器流程和26道验收门通过。[结论、变更图与实测](docs/evidence/workflow-changes-1.8.0/report.html) · [实施与边界](docs/core-bootstrap.md#workflow-changes-runtime) · [验收记录](docs/delivery-validation.md#workflow-changes-evidence)。限于执行前原始聊天Goal及严格引用式变更；执行后返工、自由语言、真实收益与生产部署仍未验证。

**交付影子核对 1.13.0：**显式事实/计划、依据版本、原回复观察与工作台修订已接通。591项回归、13条浏览器流程、32道门通过；三域24次模型调用完成。15条反例仍有3误报、3漏报，保持可选非阻断，不自动评分或结案。[结论与图表](docs/evidence/workflow-shadow-1.13.0/report.html) · [实施与用法](docs/core-bootstrap.md#workflow-shadow-runtime) · [实测与限制](docs/delivery-validation.md#workflow-shadow-evidence)。尚未证明自动可信提取、真实质量增益或全功能优秀，生产未部署。

**正文忠实性 1.12.0：**新增来源摘录正文与计划一致性核验，更新原助手事实/推断/建议及计划保留提示。561项不同用例、12条浏览器流程、30道门通过；候选v2共36轮，36通过、0失败、0待测。但旧Markdown回放仍复现日志工作流中的扩写与计划遗漏，通用提示修复未达预期。[结论与图表](docs/evidence/workflow-fidelity-1.12.0/report.html) · [实施边界](docs/core-bootstrap.md#workflow-fidelity-runtime) · [实测和未闭合项](docs/delivery-validation.md#workflow-fidelity-evidence)。限定摘录协议不等于通用语义核验，未部署，完整助手与真实净收益未签收。

**三领域对照 1.11.0：**报价、资料整理/Markdown交付、学习练习/复盘全部实测；修正助手协议与仅回复路由提示。538项不同用例、12条浏览器流程、30道验收门通过；修复后两轮48次调用，47轮冻结硬条件通过、1轮超时待测。正文补审仍发现无依据扩写及计划保留缺口，不能将字段通过率当作全文质量。[结论、图表与逐轮证据](docs/evidence/workflow-trials-1.11.0/report.html) · [实施](docs/core-bootstrap.md#workflow-trials-runtime) · [实测与缺口](docs/delivery-validation.md#workflow-trials-evidence)。仍仅6个合成任务，完整助手、真实净收益未签收，未部署。

**来源恢复 1.10.0：**已受理版本仅因祖先反馈变化失效时，可保留全部要求和旧事实，建立同一Work恢复草案；累计预算、版本上限及原权限继续有效。510项不同用例、12条浏览器流程及30道验收门全部通过。[结论、流程与实测分数](docs/evidence/workflow-recovery-1.10.0/report.html) · [实施与边界](docs/core-bootstrap.md#workflow-recovery-runtime) · [预测、失败记录与验收](docs/delivery-validation.md#workflow-recovery-evidence)。未部署，真实净收益未测。

**返工继承 1.9.0：**已执行版本可保留全部有效要求，按明确指令变更；纠错保持标准，新结果独立验收。原451项与新增29项、11条浏览器流程及28道验收门通过。[结论、流程与实测分数](docs/evidence/workflow-inheritance-1.9.0/report.html) · [实施与边界](docs/core-bootstrap.md#workflow-inheritance-runtime) · [验收记录](docs/delivery-validation.md#workflow-inheritance-evidence)。限于有限报价的全量返工；原回执、预算及取消机制保持，真实收益和自动改造未签收，未部署。

**领域核验 1.5.0：**已接通结构化报价的独立预算、交期、最低价与来源引用核对；工具执行成功但结果错误仍需纠正。344项不同用例、七条浏览器流程及20道验收门通过。[结论与预测对照](docs/evidence/workflow-domain-1.5.0/report.html) · [使用与边界](docs/core-bootstrap.md#workflow-domain-runtime) · [联合验收](docs/delivery-validation.md#workflow-domain-evidence)。自然语言理解、真实资料可信性、长期成长和生产部署仍待后续验证。

**工作闭环 1.4.0：**保守返工分析、当前版结案与聊天版本一致性已接通；316个不同用例、六条浏览器流程及原开销门在冻结候选中全部通过。[结论与图表](docs/evidence/workflow-closure-1.4.0/report.html) · [使用方式](docs/core-bootstrap.md#workflow-closure-runtime) · [联合验收](docs/delivery-validation.md#workflow-closure-evidence)。生产未部署，完整助手与长期收益未签收。

**闭环之后的实施优先级：**[顺序、预期效果与采用条件](docs/decisions-review.md#real-work-followup-analysis)。先核对交付版本，再验证真实需求和质量、降低日常打扰，按净收益扩大知识复用与多 Bot；陪伴和学习同步完善。该分析为 proposed，不改写既有实测成绩。

**工作额度 1.3.0：**同一工作及关联返工共享工具动作总额，受理先预留、原账本扣费，未知效果不释放未核清占用。281个不同用例、288次执行通过，生产未部署。[使用与边界](docs/core-bootstrap.md#workflow-budget-runtime) · [配对任务与验收](docs/delivery-validation.md#workflow-budget-evidence)。

**工作交接 1.1.0：**已实现一次请求保存批准与执行意图、满队列等待及要求覆盖核对；检查通过不再自动等同于业务目标完整正确。保留原任务、权限、反馈和核对历史。[使用与边界](docs/core-bootstrap.md#workflow-handoff-runtime) · [本轮验证](docs/delivery-validation.md#workflow-handoff-evidence)。源码尚未部署到当前生产服务。

<a id="v0-1-0"></a>
## v0.1.0 · 2026-10-23 · 首个 GitHub 早期预览

汇集 dev.1～dev.12 的源码与开发证据：自然聊天、分域记忆、目标计划、受限自主编程、受控 MCP 与原会话交付。详见[发布记录](docs/delivery-validation.md#github-v0-1-0)。
