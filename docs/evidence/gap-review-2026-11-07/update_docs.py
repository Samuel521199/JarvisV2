"""Append source-backed cross-boundary gaps without changing runtime policy."""
from pathlib import Path
import hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
p=ROOT/'docs/decisions-review.md';s=p.read_text('utf-8')
assert 'id="assistant-cross-boundary-gaps"' not in s
section='''<a id="assistant-cross-boundary-gaps"></a>
### 进一步深查：跨模块、长期运行与恢复还漏了什么

**2026-11-07增补结论：最大的补项是把已有模块接成可持续履约的个人助手。** 在[上一轮施工队列](#v012-next-work-order)之外，本轮确认了通用规划入口、时间语义、跨库交付、数据兼容和长对话连续性等连接限制。它们会直接影响提醒、常设委托、多Bot及自改造的可行性，需纳入原K阶段的具体交付。以下是源码范围内的限制或待补验收，不代表每项都是已复现故障，也不宣称彻底扫描了全部文件。

本轮在开发提交`efe50c7`上继续静态检查，并新增运行应用采用/回退、会话文件夹、记忆迁移三组现有测试，共53项、0失败、0错误、0跳过；范围与摘要见[补审证据](evidence/gap-review-2026-11-07/audit.json)。这53项不与上轮81项合并为全量验收；没有执行真实邮件、付费模型、生产升级、数据迁移或备份恢复。下面新增机制全部为proposed。

| 补项与优先级 | 实际代码依据／限制 | 应补的实现与验收 |
|---|---|---|
| **先补：通用能力接线** | [capabilities.catalog](../host/capabilities.py)只组合已发布纯文本工具与MCP，最多12个；有两类时各取前6。邮件、图片、3D专用入口不等于通用Goal能编排这些能力 | 给现有领域服务增加类型明确的能力适配：输入/输出、当前可用性、许可、目的地、效果类型、回执、取消和重试语义；注册目录是投影，沿原服务执行。大目录按任务检索并解释未选原因，测试正确工具排在第13个以后也能找到 |
| **先补：规划表达能力** | [goal-plan契约](../contracts/schemas/goal-plan.v1.json)最多4步，只能input或previous；[validate_proposal](../modules/task_resource/plans.py)限制MCP为第一步原输入；[goals](../host/goals.py)按线性文本步骤受理 | 先支持一个有界的类型化业务流程，表达外部资源ID与修订、等待、选择和部分成功；不要只放宽4步上限或把所有东西塞入text。旧纯文本契约继续兼容，新增每个动作均绑定独立来源和参数审阅 |
| **先补：长期承诺与一次执行分离** | [Plans.create](../modules/task_resource/plans.py)规划期限600秒；目标批准时生成的许可有效600秒，任务max_seconds=600；[Scheduling.pending](../modules/task_resource/scheduling.py)中的due_at只影响排序，不限制到点前执行 | 长期承诺保存当前要求、版本和到期策略，到期才在有效委托内创建短执行实例；单次许可过期不得自动延长。分别定义到期时间、最早执行时间、许可有效期、执行超时；不能把max_seconds调大冒充长期自治 |
| **先补：等待原因与唤醒** | [Waiting.advance](../modules/task_resource/waiting.py)只自动回接已请求且因module_disabled等待的任务，最多3次唤醒；邮件有自己的等待状态 | 沿原待办/任务加入有界触发适配：时间、网络、权限、用户回答、外部结果；每个等待有负责人、到期、下一动作与取消传播。源事件先于登记、重启、重复事件、过期事件都需覆盖；定时器只负责提出执行，不制造许可 |
| **先补：执行、交付、已阅分开** | 对话先finish再[发布文件](../host/session_workspace.py)；跨核心库/对话库/文件系统没有单一事务。已有错误记录与显式sync；[Sessions.publish](../modules/workspace/sessions.py)检测已有不同文件并拒绝覆盖，部分写入会成为冲突 | 为需要自动交付的域增加持久投递意图、版本、摘要、重试与冲突处置；只在自己的未改文件范围恢复。测试“已生成但文件夹失效”“写一半崩溃”“用户改过文件”“通知显示但未阅”；不能用模型说完成替代交付回执 |
| **先补：数据库和文件兼容矩阵** | [应用生命周期](../modules/release_recovery/application.py)是code-only，manifest只接受data_schema=7；[进程启动](../adapters/application_host.py)也只检查核心库schema7。其他领域表与文件还有各自结构 | 记录所有持久存储的读/写兼容范围、迁移版本与原版本可读性；采用前验证，迁移中断可接续，旧代码不能破坏新数据。业务备份与代码回退分开，离线恢复演练验证最新状态/撤回/墓碑仍生效；绝不能恢复旧业务快照来掩盖坏升级 |
| **先补：委托的细粒度边界** | [GrantStore.authorize](../control/policy/grants.py)核对主体、scope、capability、时间和动作单位；没有通用逐参数目的地/收件人/频次策略。连接器和邮件已有各自控制，不应误称完全无校验 | 新委托在原许可上约束资源与目的地、允许字段、频次、费用、时间和撤回版本；动作执行前重新核对。来源邮件/附件提出的指令不能成为授权；测试合规自动推进与超范围拒绝两侧，避免以全部阻止获得虚假达标 |
| **先补：未知外部效果的归因与补救** | [Ledger](../modules/task_resource/ledger.py)已有DISPATCHING/UNKNOWN和确认；邮件已禁止未知写入直接重放。取消只能防止后续动作，不能证明远端没有完成 | 每个外部动作声明幂等键支持、回执查询、对账窗口与补救能力；“超时→取消→迟到成功”保留事实并提示剩余影响。需要补救的动作仍走对应许可，不能把重试、撤销、补偿当成同一操作 |
| **扩自治前：预算与资源租约** | [work_budgets](../modules/task_resource/work_budgets.py)累计动作单位；[pricing](../sdk/pricing.py)提供价格快照估算。对话、规划、图片、邮件、3D等有独立队列或通道 | 原调用记录上关联root_work/attempt和费用预留、结算、未知计费；不同币种不直接相加。供应商并发/速率、CPU/GPU/内存按资源域协调，保留聊天与停止响应；多Bot共享根额度而非每人新开一份预算 |
| **扩长期陪伴前：上下文连续性** | [Dialogues.context](../modules/dialogue/store.py)最多取15个成功历史轮次，超50000字节移除最旧对话；显式依据可延续，但自动提取和所有承诺不会因此自动持久化 | 持久保存有来源的当前承诺、未决问题、计划及修订；摘要仅是可重建派生物。超过窗口、换模型、跨天、恢复后仍能找回未完成事项；误摘要可纠正，失效事实不能由摘要复活。不无限扩上下文，也不把所有闲聊存成长期事实 |
| **扩学习前：解释知识的实际贡献** | 已有来源修订、墓碑、依赖失效、修改过的导出文件保留和限定方法使用链；这不等于任意衍生摘要/通知/缓存都已覆盖 | 先列数据血缘清单，再为新增承诺、投递、摘要接失效与撤回端口；受管文件撤回、用户自改副本保留并提示，外部复制件明确边界。方法采用须记录实际使用、适用条件与迟到结果，用消融验证质量和总成本，负收益隔离 |
| **扩自愈前：健康与事件追踪** | [logs](../control/logs.py)有轮转日志与退避诊断；任务、邮件、模型、交付各有局部ID；没有统一业务故障履历足以串起全部跨域过程 | 统一关联根工作、轮次、动作、调用、交付、构建与故障ID；记录不含正文/凭据的阶段时间和原因。区分进程存活、能受理、领域可用和任务已完成；失败归因必须能指出证据和下一步，未知保留未知 |
| **长期日用前：环境、容量与恢复** | 已有路径所有权、文件摘要、SQLite保护、局部迁移测试；本轮53项不能证明磁盘满、长期累积、多库一致恢复和换机DPAPI恢复都达标 | 声明各数据类保留/压缩/清理规则与磁盘余量；清理派生缓存不删除恢复证据或用户资产。用独立数据做磁盘满、只读目录、索引损坏、模型缺失、时钟变化、断电与换机重新授权演练；断言业务恢复而不只进程能启动 |
| **每次采用前：证据覆盖和漂移** | [application_policy](../sdk/application_policy.py)固定12个测试文件作为核心门，不能覆盖全部领域；网页/原生/真实供应商行为会变化 | 核心门+变更影响的领域门+跨入口探针+必要真实集成。记录源码/运行构建/模型/提示/检索/评估器版本；模型返回、价格、工具契约变化后降级为待复核，不永久沿用旧通过。公开CI不得读取日用账号、私密数据或直接采用候选 |

**需要补的是连接，不是另建核心。** 通用规划器通过契约调用邮件等原领域服务；原服务仍持有自己的远端状态和回执。根工作维护当前目标和责任，派生执行引用它；通知投递表保存投递过程，不能竞争“哪份计划当前有效”。长期委托授权到期行为，短执行仍须重新核对许可和费用。这样既能保持模块独立，也能让三职能看到一致的真实工作状态。

**这次最应提前固定的六组联合验收：**

| 联合场景 | 期望的可观察结果 |
|---|---|
| 建立明天提醒→跨时区/休眠→更正时间→重启 | 原始时区、当前版本与补发策略清楚；旧版本不执行，同一轮次不重复交付，未知显示回执不冒充成功 |
| 发起外部动作→网络超时→撤回授权→远端迟到成功 | 不再新发动作；旧动作实际效果可对账，保留迟到成功及剩余补救事项，不倒写成“取消所以从未执行” |
| 回复已写库→文件发布一半→目录被用户修改 | 原回复仍可取；自动投递显示失败并可恢复；保留用户文件，不能重跑模型来掩盖交付故障 |
| 知识被用于回答/计划→来源撤回→恢复旧代码 | 依赖输出失效或标需复核；墓碑、撤回许可和当前计划不复活；用户自改副本有明确告知 |
| 长对话超过15轮→换模型→任务负责人交接 | 当前承诺和未决事项仍可引用来源，旧负责人不能更新当前任务；受保护背景不因换模型扩大外发 |
| 多Bot/多通道并发→预算临界→一个调用计费未知 | 根额度预留不超配；未知金额保留，不当0；暂停受影响动作并保留前台响应和可解释原因 |

这些案例补充原[V-CLC联合场景](delivery-validation.md#closure-validation-cases)，不另发一套V编号。先用隔离数据故障注入，再进行范围明确的真实请求；模型审核意见只是待核对证据，客观回执与业务真值优先。陪伴/学习继续以用户反馈、低打扰、真实作答、延迟复测衡量，不通过自动情绪推断生成身份标签或把一段心情当永久偏好。

**对下一步顺序的细化：** 先定义类型化能力适配、长期承诺/短执行和数据兼容契约；进程生命周期与可重复回归同步补齐。随后用个人待办/一次性提醒贯通来源、唤醒、交付和纠正，逐项跑上述联合故障场景。只有业务核对、撤回与费用成立后，再扩大低打扰委托、条件化经验和多Bot；自主模块改造最后依赖这些证据。原生薄壳继续作为可并行的呈现适配，不承担第二套任务或记忆逻辑。

'''
s=s.replace('<!-- book-footer:start -->',section+'<!-- book-footer:start -->')
marker='**2026-11-07最新优先级：**'
at=s.index('\n\n',s.index(marker))
s=s[:at]+' 进一步补审见[长期承诺、跨模块交付、数据兼容与联合故障缺口](#assistant-cross-boundary-gaps)。'+s[at:]
p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'docs/manifest.json';m=json.loads(p.read_text('utf-8'))
for d in m['documents']:
    if d['path']=='docs/decisions-review.md':d['owns'].append('assistant-cross-boundary-gaps')
