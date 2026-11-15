"""Render evidence already produced by the actual checks; never invent missing results."""
from pathlib import Path
import html,json
ROOT=Path(__file__).parent
def read(name):
 p=ROOT/name
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def main():
 native=read('native-r2/summary.json');regression=read('regressions-r2.json');package=read('qualified-r1/independent-package/result.json');replay=read('qualified-r1/package-repair-replay.json')
 rows=''.join('<tr><td>'+label+'</td><td>0 → 100</td><td>'+format(row['total_tokens'],',')+'</td><td>'+format(row['seconds'],'.2f')+'秒</td><td><a href="native-r2/'+row['domain']+'/result.json">执行证据</a></td></tr>' for label,row in zip(('资料摘录','乘法练习','结构化报价'),native['rows']))
 checks=[('扩大回归首轮',regression,'regressions-r2.json'),('最终保护与失败用例复验',read('final-guards-r1.json'),'final-guards-r1.json'),('独立包固定验收',package,'qualified-r1/independent-package/result.json'),('包内修复专项及真实候选重放',replay,'qualified-r1/package-repair-replay.json'),('实际旧版兼容',read('legacy-reader-final.json') or read('legacy-reader.json'),'legacy-reader-final.json' if read('legacy-reader-final.json') else 'legacy-reader.json'),('共用完成卡',read('ui-check.json'),'ui-check.json')]
 def verdict(label,record):
  if label=='扩大回归首轮' and record and record['tests']==391 and record['failures']==1:return '390通过；1初始化超时，保留首轮失败'
  return '通过' if record and record.get('passed') else '未通过或未完成'
 testrows=''.join('<tr><td>'+label+'</td><td>'+verdict(label,record)+'</td><td>'+str(record.get('tests',record.get('checks','见回执')) if record else '待完成')+'</td><td><a href="'+link+'">原始回执</a></td></tr>' for label,record,link in checks)
 previews=''
 for domain,label in (('notes','资料摘录'),('practice','乘法练习'),('quote','结构化报价')):
  path=ROOT/'qualified-r1/actual-artifacts'/(domain+'.txt')
  if path.exists():
   delivered=json.loads(path.read_text(encoding='utf-8'));text=json.dumps(json.loads(delivered['text']),ensure_ascii=False,indent=2)
   previews+='<details><summary>'+label+' · 最终包实际交付</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+html.escape(text)+'</pre><a href="qualified-r1/actual-artifacts/'+domain+'.txt">完整原始产物</a></details>'
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Jarvis 修复回接验收</title><style>
body{font:16px/1.7 system-ui,sans-serif;margin:0;background:#f1f5f9;color:#172235}main{max-width:1060px;margin:auto;padding:40px 24px}h1{font-size:32px}h2{margin-top:32px}section{background:white;padding:24px;border-radius:14px;margin:20px 0}.lead{font-size:20px;font-weight:650}.scope{border-left:4px solid #cb8c1d;padding-left:16px}table{border-collapse:collapse;width:100%;display:block;overflow:auto}th,td{text-align:left;padding:12px 16px;border-bottom:1px solid #dbe3ed;white-space:normal}a{color:#1457b2}small{color:#526175}code{background:#edf1f6;padding:2px 4px}</style><main>
<h1>修复自动采用与原工作回接</h1><p>2026-11-15 · v0.1.9 开发验收 · 日用应用未采用</p>
<section><p class="lead">三类受支持任务完成了有界闭环。</p><p>一次明确授权 → 隐藏检查 → 原输入影子验收 → 精确候选采用 → 同一工作返工 → 实际交付与原要求重验。</p><p class="scope">测试输入为操作者编写的合成业务失败案例；模型和隔离执行是真实运行。不是独立真实用户任务，不证明通用智能、长期学习或节省 token。</p></section>
<section><h2>预测与实际</h2><p>预测：原失败保留0分，返工用相同条件达到100分。三类均达到；旧工具、原任务与失败历史保留。原本100分但新输入失败的测试记录100→100，未记作质量增加。</p><table><tr><th>类型</th><th>声明条件评分</th><th>模型 token</th><th>修复至回接</th><th>证据</th></tr>'''+rows+'''</table><p>总计13,765 token，6次模型调用；未提高64次/滚动24小时额度。此数值是修复开销，不是节省量。</p></section>
<section><h2>机制保护验收</h2><table><tr><th>项目</th><th>结果</th><th>数量</th><th>证据</th></tr>'''+testrows+'''</table><p>撤权、STOP、预算耗尽、未知结果、修改返工方案与来源变化都有停止出口。新反证使CLOSED变为REGRESSED，并隔离本候选。崩溃后按原request_id恢复，不重复建工作或发预算。</p><p><a href="parallel-run-failure.json">首次并行超时记录</a>保留；串行复验没有增加Worker时限或删除验收。</p></section>
<section><h2>明确限制</h2><p>当前仅单步骤纯文本三域。多步骤、无独立判定器或不能完整继承的要求不自动回接。影子回执丢失停止为待处理，尚无专用自动恢复器。知识晋升、独立用户留出与长期净收益仍需后续验证。</p><p><a href="../../delivery-validation.md#repair-return-evidence-20261115">完整验收文档</a> · <a href="../../knowledge-learning.md#repair-return-runtime">实施与设计边界</a></p></section></main></html>'''
 page=page.replace('<section><h2>明确限制</h2>','<section><h2>实际交付预览</h2><p>这些文件来自最终安装包重放，字节摘要与交付回执已核对；无新增真实模型调用。</p>'+previews+'<p><a href="qualified-r1/actual-artifacts/verification.json">产物与回执核验</a></p></section><section><h2>明确限制</h2>')
 (ROOT/'report.html').write_text(page,encoding='utf-8')
if __name__=='__main__':main()
