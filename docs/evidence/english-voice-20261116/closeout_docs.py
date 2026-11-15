"""Record the measured scope; leave automatic STT and phonetics explicitly open."""
from pathlib import Path
import difflib,html,json,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent

def main():
    deployment=json.loads((OUT/'production.json').read_text());assert deployment['passed']
    steps={x['name']:x['result'] for x in deployment['steps']};app=deployment['after_state'];preserved=steps['business-preservation'];cost=json.loads((OUT/'accounting.json').read_text());backup=steps['full-independent-backup'];epoch=app['epoch']
    text=f'''# 日用离线归因与英语语音练习验收

<a id="english-voice-report-20261116"></a>
## 结论、改进和剩余工作

2026-11-16日用已采用 **v0.1.12 / epoch{epoch} / 控制器协议8**。本轮实现并验证：升级前真实存活校验、退出记录、本机英文朗读、录音回听、确认转写后的口语内容评价、跨会话口语记录和错题复习。**自动英文转写、发音评分、独立听力测评仍未完成**，不能将本轮标为完整听说助手验收通过。

| 事项 | 原问题 | 实际改进与效果 | 未证明的部分 |
|---|---|---|---|
| 旧日用离线 | 注册active，但端口没有服务 | 查到15日15:21关机、22:26开机；active登记跨系统启动保留。准备升级先查真实身份与健康，离线则明确要求正常启动 | 旧进程具体退出码未保存；不能排除更早未被观察的退出。上轮单项健康测试超时仍另案保留 |
| 运行诊断 | 无正常退出/异常退出记录 | 托管进程父进程保存PID、起止和退出码，host记录ready/cleanup，启用faulthandler；原生演练正常关停记录为0 | 整机突然断电可同时终止父子进程，未完成记录只能提示未知；没有重启电脑作破坏性复验 |
| 英文听读 | 浏览器音色列表为空 | 改用本机Windows已装英文音色，实际生成16kHz单声道WAV，经认证API播放；支持听参考和跟读 | 不据播放动作判断用户听懂；没有发音或听力分 |
| 口语练习 | 只有文字原答 | 明确点录音后开启麦克风、最长60秒，停止后回听，确认实际说出的文字再评价内容 | 本机只有中文离线识别器；自动英语识别未接通，转写仍需本人确认 |
| 口语记忆 | 文字统计不能代表口语 | 音频摘要、时长、确认转写与评价绑定；口语独立统计、到期与错题变式；撤回后不再用于统计或回听 | 尚无本人真实口语样本或延迟保持效果；文字评分不推断发音/流利度 |
| 兼容恢复 | 老代码可能混用口语与文字成绩 | 学习schema2和控制器8；旧版使用前拒绝；只读恢复包保留学习文件并暂停学习，重回新版继续 | 同Windows用户下验证，非跨机DPAPI恢复证明 |

## 离线原因和修复依据

[Windows原始电源事件](power-events.json)中，User32/1074记载2026-11-15 15:21:52发起关机，EventLog/6006在15:22停止；Kernel-General/12记载22:26:35重新启动系统，6005重启日志服务。旧日用日志最后请求14:28:44，下一次托管服务启动在23:24。关机会结束旧进程，但磁盘中epoch12的active记录不会自动变成stopped；先前准备流程只比较登记，未证明实际在线。[归因记录](offline-cause.json)。

这组证据足以解释当时无监听服务，无需假定发生Python崩溃。它不是旧进程逐条退出追踪，无法精确证明旧PID的最后退出时刻。修复`require_live_daily`在prepare及apply-controller之前，使用原WorkbenchProcess核验根、版本、epoch和健康；离线保持拒绝，由原托管入口显式恢复。未安装开机自启、定时任务或自动重试业务。以后开机后通过原Jarvis启动入口恢复；STOP和未知结果规则保留。

## 使用入口与学习方法

1. 原工作台顶栏进入“英语学习 · 跨会话记录与复习”。原文字学习记录和未作答首题保留。
2. 勾选“口语内容练习（录音后确认转写）”，开始一题。先尝试说，不看参考。
3. 点击“录一段英语”，说完停止并回听。在“我的回答”准确填写自己实际说出的英文；若借助翻译或改写，请勾选辅助。
4. 提交后记录录音和确认转写，模型只评意思、形式与得体，给可争议的纠错。展开学习卡可回听原录音、听参考和跟读。
5. 下次会话继续口语错题与到期复习；文字与口语趋势分开。看过参考不计独立表现，转写评价不能作为发音成绩。

听参考/跟读沿用[主动回忆、间隔练习和少量纠错](../../english-learning-method.md#english-method-evidence)；不能靠机械跟读次数宣称自然交流能力提高。Windows已装音色合成发生在本机，录音不发送给文字模型；本人确认的转写仍会按原模型设置发送，使用原预算账本。关闭开关停止新增与使用，撤回阻止学习用途和录音回听；原聊天、音频文件及备份的物理保留不等于已经擦除。

自动识别能力先检查系统实际安装，而非看到API名字就认为可用。本机System.Speech英文音色存在，InstalledRecognizers仅zh-CN。微软文档将[已装识别器枚举与音频输入](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.speechrecognitionengine)分别说明；浏览器[SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)的可用性有限，不能把它当作所有浏览器都可离线工作的英文识别器。本轮没有擅自安装语音包、下载模型或发送录音到第三方。

## 验证、预测与实际差距

| 验证 | 结果与证据 |
|---|---|
| 学习与工作站专项 | 最终41项通过，含原答绑定、音频格式/路径保护、音频持久回听、撤回、口语分开、原队列及离线登记拒绝；[日志](final-targeted.txt) |
| 原机制回归 | 首轮73项中1项夹具兼容声明仍写schema1而失败；更新为schema2且保留低版拒绝语义后，26项学习专项通过。其他已过测试不重复累计成新独立样本；[首轮](regression.txt) |
| 冻结独立政策 | 最终新版与恢复版各207项：206通过、1项平台跳过；原政策摘要保持；[日用回执](production.json) |
| 原生升级与回退 | 首版组合及TTS修复后组合均实际启动、切恢复版、返回新版、关停；学习字节不变；[最终](qualified.json)、[组合](native/result.json) |
| 录音浏览器 | 软件注入英文合成音频，录制约1.96秒并生成可回听WAV；0个JS错误；未访问真人麦克风。[结果](ui-result.json) |
| 朗读兼容 | 首测浏览器英文音色为空，改用System.Speech；认证API实际合成3.83秒/122,604字节WAV。[结果](tts-result.json) |
| 真实模型 | 合成英文音频3.135秒+操作员确认转写，内容评价2/2/2；录音逐字节回读，文字统计未混入。[结果](voice-trial.json) |
| 调用成本 | 2次文本模型调用，{cost['known_tokens']:,} token；音频云调用0、日用模型调用0；本机合成不计云调用。币种账单未核对。[账本](accounting.json) |
| 人工介入 | 测试材料与转写由操作员提供；1处产品兼容问题（浏览器音色为空）修正；新夹具声明及本地TTS输出格式/编码修正均保留限制，不伪装全自动口语测评 |
| 原业务内容 | {preserved['original_databases']}份原业务库、{preserved['original_rows']}行内容、{preserved['original_files']}份配置/会话文件比对；只允许逐列已核对的既有task_completion.checked刷新，共{len(preserved['derived_timestamp_changes'])}行，正文/任务ID/评分不变 |
| 本人进步 | 0条模拟成绩复制到日用；尚无实际口语作答、跨日保持率、独立发音或听力效果证明 |

本轮效果低于“全自动听说评估”的完整目标：录音和听读可用，自动转写/音素级评分未接通。接口与声音文件通过不能替代真实用户学习效果；下一步应先补一个可验收的英文ASR适配器，再做真实录音的人工转写对照和发音评价校准。

## 部署、数据与恢复

当前应用`{app['active']['build']}`；相容只读恢复版`{app['previous']['build']}`；控制器`{deployment['after_controller']['build']}`，固定政策`{deployment['after_controller']['policy_sha256']}`。

完整停机独立盘快照：`{backup['snapshot']}`，{backup['files']:,}文件/{backup['sqlite_integrity_ok']}份SQLite，已从D实际还原到独立E目录并核验，不启动还原业务。新能力复用原身份门、STOP、队列、模型路由、用量记录和来源重验，未扩大任务执行权限。定向由本人选择模式与录音动作控制，协作仍走原宿主，观察成长保存可撤回的来源与评价；未训练模型权重或将错句导入一般知识库。

后续验收依次为：自动英文转写的实际正确率及噪声对照 → 口语原音频与评价的来源绑定 → 经人工校准的发音反馈 → 先听后答且不泄漏文本的听力任务 → 真实跨日保持与未见场景迁移。任何一项未达到门限应保留现有可用能力，停用不可靠的评分或降低其影响，而不是丢弃学习历史或用新评分覆盖旧事实。
'''
    (OUT/'report.md').write_text(text,encoding='utf-8')
    (OUT/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jarvis 语音练习验收</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui;color:#17263a}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#1669a3}</style><a href="report.md">查看含表格与证据链接的Markdown报告</a><pre>'+html.escape(text)+'</pre></html>',encoding='utf-8')
    summary=f'2026-11-16日用v0.1.12/epoch{epoch}、控制器8：旧服务离线有系统关机/重启证据，已补升级前真实健康检查和退出记录；本机英文朗读、录音回听及确认转写后的口语内容评价可用，口语与文字统计分开。自动英文转写、发音评分及独立听力评估尚未完成。'
    anchor='english-voice-evidence-20261116'
    for name in ('README.md','docs/current-state.md'):
        path=ROOT/name;s=path.read_text(encoding='utf-8');prefix='docs/' if name=='README.md' else '';s=s.replace('\n\n','\n\n'+summary+'[结果与边界]('+prefix+'delivery-validation.md#'+anchor+')。\n\n',1);path.write_text(s,encoding='utf-8')
    path=ROOT/'CHANGELOG.md';s=path.read_text(encoding='utf-8').replace('# 版本记录\n','# 版本记录\n\n## 0.1.12 — 离线状态核验与口语练习（2026-11-16，已日用采用）\n\n'+summary+'[验收](docs/delivery-validation.md#'+anchor+')。\n',1);path.write_text(s,encoding='utf-8')
    path=ROOT/'docs/delivery-validation.md';s=path.read_text(encoding='utf-8').replace('<!-- book-nav:end -->','<!-- book-nav:end -->\n\n<a id="'+anchor+'"></a>\n## 离线归因与英语语音练习（2026-11-16）\n\n'+summary+'\n\n[完整结果、预测差距、成本与剩余门](evidence/english-voice-20261116/report.md#english-voice-report-20261116)。原业务内容与固定政策保留；真实原生回退、独立盘停机快照和惰性还原通过。\n',1);path.write_text(s,encoding='utf-8')
    path=ROOT/'docs/contracts.md';s=path.read_text(encoding='utf-8').replace('当前源码控制器协议7','当前源码控制器协议8').replace('controller_protocol=1—7','controller_protocol=1—8').replace('当前产生协议7','当前产生协议8').replace('minimum1—7','minimum1—8')
    marker='## 个人英语学习记录契约\n';s=s.replace(marker,marker+'\n**2026-11-16增量 implemented：**学习schema2支持音频摘要与确认转写的口语内容记录，协议8在写入前核验；能读取schema1并保留历史。record保存最长60秒、16kHz单声道PCM WAV；oral_start/口语原答沿同一队列，oral_progress与文字统计分开。recording重验启用、撤回和来源；speak仅朗读已暴露参考或已完成评价，使用本机Windows英文音色。音频不发给文本模型，转写仍按原路由发送；不能据转写评发音。原生相容恢复版只读保留schema2并阻止学习派发。[本轮证据](delivery-validation.md#'+anchor+')。下表保留首版契约背景，冲突处以上述增量为准。\n',1);path.write_text(s,encoding='utf-8')
    path=ROOT/'docs/english-learning-method.md';s=path.read_text(encoding='utf-8').replace('## 结论与适用范围\n','## 结论与适用范围\n\nv0.1.12增加本机朗读/跟读、录音回听与本人确认转写的口语内容评价；文字与口语趋势分开。自动转写、发音和独立听力测评仍待接入。[实际范围](evidence/english-voice-20261116/report.md#english-voice-report-20261116)。\n',1);path.write_text(s,encoding='utf-8')
    path=ROOT/'docs/manifest.json';m=json.loads(path.read_text(encoding='utf-8'));m['runtime_version']='0.1.12';m['documents'].append({'id':'english-voice-report-20261116','path':'docs/evidence/english-voice-20261116/report.md','title':'日用离线归因与英语语音练习验收','owns':['english-voice-report-20261116'],'kind':'evidence','status':'verified','reader_summary':'离线归因、健康门、本机朗读和口语转写内容练习；完整听说评估未完成。'})
    for d in m['documents']:
        if d['path']=='docs/delivery-validation.md':d['owns'].append(anchor)
    path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Documented measured partial speech scope and deployed runtime')
if __name__=='__main__':main()
