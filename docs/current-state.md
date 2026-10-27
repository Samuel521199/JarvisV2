# 当前真实状态

> v0.1.1 · 2026-10-27。本页只写已经在本工程代码里存在、可以运行的东西，以及明确的空白。设计目标见各章正文，逐项证据见[能力验收](delivery-validation.md)，版本流水见[版本记录](../CHANGELOG.md)。本页与正文冲突时，以代码和验收记录为准，并修正本页。

<a id="current-state-summary"></a>
## 一句话

Jarvis 现在是一个**本机网页工作台 + 模块化 Python 服务**：能聊天、按域记住和检索、把一句话目标做成计划并在受限执行器里完成纯文本任务、生成和审阅受限的自写工具，另有 Gmail、出图、3D 资产、机械科普等独立模块。透明桌面精灵、多 Bot、自愈、自身模块替换、多设备共同体和语音都还**只有设计**。

<a id="current-state-runs"></a>
## 能运行的部分

| 能力 | 代码位置 | 验证情况与限制 |
|---|---|---|
| 网页工作台、设置、项目与会话目录 | `apps/workbench/`、`host/workbench.py`、`modules/workspace/` | 单测与浏览器探针；仅监听 127.0.0.1，0.1.1 起需本机访问钥匙 |
| 多模型聊天、持久会话、费用快照 | `host/dialogue.py`、`modules/dialogue/`、`adapters/models/` | 少量真实调用；回退顺序由设置决定，只有一家供应商时没有真正的备用线路 |
| 分域记忆、检索、资料库（FTS + 语义） | `modules/context_knowledge/`、`host/memory.py`、`host/knowledge*.py` | 单测与合成评估；多语留出集回答 79/90，低于自定 90% 门槛；语义检索需本地 E5 模型 |
| 目标 → 计划 → 审批 → 执行 → 原会话交付 | `host/goals.py`、`host/task_scheduler.py`、`modules/task_resource/` | 通用执行两路并行（同类插件任务互斥）；“目标逐项结案”目前只覆盖文本统计与结构化报价两种判定 |
| 受限自写工具与 Codex 候选 | `modules/autonomous_development/`、`modules/release_recovery/`、`adapters/models/codex_cli.py` | 只生成纯文本 Python 工具；在 Windows LPAC 隔离进程中验证；人工审阅节点在测试中曾由 Codex 代为核对 |
| 受控 HTTP MCP | `adapters/mcp/http.py`、`modules/registry_composer/connectors.py` | 只对接过本机模拟服务；端点由主人登记，无目的地白名单 |
| Gmail 助手 | `host/mailbox.py`、`adapters/mail/` | 真实 OAuth、读取过 10 封摘要；发送与草稿未做真实发送验证 |
| 英语练习、日志复盘 | `seed/skills/conversation.json` | 47 项单测 + 7 次真实调用，短文本 |
| 图片设计、3D 工作室、机械科普 | `host/image_generation.py`、`host/studio3d*.py`、`host/anatomy*.py` | 可用但属专业侧线；3D 参考还原与美术验收未通过；高分辨率出图未完成真实验证 |
| 家庭私密空间 | `control/family_identity.py`、`host/family.py` | 可选登录、DPAPI 加密、成员隔离；规则为“主人可查看全部、成员只看自己和共享内容”（主人 2026-10-24 选定并向成员明示） |

<a id="current-state-design-only"></a>
## 只有设计、没有代码

透明桌面精灵与原生壳（Tauri 方案未落地）；语音（STT/TTS）；本地对话大模型（只有 E5 嵌入可运行）；多 Bot / 负责人任期 / Agent 工厂；资源租约与跨模块额度；自检—自愈—进化流水线、incident 与自身模型六视图；签名更新与有状态交接；多设备共同体、联邦同步；NPC 世界；机器人。`contracts.md` 前半部分的概念接口（如 ContinuityRecord、BotBinding、MemoryStore、TaskOwnership）在代码中都还不存在，见[契约实现索引](contracts.md#contracts-implementation-index)。

<a id="current-state-evidence"></a>
## 证据边界

- 验收几乎全部来自本工程自建的测试、探针和合成数据。真实个人数据只用过一次（Gmail 读信），真实模型调用累计数百次。
- 工作流 1.1～1.13 都在合成“报价”任务上验证，台账写明“生产未部署”；尚未做“实际运行的代码 = 测试通过的代码”的交付核对，这也是[决策评审](decisions-review.md#real-work-followup-analysis)排在第一位的工作。
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
| host 层 16 个模块的导入环 | 未拆；已加检查防止继续扩大 |
| 4 天工作曾只在本机工作区 | 需按 0.1.1 说明提交到 Git；大文件已排除 |

<a id="current-state-next"></a>
## 下一步

1. 在本机 Windows 上跑全量测试并提交 Git，打 `v0.1.1` 标签；重启服务，确认运行中的版本与提交一致。
2. 用一周真实日常请求代替新增合成验收，按真实卡点排序后续开发。
3. 回到主链：委托 → 完整要求 → 独立核验 → 低打扰推进；专业侧线（3D、机械、出图）只修缺陷。

<a id="current-state-owner-decisions"></a>
## 需要主人决定

- `control/bootstrap`（Rust 停止控制）目前没有入口在用，功能与 Python 版重复：保留并改造成真正的进程监管器，还是删除。
- 验收截图、贴图与 CAD 导出（约 200 MB PNG）已不再进入 Git：是否改用 GitHub Release 附件或 Git LFS 对外发布。
- G0 锁存是否投入实现“工作负载不可写”的受保护存放位置。
