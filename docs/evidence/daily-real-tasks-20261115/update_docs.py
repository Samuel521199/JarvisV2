"""Register this bounded real-task trial in the existing authoritative chapters."""
from pathlib import Path
import json,html
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent

def insert(path,marker,value):
    p=ROOT/path;raw=p.read_bytes();needle=marker.encode();assert needle in raw
    assert value.strip().encode() not in raw
    p.write_bytes(raw.replace(needle,value.encode()+needle,1))

def main():
    link='docs/delivery-validation.md#daily-real-tasks-evidence-20261115'
    insert('README.md','2026-11-15日用升级完成',f'2026-11-15真实使用验证：已启动Jarvis内置英语练习，面向生活、沟通与工作资料，等待真实作答；两份材料辅助交付通过，不代表自动修复闭环或学习提升。9次模型调用22,745 token。[结果与使用入口]({link})。\r\n\r\n')
    p=ROOT/'docs/current-state.md';raw=p.read_bytes();pos=raw.find(b'\n')+1
    value='\r\n2026-11-15真实需求接续：用户要在Jarvis内学习英语，不购买英语服务。日用既有英语技能已发首题；英语与资料两项交付有操作员辅助，交付100分不代表学习掌握。共9次调用22,745 token；原数据与681份运行文件保留。跨会话复习与真实学习效果未验，报价无真实标的不计通过。[完整证据](delivery-validation.md#daily-real-tasks-evidence-20261115)。\r\n'
    p.write_bytes(raw[:pos]+value.encode()+raw[pos:])
    section='''<a id="daily-real-tasks-evidence-20261115"></a>
## 日用真实任务与英语学习接续（2026-11-15）

**限定 verified。** 日用v0.1.10/epoch12不重启；已用真实需求生成英语/资料材料，经操作员辅助回接与交付。既有英语技能已在同一会话开始生活情境练习，用户尚未作答。用户明确要Jarvis内学习，不购买英语服务；报价无真实标的，保留未验。

| 实测 | 结果与边界 |
|---|---|
| 英语、资料交付 | 均为逐字交付100分；原NEEDS_INPUT、资料两处语义错误和操作员纠正完整保留 |
| 自动程度 | 来源正文一致性5/6→6/6由宿主修复；语义发现和原目标回接有操作员辅助，repair_return事件0 |
| 成本 | 英语12,983、资料7,174、共享工具研发2,588，共9次22,745 token；无学习收益/省token证明 |
| 回归与保留 | 新只读采集6项及原英语流程4项通过；原业务/授权未变，681份活动文件相同，未升级Host |

[详细报告、使用入口与后续实施顺序](evidence/daily-real-tasks-20261115/report.md) · [可视报告](evidence/daily-real-tasks-20261115/report.html) · [实际开场](evidence/daily-real-tasks-20261115/english-coach-opening.txt) · [账本](evidence/daily-real-tasks-20261115/accounting-r2.json)。首次保留检查将正常认证会话变化误判失败，原失败与按密钥/寿命/原有效会话复核的结果均保留。范围不包括发音、跨会话复习、独立学习效果或全部业务组合。

'''.replace('\n','\r\n')
    insert('docs/delivery-validation.md','<a id="daily-upgrade-evidence-20261115"></a>',section)
    insert('docs/tasks-agents.md','**使用方式：**在聊天技能选框选择', '**2026-11-15真实接续：**按用户生活交流、日常沟通、工作资料需求，在日用原会话显式选择英语技能发出首题，等待真实回答。材料交付与教学效果分开验收；原目标工具不足不能由乘法用例代验。后续按“实际互动 → 来源绑定学习项 → 有界复习 → 未见变式效果对照 → 语音适配”推进，复用同一聊天/知识/任务服务；后四项尚未由本轮实现。[实测与具体顺序](evidence/daily-real-tasks-20261115/report.md)。\r\n\r\n')
    insert('docs/knowledge-learning.md','**三职能保持原定义。**','**2026-11-15日用边界实测：**真实英语资料需求仍需操作员审阅交付工具与衔接；资料语义问题也由操作员识别，只有来源正文一致性由既有渲染器修复。本轮无repair_return事件，交付评分不等于教学收益；不将未审阅试验内容自动晋升长期知识。[证据](delivery-validation.md#daily-real-tasks-evidence-20261115)。\r\n\r\n')
    insert('CHANGELOG.md','- 自动修复回接记录加入版本兼容门','- 新增只读真实任务账本采集，保留失败/返工成本及人工介入；日用既有英语工作流已按真实需求启动，未升级Host。9次调用22,745 token，交付通过不等于学习效果。[证据](docs/delivery-validation.md#daily-real-tasks-evidence-20261115)。\r\n')
    p=ROOT/'docs/manifest.json';raw=p.read_bytes();needle=b'"daily-upgrade-evidence-20261115"';assert raw.count(needle)==1
    p.write_bytes(raw.replace(needle,b'"daily-real-tasks-evidence-20261115",\r\n          '+needle))
    report=(OUT/'report.md').read_text(encoding='utf-8')
    # Standalone evidence view; Markdown remains the complete auditable record.
    cards=[('可用入口','Jarvis内置英语练习，首题待作答'),('本轮用量','9次 / 22,745 token'),('交付验收','两项100；不是英语水平分'),('自动闭环','未签收；含操作员辅助')]
    tiles=''.join('<article><small>'+html.escape(a)+'</small><h2>'+html.escape(b)+'</h2></article>' for a,b in cards)
    text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jarvis日用英语与资料验证</title><style>body{font:17px/1.7 system-ui;margin:0;background:#101827;color:#e8edf6}main{max-width:1050px;margin:auto;padding:32px}a{color:#83cfff}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}article{background:#1d2b42;padding:18px;border-radius:12px}h2{font-size:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.8 system-ui;border-top:1px solid #53647a;padding-top:20px}</style><main><h1>在 Jarvis 里学习英语</h1><p>生活交流 · 日常沟通 · 工作资料。已有练习入口，学习效果等待真实作答验证。</p><div class="cards">'''+tiles+'''</div><p><a href="http://127.0.0.1:18282/#chat=chat-07c934420a2e4cd2a878fc3cf84cf837">打开日用英语会话（需本机登录）</a> · <a href="english-coach-opening.txt">第一题</a> · <a href="report.md">完整Markdown报告</a> · <a href="accounting-r2.json">原始用量</a></p><pre>'''+html.escape(report)+'''</pre></main></html>'''
    (OUT/'report.html').write_text(text,encoding='utf-8')

if __name__=='__main__':main()
