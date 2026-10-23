# JARVIS

<p align="center">
  <img src="apps/workbench/brand/core.png" width="156" alt="Jarvis blue core emblem">
</p>
<p align="center"><strong>与你交流 · 为你办事 · 与你一同成长</strong></p>
<p align="center">A personal AI companion, built around your computer and your context.</p>
<p align="center">
  <img src="https://img.shields.io/badge/release-v0.1.0-38bdf8?style=for-the-badge" alt="Release v0.1.0">
  <img src="https://img.shields.io/badge/Local_First-0f172a?style=for-the-badge" alt="Local first">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge" alt="Python 3.13">
  <img src="https://img.shields.io/badge/Stage-Early_Preview-8b5cf6?style=for-the-badge" alt="Early preview">
</p>
<p align="center"><a href="#quick-start">开始使用</a> · <a href="docs/memory-cognition-design.md#memory-guide-start">记忆与认知</a> · <a href="#book-tree">完整文档</a> · <a href="docs/architecture-atlas.md#diagram-index">架构图册</a> · <a href="docs/delivery-validation.md#github-v0-1-0">版本与验证</a></p>

---

一个以普通 PC 为主要载体、以个人为主、以其家庭或以其为中心的小团体为辅，能够长期相处、自主工作并持续成长的 AI 助手与伙伴。最终目标是在明确目标与有效授权内独立完成任务、验证结果并交付。

**这里是工程与文档的主入口。** 首个 GitHub 发布版本为 **v0.1.0 · 早期预览**，汇集当前源码及此前 dev.12 等开发证据，历史证据保持原编号。本版把自然聊天、分域记忆、目标计划、受限自主编程和原会话交付串联起来；缺少能力时可拟订规格、生成候选，经独立检查与审阅后回到原目标。[受控 MCP 接入](docs/tasks-agents.md#mcp-runtime)复用原任务体系。当前自主研发仍受限于纯文本能力，完整助手与 K0—K6 按分项证据判断。

**现在可以运行：[聊天到交付](docs/core-bootstrap.md#conversation-operation) · [当前验收与限制](docs/delivery-validation.md#conversation-evidence) · [目标关联研发](docs/core-bootstrap.md#goal-growth-operation) · [Codex 候选端口](docs/toolchains.md#codex-candidate-runtime) · [记忆与经验](docs/knowledge-learning.md#goal-memory-runtime) · [数据位置](docs/stack-project-layout.md#portable-data-runtime) · [后续工作](docs/development-guide.md#direction-start)。**

**会话目录与跨平台项目创建：**每个项目会话有专属目录，独立会话留在 Jarvis 数据根；新增项目位置窗口、集中测试目录、配置/草稿保存和交付补齐。[目录与平台策略](docs/stack-project-layout.md#session-folder-layout) · [交互入口](docs/interaction-persona.md#session-folder-interface) · [验收范围](docs/delivery-validation.md#session-folder-evidence)。

**新增机械与场实验台：**Anatomy 3.0.0 支持自由描述/JSON组合、基础零件关节树、发动机与喷气引擎、电机电路、水泵和水波联动，气流/火焰等示意效果及HTML/SVG/JSON导出；保留行星齿轮和曲柄滑块，出处和MIT许可随产物交付。[使用与边界](docs/tasks-agents.md#anatomy-runtime) · [实测和评分](docs/delivery-validation.md#anatomy-evidence)。

**综合记忆与认知方案 · r2：**[单篇完整阅读：架构、选型与场景图解](docs/memory-cognition-design.md#memory-guide-start)。包含 8 张架构／流程／时序示意图，以及分支冲突、遗忘竞态、离线重连、家庭隐私和抗污染等案例；[详细技术选型](docs/stack-project-layout.md#memory-desktop-selection) · [验收与实施次序](docs/delivery-validation.md#memory-context-acceptance)。方案为 proposed；记忆缺口依据 dev.10 核查基线，后续运行版本按各自验收记录判断。

[阅读起点](#start-here) · [全部章节](#book-tree) · [图表预览](#architecture-preview) · [维护方法](#maintaining)

## 产品一览

| 💬 交流 | 🧠 理解与记忆 | 🛠️ 行动与成长 |
|---|---|---|
| 文字会话、项目上下文、模型选择与路由 | 可查看、纠正、撤回的分域事实与来源候选 | 目标计划、现有技能与受控 MCP 工具 |
| 在原会话查看任务进度与产物 | 记忆、知识、分支和多设备的完整设计 | 受限代码候选、检查、审阅、发布与恢复 |
| 独立管理会话与工作任务 | 主体、范围、用途和渠道可追溯 | 可视化机械与场实验台及交互产物 |

本版以 Windows 为主，尚属早期预览。完整语音伙伴、家庭身份与私密库、多设备共同体和自主进化能力仍按路线逐步实现。仓库不包含使用者的模型凭据、聊天内容、个人记忆或本地模型权重。第一方代码尚未声明开源许可；第三方材料保留各自许可和出处。

<a id="quick-start"></a>
## 开始使用

```powershell
git clone https://github.com/Samuel521199/JarvisV2.git
cd JarvisV2
python -I -B apps/cli/main.py init
python -I -B apps/workbench/server.py --port 18282
```

然后打开 [本机工作台](http://127.0.0.1:18282/)，在设置中配置自己的模型连接。默认数据保存在本工程的 `user-data/`；项目目录和跨平台边界见[运行说明](docs/stack-project-layout.md#portable-data-runtime)。macOS 和 Linux 的完整功能尚未验收。

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
| [个人助手体验、工作台与人格形态](docs/interaction-persona.md) | 怎样自然交流、延续人格，并在需要时展开工作台？ |
| [NPC 小镇与虚拟世界](docs/simulation.md) | 怎样运行 NPC 小镇，并隔离虚拟与现实？ |

<a id="part-foundation"></a>
### 第二篇 · 核心与工程基础

| 章节 | 这章回答什么 |
|---|---|
| [最小核心、初始资产与开发路线](docs/core-bootstrap.md) | 个人助手与自主成长核心从哪里开始，怎样沿 K0—K6 扩展？ |
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
| [开发环境、多语言工具链与构建](docs/toolchains.md) | 怎样准备编译环境，构建和测试不同语言的程序？ |
| [系统健康、防退化与自愈](docs/health-maintenance.md) | 怎样发现故障与结构退化，清理和修复隐患？ |
| [系统自身模型与能力认知](docs/self-model.md) | 如何自动知道当前版本、结构、进程与能力，并为修复和改造提供可靠依据？ |

<a id="part-evidence"></a>
### 第五篇 · 验证与参考

| 章节 | 这章回答什么 |
|---|---|
| [能力验收、故障演练与评估证据](docs/delivery-validation.md) | 哪些能力测过，证据在哪里，下一阶段怎样验收？ |
| [架构决策、批判性评审与评分](docs/decisions-review.md) | 当前实现离伙伴核心有多远，工程评分和架构取舍依据是什么？ |
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

设计状态与验收结果见[交付记录](docs/delivery-validation.md#documentation-handoff-evidence)。历史来源与未迁内容见[交接说明](docs/references.md#legacy-project)。不自动创建后台维护任务。
