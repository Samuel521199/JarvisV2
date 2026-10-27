# 火炮类游戏资产制作与经验学习实施手册

<!-- book-nav:start -->
[工程主入口](../README.md) › [第四篇 · 自主成长与维护](../README.md#part-evolution) › 第 16 章

**本章导航**

- [目标、范围与当前状态](#studio3d-learning-scope)
- [实施工作包与顺序](#studio3d-learning-packages)
- [接入位置与运行契约](#studio3d-learning-runtime)
- [方法卡和可复用经验](#studio3d-learning-methods)
- [比较与局部修复闭环](#studio3d-learning-review-loop)
- [24 项练习和收益评测](#studio3d-learning-curriculum)
- [已实现工具与调用方法](#studio3d-learning-commands)
- [执行登记与剩余工作](#studio3d-learning-evidence)
<!-- book-nav:end -->

<a id="studio3d-learning-scope"></a>
## 目标、范围与当前状态

用户于 2026-10-27 授权先保存具体步骤，再依本文实施。目标 accepted；下列工作包按实际证据分别登记；1.0.0 已实现受限工具闭环，完整美术学习与迁移收益仍 proposed。本文是 Studio3D 领域实施手册，复用 [K0—K6 主路线](core-bootstrap.md#bootstrap-5)、[经验编纂](knowledge-learning.md#experience-consolidation)与[知识贡献验收](delivery-validation.md#knowledge-value-ablation)，不建立第二套核心架构。

第一版服务于游戏用火炮及相似硬表面部件的外观制作、可见装配、材质、动画分组和交付验证。原始参考及高模母版保持可追溯；高模用户验收前不进行低模、投射烘焙或 LOD。AAA、历史精确复原及长期学习收益分别需要证据，不能由格式检查或面数替代。

现有 leFH18 经验来自一个资产，数十次候选不算数十个独立学习样本。其折叠侧翼属于当前资产要求；通用审查不得把这一要求强加给其他资产。知识内容、图片和模型输出均为资料，不能扩大工具权限。

<a id="studio3d-learning-packages"></a>
## 实施工作包与顺序

| 工作包 | 具体操作与交付 | 验收条件 | 当前状态 |
|---|---|---|---|
| S3DL-01 经验种子 | 从 leFH18 已确认的问题提炼条件化方法卡；记录来源、反例、范围、检查器和工具绑定 | 原始证据可定位；未知结果不记成功；资产特例不会命中其他型号 | verified：10 张种子卡；未证明迁移收益 |
| S3DL-02 参考规范 | 通用检查与资产参考策略分离；保存最新用户纠正、禁止恢复零件及未决冲突 | 不同炮盾类型可使用同一审查器；图像内容不变成指令 | verified：通用/资产策略分离，策略/经验变化拒用旧审查缓存 |
| S3DL-03 经验运行 | 接入领域经验存储、匹配、采用记录和迟到反例停用；每次使用记录方法版本 | 错误条件拒用；成功需关联实际工具证据；同资产反复成功不算迁移 | verified：条件检索、采用收据、反例停用；晋升仍人工 |
| S3DL-04 工具与执行 | 固定第一方 Blender 工具检查部件图、局部修复和导出；有界循环、停止、预算与失败记录 | 不执行模型生成 Python；修改受限且可回退；最终文件重新检查 | verified（限定）：两种修复工具；其余工具待实现 |
| S3DL-05 真实闭环验证 | 用实际 Blender 文件运行诊断、修改、复查和渲染对照；保存模型及图片摘要和耗时 | 有故障前后的实际文件；成功和未解决项分别报告；回归检查通过 | verified（诊断）：3 个小样 + 1 次母版只读检查 |
| S3DL-06 练习协议 | 冻结 24 个独立练习的任务、训练/开发/留出分组、评价口径与全成本账本 | 同资产视图不跨组；测试结果不反向进入调优；未运行项明确标记 | implemented（登记）：24 项清单，参考与基线待冻结 |
| S3DL-07 迁移验收 | 对新参考资产逐级练习；比较知识、方法与工具的贡献；用户审阅完整高模 | 新资产重大错误、人工介入、返工及成本有配对证据，才能声称收益 | proposed：正式美术练习 0/24，迁移收益未验证 |

实施顺序为 01→02→03→04→05→06→07。每个工作包均在既有 K 阶段下实现。先完成可运行、可验证的最小闭环；24 项正式美术练习与跨资产收益不能用单元测试或人工植入故障的小样替代。

<a id="studio3d-learning-runtime"></a>
## 接入位置与运行契约

- 领域知识和经验生命周期复用 `modules/context_knowledge` 的职责；Studio3D 经验使用明确的领域记录，不混入现有纯文本方法并假装兼容。
- 制作流程、参考策略和方法绑定归 `modules/skills/studio3d`；实际场景操作归 `adapters/studio3d` 的固定第一方工具。
- Host 负责启用状态、停止、路径与文件身份、工具执行、预算和收据；CLI 与工作台共享同一领域服务。
- 通用知识治理仍由[条件经验路由](knowledge-learning.md#conditional-experience-routing)与[迟到结果](knowledge-learning.md#experience-delayed-outcome)维护；领域实现记录版本、适用条件和未实现范围。

一次工具输入至少包含：资产身份、源模型摘要、方法版本、检查/修复范围、对象语义 ID、可动归属及有界参数。一次输出包含：实际源/结果摘要、改变对象、检查结果、渲染证据、工具版本、阶段耗时、费用已知/未知项与未解决问题。

工具先执行只读检查，再按已授权范围局部修改；禁止全场景随意重写。部件关系需区分组织父子关系、真实可见支撑关系和动画归属。缺少接触证据时保持未知，不用包围盒相交宣称装配正确。多轮没有改善时诊断停滞并退出本次有界运行，不无界重试。

<a id="studio3d-learning-methods"></a>
## 方法卡和可复用经验

方法卡包含：稳定 ID、版本、问题现象、适用条件、排除条件、原因及证据、检查工具、修复工具、验证要求、来源、反例和生命周期。区分事实、用户要求、推测和已验证方法。运行检索先判断范围/版本/条件及来源 SHA256 是否仍一致，再选择少量相关卡片；不把全部聊天反复发送给模型。

首批经验覆盖：多视图矛盾、相机误判、过度细分、表面投影与 UV 错误、悬空附件及删除残留、禁止零件复活、实际导出版本、可动部件合并、漆面与金属分区。`3DModels/leFH18/metadata/optimization-recipe.json` 继续维护该资产的具体要求；通用方法只引用来源和提炼后的条件，不复制全部资产规则。

晋升顺序：候选→本资产验证→跨资产验证。只有符合事前标准的独立资产结果才能扩大范围；迟到反例停用相关方法，保留历史采用记录。停用不能自动撤销用户当前资产，后续使用必须重新核对。格式通过、检查器通过、视觉近似、用户批准分别记录。

<a id="studio3d-learning-review-loop"></a>
## 比较与局部修复闭环

1. 固定参考来源、资产变体及用户纠正；记录图间冲突与未覆盖区域。
2. 建立部件身份、附件归属、材质和运动关系；检索匹配的方法。
3. 校准相机、构图、灯光和动画时刻，保存设置与摘要。
4. 渲染同一模型的五视图和指定局部；需要时输出对象 ID、法线和深度辅助定位。
5. 将差异分为相机、几何、材质、灯光；优先修复少量证据明确的问题。
6. 对改变对象及依赖部件复查，检查其他视图回归；失败保留前后证据并回退候选。
7. 对实际导出并重新导入的文件重复检查；确认预览文件身份。
8. 保存经验采用、工具动作、结果、人工介入及成本。完整高模仍需用户验收，之后才可低模与 LOD。

第一版允许部分检查仍需人工或视觉模型，必须明确显示未测；不得用生成图片重绘结果冒充真实模型渲染。

<a id="studio3d-learning-curriculum"></a>
## 24 项练习和收益评测

先登记 12 个制作学习任务、6 个开发验证任务、6 个留出验收任务，按独立资产/参考来源分组。训练覆盖折弯板与孔洞、轮毂、摇轮及支撑、附件归属、涂装金属、UV 与法线、运动分组、组合体和完整高模。开发/留出保留相近难度并包含不同变体，防止只会重复一个造型。

正式练习必须有独立目标参考和质量验收。工具回归小样、人工植入缺陷和同模型的多视图单独登记为诊断用例，不计入 24 项正式练习。留出结果一旦用于改方法，该任务退出留出组，另补未见任务。

比较固定模型/工具/硬件/参考/预算：基础流程、加事实、加条件方法、加执行技能。记录重大错误、轮廓与关键部件差异、重复错误、人工介入、修复轮数、阶段耗时、输入/输出 token、API 费用及失败尝试。未知费用保留 null；本地工具无 API 调用不代表设备、电力和作者成本为零。不能把各方法收益相加成“智能提升百分比”。


<a id="studio3d-learning-commands"></a>
## 已实现工具与调用方法

当前源码中的 CLI 与 HTTP 共享 `host/studio3d_learning.py`。CLI 已在本机实际执行；HTTP 计划、鉴权、启用状态、真实 Blender 异步执行、同 ID 不重放及反例停用在隔离测试服务中通过，见[实际回执](evidence/studio3d-learning-1.0.0/http-native/report.json)。正在使用的 18283 服务本轮没有重启，因此不能声称该进程已加载新路由；正常重启后加载。没有创建定时任务或后台练习循环。

在工程根目录使用已配置的 Python 运行：

```text
python -m tools.studio3d_learning --data-root user-data status
python -m tools.studio3d_learning --data-root user-data plan --contract 3DModels/Studio3D-Learning/diagnostics-v1/plate/contract.json
python -m tools.studio3d_learning --data-root user-data run --source 3DModels/Studio3D-Learning/diagnostics-v1/plate/source.glb --contract 3DModels/Studio3D-Learning/diagnostics-v1/plate/contract.json --repair
```

默认 run 为检查；`--repair` 明确启用条件匹配到的固定修复工具。无目标位置、无否定清单或方法被停用时不会猜测修复。每次最多按顺序执行两种工具；没有改善则 STALLED；声明问题新增则拒绝候选，原文件保留。退出与停止按现有 Studio3D 技能开关和 StopGate 执行；不加载外部 BLEND，不执行模型生成代码，不自动重放失败任务。

| API | 内容 |
|---|---|
| GET `/api/studio3d/learning` | 经验目录、状态和运行数量 |
| POST `/api/studio3d/learning/plan` | 对声明契约进行条件匹配，不执行修改 |
| POST `/api/studio3d/learning/run` | 输入唯一 id、source_job、contract 和 repair/render；仅使用已交付且摘要核对的 Jarvis GLB，异步返回运行 ID |
| GET `/api/studio3d/learning/runs/{id}` | 查询收据；其他进程的未完成状态保持 UNKNOWN，不伪称仍在运行 |
| POST `/api/studio3d/learning/cancel` | 请求停止指定运行 |
| POST `/api/studio3d/learning/feedback` | 引用真实采用记录登记反例并停用方法 |

新入口继承现有页面会话、家庭访问门和技能启用策略。工具临时目录与收据归当前数据根的 `artifacts/studio3d-learning`；经验状态归 `state/studio3d-experience.sqlite3`。结果中的已知检查通过、候选可继续编辑和用户高模批准是不同字段。

<a id="studio3d-learning-evidence"></a>
## 执行登记与剩余工作

1.0.0 已通过 100 项 Studio3D 相关测试、29 项共享技能/工作流/家庭访问回归及 4 项实际 Blender 诊断，并完成隔离 HTTP 到真实 Blender 的闭环。当前 leFH18 高模未获得用户完整批准，未生成低模或 LOD。完整 24 项美术练习尚未执行。

- [实际执行报告](evidence/studio3d-learning-1.0.0/native-final/native-report.json)：板件与圆法兰各从 4 项声明问题修复为 0；第三个小样从 5 项变为 1，正确保持 PARTIAL_REPAIR。3 个候选重新导入后复查，官方 glTF 检查均 0 错误、0 警告。五视图来自 Blender 实际渲染。
- [leFH18 只读记录](evidence/studio3d-learning-1.0.0/native-final/lefh18-inspection-receipt.json)：确认当前 GLB 的 19 个声明网格；没有修改或替换母版，没有在本轮验证运动、材质或美术相似度。
- [尝试与成本](evidence/studio3d-learning-1.0.0/attempt-ledger.json)：保留相对路径和空场景 World 初始化两次实际失败；修复后的两轮诊断及隔离 HTTP 执行全部保留，重复小样不增加独立练习计数。工具运行没有模型 API 调用；作者 token、作者费用和本地计算美元成本未知，总价保持 null。
- 经验条目保存在 [领域方法目录](../modules/skills/studio3d/experience-cards.json)；正式练习登记在 [24 项清单](../modules/skills/studio3d/learning-curriculum.json)。全部正式练习为 PENDING_REFERENCE，诊断小样不计入。

| 实际渲染：修复前 | 实际渲染：修复后 |
|---|---|
| ![诊断板件修复前](evidence/studio3d-learning-1.0.0/previews/plate-before.png) | ![诊断板件修复后](evidence/studio3d-learning-1.0.0/previews/plate-after.png) |

以下边界保留：两种工具依赖调用者明确声明对象和已确认目标位置；尚无自动截图到网格定位、参考相机自动拟合、任意零件重建、通用材质自动修复或完整刚性合批工具。接近表面的采样距离不能证明无穿插或结构真实；动画资产在本学习工具版本中只允许检查。视觉模型审查已可按条件加载经验，未证明模型会从自然聊天独立编制完整的高模修复契约。

下一步按 S3DL-04 扩展工具并按 S3DL-06 为正式练习登记独立参考和基线，再执行 S3DL-07。完整高模的用户验收门保留。

验证至少执行相关单元/集成测试、实际 Blender 闭环，以及 `python tools/sync_doc_navigation.py --root .` 和 `python tools/check_docs.py --root .`。证据放在 `docs/evidence/studio3d-learning-1.0.0/`，资产输出归任务目录。测试通过不代替 24 项正式练习和跨资产美术验收。

<!-- book-footer:start -->
[返回工程主入口](../README.md) · [全书目录](../README.md#book-tree) · [上一章：自主进化、外部编码协作与版本发布](evolution-release.md) · [下一章：开发环境、多语言工具链与构建](toolchains.md)
<!-- book-footer:end -->
