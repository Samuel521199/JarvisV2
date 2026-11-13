# 当前真实状态

2026-11-13 源码 v0.1.9 为[大型平台记忆优化方案](long-term-memory-scale-optimization.md#platform-memory-scope)及文档收尾更新，状态 proposed，未构建或安装本轮日用候选。VERSION、发布锁与 manifest 的版本是源码版本，不改写下方既有日用验收。Redis 热记忆、平台重排和梦境整理的实施/性能验收仍待完成；[收尾证据](evidence/memory-docs-closeout-20261113.md#memory-docs-closeout-checks)仅证明文档与提交检查。

2026-11-12 日用恢复：已从11月11日备份恢复到独立 `D:/Jarvis-runtime/user-data`，当前采用v0.1.7、epoch 1，开发数据未覆盖。工作台、模型库高模/LOD同步对比、线框和持久标注通过实际浏览器检查；原生机器人及标签窗口已显示，Gmail只读连通检查成功。两个已删除项目目录、部分原产物和未备份的可选环境仍缺失，历史UNKNOWN保留且不重放。[恢复证据与限制](delivery-validation.md#daily-restore-20261112)。

2026-11-11 恢复核对：原D盘日用目录已由用户删除，当前代码保留在D:/Jarvis-dev，日用数据尚未重新安置或启动。模型库13资产、24版本、74登记文件完整；整库8166文件已按摘要迁至D:/Jarvis-backups/JarvisModelLibrary。已从正确的JarvisV2远端找回开发分支历史，并与本地新代码比较；源码与资产备份分开，不上传模型或私人数据。[迁移和恢复范围](tasks-agents.md#studio3d-model-library)。


2026-11-11 模型库同步对比与标注导航已实现并在C盘独立预览验证：实际高模/LOD共享相机与模式，标注可定位及保存处理状态，整模与部件互相跳转。日用更新受D盘空间不足阻塞，未替换原版；原模型保持。详见[范围与证据](tasks-agents.md#studio3d-model-library)。

2026-11-10 补充：模型库已收录三个完整二战模型与十个真实独立部件，预留人物与其他分类；PaK38高模和LOD0–3关联，支持真实3D旋转／平移／缩放／线框，持久标签、说明与按版本摘要绑定的三维标注。网页、CLI和制作参考共用本机内容仓库；原文件保持，D盘空间不足后新库置于C盘。74个登记文件摘要、三种完整模型加载和标注重开／不串LOD已实测；人物绑定、目标游戏引擎及自主检索学习不在此次证明内。[能力与边界](tasks-agents.md#studio3d-model-library)。

> v0.1.7 · 2026-11-12恢复后日用epoch 1；旧安装epoch 18已随原目录删除，不与新安装代际混用。本页只写已经在本工程代码里存在、可以运行的东西，以及明确的空白。设计目标见各章正文，逐项证据见[能力验收](delivery-validation.md)，版本流水见[版本记录](../CHANGELOG.md)。本页与正文冲突时，以代码和验收记录为准，并修正本页。

<a id="current-state-summary"></a>
## 一句话

Jarvis 现在是一个**本机网页工作台 + 模块化 Python 服务**：能聊天、按域记住和检索、把一句话目标做成计划并在受限执行器里完成纯文本任务、生成和审阅受限的自写工具，另有 Gmail、出图、3D 资产、机械科普等独立模块。网页精灵已与工作台共用实际能力；原生透明壳已在v0.1.5修复命中并拆为独立机器人/标签窗，主人确认了拖动与点击，多屏实际移动尚未验收；多 Bot运行时、统一自愈流水线、通用自身模块替换、多设备共同体和语音仍未实现，已有局部重试与受控应用恢复。

<a id="current-state-runs"></a>
## 能运行的部分

| 能力 | 代码位置 | 验证情况与限制 |
|---|---|---|
| 网页工作台、设置、项目与会话目录 | `apps/workbench/`、`host/workbench.py`、`modules/workspace/` | 单测与浏览器探针；仅监听 127.0.0.1，0.1.1 起需本机访问钥匙 |
| 单机日用／开发分离 | `apps/development/`、`host/development_bridge.py`、`host/development_runtime.py` | GitHub 开发检查点、独立 worktree／数据、受限 Google 代发与开发单独重启已核验；受控代码包已日用采用，未启用 GitHub 自动拉取或定时更新；[证据](delivery-validation.md#pc-environments-evidence) |
| 应用级准入、A/B 交接与代码恢复 | `modules/release_recovery/application.py`、`adapters/application_host.py` | 隔离测试完成真实进程切换／失败恢复，真实工作台完成托管与浏览器接续；原有 253 项诊断修复；v0.1.5 已采用，保留兼容的 v0.1.5-rc.1 为上一版；旧版固定启动器到新控制器已实测，见[本轮验收](delivery-validation.md#assistant-release-20261109)。原专用通道排空与跨入口核验见[精灵共享验收](delivery-validation.md#companion-shared-evidence)；[证据](delivery-validation.md#architecture-repair-evidence) |
| 网页精灵与工作台共享入口 | `apps/workbench/companion-shell.js`、`work-client.js`、`conversation-groups.js` | 真实聊天／模型／技能／项目／工作与邮件，不再用演示任务；共享已阅标记和单项停止；[接口与限制](contracts.md#desktop-presence-web-runtime)、[核验](delivery-validation.md#companion-shared-evidence)；v0.1.5双窗的基本拖动/点击已获主人确认，多屏仍待验收 |
| 个人待办/一次性本地提醒 | `host/commitments.py`、`modules/task_resource/commitments.py` | v0.1.5 已日用采用；另接通[邮件来源闭环](tasks-agents.md#mail-work-local-closure)。明确时间、改期/取消、离线补投、已阅与完成分开。已见样本修复24/24（非新盲测）；8次真实模型端到端通过。全量1543项中1532通过/11跳过；独立包190项中189通过/1跳过；控制器自身升级和兼容回退实跑通过。仍是有限自然表达、本地一次性提醒，不代表任意语言、循环日程或外部通知已完成。[实现](tasks-agents.md#personal-commitments-chat)／[验收](delivery-validation.md#assistant-release-20261109) |
| 低打扰持续办事 | `host/standing_work.py`、`modules/task_resource/standing.py`、共用`standing-work.js` | v0.1.6已日用采用；固定文字计划的持久委托/周期/次数与行动预算、有限接续、安静时间/通知合并、来源验收、原会话/文件夹交付与可撤回方法候选；[范围](tasks-agents.md#standing-work-runtime)。真实模型识别/规划/暂停、真实Host重启8步、控制器恢复6步、最终全量1572项（1561通过/11跳过）和当前PC五分钟空闲安排观察已通过，[证据](delivery-validation.md#standing-work-20261110)。新界面实际点击待主人反馈；不代表跨应用常设管家已完成 |
| 邮件持续检查与待办跟进 | `host/mail_standing.py`、`modules/mail/standing.py`、共用`mail-standing.js` | v0.1.7已通过限定真实Gmail读信→唯一待办→到期提醒→原草稿审阅→五分钟第二轮→测试反馈；两个测试委托均已取消，原邮件未写入。有限跟进/断网/重试/安静/撤权通过反例；真实15分钟以上跟进间隔未实等；工作台/网页精灵的实际浏览器入口点击通过，原生窗口内点击与多屏仍待验。[使用](tasks-agents.md#mail-standing-runtime)／[逐项验收](delivery-validation.md#mail-standing-20261110)。不自动外发、修改标签或判断开放业务已完成 |
| 多模型聊天、持久会话、费用快照 | `host/dialogue.py`、`modules/dialogue/`、`adapters/models/` | 少量真实调用；回退顺序由设置决定，只有一家供应商时没有真正的备用线路 |
| 分域记忆、检索、资料库（FTS + 语义） | `modules/context_knowledge/`、`host/memory.py`、`host/knowledge*.py` | 单测与合成评估；多语留出集回答 79/90，低于自定 90% 门槛；语义检索需本地 E5 模型 |
| 目标 → 计划 → 审批 → 执行 → 原会话交付 | `host/goals.py`、`host/task_scheduler.py`、`modules/task_resource/` | 通用执行两路并行（同类插件任务互斥）；“目标逐项结案”目前只覆盖文本统计与结构化报价两种判定 |
| 受限自写工具与 Codex 候选 | `modules/autonomous_development/`、`modules/release_recovery/`、`adapters/models/codex_cli.py` | 只生成纯文本 Python 工具；在 Windows LPAC 隔离进程中验证；人工审阅节点在测试中曾由 Codex 代为核对 |
| 受控 HTTP MCP | `adapters/mcp/http.py`、`modules/registry_composer/connectors.py` | 只对接过本机模拟服务；端点由主人登记，无目的地白名单 |
| Gmail 助手与邮件待办 | `host/mailbox.py`、`host/mail_work.py`、`adapters/mail/` | 原OAuth/有限读信保留；v0.1.5接通选信→共用待办→提醒→草稿/准确审阅→回执→本人反馈。原7步Host/重启验收使用合成适配器；[2026-11-10真实续验](delivery-validation.md#gmail-real-20261110)已通过真实读信、提醒、审阅后向本人发送1封并读回及测试反馈。主人澄清机器人默认聊天、邮件按请求呼出，并确认右侧邮件标签有用；此前“机器人未展示邮件即故障”的判断已纠正，完整工作台/精灵操作仍未逐项实点确认。正文/账号身份保持加密，缓存变更和账号代际不符拒绝沿用；[验收与限制](delivery-validation.md#native-mail-20261109) |
| 英语练习、日志复盘 | `seed/skills/conversation.json` | 47 项单测 + 7 次真实调用，短文本 |
| 图片设计、3D 工作室、机械科普 | `host/image_generation.py`、`host/studio3d*.py`、`host/anatomy*.py` | [Blender 制作与局部改模](tasks-agents.md#blender-workflow-runtime)已进入日用代码包，本轮核验限合成建模／裁切及接口，资产视觉验收分别判断；可用但属专业侧线；leFH18 已获用户视觉验收；PaK38 完整保留基线为 r25，最新工作候选见资产 current-model；[局部示范、Jarvis 复做与核验](studio3d-learning.md#studio3d-teacher-delivery)已记录清理拒收和未解三角化缺陷，未完成高模验收；[人物独立草模试验](studio3d-learning.md#studio3d-character-trial)尚未验收，跨资产独立制作收益未验证；高分辨率出图未完成真实验证 |
| 家庭私密空间 | `control/family_identity.py`、`host/family.py` | 可选登录、DPAPI 加密、成员隔离；规则为“主人可查看全部、成员只看自己和共享内容”（主人 2026-10-24 选定并向成员明示） |

<a id="current-state-design-only"></a>
## 按原设计尚未完成的部分

**2026-11-10对照：**以本工程K0—K6路线、当前证据和关键代码为准；不是全仓安全审计，也没有重跑全部验收。源码中有功能与原设计整体已交付分开判断；H盘旧工程的阶段成绩不能作为D盘新工程的完成证明。不按文件数或单测数估算完成百分比。

| 原设计目标 | 已有基础 | 尚缺的交付或证据 |
|---|---|---|
| 连续身份与三职能核心 | 身份/规则/账本、规划、交互与观察的局部接线 | 治理、交互执行、监督的完整版本化端口与独立管理；ContinuityRecord等概念契约仍未全落地。[路线](core-bootstrap.md#bootstrap-5)、[契约索引](contracts.md#contracts-implementation-index) |
| 低打扰、主动且持续办事 | 目标受理、队列执行、局部失败接续、个人一次性提醒及Gmail类型化常设安排 | 固定文字计划和Gmail读取→待办→提醒/跟进已接入；更广有费用模型、其他外部服务、通用实时来源及跨域履约仍未完成。[实施顺序](decisions-review.md#assistant-release-follow-up) |
| 通用结果验收 | 文本/报价的确定性检查、要求覆盖、反馈和影子核对 | 更广泛真实领域的验收标准与校准，未知结果、延迟回执、返工后接回原工作；模型自行判高分不算独立证明 |
| 长期个人认知与知识成长 | 分域事实/检索、纠正撤回、资料库、受限经验方法 | 现有多语合成回答79/90低于自定90%门槛；长期真实个性/关系体验、方法净收益、知识表示/存储迁移与失效传播仍须扩大验证 |
| 多Bot、Agent与角色蓝图 | 原任务调度与默认负责投影的局部机制 | BotBinding/TaskOwnership、负责人任期、委派DAG、子预算、撤权和迟到结果；通用Agent工厂及按需角色装载，NPC世界仍仅设计 |
| 全局资源协调 | 默认两路任务并行、队列/优先级、部分预算与资源检查 | 跨聊天、研发、模型和专业工具的统一资源租约、根预算及前台响应保障；未证明低内存PC长期资源表现 |
| 更广的自主编程 | 模型/Codex CLI产出候选、纯文本Python工具、受限验证、受控发布与回退 | 多文件/多语言工程研发、桌面操控外部编码软件、跨任务通用化和完整业务验收；不能称任意需求都可自动补齐。[编码通路](toolchains.md#autonomous-development-providers) |
| 自检、自愈、进化三种能力 | 局部健康查询、执行重试、恢复等待、候选和包回退 | 统一SelfModel、incident去重、原因定位、修复租约、原故障独立复测、观察及回接；分别可配置的完整流水线尚未落地 |
| 可持续自主进化 | 受限经验/试验、候选检查与包版本管理 | 真实改进机会、预授权低风险自动准入、灰度收益、跨版本防退化、失败回退、旧能力安全退役形成常态闭环；不能用一次生成代码证明长期进化 |
| 核心/模块可替换 | Windows工作台A/B应用交接、排空与兼容恢复 | 通用模块drain/export_state/import_state、第二实现的状态迁移、版本栅栏、净收益与独立回退；应用换包不等于K5自身模块改造 |
| 本地小模型和语音 | 模型目录/下载/评估基础、E5嵌入；本地Qwen配置保留 | 可运行本地对话LLM、STT/TTS/VAD/声纹、实时双工语音及中断；自动装卸/替换和离线网络诊断自恢复。目录能声明模型种类不等于已有运行器 |
| 原生精灵与跨平台 | Windows透明双窗、独立机器人/标签、共用API，主人确认基础拖动和右侧邮件标签有用 | 多屏/DPI、托盘/键盘完整路径、自然表达调用及长时资源；Linux/macOS原生壳、隔离和秘密存储适配尚未验收 |
| 全面的个人生活/工作助手 | Gmail有限管理及邮件待办闭环、个人提醒、家庭私密空间、部分学习/专业能力 | Gmail增量/长期规则质量与更广写入验收；QQ、真实日历、微信、播放、旅行购买、密码管理与可靠本人识别等完整共用能力；已有私密空间不等于这些账号/服务已接入 |
| 多设备统一助手与硬件 | 领域/设备端口设计 | 配对、共享分域、断网单机续行、重连合并、唯一执行权/冲突处理；真实第二节点和物理设备/机器人。设计图或单机模拟不算跨机验收 |
| 扩展、安全与环境治理 | 受控HTTP MCP、本机访问门、Windows DPAPI/LPAC/Job、停止和恢复入口 | MCP真实外部服务组合与供应链验收、公开发布签名、独立监督/锁存、依赖/旧代码/数据的安全退役及恢复矩阵。G0无通用自动判定器，不能承诺绝对无误或永不违背主人利益 |

优先把低打扰委托、可靠执行/结果验收和资源协调接到现有能力，再扩经验/多Bot、自愈和K5模块替换；语音、多设备与硬件按K6能力分别推进。不是另建阶段，也不要求等全部功能完成才为主人办事。

<a id="current-state-evidence"></a>
## 证据边界

- 验收几乎全部来自本工程自建的测试、探针和合成数据。真实个人数据已用于有限Gmail读取；2026-11-10又完成限定本人邮箱的1封验收邮件发送与读回，未调用模型处理邮件正文。真实模型历史调用累计数百次，本文未重新统计账单或调用总数。
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
| 原生精灵多屏与长期交互 | 双窗已采用，基本拖动/点击已获主人确认；真实多屏/DPI、全部托盘/键盘路径及长期资源表现待验 |
| host 层 20 个模块的既有导入环 | 未拆；已加检查防止继续扩大 |
| 工作曾只在本机工作区 | 2026-10-30 已保存源码检查点并推送 GitHub 开发分支；运行数据和私密凭据仍不入库 |

<a id="current-state-next"></a>
## 下一步

1. v0.1.5已采用，原生精灵命中/独立拖动与受控邮件闭环已实现并取得分项证据；数据、凭据与设置保留，备份位于 `D:/Jarvis-backups/native-mail-20261109-a`。[本轮验收](delivery-validation.md#native-mail-20261109)。原生入口为`StartJarvisCompanion.bat`，仍共用工作台API。
2. 后续补真实多屏/DPI移动、托盘/键盘和长期资源验收；真实Gmail接口限定本人邮箱的1封发送/读回已验收；保持机器人通用聊天与右侧独立邮件标签；补充邮件自然请求及完整工作台/精灵操作实点，不再将机器人不展示邮件判作故障，不能用接口通过替代界面通过。当前邮件完成反馈是本人确认，不是通用业务自动验收。
3. 扩大真实语言来源、委托授权、任务结果核对与经验收益对照后，再推进小规模多Bot责任链、统一自愈和自身模块改造。[后续顺序](decisions-review.md#assistant-release-follow-up)。完整迁移矩阵、无人值守邮件管理和长期收益仍未完成。

<a id="current-state-owner-decisions"></a>
## 需要主人决定

- `control/bootstrap`（Rust 停止控制）尚未作为日用默认监管器，部分 CLI 故障测试有使用，控制语义与 Python 版部分重复：保留并改造成真正的进程监管器，还是删除。
- 验收截图、贴图与 CAD 导出（约 200 MB PNG）已不再进入 Git：是否改用 GitHub Release 附件或 Git LFS 对外发布。
- G0 锁存是否投入实现“工作负载不可写”的受保护存放位置。
