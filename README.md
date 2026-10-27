# JARVIS

<p align="center">
  <img src="apps/workbench/brand/core.png" width="156" alt="Jarvis blue core emblem">
</p>
<p align="center"><strong>与你交流 · 为你办事 · 与你一同成长</strong></p>
<p align="center">A personal AI companion, built around your computer and your context.</p>
<p align="center">
  <img src="https://img.shields.io/badge/release-v0.1.1-38bdf8?style=for-the-badge" alt="Release v0.1.1">
  <img src="https://img.shields.io/badge/Local_First-0f172a?style=for-the-badge" alt="Local first">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge" alt="Python 3.13">
  <img src="https://img.shields.io/badge/Stage-Early_Preview-8b5cf6?style=for-the-badge" alt="Early preview">
</p>
<p align="center"><a href="#desktop-companion-overview">桌面精灵设计</a> · <a href="#quick-start">开始使用</a> · <a href="docs/memory-cognition-design.md#memory-guide-start">记忆与认知</a> · <a href="#book-tree">完整文档</a> · <a href="docs/architecture-atlas.md#diagram-index">架构图册</a> · <a href="docs/current-state.md">当前状态</a> · <a href="CHANGELOG.md">版本记录</a></p>

---

一个以普通 PC 为主要载体、以个人为主、以其家庭或以其为中心的小团体为辅，能够长期相处、自主工作并持续成长的 AI 助手与伙伴。最终目标是在明确目标与有效授权内独立完成任务、验证结果并交付。

