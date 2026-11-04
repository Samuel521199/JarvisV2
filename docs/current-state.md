# 当前真实状态

> v0.1.2 · 2026-11-04。本页只写已经在本工程代码里存在、可以运行的东西，以及明确的空白。设计目标见各章正文，逐项证据见[能力验收](delivery-validation.md)，版本流水见[版本记录](../CHANGELOG.md)。本页与正文冲突时，以代码和验收记录为准，并修正本页。

<a id="current-state-summary"></a>
## 一句话

Jarvis 现在是一个**本机网页工作台 + 模块化 Python 服务**：能聊天、按域记住和检索、把一句话目标做成计划并在受限执行器里完成纯文本任务、生成和审阅受限的自写工具，另有 Gmail、出图、3D 资产、机械科普等独立模块。透明桌面精灵、多 Bot、自愈、通用自身模块替换、多设备共同体和语音都还**只有设计**。

<a id="current-state-runs"></a>
## 能运行的部分

| 能力 | 代码位置 | 验证情况与限制 |
|---|---|---|
| 网页工作台、设置、项目与会话目录 | `apps/workbench/`、`host/workbench.py`、`modules/workspace/` | 单测与浏览器探针；仅监听 127.0.0.1，0.1.1 起需本机访问钥匙 |
| 单机日用／开发分离 | `apps/development/`、`host/development_bridge.py`、`host/development_runtime.py` | GitHub 开发检查点、独立 worktree／数据、受限 Google 代发与开发单独重启已核验；受控代码包已日用采用，未启用 GitHub 自动拉取或定时更新；[证据](delivery-validation.md#pc-environments-evidence) |
| 应用级准入、A/B 交接与代码恢复 | `modules/release_recovery/application.py`、`adapters/application_host.py` | 隔离测试完成真实进程切换／失败恢复，真实工作台完成托管与浏览器接续；原有 253 项诊断修复、独立包与日用接口通过，v0.1.2 已采用；首次日用没有已采用上一版；[证据](delivery-validation.md#architecture-repair-evidence) |
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

透明桌面精灵与原生壳（Tauri 方案未落地）；语音（STT/TTS）；本地对话大模型（只有 E5 嵌入可运行）；多 Bot / 负责人任期 / Agent 工厂；资源租约与跨模块额度；统一的自检—自愈—进化流水线、incident 与自身模型六视图（已有局部重试、模块恢复等待及包回退）；公开发布者签名及跨模式通用状态交接；多设备共同体、联邦同步；NPC 世界；机器人。`contracts.md` 前半部分的概念接口（如 ContinuityRecord、BotBinding、MemoryStore、TaskOwnership）在代码中都还不存在，见[契约实现索引](contracts.md#contracts-implementation-index)。

<a id="current-state-evidence"></a>
## 证据边界

- 验收几乎全部来自本工程自建的测试、探针和合成数据。真实个人数据只用过一次（Gmail 读信），真实模型调用累计数百次。
- 工作流 1.1～1.13 都在合成“报价”任务上验证，台账写明“生产未部署”；v0.1.2 已核对 601 个运行文件与日用构建；真实开放业务、跨域在途交接与长期收益仍不能由这些合成试验代替。
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
| Blender/工程 Worker 先启动后挂 Job，Codex 子进程无 Job | 未修复，需在 Windows 上实现与验证 |
| 部分读接口会写库（结果评价投影） | 未改：评价依据随文件变化即时失效是现有设计，改为纯读需单独设计 |
| 应用升级排空尚未覆盖全部专用工作通道 | 聊天、通用任务与后台模型已接；专用邮箱/3D/出图等须统一登记并做在途故障验收，见[采用后核对](decisions-review.md#v012-post-release-audit) |
| host 层 20 个模块的既有导入环 | 未拆；已加检查防止继续扩大 |
| 工作曾只在本机工作区 | 2026-10-30 已保存源码检查点并推送 GitHub 开发分支；运行数据和私密凭据仍不入库 |

<a id="current-state-next"></a>
## 下一步

1. v0.1.2 已修复 253 项架构诊断并完成受控日用采用；按[本轮证据](delivery-validation.md#architecture-repair-evidence)保留基线、备份及后续反例。
2. 先补跨通道升级/恢复与轻量监督，再接邮件待办、日程提醒和记忆纠正这条个人助手工作；优先级和出口见[剩余缺口](decisions-review.md#v012-next-work-order)。
3. 回到真实日常请求的委托、要求、核验与低打扰推进，按原 K0—K6 路线补齐；3D 等专业侧线先修已有缺陷。

<a id="current-state-owner-decisions"></a>
## 需要主人决定

- `control/bootstrap`（Rust 停止控制）尚未作为日用默认监管器，部分 CLI 故障测试有使用，控制语义与 Python 版部分重复：保留并改造成真正的进程监管器，还是删除。
- 验收截图、贴图与 CAD 导出（约 200 MB PNG）已不再进入 Git：是否改用 GitHub Release 附件或 Git LFS 对外发布。
- G0 锁存是否投入实现“工作负载不可写”的受保护存放位置。
