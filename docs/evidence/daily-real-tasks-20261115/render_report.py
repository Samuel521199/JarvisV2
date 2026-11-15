"""Render the local Markdown evidence into a readable standalone HTML report."""
from pathlib import Path
import html,re
OUT=Path(__file__).parent

def inline(text):
    value=html.escape(text)
    value=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:'<a href="'+m[2]+'">'+m[1]+'</a>',value)
    value=re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)

def main():
    lines=(OUT/'report.md').read_text(encoding='utf-8').splitlines();parts=[];table=False;first=False
    for line in lines:
        if line.startswith('|'):
            if re.fullmatch(r'[| :\-]+',line):continue
            if not table:parts.append('<div class="scroll"><table>');table=True;first=True
            tag='th' if first else 'td';first=False
            parts.append('<tr>'+''.join('<'+tag+'>'+inline(cell.strip())+'</'+tag+'>' for cell in line.strip('|').split('|'))+'</tr>');continue
        if table:parts.append('</table></div>');table=False
        if not line.strip():continue
        heading=re.match(r'^(#{1,3}) (.*)',line)
        if heading:
            n=len(heading[1]);parts.append(f'<h{n}>'+inline(heading[2])+f'</h{n}>')
        else:parts.append('<p>'+inline(line)+'</p>')
    if table:parts.append('</table></div>')
    top='<p><a href="http://127.0.0.1:18282/#chat=chat-07c934420a2e4cd2a878fc3cf84cf837">打开日用英语会话（需本机登录）</a> · <a href="report.md">Markdown报告</a></p>'
    style='body{font:17px/1.75 system-ui;margin:0;background:#101827;color:#e8edf6}main{max-width:1120px;margin:auto;padding:32px}a{color:#83cfff}h1{font-size:30px}h2{font-size:23px;margin-top:38px}table{width:100%;border-collapse:collapse;min-width:720px;background:#18253a}th,td{text-align:left;vertical-align:top;border:1px solid #455673;padding:12px}th{background:#263953}code{overflow-wrap:anywhere;color:#a9d9ff}.scroll{overflow:auto}p{overflow-wrap:anywhere}'
    result='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jarvis英语学习与日用验证</title><style>'+style+'</style></head><body><main>'+top+''.join(parts)+'</main></body></html>'
    (OUT/'report.html').write_text(result,encoding='utf-8')

if __name__=='__main__':main()
