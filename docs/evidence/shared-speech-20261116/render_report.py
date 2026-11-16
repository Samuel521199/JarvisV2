from pathlib import Path
import html,re
out=Path(__file__).parent
text=(out/'report.md').read_text(encoding='utf-8')
def inline(s):
 s=html.escape(s);s=re.sub(r'\[([^\]]+)\]\(([^ )]+)\)',r'<a href="\2">\1</a>',s);s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s);return re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
parts=[];table=False;header=False
for line in text.splitlines():
 if line.startswith('|'):
  if not table:parts.append('<table>');table=True;header=True
  if set(line.replace('|','').strip())<={'-',' ',':'}:continue
  tag='th' if header else 'td';parts.append('<tr>'+''.join('<'+tag+'>'+inline(c.strip())+'</'+tag+'>' for c in line.strip('|').split('|'))+'</tr>');header=False;continue
 if table:parts.append('</table>');table=False
 if not line.strip() or line.startswith('<a '):continue
 if line.startswith('# '):parts.append('<h1>'+inline(line[2:])+'</h1>')
 elif line.startswith('## '):parts.append('<h2>'+inline(line[3:])+'</h2>')
 else:parts.append('<p>'+inline(line)+'</p>')
(out/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jarvis共用离线语音实现与验收</title><style>body{max-width:1120px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui;color:#17263a;background:#f7f9fc}td,th{border:1px solid #ccd8e6;padding:12px;text-align:left;overflow-wrap:anywhere}th{background:#e5eef8}table{border-collapse:collapse;background:white;font-size:14px;width:100%}h2{margin-top:36px;color:#17527c}p{overflow-wrap:anywhere}a{color:#1669a3}</style><a href="report.md">查看完整Markdown报告</a>'+''.join(parts)+'</html>',encoding='utf-8')
