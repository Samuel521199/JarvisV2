"""Publish evidence only after successful daily adoption and one bounded first question."""
from pathlib import Path
import html,json,re,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent

def main():
    production=json.loads((OUT/'production.json').read_text());daily=json.loads((OUT/'daily-first-question.json').read_text());shadow=json.loads((OUT/'shadow-results.json').read_text());native=json.loads((OUT/'native/result.json').read_text());tests=json.loads((OUT/'targeted-test-summary.json').read_text())
    assert production['passed'] and daily['passed'] and native['passed']
    steps={r['name']:r['result'] for r in production['steps']};state=production['after_state'];epoch=state['epoch'];backup=steps['stopped-full-independent-disk-backup'];preserved=steps['original-data-preservation-reviewed'];tokens=daily['attempts'][0]['usage']['total_tokens']
    md=f'''# Jarvis 跨会话英语学习与日用升级验收

<a id="english-learning-report-20261115"></a>
## 结论、改进与实际边界

2026-11-15已日用采用 **v0.1.11 / epoch{epoch} / 控制器协议7**。入口是原工作台顶栏“英语学习 · 跨会话记录与复习”。已在原英语会话准备一道生活交流题，等待用户本人作答；个人成绩仍为0条，未把开发测试混入日用。

本轮完成“出题 → 实际原答 → 可争议评价 → 记忆提示 → 跨会话错题变式 → 延迟复习与保守统计”的文字学习链。三类真实模型测试使用的是**开发环境合成学习者回答**；证明功能可运行，不证明用户英语提高，更不证明口语、听力或发音水平。

仍有一个运行问题待追踪：升级检查期间发现旧日用端口离线，起点和原因未查明；新版恢复后完成了有限在线观察，不能据此宣称长期稳定或本轮全程无中断。详见下方恢复记录。

| 改进 | 预期作用 | 本轮实际结果 / 差距 |
|---|---|---|
| 原答与模型判断分开保存 | 记住表现，避免把模型编造当作学习事实 | 三组原答绑定通过；评价可异议、来源可撤回；日用等待真实作答 |
| 错题跨会话接续 | 不必重复解释上次问题，换情境练习 | 新会话依据“周五/周四截止时间”错题出新通知题，实际读到了原答、纠错和记忆提示 |
| 主动回忆、辅助标记、间隔复习 | 改善保持与独立表达，避免抄答案刷分 | 算法时钟/同题/提示保护通过；真实隔天保持率和净学习收益未到观察时间 |
| 少量相关经历 | 控制上下文成本 | 每次最多2条相关评价、3道近期题，24KB消息限额；未与无记忆条件配对，不能声称已节省token |
| 工作资料绑定 | 练习用户提供的真实材料 | 首次模型擅自换材料失败，操作员发现；修复后原文由宿主直接展示、逐字引用校验，定向重测通过。不是全新留出泛化证明 |
| 兼容控制器与恢复包 | 出问题可回退而不丢学习记录 | 真实进程旧版拒绝发生在排空前；相容恢复版回退→新版恢复后文件与撤回状态保留 |
| 日用升级保留原机制 | 本机仍能边用边开发 | 原{preserved['original_databases']}份业务库的业务内容、{preserved['original_files']}份配置/会话文件保留；{preserved['unchanged_original_rows']}行不变，另2行仅原完成观察器刷新checked时间，正文/评分不变；原9类认证入口可读 |

## 科学方法与使用顺序

[方法与研究全文](../../english-learning-method.md#english-method-scope)给出检索来源与局限。没有对所有人、所有英语技能都最好的单一方法；本次组合采用主动回忆、间隔练习、行动任务、少量纠错、语块联想和变式再用。

1. 打开日用工作台顶栏英语学习，选择生活交流、日常沟通、工作资料或错题复习。
2. 在“我的回答”填写自己的英文表达。可要提示或看参考；外部翻译/他人帮助请标记，仍可学习但不计独立表现。
3. 看原答、纠错理由和记忆提示；模型判断不准确可点“这次评价不准确”，该评价不再参与调整。
4. 下次打开继续未完成题或到期复习，也可主动选择错题。原聊天和学习卡共用来源；删除来源后不再用于复习判断。
5. 累积跨日、同技能同难度、不同题面的独立作答后才显示描述性变化。初始1/3/7/14/30天是可调整的工程规则，不是个人遗忘曲线实测。

普通聊天原技能继续可用，但不自动转为学习成绩；避免将随意聊天、引用文本或模型回复误认为本人作答。首版仅个人文字学习；工作资料通过面板明确粘贴，发送给当前所选模型。没有新增自动提醒、任务授权、模型权限或后台付费循环。

## 验证、评分、成本与人工介入

| 项目 | 结果 | 证据 |
|---|---|---|
| 专项与原机制回归 | {tests['passed']}个唯一测试ID最终通过；不把重跑重复相加 | [去重结果](targeted-test-summary.json)、[最终48项](learning-final-r3.txt) |
| 原冻结政策独立验收 | 新版与恢复版各207项：206通过、1项平台跳过；政策摘要保持 | [日用采用回执](production.json)、[原生回执](native/result.json) |
| 浏览器 | 三条评价、原答/纠错、跨刷新保留、窄屏、无JS异常；未代用户提交回答 | [结果](ui-result.json) |
| 实际日用入口 | 首题跨刷新保留，0条伪造学习成绩，无JS异常；开发重启前后120秒25次日用观察同boot/build、无失败 | [日用界面](daily-ui-result.json)、[有限在线观察](live-observation.json)、[开发重启](development-restart-final.json) |
| 生活表达 | 意思/形式/得体 2/2/2；不同正确表达被接受 | [三类汇总](shadow-results.json) |
| 日常沟通 | 2/2/2；请求慢说与重复被接受 | 同上 |
| 工作通知 | 0/2/2；识别错误截止日，未被语法正确掩盖意义错误 | 同上 |
| 跨会话错题 | 新聊天选择work.notice，实际使用上次错误及纠正，生成新情境 | [复习原回执](english-shadow-20261115-cross-review.json) |
| 模型调用 | 开发8次真实调用、8,481 token；另有1次派发前本地UNKNOWN；日用首题1次、{tokens:,} token | [开发账本](shadow-results.json)、[日用首题](daily-first-question.json) |
| 人工介入 | 操作员纠正2处产品问题；未知结果自动重试0次 | 消息格式契约失败、模型替换工作资料，均保留原记录 |
| 学习提升 | 暂无本人作答、无真实跨日保持率、无受控净收益证明 | 不计算虚假提升百分比或CEFR等级 |

合计9次外部调用、{8481+tokens:,} token（含修复前浪费与推理token）。没有把币种成本猜成0；本轮未核对供应商最终账单。上轮9次/22,745 token属不同任务，不能直接作本轮节省率基线。

首轮测试还暴露了测试夹具路径、协议版本固定期望和原生观察器写入元数据的问题；失败日志保留，修正后复验。原生首次回退最后的字节断言失败，是测试观察器调用Store初始化写入PRAGMA所致；改为只读观察后再次真实回退/升回，字节、记录、撤回状态一致。日用冻结政策首验恢复包时，原有重启健康测试超时，阻止了升级；包字节和标准未改，单独复验通过后才继续。首次超时的具体系统原因未证明，不能笼统归为已排除的偶发问题；保留[fallback-validation-initial.txt](fallback-validation-initial.txt)。没有修改产品数据或降低旧版拒绝标准来过关。

## 原机制、版本与恢复

定向仍由本人目标和启用开关控制；协作复用DialogueHost、模型路由与预算账本；观察成长保存来源绑定的可争议评价。学习模块没有创建业务执行权限，不训练模型权重，不把错句导入一般知识库。普通聊天、自动修复回接、任务授权、STOP、未知结果处理与既有冻结验收政策保留。

| 标识 | 值 |
|---|---|
| 当前应用 | `{state['active']['build']}` |
| 相容恢复版 | `{state['previous']['build']}`（{state['previous']['version']}） |
| 当前控制器 | `{production['after_controller']['build']}` |
| 固定验收策略 | `{production['after_controller']['policy_sha256']}` |
| 独立盘停机快照 | `{backup['snapshot']}`，{backup['files']:,}文件，{backup['sqlite_integrity_ok']}份SQLite |
| 实际还原 | [还原及采用步骤](production.json)，逐字节/完整性核对；未启动还原业务 |
| 升级后恢复增量 | `D:/Jarvis-Recovery/controllers/2026-11-15-english-r2`；1,967文件、14份SQLite、控制器归档摘要核验，含新学习库与会话导出；[回执](recovery-increment.json) |

恢复版保留旧日用功能和学习库，只读保护学习任务；它没有新版学习面板，不宣称降级后还能继续学习。完整学习需再采用v0.1.11。原始不兼容v0.1.10会在排空前拒绝；切代码不恢复旧业务库、不复活撤回权限。跨机DPAPI恢复、整盘灾难恢复和长期自动学习收益不在本轮签收范围。

日用控制器已提交协议7后，在线探测发现18282没有监听，但应用登记仍为active；切换前boot_id未持久保存，无法确定离线起点及原因。因此**本轮日用连续在线性未签收**，不能借用隔离原生same-boot通过冒充日用无中断。保留当时失败回执，经原生命周期确认停止、备份、采用已验证版本并检查真实入口。原数据比较首次报两行变化；逐列核查确认仅既有完成观察器的checked时间更新，任务ID和正文逐字相同，其他行/文件保留；没有忽略整张表或覆盖数据。后续需要补持久健康观察和异常退出归因，不能以恢复可用代替原因查清。

## 后续效果如何验收

| 后续观察 | 判定方法 | 不满足时怎么处理 |
|---|---|---|
| 真实日用接续 | 用户答题后重开会话仍见原答、纠错与复习 | 检查原请求/模型回执/学习job，不自动重发未知付费调用 |
| 保持而非当天刷分 | 同目标同难度隔天独立变式，单列辅助作答 | 降低难度、缩短候选间隔、再解释重点；不因缺勤推断遗忘 |
| 评价可信 | 用户异议、人工抽查意义/形式/得体 | 有争议评价停用，保留原答；不让错误评分继续影响选题 |
| 效率 | 每个有效练习token、重复解释次数、介入数；后续做同任务配对 | 有记忆不省token或质量退步时精简召回，不以测试分数包装净收益 |
| 真实应用迁移 | 新生活情境、未见工作材料，与练习题分开 | 样本不足保持未知；文字证据不外推听力、发音、自然口语 |

本轮签收的是有限文字学习闭环与日用安全采用；长期个人效果需要真实使用后持续观察。语音输入输出、发音评价和独立标准化语言测评尚未实现。
'''
    (OUT/'report.md').write_text(md,encoding='utf-8')
    # Small standalone review artifact; tables are selectable text, not screenshots.
    def inline(value):
        value=html.escape(value)
        value=re.sub(r'\[([^\]]+)\]\(([^ )]+)\)',r'<a href="\2">\1</a>',value)
        value=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)
        return re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    parts=[];in_table=False;table_header=False
    for line in md.splitlines():
        if line.startswith('|'):
            if not in_table:parts.append('<table>');in_table=True;table_header=True
            if set(line.replace('|','').strip())<={'-',' ',':'}:continue
            cells=line.strip('|').split('|');tag='th' if table_header else 'td';parts.append('<tr>'+''.join(f'<{tag}>'+inline(c.strip())+f'</{tag}>' for c in cells)+'</tr>');table_header=False;continue
        if in_table:parts.append('</table>');in_table=False
        if not line.strip() or line.startswith('<a '):continue
        if line.startswith('# '):parts.append('<h1>'+html.escape(line[2:])+'</h1>')
        elif line.startswith('## '):parts.append('<h2>'+html.escape(line[3:])+'</h2>')
        else:parts.append('<p>'+inline(line)+'</p>')
    (OUT/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jarvis 英语学习验收</title><style>body{font:16px/1.75 system-ui,"Microsoft YaHei";margin:40px auto;padding:0 24px;max-width:1120px;color:#17263a;background:#f7f9fc}h1{font-size:30px}h2{margin-top:36px;color:#17527c}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{border:1px solid #d7e0ea;padding:12px;text-align:left;overflow-wrap:anywhere}th{background:#e8f0f9}p{overflow-wrap:anywhere}a{color:#16699b}</style><body><p><a href="report.md">打开含可点击证据链接的 Markdown 全文</a></p>'+''.join(parts)+'</body></html>',encoding='utf-8')
    if '--render-only' in sys.argv:return
    anchor='english-learning-evidence-20261115';summary=f'2026-11-15已日用采用v0.1.11/epoch{epoch}、控制器协议7：个人跨会话文字学习记录、错题变式、记忆提示和保守进步统计可用。原数据保留、相容恢复版和独立盘还原核验通过；开发三类合成答题不计本人表现，日用首题等待作答。真实跨日保持与口语提升仍待验。'
    for name in ('README.md','docs/current-state.md'):
        path=ROOT/name;text=path.read_text(encoding='utf-8');link=('docs/' if name=='README.md' else '')+'delivery-validation.md#'+anchor
        text=text.replace('\n\n','\n\n'+summary+'[方法、实测与入口]('+link+')。\n\n',1)
        if name=='README.md':
            text=text.replace('source-v0.1.9','source-v0.1.11').replace('Source v0.1.9','Source v0.1.11').replace('最近日用验收记录 **v0.1.8 ·','最近日用验收记录 **v0.1.11 ·')
        path.write_text(text,encoding='utf-8')
    path=ROOT/'CHANGELOG.md';text=path.read_text(encoding='utf-8').replace('2026-11-15，开发中','2026-11-15，已日用采用').replace('日用采用及长期学习效果尚待验证。','已完成日用采用、原数据保留及相容回退；长期学习效果尚待验证。').replace('## 0.1.10## 0.1.10','## 0.1.10');path.write_text(text,encoding='utf-8')
    path=ROOT/'docs/tasks-agents.md';text=path.read_text(encoding='utf-8').replace('跨会话学习开发（v0.1.11，待日用采用）','跨会话学习（v0.1.11，已日用采用）').replace('日用采用以新增实测为准。','采用与范围见[本轮实测](delivery-validation.md#'+anchor+')。');path.write_text(text,encoding='utf-8')
    path=ROOT/'docs/delivery-validation.md';text=path.read_text(encoding='utf-8');marker='<!-- book-nav:end -->';addition=f'\n\n<a id="{anchor}"></a>\n## 跨会话英语学习与日用采用（2026-11-15）\n\n{summary}\n\n{tests["passed"]}个唯一专项回归最终通过；新版和恢复版分别通过冻结207项中的206项，1项平台跳过。真实模型开发8次8,481 token，日用首题1次{tokens:,} token；2处产品问题人工修正，原失败保留。原生回退和只读再核验、完整D盘快照及惰性还原通过。\n\n[完整结果、预测差距与后续门](evidence/english-learning-20261115/report.md#english-learning-report-20261115)；[科学方法和记忆设计](english-learning-method.md#english-method-scope)；[学习数据契约](contracts.md#english-learning-contract)。\n';text=text.replace(marker,marker+addition,1);path.write_text(text,encoding='utf-8')
    path=ROOT/'docs/english-learning-method.md';text=path.read_text(encoding='utf-8');text=text.replace('## 结论与适用范围\n','## 结论与适用范围\n\n文字学习能力已在v0.1.11日用采用；[工程实测与剩余边界](evidence/english-learning-20261115/report.md#english-learning-report-20261115)。下文教学安排是可调整建议，长期个人效果尚待真实使用验证。\n',1);path.write_text(text,encoding='utf-8')
    manifest=ROOT/'docs/manifest.json';m=json.loads(manifest.read_text(encoding='utf-8'));m['documents'].append({'id':'english-learning-report-20261115','path':'docs/evidence/english-learning-20261115/report.md','title':'跨会话英语学习与日用升级验收','owns':['english-learning-report-20261115'],'status':'verified','kind':'evidence','reader_summary':'文字学习、真实模型合成答题、兼容回退与日用采用；实际个人提升待验。'})
    for doc in m['documents']:
        if doc['path']=='docs/delivery-validation.md':doc['owns'].append(anchor)
    manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':'report.md','epoch':epoch,'tokens':8481+tokens}))
if __name__=='__main__':main()
