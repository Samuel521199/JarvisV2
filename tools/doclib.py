"""Small, standard-library-only helpers for this project's documentation.

Written for the new project. Does not import the legacy project or render diagrams.
"""
from pathlib import Path
import hashlib
import json
import os
import re

MARKDOWN_LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"]*")?\)')


def read(path):
    return Path(path).read_text(encoding='utf-8')


def write(path, text):
    path = Path(path)
    if path.exists() and read(path) == text:
        return False
    path.write_text(text, encoding='utf-8', newline='\n')
    return True


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(root):
    return json.loads(read(Path(root) / 'docs/manifest.json'))


def without_blocks(text):
    return re.sub(r'<!-- book-(?:tree|nav|footer):start -->.*?<!-- book-(?:tree|nav|footer):end -->', '', text, flags=re.S)


def visible(text):
    result = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            char = match.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            continue
        if fence is None:
            result.append(line)
    return '\n'.join(result)


def headings(text):
    rows = []
    pending = None
    for number, line in enumerate(visible(without_blocks(text)).splitlines(), 1):
        a = re.fullmatch(r'\s*<a id="([^"]+)"></a>\s*', line)
        if a:
            pending = a.group(1)
            continue
        h = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
        if h:
            rows.append((len(h.group(1)), h.group(2), pending, number))
            pending = None
        elif line.strip():
            pending = None
    return rows


def anchors(text):
    return re.findall(r'<a id="([^"]+)"></a>', visible(text))


def relative(source, target):
    return os.path.relpath(target, Path(source).parent).replace('\\', '/')


def replace_block(text, kind, body):
    start, end = f'<!-- book-{kind}:start -->', f'<!-- book-{kind}:end -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f'Expected exactly one {kind} navigation block')
    a, b = text.index(start), text.index(end) + len(end)
    return text[:a] + start + '\n' + body.strip() + '\n' + end + text[b:]


def navigation(root, data):
    root = Path(root)
    docs = {d['id']: d for d in data['documents']}
    chapters = [(part, docs[ident]) for part in data['book']['parts'] for ident in part['chapters']]
    results = {}
    for entry in ('README.md', 'docs/README.md'):
        rows = []
        for part in data['book']['parts']:
            rows += [f'<a id="{part["id"]}"></a>', f'### {part["title"]}', '', '| 章节 | 这章回答什么 |', '|---|---|']
            for ident in part['chapters']:
                doc = docs[ident]
                rows.append(f'| [{doc["title"]}]({relative(entry, doc["path"])}) | {doc["reader_summary"]} |')
            rows.append('')
        results[entry] = replace_block(read(root / entry), 'tree', '\n'.join(rows))
    for number, (part, doc) in enumerate(chapters, 1):
        path = doc['path']
        text = read(root / path)
        lead = f'[工程主入口]({relative(path, "README.md")}) › [{part["title"]}]({relative(path, "README.md")}#{part["id"]}) › 第 {number:02d} 章'
        rows = [lead, '', '**本章导航**', '']
        for level, title, anchor, _ in headings(text):
            if level >= 2:
                if not anchor:
                    raise ValueError(f'{path}: heading missing explicit anchor: {title}')
                rows.append('  ' * (level - 2) + f'- [{title}](#{anchor})')
        text = replace_block(text, 'nav', '\n'.join(rows))
        foot = [f'[返回工程主入口]({relative(path, "README.md")})', f'[全书目录]({relative(path, "README.md")}#book-tree)']
        if number > 1:
            prev = chapters[number-2][1]
            foot.append(f'[上一章：{prev["title"]}]({relative(path, prev["path"])})')
        if number < len(chapters):
            nxt = chapters[number][1]
            foot.append(f'[下一章：{nxt["title"]}]({relative(path, nxt["path"])})')
        results[path] = replace_block(text, 'footer', ' · '.join(foot))
    return results
