# 当前真实状态

> v0.1.4 · 2026-11-09。本页只写已经在本工程代码里存在、可以运行的东西，以及明确的空白。设计目标见各章正文，逐项证据见[能力验收](delivery-validation.md)，版本流水见[版本记录](../CHANGELOG.md)。本页与正文冲突时，以代码和验收记录为准，并修正本页。

<a id="current-state-summary"></a>
## 一句话

Jarvis 现在是一个**本机网页工作台 + 模块化 Python 服务**：能聊天、按域记住和检索、把一句话目标做成计划并在受限执行器里完成纯文本任务、生成和审阅受限的自写工具，另有 Gmail、出图、3D 资产、机械科普等独立模块。网页精灵已与工作台共用实际能力；原生透明壳有未验收原型（鼠标透传失败），未日用启用；多 Bot运行时、统一自愈流水线、通用自身模块替换、多设备共同体和语音仍未实现，已有局部重试与受控应用恢复。

<a id="current-state-runs"></a>
## 能运行的部分

| 能力 | 代码位置 | 验证情况与限制 |
|---|---|---|
| 网页工作台、设置、项目与会话目录 | `apps/workbench/`、`host/workbench.py`、`modules/workspace/` | 单测与浏览器探针；仅监听 127.0.0.1，0.1.1 起需本机访问钥匙 |
| 单机日用／开发分离 | `apps/development/`、`host/development_bridge.py`、`host/development_runtime.py` | GitHub 开发检查点、独立 worktree／数据、受限 Google 代发与开发单独重启已核验；受控代码包已日用采用，未启用 GitHub 自动拉取或定时更新；[证据](delivery-validation.md#pc-environments-evidence) |
| 应用级准入、A/B 交接与代码恢复 | `modules/release_recovery/application.py`、`adapters/application_host.py` | 隔离测试完成真实进程切换／失败恢复，真实工作台完成托管与浏览器接续；原有 253 项诊断修复；v0.1.4 已采用，保留兼容的 v0.1.4-rc.1 为上一版；旧版固定启动器到新控制器已实测，见[本轮验收](delivery-validation.md#assistant-release-20261109)。原专用通道排空与跨入口核验见[精灵共享验收](delivery-validation.md#companion-shared-evidence)；[证据](delivery-validation.md#architecture-repair-evidence) |
| 网页精灵与工作台共享入口 | `apps/workbench/companion-shell.js`、`work-client.js`、`conversation-groups.js` | 真实聊天／模型／技能／项目／工作与邮件，不再用演示任务；共享已阅标记和单项停止；[接口与限制](contracts.md#desktop-presence-web-runtime)、[核验](delivery-validation.md#companion-shared-evidence)；原生透明壳仅有未验收原型，不默认启用 |
| 个人待办/一次性本地提醒 | `host/commitments.py`、`modules/task_resource/commitments.py` | v0.1.4 已日用采用；明确时间、改期/取消、离线补投、已阅与完成分开。已见样本修复24/24（非新盲测）；8次真实模型端到端通过。全量1531项中1520通过/11跳过；独立包178项中177通过/1跳过；控制器自身升级和兼容回退实跑通过。仍是有限自然表达、本地一次性提醒，不代表任意语言、循环日程或外部通知已完成。[实现](tasks-agents.md#personal-commitments-chat)／[验收](delivery-validation.md#assistant-release-20261109) |
| 多模型聊天、持久会话、费用快照 | `host/dialogue.py`、`modules/dialogue/`、`adapters/models/` | 少量真实调用；回退顺序由设置决定，只有一家供应商时没有真正的备用线路 |
| 分域记忆、检索、资料库（FTS + 语义） | `modules/context_knowledge/`、`host/memory.py`、`host/knowledge*.py` | 单测与合成评估；多语留出集回答 79/90，低于自定 90% 门槛；语义检索需本地 E5 模型 |
| 目标 → 计划 → 审批 → 执行 → 原会话交付 | `host/goals.py`、`host/task_scheduler.py`、`modules/task_resource/` | 通用执行两路并行（同类插件任务互斥）；“目标逐项结案”目前只覆盖文本统计与结构化报价两种判定 |
| 受限自写工具与 Codex 候选 | `modules/autonomous_development/`、`modules/release_recovery/`、`adapters/models/codex_cli.py` | 只生成纯文本 Python 工具；在 Windows LPAC 隔离进程中验证；人工审阅节点在测试中曾由 Codex 代为核对 |
| 受控 HTTP MCP | `adapters/mcp/http.py`、`modules/registry_composer/connectors.py` | 只对接过本机模拟服务；端点由主人登记，无目的地白名单 |
| Gmail 助手 | `host/mailbox.py`、`adapters/mail/` | 真实 OAuth、有限读信；2026-10-30 接入[精灵邮件轻视图](tasks-agents.md#gmail-companion)，真实计数／摘要／正文与共享 API 已检查；发送未做真实验收，完整自动化尚未实现 |
| 英语练习、日志复盘 | `seed/skills/conversation.json` | 47 项单测 + 7 次真实调用，短文本 |
| 图片设计、3D 工作室、机械科普 | `host/image_generation.py`、`host/studio3d*.py`、`host/anatomy*.py` | [Blender 制作与局部改模](tasks-agents.md#blender-workflow-runtime)已进入日用代码包，本轮核验限合成建模／裁切及接口，资产视觉验收分别判断；可用但属专业侧线；leFH18 已获用户视觉验收；PaK38 完整保留基线为 r25，最新工作候选见资产 current-model；[局部示范、Jarvis 复做与核验](studio3d-learning.md#studio3d-teacher-delivery)已记录清理拒收和未解三角化缺陷，未完成高模验收；[人物独立草模试验](studio3d-learning.md#studio3d-character-trial)尚未验收，跨资产独立制作收益未验证；高分辨率出图未完成真实验证 |
| 家庭私密空间 | `control/family_identity.py`、`host/family.py` | 可选登录、DPAPI 加密、成员隔离；规则为“主人可查看全部、成员只看自己和共享内容”（主人 2026-10-24 选定并向成员明示） |

<a id="current-state-design-only"></a>
## 只有设计、没有代码

原生透明精灵的完整交互（已有Tauri原型，命中透传未通过）；语音（STT/TTS）；本地对话大模型（只有 E5 嵌入可运行）；多 Bot / 负责人任期 / Agent 工厂；资源租约与跨模块额度；统一的自检—自愈—进化流水线、incident 与自身模型六视图（已有局部重试、模块恢复等待及包回退）；公开发布者签名及跨模式通用状态交接；多设备共同体、联邦同步；NPC 世界；机器人。`contracts.md` 前半部分的概念接口（如 ContinuityRecord、BotBinding、MemoryStore、TaskOwnership）在代码中都还不存在，见[契约实现索引](contracts.md#contracts-implementation-index)。

<a id="current-state-evidence"></a>
## 证据边界

- 验收几乎全部来自本工程自建的测试、探针和合成数据。真实个人数据只用过一次（Gmail 读信），真实模型调用累计数百次。
- 工作流1.1～1.10主要在合成报价/文本任务验证，1.11～1.13另有报价、文档、学习三域合成对照；不能都称为独立真实请求。各版本候选台账仍保留当时“生产未部署”状态；v0.1.2 已核对 601 个运行文件与日用构建；真实开放业务、跨域在途交接与长期收益仍不能由这些合成试验代替。
- 隔离（LPAC/Job）、DPAPI、文件锁只在 Windows 上有效；Linux 环境下的回归会跳过这些用例。
- G0 主人利益原则目前**没有自动判定器**；停机锁存只能用命令行手动设置，存于数据根 `state/LATCH`，解除尚未实现。安全章节中“独立监督发现即锁存”描述的是目标设计。

<a id="current-state-risks"></a>
## 已知风险

| 风险 | 状态 |
|---|---|
| 本机其他程序可通过回环接口取得写权限 | 0.1.1 已修复（访问钥匙）；浏览器 Cookie 不按端口隔离，同浏览器访问恶意本机服务仍有残余风险 |
| 后台执行时管理操作报 busy | 0.1.1 已修复 |
| 已交付回复被异常改写 | 0.1.1 已修复 |
| 自写工具静态检查可绕过 | 0.1.1 已收紧；实际边界仍是 LPAC |
| Blender/工程 Worker 启动窗口与 Codex 进程树清理 | v0.1.4 已采用创建时Job；真实工程14项无跳过、Blender构建/修复与关停补验通过，独立包123通过/1项POSIX跳过。本轮完整回归与采用见[收尾验收](delivery-validation.md#assistant-release-20261109)；[实施](stack-project-layout.md#worker-process-lifetime)／[补验](delivery-validation.md#native-handoff-evidence) |
| 部分读接口会写库（结果评价投影） | 未改：评价依据随文件变化即时失效是现有设计，改为纯读需单独设计 |
| 专用通道排空与外部进程边界 | v0.1.3 补齐受管理的邮箱／授权、私密聊天、3D、出图、知识、本地模型操作及在途 HTTP；未知检查阻止交接。任意外部 CLI、原生窗口和业务级长时故障恢复仍未验证，见[共享实现](contracts.md#desktop-presence-web-runtime) |
| host 层 20 个模块的既有导入环 | 未拆；已加检查防止继续扩大 |
| 工作曾只在本机工作区 | 2026-10-30 已保存源码检查点并推送 GitHub 开发分支；运行数据和私密凭据仍不入库 |

<a id="current-state-next"></a>
## 下一步

1. v0.1.4 已完成本轮收尾、日用采用与兼容恢复验证；原数据/凭据/设置保留，本机备份位于 `D:/Jarvis-backups/assistant-release-20261109-a`。证据见[本轮验收](delivery-validation.md#assistant-release-20261109)。没有启用自动拉取/无人审阅任意代码升级。
2. 修复原生精灵的空白鼠标透传，补托盘恢复、多屏/DPI和资源验证；仍共用工作台组件与API。随后贯通邮件→待办→提醒→处理→反馈，先做主人明确选取、有来源与撤回边界的本地闭环。
3. 扩大真实语言来源、委托授权、任务结果核对与经验收益对照后，再推进小规模多Bot责任链、统一自愈和自身模块改造。[后续顺序](decisions-review.md#assistant-release-follow-up)。完整迁移矩阵、公开请求的广泛验收和长期资源表现仍未完成。

<a id="current-state-owner-decisions"></a>
## 需要主人决定

- `control/bootstrap`（Rust 停止控制）尚未作为日用默认监管器，部分 CLI 故障测试有使用，控制语义与 Python 版部分重复：保留并改造成真正的进程监管器，还是删除。
- 验收截图、贴图与 CAD 导出（约 200 MB PNG）已不再进入 Git：是否改用 GitHub Release 附件或 Git LFS 对外发布。
- G0 锁存是否投入实现“工作负载不可写”的受保护存放位置。
