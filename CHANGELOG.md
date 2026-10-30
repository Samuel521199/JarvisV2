# 版本记录

2026-10-30 单机边用边开发方案（proposed）：明确稳定／开发环境分离、正式数据单一权威与受控共享，具体化 A/B 槽、MCP 局部更新及检查点接续；核对现有启动参数与缺口，未移动数据、建立第二实例或启用自动更新。[布局](docs/stack-project-layout.md#single-pc-development)／[更新接续](docs/evolution-release.md#single-pc-ab-upgrade)。

2026-10-30 PaK38 后部 C 形外缘（工作候选）：Jarvis 在作者提供的工具中选参并实际执行，保留倒向三角形、邻物距离与回执缺项失败；作者修复原生报告后验证与 Jarvis 实际表面相同，再做高模贴图和 GLB 回读。13 项相关测试通过；案例限本资产，原炮口缺陷及整体材质问题未解，不称自主建模或高模验收。[实施与边界](docs/studio3d-learning.md#studio3d-teacher-demonstration)。

2026-10-30 模型解耦与 Google／MCP 探针：明确 Skill 不指定提供者／型号，由执行路由遵守主人当前 Google 约束；新增显式合成验证，真实 Vertex 往返本机模拟 MCP 通过，2 次模型请求／1 次工具调用；生产微信闭环仍未接通。[规则与证据](docs/tasks-agents.md#weixin-model-neutral-routing)。

2026-10-30 MCP 候选补充（仅研究）：找到 Windows 微信 4.1、wxauto、iLink、通用 Windows 和网页 MCP，核对部分清单与工具源码；明确候选顺序、版本／认证／凭据及真实测试边界。未安装或连接，见[候选对比](docs/tasks-agents.md#weixin-mcp-candidates)。

2026-10-30 微信电脑操作补充（仅 proposed）：核实 GPT-6.1 Terra、官方 ComputerToolset 和 Responses 动作循环；定位当前 OpenAI 文字通道及 Gemini 图片限制，明确独立执行端口与本机 driver，未安装或调用模型。见[Terra 接入设计](docs/tasks-agents.md#weixin-terra-computer-use)。

2026-10-30 微信接入评估（仅 proposed）：比较官方 ClawBot 消息入口、Windows／macOS 桌面适配、MCP、企业微信与多后端方案；明确共用核心、资料分域、Python 兼容、未知发送状态、资源与实施验收。未安装或绑定微信，见[接入方案](docs/tasks-agents.md#weixin-integration-plan)。

2026-10-30 精灵邮件轻视图（未发布）：复用 Gmail 领域服务与共享 API，接通真实摘要、正文、未读计数、本地草稿和工作台管理入口；授权失效正确提示与重连。32 项邮件测试及相关访问／家庭回归完成，保留后台自动化、原生透明与真实发送的验收边界。见[邮件轻视图](docs/tasks-agents.md#gmail-companion)与[本轮证据](docs/delivery-validation.md#gmail-companion-evidence)。

2026-10-30 PaK38 上部提手贴合闭环（整炮未验收）：绑定实际开口帽缘与顶盖，原拱形保持并局部延伸封帽；Jarvis 在作者算法内选择参数并实际执行，保存回载验证、两向实渲与错误源／帽缘拒绝证据。11 项相关领域检查通过，原炮口微面／三角化问题明确保留；未证明自主诊断、迁移或提速。[范围与证据](docs/studio3d-learning.md#studio3d-teacher-demonstration)。

2026-10-30 炮口表面质量检查（清理未采用）：已发布端面明暗候选保持；新增实际三角化检查揭示多边形清理仍残留零面积／微三角形，作者试作及后续有界工具均拒收。Jarvis 实际评审参与拒收，没有几何复做。补充当前源正前实渲与署名博物馆外观照片，保留未解缺陷、失败和费用；最终 11 项相关测试通过，未宣称完整高模或自主能力达标。见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 炮架浅层外观续作（工作候选）：绑定原夹带、提手与支撑管，追加参考可见的长浅片及低片；保留着色条纹、取景遗漏与错误依赖拒绝。Jarvis 选择不同长度后实际执行，原生检查及作者补充支撑射线、高模贴图回读和多视图通过；35 项相关领域测试通过，仍非自主建模或完整高模验收，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 炮架提手有界修正（工作候选）：实际脚底采样补足中心射线遗漏，原六提手改为直顶圆转角并修正露空脚点；保留其他 73 对象。Jarvis 选参后从原源执行，真实错误依赖拒绝、152 项相关测试、高模贴图回读及多视图检查完成。仅证明本资产受限复现，完整高模与跨资产学习未验收，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 驻锄框架有界工具与复做（工作候选）：将已诊断的重叠暗块、板角及杆端修正接入既有领域服务；真实错误源／组件和外部支撑故障拒绝通过。Jarvis 选参并在原源副本执行，贴图回读与多视图已检查；147 项相关领域测试通过。仅有界局部执行，非自主建模或迁移，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 驻锄框架作者试作（未发布）：重新绑定组件，实际射线纠正“暗块即孔洞”的误判，局部并集诊断支持共面重叠造成该处伪影；封口断边、鼓胀着色和微面失败均保留。新试作补齐平面帽法线及相同支撑集合的有限重叠检查，尚待接入有界工具、Jarvis 复做和导出回读，网页候选保持。见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 驻锄曲板局部续作（工作候选）：跨视图证据不足时未强行改变上部盒体，转向明确的驻锄下角；直接复用已有薄板工具，Jarvis 选择参数并实际执行。新输入、错误坐标拒绝、固定相机／灯光前后实渲和高模贴图回读已检查；未新增领域代码、未重跑原测试或晋升通用经验，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 上部外壳只读核查：重绑最新候选与相邻附件，完成实际正交侧／斜视和一次 Jarvis 对照；降低前端肩部的假设缺乏支持，未执行变形，保留原模型。纠正相机与机械基准推断，本轮不计新建模或学习成功，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 尾部外观方向与凹凸修正（工作候选）：绑定真实求值几何，修正 C 形外缘方向和装饰圆面前后关系，保留原附件依赖与非目标对象；悬空、倒角重新求值及三角化误差均保留为拒收反例。Jarvis 实际选参复做后，作者另外清理未使用空材质槽，未重放计划；293 项领域测试与真实高模导出回读完成。仅游戏外观候选，完整高模和自主迁移尚未验收，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 外壳倒角明暗修正（工作候选）：依据实际全 flat 求值面的诊断，仅平滑三外壳的倒角，原主平面与几何／UV 保持；Jarvis 选取作者提供目标后同工具复做，前后实渲、已改源重放拒绝、贴图回读及五视图均保留，288 项领域测试通过。不计独立发现、泛化或完整高模验收，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 二号坦克炮塔改造 r3（未发布）：按接缝反证移除独立衬座并局部重塑原炮塔前壳、前顶面；保留非目标部件、原拓扑/UV及PBR图。实际三角面方向/退化、124点周边、同相机近景、GLB回读和错误来源拒绝检查通过。条件案例修订为第3版，见[案例与边界](docs/studio3d-learning.md#studio3d-part-assembly-case)。

2026-10-29 穿孔外侧板作者示范（未发布）：增加绑定实际布尔依赖的可见圆润外缘，保留原求值表面／UV与非目标对象，完成实际前后实渲、依赖错误拒绝和高模贴图回读；286 项领域测试通过。Jarvis 有界选参连接失败并隔离第五项 UNKNOWN，无复做或学习成功声明，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 二号坦克高模基础修订（未发布）：按用户反证修复炮盾埋入，补贴合衬座和独立前灯；保留原网格/UV、主体变换与15张原贴图。底座干涉检查失败后使用表面采样拟合落点，实际多视图和GLB回读通过；修订条件案例，不把原模型审阅当作本轮验收。见[案例与边界](docs/studio3d-learning.md#studio3d-part-assembly-case)。

2026-10-29 中央炮架试作评审（未发布）：Jarvis 对新实渲的独立请求成功，因参考收益不足拒收浅凹面；保留原网页候选和四项 UNKNOWN，不补跑失败分析。反例条件检索正负检查通过，并保存署名授权的实物参考及当前穿孔板只读依赖诊断，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-29 中央炮架局部试作（未发布）：补齐源绑定的后表面浅凹面、邻物采样及闭合／UV 检查，保存实际前后 Blender 与渲染；280 项领域测试通过，尚未替换网页模型。新的 Jarvis 参考分析连接失败，保留第四项 UNKNOWN 及查询修复证据，未重放或计作学习成功，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 二号坦克分件装配（未发布）：新增本机高模 GLB 装配固定工具，保留来源、层级和原始 PBR；实际组装用户五个分件、修正安装并完成 GLB 回读与多视图。四项本资产候选经验可检索，Jarvis Flash 实际识图审阅完成；Argon 超时/费用未知如实保留。23 项相关测试通过；低模、运动和跨资产学习收益未验收。[案例与边界](docs/studio3d-learning.md#studio3d-part-assembly-case)。

2026-10-28 独立人物建模技能（未发布）：本机新增 `blender-character-authoring` 与实际 Blender 创建／形态修改／引导发束／回读检查工具，完成样例及三种拒绝验证，并直接用于人物头发副本；保留失败试作与四方向实渲。人物相似度和发型仍未验收，表情、动态与导出未验证，见[人物试验](docs/studio3d-learning.md#studio3d-character-trial)。

2026-10-28 Blender 技能适配（未发布）：参考 Charakuru 非官方工作流，将现有 3D 工作室统一为分阶段制作与修改技能；增加源摘要绑定的部件/材质编辑、真实渲染、新旧版本与差异回执。65 项相关测试通过，并完成原生和界面改模；角色绑定/表情/VRM 与任意外部 Blend 编辑未接入，主服务未重载。见[验收记录](docs/delivery-validation.md#blender-workflow-evidence)。

2026-10-29 车轴外罩续作（未发布）：补齐原源绑定的闭合肩部／中段轮廓工具，保留实际端盖 UV 退化反例并修复分岛与面积检查。Jarvis 未获示范数值时选两项参数并实际执行，270 项领域测试通过；真实映射回读仍只属局部候选，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)，不计自主建模、史实认证或迁移。

2026-10-29 下炮盾续作（未发布）：增加源绑定的六薄板下缘与原附件关联变形、求值依赖／支撑采样和固定方向遮挡检查。实际取景遗漏与已改变源重放均拒绝；Jarvis 未获示范数值时选择单标量并实际执行，265 项领域测试通过。仅为局部外观与受限复做证据，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 下部炮架续作（未发布）：补齐限定原盒体的局部轮廓与浅面板工具，保留空顶点邻近、300 秒超限和视觉退步反例；装饰收腰未采用。Jarvis 在未告知示范数值时选择单个面板厚度并实际执行，261 项领域测试通过；见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)，不计自主建模或迁移。

2026-10-28 前端外壳续作（未发布）：增加保留原顶点／面／UV 的有界外观曲面追加，按实际局部表面校正过大开口；保留 UV 拒绝、视觉间隙失败及未执行的旧规划。Jarvis 采用修正示范并实际复做，253 项领域测试通过；不计工程结构认证或自主迁移，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 摇架外观续作（未发布）：增加完整组件绑定的轴向贴合工具，保留既有小倒角、拓扑与非目标对象；实际过小位移限制负例拒绝。Jarvis 采用示范值并从原源复做，246 项领域测试通过；局部减少悬空，不代表整炮细节或自主学习达标，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 炮盾紧固件续作（未发布）：增加源组件绑定的头部布局与板面朝向工具，保留拓扑和其他对象；实际观察孔悬空落点被拒绝。Jarvis 采用作者控制并完成原源复做，240 项领域测试通过；不计跨资产迁移或完整碰撞证明，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 炮盾开孔续作（未发布）：增加摘要绑定的局部开孔轮廓工具，保留真实补片重叠失败并修正；Jarvis 采用作者控制后从原源实际执行，局部方法只作有前提的资产候选。234 项领域测试通过，不计完整自主建模或迁移，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 资产候选检索与炮盾诊断（未发布）：复用 Studio3D 经验服务增加资产范围、前提、工具版本及证据摘要受约束的建议案例读取；Jarvis 实际提出查询并选择返回案例，保留作者纠正和无晋升边界。227 项领域测试通过；炮盾光照／通道检查未改变模型，不计美术改善或自主学习收益，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 炮盾外缘续作（未发布）：增加绑定原始边界角点的薄板局部修圆、壳体拓扑及固定附件最近距离检查，实际局部边长反例拒绝过大偏移。Jarvis 读作者案例后采用原控制并实际执行；217 项测试通过，不计自动选例或独立迁移，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 环形轮廓续作（未发布）：新增限定圆环重采样、平滑与支撑贴合工具，保留源尺寸和非目标对象；实际位移限制反例及作者前后渲染已记录。Jarvis 读取示范后采用原控制，执行与采用证据单列，不计独立迁移，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 高模局部导出续作（未发布）：针对本地全量转换超时，增加受来源、几何和受支持涂层约束的声明组复用，重做变化轮组并实际 GLB 回读；失败和边界均保留，不提高资源或质量门。207 项测试通过，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 轮毂连接续作（未发布）：增加受限紧固件支撑与相邻物体检查，保留“已贴合但被内环遮挡”的真实失败。Jarvis 读取反例后选参，经实际 Blender 执行改善一处局部连接；205 项测试通过，仍不代表完整自主建模或跨资产经验，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 局部做旧续作（未发布）：增加受限损伤区域及保留原涂层的增量覆盖；近景纠正了整块重做漆面的过度清理，实际验证遮罩和金属度通道。视觉收益仍不确定，未更新已发布模型或晋升经验，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 局部漆面与诊断续作（未发布）：增加明确目标和材质角色保护，以及真实着色通道检查。Jarvis 原值选参已实际执行，但视觉效果不足而拒收，保留最新轮胎候选；不将工具通过计作学习成功，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 轮胎局部续作（未发布）：增加基于实际材质槽、连通组件和源码回执的轮胎表面修整工具，保留轮盘并以连续内凹胎纹替换错误凸片；失败试验与后续局部修正均保留，实际范围见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 材质检查续作（未发布）：只读补充渲染支持声明区域近景和三个固定灯光预设，资产入口核对锁、来源与成本；PaK38 最新候选已实际检查炮盾和轮组，仍需局部修整。模型复核中的低模投射推测已与真实操作记录区分，见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 火炮材质续作（未发布）：增加绑定候选的材质操作与导出回读，复用高模表面贴图导出、保留轮盘修订和失败反例。格式与几何检查不代替材质视觉验收；未减面或生成 LOD，见[材质与示范证据](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 火炮建模教学方案（proposed，未实施）：补齐作者直接操作 Blender、保存真实前后模型/动作/渲染、Jarvis 独立复做与变题验证的具体步骤，以及工具接入、条件经验、质量和全成本验收。仅形成方案，不计自主建模能力已提升，见[示范与验证方案](docs/studio3d-learning.md#studio3d-teacher-demonstration)。

2026-10-28 教学工具首轮实施（未发布）：Jarvis Host 已执行有界轮盘局部示范，保存前后 BLEND、动作和真实渲染；172 项 Studio3D 测试通过。示范仍有形状和表面问题，未采用为成功经验，Jarvis 独立复做及迁移尚未执行；实际范围与失败记录见[示范实施登记](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-28 教学局部续作（未发布）：增加有界筋条截面重塑、资产内示范归档和 Jarvis 参数复做执行器；真实前后渲染已出现局部改善。保留失败示范、审查误判和 UNKNOWN 费用；未证明全模型合格或跨资产学习收益，见[当前示范证据](docs/studio3d-learning.md#studio3d-teacher-delivery)。

2026-10-27 工作区增量（未发布）：增加人物独立经验契约、首次草模试验和固定 Blender Worker 协作资源通道；范围及未验证项见[人物草模试验](docs/studio3d-learning.md#studio3d-character-trial)。

2026-10-27 后续工作区增量（未发布）：人物新增连续身体固定配方、四参考复审及有界迭代控制；四视图审查、迭代进度和未验证项以[人物试验](docs/studio3d-learning.md#studio3d-character-trial)及本地实际回执为准。

2026-10-27 人物重点试验（未发布）：限定本资产的形体、脸与发型重点，修正侧视配对并保存实际审查和隔离试验；试验与 FBX 派生候选均未达到人物验收，详见[人物试验](docs/studio3d-learning.md#studio3d-character-trial)。

2026-10-27 人物反馈续作（未发布）：根据用户意见保留可回退的形体修订，定位用户贴图并试验分材质 UV 映射，记录四视图审查和资产专属经验；头发、动画与最终相似度仍待完善。

2026-10-27 可替换发型试验（未发布）：发型对象独立成集合，新增发束绑定头骨；完成集合开关和一次转头检查，其他姿态、导出与外观仍未验收。

2026-10-28 人物续作（未发布）：新增可回退的正面比例试作及四视图比较，保留后发失败试验并隔离模型审查中的相机误判；整体外观和动画仍未验收。

2026-10-28 人物脸部试作（未发布）：继续试验可回退的眼形与脸部轮廓，保留发型独立集合及对照证据；后发试验尚未达到要求。

2026-10-28 人物眼部参考续作（未发布）：新增蓝色虹膜、独立睫毛与可回退眼形试验，保留 Jarvis 的本资产视觉复核和失败发束证据；脸、发型、眨眼和动画仍未验收。

2026-10-28 人物新设计图续作（未发布）：保存脸型、眉色、嘴部与睫毛试验及多视图渲染，记录失败耳部和长发试验；整体相似度及动画未验收。

2026-10-28 人物脸部继续试作（未发布）：实验蓝色虹膜、眼周与嘴部局部修改并保留多视图，审计复核中的坐标错误；整体外观、动画和导出仍未验收。

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

**3D 能力接续（2026-10-27）**

- 新增语义外观参数及四类有界造型工具、真实五视图审查与证据绑定的局部修改循环；保留退步候选和失败请求，候选经验不自动晋升。leFH18 已获用户验收，PaK38 开始实际运行；独立建模与跨模型收益尚未通过验证。见[制作闭环](docs/studio3d-learning.md#studio3d-learning-commands)。
- 制作循环增加未改部件摘要约束、补充实渲视图/几何区域裁图及独立刚性组表面贴图导出。小样验证 GLB 重导入后的层级、原点与材质画面，失败尝试保留；完整 PaK38 质量与可动性仍在验证。

- 修复程序化漆面导出 GLB 时缺省成白色：导出声明的基础 PBR 并保留几何；程序纹理仍留在 BLEND。可对确认中断的成对比较保留未知费用并隔离候选，继续独立工作，不重放原请求。

- 针对 PaK38 细节不足，增加可选的连续冲压轮盘与固定操控座结构；候选须经实际渲染、五视图回归和人工验收。

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