**这里是工程与文档的主入口。** 当前版本 **v0.1.1 · 早期预览**（首个 GitHub 发布为 v0.1.0），历史开发证据保持原编号，版本号规则见 [CHANGELOG](CHANGELOG.md#changelog-rules)。本版把自然聊天、分域记忆、目标计划、受限自主编程和原会话交付串联起来；缺少能力时可拟订规格、生成候选，经独立检查与审阅后回到原目标。[受控 MCP 接入](docs/tasks-agents.md#mcp-runtime)复用原任务体系。当前自主研发仍受限于纯文本能力，完整助手与 K0—K6 按分项证据判断。

**先读这一页：[当前真实状态](docs/current-state.md)**：能运行什么、哪些只是设计、证据边界与已知风险都在一页内。按版本的变更流水见 [CHANGELOG](CHANGELOG.md)。

**项目级准则：精灵与工作台是同一个 Jarvis 的两种表现和工作形式。** 精灵侧重自动化、简洁和低打扰，工作台侧重任务的详细展示、设置与控制；共用能力、配置、任务及成果，避免重复实现。这也是未来跨平台入口和远程机器人执行的桌面雏形。[架构准则](docs/architecture.md#unified-system-principle) · [透明精灵、场景呼出与预览图](#desktop-companion-overview)。准则已采纳，原生桌面与跨平台完整闭环仍待实现。

[阅读起点](#start-here) · [全部章节](#book-tree) · [图表预览](#architecture-preview) · [维护方法](#maintaining)

## 产品一览

| 能力 | 状态 | 说明 |
|---|---|---|
| 💬 聊天与会话 | 可用 | 多模型、持久会话、项目目录与原会话交付；[使用](docs/core-bootstrap.md#conversation-operation) |
| 🧠 记忆与资料库 | 可用（质量未达自定门槛） | 分域事实、按问题检索、全文与语义资料库、纠正与撤回；[使用](docs/knowledge-learning.md#memory-retrieval-runtime) |
| 🛠️ 目标与执行 | 可用（文本任务） | 一句话目标 → 计划 → 审批 → 受限执行，两路并行；[使用](docs/core-bootstrap.md#goal-growth-operation) |
| 🧩 自写工具 | 受限可用 | 纯文本 Python 工具候选、独立检查、审阅后发布与回退；[使用](docs/toolchains.md#codex-candidate-runtime) |
| 🔌 MCP / Gmail | 可用（验证有限） | [MCP](docs/tasks-agents.md#mcp-runtime) · [Gmail](docs/tasks-agents.md#gmail-runtime) |
| 📚 英语练习、日志复盘 | 可用 | [使用](docs/tasks-agents.md#personal-workflows-runtime) |
| 🎨 出图 · 3D · 机械科普 | 专业侧线 | [出图](docs/tasks-agents.md#image-studio-workflow) · [3D](docs/tasks-agents.md#studio3d-production-workflow) · [机械](docs/tasks-agents.md#anatomy-engineering-runtime) |
| 👪 家庭私密空间 | 可用（Windows） | 可选登录、加密资料与成员隔离；[规则](docs/knowledge-learning.md#family-private-runtime) |
| 🤖 桌面精灵、语音、多设备、自愈 | 设计中 | 见下方[桌面精灵设计](#desktop-companion-overview)与[路线](docs/core-bootstrap.md#bootstrap-5) |

本版以 Windows 为主，尚属早期预览。完整语音伙伴、家庭私密跨机恢复、多设备共同体和自主进化能力仍按路线逐步实现。仓库不包含使用者的模型凭据、聊天内容、个人记忆或本地模型权重。第一方主体尚未声明统一开源许可；Blender Worker 按文件声明采用 GPL-2.0-or-later，附完整许可。第三方材料保留各自许可和出处。

<a id="desktop-companion-overview"></a>
## 桌面精灵与按需工作台

**统一系统准则 accepted；原生实现 proposed。** 精灵与工作台共用整个 Jarvis 的功能基础；区别是交互深度和呈现形式。日常以透明、无边框、可拖动的精灵自动推进工作、简洁交流和按需反馈；需要直观检查任务全貌、细节、设置及控制时展开工作台。**工作台是同一系统的详细工作形式，无需日常常开。** 关闭卡片或工作台后，助手及后台工作继续；停止按钮只停止当前会话或选中的任务。完整共享规则归[架构准则](docs/architecture.md#unified-system-principle)。

本节将已确认的产品设计与参考图合并呈现在主文档中；各主题的完整工程规则仍由下方链接指向的原章节维护。

**2026-10-27 r5 造型与表达已确认：**当前采用方案为仅头部、兼具图标与精灵的机器人形象，无身体，采用更饱满的银蓝圆润外框与冰蓝电子面罩，精灵不再叠加 J 标记。[当前造型](docs/interaction-persona.md#desktop-robot-form)与[电子面罩规范](docs/interaction-persona.md#desktop-face-display)明确简洁可爱的单圈圆润头壳、日常柔和双眼，以及聆听声波、思考运算环、排队沙漏等九种状态形态与短词显示。[动态设计预览](docs/evidence/desktop-robot-2026-10-27/face-expression-preview.html)可切换示例状态；原生动画、正式分层资产及真实任务接入仍待实现。下方早期场景图继续用于说明交互。

<a id="desktop-companion-transparent"></a>
### 透明地出现在桌面上

- **纯头部形象。** 使用[当前圆润头部方案](docs/interaction-persona.md#desktop-robot-form)，不叠加 J 标记；默认约 64–96 个逻辑像素（[面罩规范](docs/interaction-persona.md#desktop-face-settings)），状态由电子面罩表达。
- **背景真正透明。** 轮廓和局部光效之外能直接看见桌面及后方应用，没有矩形底板、标题栏或浏览器外框。技术上由透明无边框小窗口承载。
- **空白不挡操作。** 轮廓外、光晕及卡片之间的空白处允许鼠标操作下方应用；精灵主体仍能点击、拖动和停靠。
- **悬浮而不抢焦点。** 普通应用窗口前保持可见；全屏演示、游戏、免打扰及锁屏时按规则收起或隐藏，可通过托盘／快捷键找回。
- **内容卡片保持可读。** 只有精灵背景全透明；输入、回答和成果卡使用主题底色，关闭后恢复纯精灵。背景透明与精灵主体透明度分别控制。

当前原 Logo 已确认具有透明通道；**素材透明不等于原生窗口已经实现透明、透传或置顶。** 窗口、焦点与命中行为的完整定义见[透明性规则](docs/interaction-persona.md#desktop-presence-transparency)。

<a id="desktop-companion-scenarios"></a>
### 什么情况下出现什么

| 情况 | 出现的内容 | 处理完以后 |
|---|---|---|
| 平时待命、后台正常执行 | 只有精灵，以低频呼吸／分段光轨表达真实状态 | 保持安静，不常开任务清单或功能栏 |
| 点击精灵、快捷键或已启用的语音唤起 | 一句输入条，按需提供附件与按键说话入口 | 提交后短回执收拢；未提交草稿保留 |
| 拖入文件、图片或粘贴内容 | 临时投放区、附件缩略项和输入条 | 提交前可移除，不自动发送；不铺满屏透明拖放层 |
| 日常问答 | 短回答气泡，长内容在同一卡片内展开 | 正文由用户关闭，不读到一半消失 |
| 询问“你在做什么” | 紧凑工作卡：当前动作、进度依据、等待原因、单项操作 | 关闭回到精灵；停止此项不影响其他工作 |
| 确实需要用户选择 | 问题卡：哪项工作、为何受阻、建议、影响、选项与自由输入 | 回答受理后继续相关工作；稍后或沉默不视为同意 |
| 工作完成并已核验交付 | 简短成果提示；主动展开后查看摘要、文件与预览 | 未读结果保留；深度编辑才打开工作台 |
| 无法自行恢复的异常、来源失联 | 原因与可用操作；状态不明就明确显示待核对 | 重连先核对结果；可恢复波动不反复弹窗 |
| 主动需要完整历史、多文件编辑、专业工具或集中设置 | **补充工作台**，直接定位原会话／文件／工具／设置 | 关闭后回到精灵，任务继续 |
| 全屏、免打扰或主动隐藏 | 小标或托盘，问题与成果排队 | 恢复后汇总一次，不连弹所有历史通知 |
| 锁屏、睡眠、断线或显示器变化 | 隐藏正文；恢复后找回位置并校准状态 | 有事项再按需出现，不自动打开工作台 |

**一次只出现一张主要卡片。** 用户正在输入或阅读时，新事项先留标记，不顶掉当前内容、不抢焦点；卡片切换保留草稿和未处理状态。工作台已经处理同一事项时，精灵不再重复弹出。按需呈现的完整规则见[场景清单](docs/interaction-persona.md#desktop-presence-scenarios)。

<a id="desktop-companion-motion"></a>
### 精灵如何表达状态

| 状态 | 早期 Logo 形态示意；当前头部表达见[面罩规范](docs/interaction-persona.md#desktop-face-expression-map) |
|---|---|
| 待命 | 低频、轻微呼吸发光 |
| 执行中 | 外围分段光轨流动；主动查看时才展开实际进度 |
| 需要回答 | 保留蓝色主体，增加琥珀色小标 |
| 等待外部 | 静止等待标记，区分等待与正在思考 |
| 已交付 | 光片短暂收拢归位一次，随后回到对应状态 |
| 异常或未知 | 静态断轨；展开后说明原因和可用操作 |

动效依据实际任务来源，不制造虚假忙碌或百分比；文字提示和图形共同表达状态。主题变化统一影响精灵光效、面板与控件，遵守减少动态效果设置，隐藏时停止动画。详细语义见[状态规则](docs/interaction-persona.md#desktop-presence-state)与[品牌规范](docs/interaction-persona.md#jarvis-brand-icon)。

<a id="desktop-companion-previews"></a>
### 分场景参考图

下图为设计参考，任务与文件均为示例；每格表示不同时间，四格不会同时出现在桌面上。网格背景、场景标题与画框仅用于展示，**不属于精灵窗口**。

**图 A：日常待命、输入与附件、回答、主动查看工作。**

![Jarvis 日常桌面精灵与按需交流设计](docs/evidence/desktop-companion-2026-10-25/presence-daily.jpg)

**图 B：问题、成果、异常，以及主动打开的补充工作台。**

![Jarvis 回问、交付、异常与补充工作台设计](docs/evidence/desktop-companion-2026-10-25/presence-events.jpg)

[浅色主题对照](docs/evidence/desktop-companion-2026-10-25/presence-events-light.jpg) · [可切换主题和动效的参考图源](docs/evidence/desktop-companion-2026-10-25/presence-scenarios.html) · [预览核查记录](docs/evidence/desktop-companion-2026-10-25/scenario-preview-checks.json)。静态图片只能表现一个动画相位，不能作为原生桌面功能已运行的证据。

<a id="desktop-companion-integration"></a>
### 怎样接入现有 Jarvis

精灵、按需卡片和工作台按[统一系统准则](docs/architecture.md#unified-system-principle)共用领域服务、设置、主题、原会话、任务及交付记录；简洁操作和详细操作都回到同一受理路径。当前单机复用同一个 Host，未来其他平台与远端设备沿相同契约扩展交互或执行适配。原生壳负责透明窗口、命中、位置、托盘和快捷键；业务事实来自统一投影，不因更换外形复制执行器。未接入、断线和过期来源如实标注；问题回答、取消和恢复沿原任务编号与修订受理。

实施继续归入 K0—K6：K0/K1 准备契约、真实状态和独立控制；K2 接透明精灵、卡片与问答交付闭环；完整可选语音与复杂形态按后续能力扩展。原生壳候选为 Tauri 2/Rust 与 Windows WebView2，待透明性、命中、焦点和资源实测后确定。

**当前状态：**已完成设计、场景图、主题示意和原 Logo 透明通道核查；尚未完成原生精灵的运行实现及实机验收。下方启动说明仍对应现在可运行的网页工作台。

[呈现架构](docs/architecture.md#desktop-presence-architecture) · [状态与回答契约](docs/contracts.md#desktop-presence-contract) · [原生壳与目录](docs/stack-project-layout.md#desktop-presence-shell) · [唯一实施路线](docs/core-bootstrap.md#bootstrap-5) · [透明性与闭环验收](docs/delivery-validation.md#desktop-presence-validation) · [资源验收](docs/delivery-validation.md#pc-footprint)。

<a id="conversation-first-concurrency"></a>
## 聊天优先的多任务助手

**2026-10-26 产品要求 accepted；完整资源隔离、动态并发与压力验收 proposed。** 聊天是主人向 Jarvis 提供重要信息、交办新任务、了解进度和改变既有任务的主要入口。后台忙碌时仍须正常接收、理解与回应，不能只保持页面能输入，或用一条“收到”掩盖回答一直等待。

- **交流与控制始终有资源。** 为输入、回复、明确任务控制保留执行容量和本机/模型额度；研究、出图、渲染、索引与邮件不能占满它们。压力下先限制后台新增工作、释放闲置资源或让低优先级步骤在检查点让出。
- **多个任务实际并行。** 独立步骤在有限资源内同时推进；同文件写入、同一桌面/设备等冲突步骤才串行。一个任务等待你回答、失败或取消，不阻塞其他任务，关闭界面也不停止助手。
- **理解先后与轻重。** 结合你的明确指令、截止时间、重要性、延误影响、任务依赖及已等待时长安排工作；优先级有理由、可调整，资源不足时说明哪些任务延期及原因。
- **状态统一且按需出现。** 精灵/卡片与补充工作台显示“运行中、排队中、等待你回答”；外部等待和未知状态另行说明。平时仍只有精灵，需要时再打开详情。
- **以响应实测决定并发。** 记录有内容的回答、控制、后台进展与资源峰值，逐档增加通用执行并发。未经过同机混合负载验证，不承诺任意任务数量或所有外部网络条件下零延迟。

已实现[有界并发 1.0.0](docs/tasks-agents.md#bounded-concurrency-runtime)：通用任务默认两路，聊天保留独立回复槽，后续输入持久排队，支持统一工作状态、任务优先级和 CPU／内存准入设置。[本轮测试与评估](docs/delivery-validation.md#bounded-concurrency-evidence)单独记录；全模块配额、GPU 隔离和完整自然语言控制仍待完成，不宣称已具备任意负载下的响应保障。完整规则见[优先级](docs/tasks-agents.md#resource-scheduling-2)、[前台隔离](docs/tasks-agents.md#conversation-resource-isolation)、[本机资源准入](docs/tasks-agents.md#resource-admission-loop)与[状态呈现](docs/interaction-persona.md#desktop-presence-state)，实施沿[既有 K0—K6 路线](docs/core-bootstrap.md#bootstrap-5)推进。

<a id="quick-start"></a>
## 开始使用

**Windows 本机启动：**双击根目录的 [StartJarvis.bat](StartJarvis.bat)，自动定位 Python、首次建立本地数据并在服务就绪后打开工作台。已有同目录服务时直接打开页面；新启动的服务保留在窗口中，按 `Ctrl+C` 正常停止。需要 Python 3.13 或更新版本；可用 `JARVIS_PYTHON` 指定解释器完整路径。命令行可附加 `--port 18283` 或 `--no-browser`。该批处理适用于 Windows，其他平台继续使用下方 Python 命令。

```powershell
git clone https://github.com/Samuel521199/JarvisV2.git
cd JarvisV2
python -I -B apps/cli/main.py init
python -I -B apps/workbench/server.py --port 18282
```

**本机访问钥匙（v0.1.1 起）：**工作台只监听本机，但同一台电脑上的其他程序也能连到它，所以未启用家庭登录时需要一把按当前系统用户加密保存的访问钥匙。`StartJarvis.bat` 打开的网址末尾带 `#access=…`，页面会自动换成本机会话并从地址栏去掉；直接运行 `server.py` 时，用窗口里打印的完整链接打开。看到“需要访问钥匙”时，从启动窗口重新打开即可。评估脚本请在工程根目录以 `python -m tools.<脚本名>` 运行，它们会自动解锁。

在设置中配置自己的模型连接。默认数据保存在本工程的 `user-data/`，诊断日志在 `user-data/logs/jarvis.log`；项目目录和跨平台边界见[运行说明](docs/stack-project-layout.md#portable-data-runtime)。macOS 和 Linux 的完整功能尚未验收。

<a id="start-here"></a>
## 建议阅读顺序

1. [目标、规则与定义](docs/product-requirements.md#autonomous-companion-baseline)：它是谁、为谁工作，哪些内容不能被自主更改。
2. [核心架构](docs/architecture.md#clean-core-architecture)：连续身份、三职能与可替换模块怎样配合。
3. [安全与主人控制](docs/security-sovereignty.md#product-definition-6)：权限、停止、恢复和忠诚的工程约束。
4. [目录与文件格式](docs/stack-project-layout.md#clean-project-layout)：模块、配置、资料、候选与恢复材料放在哪里。
5. [自主研发](docs/toolchains.md#autonomous-development-providers)：如何使用 Codex、桌面工具与模型编写、检查和改进能力。
6. [第一批实现与验收](docs/core-bootstrap.md#clean-project-bootstrap)：先交付什么，怎样证明主模块能支持后续成长。
7. [记忆与认知综合方案](docs/memory-cognition-design.md#memory-guide-start)：通过架构、选型和特殊场景，理解聊天、办事、学习、隐私与多设备怎样连接。

<a id="architecture-preview"></a>
## 核心架构预览

![新工程核心管理与自主研发架构](docs/diagrams/clean-core-architecture.png)

[放大 SVG](docs/diagrams/clean-core-architecture.svg) · [全部架构图和流程图](docs/architecture-atlas.md) · [自主研发闭环](docs/toolchains.md#autonomous-development-providers)。图片表达目标设计，不代表这些模块已经运行。

<a id="book-tree"></a>
## 全部文档

<!-- book-tree:start -->
<a id="part-product"></a>
### 第一篇 · 产品与体验

| 章节 | 这章回答什么 |
|---|---|
| [产品定义、需求与能力边界](docs/product-requirements.md) | 如何以个人为主、家庭与小团体为辅，自主工作并独立完成任务？ |
| [个人助手体验、工作台与人格形态](docs/interaction-persona.md) | 怎样通过透明精灵按需交流，并把工作台作为特殊补充？ |
| [NPC 小镇与虚拟世界](docs/simulation.md) | 怎样运行 NPC 小镇，并隔离虚拟与现实？ |

<a id="part-foundation"></a>
### 第二篇 · 核心与工程基础

| 章节 | 这章回答什么 |
|---|---|
| [最小核心、初始资产与开发路线](docs/core-bootstrap.md) | 最小核心怎样起步；现有代码如何按 K0—K6 改造并保持三位一体、自愈与持续成长？ |
| [后续方向指南：现状、缺口与优化工作清单](docs/development-guide.md) | 当前版本还缺什么、先优化哪里，原方案的后续工作怎样落到代码与验收？ |
| [系统架构、运行边界与模块职责](docs/architecture.md) | 个人助手核心如何连接记忆、模型、任务与可替换能力？ |
| [主人利益原则、身份授权与停止控制](docs/security-sovereignty.md) | 当前个人使用边界是什么，哪些监督与认证设计已延期？ |
| [公共接口与数据契约](docs/contracts.md) | 模块之间怎样交换任务、事件和记忆数据？ |
| [技术栈、源码目录与运行数据](docs/stack-project-layout.md) | 选哪些技术，代码放哪里，开源组件如何取舍？ |

<a id="part-runtime"></a>
### 第三篇 · 智能运行与多设备协同

| 章节 | 这章回答什么 |
|---|---|
| [模型路由、本地模型与离线生存](docs/models-offline.md) | 用哪些云端和本地模型，怎样切换与离线降级？ |
| [记忆、知识库与持续学习](docs/knowledge-learning.md) | 记住什么，怎样检索、纠正、遗忘和持续学习？ |
| [记忆与认知综合方案：架构、选型与场景图解](docs/memory-cognition-design.md) | 怎样把记忆、知识、聊天、工作、隐私与多设备组成完整方案，并处理特殊情况？ |
| [任务、动作、多 Agent 与资源调度](docs/tasks-agents.md) | 怎样一边交流一边执行任务，如何组织多 Agent？ |
| [离线自治、多设备共同体与重连](docs/federation.md) | 断网怎样独立工作，重连怎样共享记忆与协同？ |

<a id="part-evolution"></a>
### 第四篇 · 自主成长与维护

| 章节 | 这章回答什么 |
|---|---|
| [自主进化、外部编码协作与版本发布](docs/evolution-release.md) | 怎样自编工具、改进模块，并验证和回退？ |
| [火炮类游戏资产制作与经验学习实施手册](docs/studio3d-learning.md) | 怎样把火炮游戏资产经验接成可执行工具、条件方法与可验证的练习闭环？ |
| [开发环境、多语言工具链与构建](docs/toolchains.md) | 怎样准备编译环境，构建和测试不同语言的程序？ |
| [系统健康、防退化与自愈](docs/health-maintenance.md) | 怎样发现故障与结构退化，清理和修复隐患？ |
| [系统自身模型与能力认知](docs/self-model.md) | 如何自动知道当前版本、结构、进程与能力，并为修复和改造提供可靠依据？ |

<a id="part-evidence"></a>
### 第五篇 · 验证与参考

| 章节 | 这章回答什么 |
|---|---|
| [能力验收、故障演练与评估证据](docs/delivery-validation.md) | 哪些能力测过，证据在哪里，下一阶段怎样验收？ |
| [架构决策、批判性评审与评分](docs/decisions-review.md) | 关键架构取舍是否合理；自主助手哪些链条已有基础、哪些交接和长期闭环仍缺证据？ |
| [Grok Bot 功能、界面与运行机制：Jarvis 对比研究（2026-10-26）](docs/grok-bot-comparison.md) | 先看结论、闭环缺口、实施与预测；对比 Grok、多 Bot 与 Harness²，并核对原目标保持和知识收益。 |
| [架构与流程图册](docs/architecture-atlas.md) | 在哪里集中查看架构图和流程图？ |
| [研究资料与证据边界](docs/references.md) | 设计和选型参考了哪些论文与官方资料？ |
| [文档维护规范](docs/MAINTENANCE.md) | 以后怎样归类、更新、检查和清理文档？ |
<!-- book-tree:end -->

<a id="maintaining"></a>
## 后续维护

在 Cursor／VS Code 中打开整个 `D:/Jarvis` 文件夹，再预览本文件。文档使用相对链接，架构图直接嵌入正文，离线阅读不需要 Mermaid 插件或旧工程。`docs/README.md` 是辅助目录，不另立一套设计。

修改前阅读 [AGENTS.md](AGENTS.md) 与 [维护规范](docs/MAINTENANCE.md)。维护命令只使用 Python 标准库：

```text
python tools/sync_doc_navigation.py --root .
python tools/check_docs.py --root .
```

提交到 GitHub 前运行 `python tools/check_repo_size.py`：它列出将被提交且超过 50 MB（警告）或 100 MB（GitHub 上限）的文件。3D 资产、压缩包和验收截图（`docs/evidence` 下的 PNG）已在 `.gitignore` 中排除，只保留在本机；从 GitHub 克隆的副本里这些截图链接会失效。

设计状态与验收结果见[交付记录](docs/delivery-validation.md#documentation-handoff-evidence)。历史来源与未迁内容见[交接说明](docs/references.md#legacy-project)。不自动创建后台维护任务。
