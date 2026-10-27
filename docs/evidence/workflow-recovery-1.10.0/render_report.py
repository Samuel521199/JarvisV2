"""Measured technical recovery report; unavailable business outcomes stay null."""
from pathlib import Path
import hashlib
import html
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads((HERE/p).read_text('utf-8'))
write=lambda p,v:(HERE/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
run=read('frozen-r2/run/report.json');tests=read('frozen-r2/run/tests.json');snapshot=read('frozen-r2/snapshot.json');wrapper=read('frozen-r2/result.json')
assert run['local_verdict']==wrapper['local_verdict']=='PASS' and tests['passed']
baseline=json.loads((HERE.parent/'workflow-inheritance-1.9.0/frozen-r3/run/plan.json').read_text('utf-8'))['test_ids']
current=read('frozen-r2/run/plan.json')['test_ids'];missing=sorted(set(baseline)-set(current));assert not missing
runtime=read('frozen-r2/run/recovery/runtime.json');perf=read('frozen-r2/run/performance.json')
off=perf['task_ms']['False']['p95'];on=perf['task_ms']['True']['p95'];added=round(on-off,3)
verification={'version':'workflow-recovery-1.10.0','local_verdict':'PASS','tests':tests['run'],'baseline_retained':len(baseline),
    'new_cases':len(set(current)-set(baseline)),'missing_baseline':missing,'browser_workflows':12,'gates':len(run['checks']),
    'source_count':snapshot['source_count'],'supporting_count':len(snapshot['supporting_input_digests']),
    'original_observer_p95_ms':{'off':off,'on':on,'added':added,'budget':25},
    'quality_gain':None,'real_user_accuracy':None,'unnecessary_rejection_rate':None,'token_savings':None,'learning_gain':None,'production_deployed':False}
write('verification.json',verification)
before=read('plan.json')['source_before'];after=snapshot['source_digests']
changes=[{'path':p,'before':before.get(p),'candidate':after.get(p),'created':p not in before} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
assert hashlib.sha256((HERE.parent/'assistant-forecast-r1-2026-10-26.json').read_bytes()).hexdigest()=='035f34e43b8b1f7c974202c0820fef905abe86674c5089be6be28a44a76ef66f'
assert hashlib.sha256((ROOT/'host/work_status.py').read_bytes()).hexdigest()=='16784cdf2a387efd191e7c6dd89a8fbe8aa92edb450620054f6e3c5596947e10'
write('candidate-audit.json',{'changed_sources':changes,'original_forecast_preserved':True,'old_work_status_preserved':True,'frozen_result':wrapper,'production_deployed':False})
css='''*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e8eef8;font:17px/1.75 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:44px 26px}h1{font-size:40px;line-height:1.25}h2{font-size:25px;margin-top:38px}p{color:#c3cfdf}a{color:#78cbff}strong,.pass{color:#77e1bb}.tag{letter-spacing:2px;font-size:13px;color:#78cbff}.cards,.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.flow{grid-template-columns:repeat(5,1fr)}.card,.flow>div{background:#142239;border:1px solid #2c415e;border-radius:14px;padding:18px}.number{display:block;font-size:30px;color:#77e1bb}.flow>div{font-size:15px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;background:#101c30;font-size:15px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #2c415e;padding:14px;min-width:110px}th{color:#78cbff}details{border:1px solid #2c415e;border-radius:12px;padding:16px;margin:24px 0}summary{cursor:pointer}img{max-width:100%;display:block;margin:18px auto;border-radius:10px}code{color:#f8d190;overflow-wrap:anywhere}.note{border-left:3px solid #efbc67;padding:8px 18px}.bar{display:flex;height:30px;margin:8px 0;gap:2px}.old{background:#396b93;flex:480}.new{background:#53b99a;flex:30}.caption{font-size:14px;color:#aebed4}@media(max-width:720px){main{padding:24px 16px}h1{font-size:30px}.cards,.flow{grid-template-columns:repeat(2,1fr)}.flow>div:last-child{grid-column:span 2}}'''
gates=''.join('<tr><td>'+html.escape(c['id'])+'</td><td class="pass">'+c['status']+'</td></tr>' for c in run['checks'])
score=runtime['tasks'][0]['completion']['condition_score']
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis 1.10 来源恢复验收</title><style>{css}</style>
<main><div class="tag">JARVIS · WORKFLOW RECOVERY 1.10.0</div><h1>旧事实保留，失效的工作可以接续</h1>
<p><strong>有限反馈恢复链已通过本地技术验收。</strong> 已受理的报价返工版本，能证明只有祖先反馈发生变化时，建立同一工作的恢复草案，保留全部要求、原动作及累计成本，再独立验收新结果。</p>
<p class="note">本轮未部署。完整助手、真实业务质量、token收益、长期越用越聪明仍未签收；恢复创建需要显式复核，不是自动诊断修码。</p>
<div class="cards"><div class="card"><b class="number">{tests['run']}</b>不同回归用例<br><span class="caption">原480项＋新增{verification['new_cases']}项</span></div><div class="card"><b class="number">12</b>浏览器流程<br><span class="caption">真实界面、HTTP与临时执行器</span></div><div class="card"><b class="number">{len(run['checks'])}/{len(run['checks'])}</b>联合验收门通过<br><span class="caption">原门槛保留</span></div><div class="card"><b class="number">未测</b>真实业务净收益<br><span class="caption">不能用通过率代替Q</span></div></div>
<h2>改了什么，会产生什么效果</h2><div class="scroll"><table><tr><th>改进</th><th>以前的断点</th><th>本轮实测</th><th>预期差距</th></tr>
<tr><td>证明只有反馈变化</td><td>旧依据失效后不能给已受理版本改签</td><td>旧摘要对照成立才允许新恢复；原话变化、回执/文件损坏仍拒绝</td><td>限定技术预期达到；真实诊断覆盖率未测</td></tr>
<tr><td>停止旧待办并新建草案</td><td>失效的已受理任务缺少保持Work链的接续路径</td><td>READY、来源WAITING、SUCCEEDED均有相应保留策略；失败事务回滚</td><td>技术预期达到；新版本仍需核对和受理</td></tr>
<tr><td>保留全部要求</td><td>恢复可能被误当成降低验收标准的机会</td><td>未知保修仍待证据，错误最低价仍需纠正；反馈文字不隐式改要求</td><td>没有证据证明真实漏项率已下降</td></tr>
<tr><td>同一预算、责任和版本链</td><td>另起工作可能丢掉累计成本与失败关系</td><td>旧动作不重放；仅未用预留释放；最多4版本；过期、撤权和停止仍有效</td><td>工具动作账闭合；完整费用账未闭合</td></tr></table></div>
<h2>闭环怎样接起来</h2><div class="flow"><div>① 反馈变化<br>旧后代结论失效或等待</div><div>② 只读分析<br>证明其他依据保持一致</div><div>③ 明确复核<br>保持要求，建立新草案</div><div>④ 原机制受理<br>新许可＋原共享预算</div><div>⑤ 独立验收<br>结案、待证据或纠正</div></div>
<p>再次出现反馈变化时，新恢复也会失效；可在原版本和预算上限内再分析。旧任务不恢复成“已通过”，新版本也不继承旧分数。</p>
<h2>实际评分与成本：分别看，不混算</h2><div class="scroll"><table><tr><th>合成场景</th><th>新结果</th><th>明确条件分</th><th>整件工作动作单位</th><th>业务Q</th></tr>
<tr><td>已完成版本失效后恢复</td><td>VERIFIED</td><td>{score:g}%</td><td>6＝根2＋旧版2＋恢复2</td><td>未测</td></tr>
<tr><td>未执行旧版，含未知保修要求</td><td>WAITING_EVIDENCE</td><td>不生成</td><td>4＝根2＋恢复2</td><td>未测</td></tr>
<tr><td>旧版确认1个动作后来源等待</td><td>VERIFIED（集成用例）</td><td>仅有限条件</td><td>5＝根2＋旧计算1＋恢复2</td><td>未测</td></tr>
<tr><td>恢复工具输出错误最低价</td><td>NEEDS_CORRECTION</td><td>失败，不结案</td><td>仍累计，不退款</td><td>未测</td></tr>
<tr><td>原话发生变化</td><td>恢复分析拒绝，无新版本</td><td>不适用</td><td>未新增动作</td><td>未测</td></tr></table></div>
<p>100%是明确受支持条件的检查分；语义目标验证仍为false，综合质量没有证据就不生成。报价成功也没有自动成为知识方法。</p>
<h2>兼容性与原理念</h2><div class="scroll"><table><tr><th>核心目标</th><th>本轮保证</th><th>尚未实现</th></tr>
<tr><td>三位一体、模块独立</td><td>Direction管理版本；Engagement复用任务/权限/预算；Reflection独立评估；核验策略留在任务模块</td><td>未增加第二执行器或最高权限Agent；通用多Bot租约仍待做</td></tr>
<tr><td>自愈、自评估</td><td>反馈失效后接回新版本；动作未知时不重放；正确、错误、未知分别判定</td><td>自动根因诊断、任意故障恢复尚未闭合</td></tr>
<tr><td>自改造、自进化</td><td>留下可追溯失败与恢复记录，不改评分器让候选过关</td><td>自动产出、留出评测、发布与累计非退化还需独立验收</td></tr>
<tr><td>越用越聪明</td><td>旧要求与反证不丢失，知识准入保持原标准</td><td>带适用边界、反例、过期和净收益证据的方法候选；长期学习增益未测</td></tr></table></div>
<h2>如何证明没有把旧系统改差</h2><div class="bar" aria-label="480项原基线与30项新增用例"><div class="old"></div><div class="new"></div></div>
<p>冻结{snapshot['source_count']}项源码输入与{len(snapshot['supporting_input_digests'])}项支持输入；原480个测试ID全部保留，新增加{verification['new_cases']}个不同用例。旧11条界面流程全部重跑，加上恢复流程；测试次数不充作新增样本。</p>
<p>原观察器P95：关闭{off:g}ms → 开启{on:g}ms，差值{added:+g}ms，沿用25ms门槛。这测的是原观察器开销，不是恢复耗时或真实任务效率；未声称比预测更聪明。</p>
<details><summary>查看{len(run['checks'])}道验收门</summary><div class="scroll"><table><tr><th>检查</th><th>结果</th></tr>{gates}</table></div></details>
<h2>失败也留在证据中</h2><p>首轮12项中10项报错：恢复把保存文件当成需要计算回执，误拒合法恢复。按原证据类型分别核对后，12项和扩展28项专项通过，另加停止/过期许可用例，再完整冻结验收。首轮完整冻结中509/510项通过，旧部分复用拒绝契约因检查顺序改变而失败；恢复原顺序后，保留原断言复验，再以第二轮冻结重新执行全部验收。没有降低旧门槛或删除失败样本。</p>
<p><a href="narrow-r1.json">首轮失败摘要（终端输出曾截断）</a> · <a href="narrow-r2.json">12项复验</a> · <a href="narrow-r3.json">28项扩展</a> · <a href="authority-r4.log">权限边界复验</a> · <a href="frozen-r1/run/regression.log">首轮冻结失败</a> · <a href="compatibility-r5.log">兼容性复验</a> · <a href="compatibility-change-audit.json">两轮源码与验收标准对照</a> · <a href="frozen-r2/result.json">最终冻结结果</a></p>
<p>报告首轮窄屏检查发现展开截图后横向溢出，已将窄屏图片限制在父容器宽度内；<a href="report-ui-r1.json">首轮展示失败</a>单独保留，运行成绩不变。</p><h2>下一步：从链路可用转向真实工作是否更好</h2><p>先做真实请求的采集、冻结、对照与失败归因：固定参照、同一输入、量表和预算，同时统计错误交付、无谓拒绝、必要/不必要人工介入和完整成本。无真实样本时不编造收益。随后依次接完整费用与有限常设委托、条件化知识候选、多Bot负责人/委派；每次采用都要保留反例与退化暂停。</p>
<p><a href="../../delivery-validation.md#workflow-recovery-evidence">权威验收页</a> · <a href="../../core-bootstrap.md#workflow-recovery-runtime">实施与操作</a> · <a href="../../contracts.md#workflow-recovery-contract">契约</a> · <a href="plan.json">事前预测</a> · <a href="verification.json">实测汇总</a> · <a href="candidate-audit.json">源码差异</a> · <a href="delivery-checks.json">最终交付检查</a></p>
<details><summary>查看真实界面截图（临时合成数据）</summary><p>桌面恢复核对</p><img loading="eager" src="frozen-r2/run/recovery/analysis-desktop.png" alt="恢复来源、预算与要求核对窗口"><p>390px窄屏</p><img loading="eager" style="width:100%;max-width:390px" src="frozen-r2/run/recovery/analysis-mobile.png" alt="窄屏恢复核对"><p>新结果独立评价</p><img loading="eager" src="frozen-r2/run/recovery/correct-result.png" alt="恢复后的正确结果与累计预算"></details>
</main></html>'''
(HERE/'report.html').write_text(page,encoding='utf-8',newline='\n')
print(json.dumps(verification,ensure_ascii=False))