p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
p=ROOT/'CHANGELOG.md';s=p.read_text('utf-8');needle='[分析与实施顺序](docs/decisions-review.md#v012-next-work-order)。'
s=s.replace(needle,needle+' 同日补审类型化能力接线、长期承诺/短执行、交付恢复与多库兼容等14项，补6组联合故障验收；另跑53项现有离线测试通过。[补审](docs/decisions-review.md#assistant-cross-boundary-gaps)。',1)
p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'docs/current-state.md';s=p.read_text('utf-8');needle='[施工顺序、效果与采用条件](decisions-review.md#v012-next-work-order)。'
s=s.replace(needle,needle+' [补充连接缺口](decisions-review.md#assistant-cross-boundary-gaps)：当前四步文本计划、十分钟执行与排队due_at不能直接承担长期提醒；通用能力适配及数据迁移兼容需先定义。',1)
p.write_text(s,encoding='utf-8',newline='\n')
files=['host/capabilities.py','modules/task_resource/plans.py','contracts/schemas/goal-plan.v1.json','host/goals.py',
       'modules/task_resource/scheduling.py','modules/task_resource/waiting.py','modules/task_resource/coverage.py',
       'modules/task_resource/ledger.py','control/policy/grants.py','sdk/pricing.py','sdk/application_policy.py',
       'modules/release_recovery/application.py','adapters/application_host.py','adapters/storage/sqlite.py',
       'modules/dialogue/store.py','modules/workspace/sessions.py','host/session_workspace.py','control/logs.py']
assert 'COUNTS 53 0 0 0' in (HERE/'tests.log').read_text('utf-8')
audit={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'date':'2026-11-07','scope':'Source-backed design gaps, not proof that every gap is an observed failure',
       'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
       'tests':{'run':53,'failed':0,'errors':0,'skipped':0,'full_regression':False},
       'runtime_changed':False,'production_accessed':False,'checks':{}}
write=lambda:(HERE/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write()
for name,cmd in [('navigation',[sys.executable,'tools/sync_doc_navigation.py','--root','.']),
                 ('docs',[sys.executable,'tools/check_docs.py','--root','.']),
                 ('architecture',[sys.executable,'tools/check_architecture.py']),
                 ('diff',['git','diff','--check'])]:
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (HERE/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    audit['checks'][name]={'returncode':r.returncode,'output':(r.stdout+r.stderr).strip()};write()
    print(name,r.returncode,(r.stdout+r.stderr)[:600]);assert r.returncode==0
