"""Validate this project's document book without legacy code or dependencies.

Does not fetch remote URLs, run code samples or certify runtime behavior.
"""
import argparse
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from doclib import MARKDOWN_LINK, anchors, digest, headings, manifest, navigation, read, visible


def validate(root):
    root = Path(root).resolve()
    data = manifest(root)
    errors = []
    docs = data['documents']
    ids, paths, owned, texts = set(), set(), {}, {}
    for doc in docs:
        ident, path = doc['id'], doc['path']
        if ident in ids or path in paths:
            errors.append(f'Duplicate document id/path: {ident} {path}')
        ids.add(ident); paths.add(path)
        dest = (root / path).resolve()
        if not dest.is_relative_to(root) or not dest.is_file():
            errors.append(f'Missing or out-of-root document: {path}')
            continue
        text = read(dest); texts[path] = text
        hs = headings(text)
        if len([h for h in hs if h[0] == 1]) != 1 or not hs or hs[0][1] != doc['title']:
            errors.append(f'Title mismatch: {path}')
        found = anchors(text)
        if len(found) != len(set(found)):
            errors.append(f'Duplicate explicit anchor: {path}')
        for topic in doc['owns']:
            if topic in owned:
                errors.append(f'Duplicate topic ownership: {topic}')
            owned[topic] = path
    chapter_ids = [i for p in data['book']['parts'] for i in p['chapters']]
    part_ids = [p['id'] for p in data['book']['parts']]
    if len(part_ids) != len(set(part_ids)):
        errors.append('Duplicate book part id')
    expected = {d['id'] for d in docs if d.get('kind') == 'chapter'}
    if set(chapter_ids) != expected or len(chapter_ids) != len(set(chapter_ids)):
        errors.append('Every chapter must belong to exactly one part')
    for doc in docs:
        path = doc['path']
        if doc.get('kind') != 'chapter' or path not in texts:
            continue
        previous = 1
        for level, title, anchor, _ in headings(texts[path]):
            if level > 4 or level > previous + 1:
                errors.append(f'Skipped/unsupported heading level: {path} {title}')
            if level > 1 and not anchor:
                errors.append(f'Missing heading anchor: {path} {title}')
            previous = level
    found_md = {p.relative_to(root).as_posix() for p in root.rglob('*.md') if not any(x in p.parts for x in ['.git', 'user-data', '.venv', 'node_modules'])}
    for extra in sorted(found_md - paths):
        errors.append(f'Unregistered Markdown: {extra}')
    link_count = 0
    for path, text in texts.items():
        for match in MARKDOWN_LINK.finditer(visible(text)):
            target = match.group(1).strip('<>')
            bits = urlsplit(target)
            if bits.scheme in ['http','https','mailto']:
                continue
            if bits.scheme or target.startswith(('/', '\\')):
                errors.append(f'Non-portable local link: {path} -> {target}')
                continue
            file_part = unquote(bits.path)
            dest = ((root / path).parent / file_part).resolve() if file_part else (root / path).resolve()
            link_count += 1
            if not dest.is_relative_to(root) or not dest.is_file():
                errors.append(f'Broken/outside link: {path} -> {target}')
                continue
            if bits.fragment and dest.suffix == '.md':
                if unquote(bits.fragment) not in anchors(read(dest)):
                    errors.append(f'Broken anchor: {path} -> {target}')
    try:
        for path, wanted in navigation(root, data).items():
            if wanted != texts.get(path):
                errors.append(f'Stale navigation: {path}')
    except (ValueError, KeyError, OSError) as exc:
        errors.append(f'Navigation: {exc}')
    registered_assets = set()
    for diagram in data['generated_diagrams']:
        if diagram['owner_document'] not in paths:
            errors.append(f'Unknown diagram owner: {diagram["id"]}')
        for path, sha in [(diagram['source_document'], diagram['source_sha256'])] + [(a['path'],a['sha256']) for a in diagram['artifacts']]:
            registered_assets.add(path)
            p=(root/path).resolve()
            if not p.is_relative_to(root) or not p.is_file() or digest(p) != sha:
                errors.append(f'Missing or changed diagram: {path}')
        image_path=next((a['path'] for a in diagram['artifacts'] if a['path'].endswith('.png')),None)
        if not image_path or not any(image_path.removeprefix('docs/') in t for t in texts.values()):
            errors.append(f'Diagram is not embedded in documentation: {diagram["id"]}')
    for p in (root/'docs/diagrams').iterdir():
        if p.is_file() and p.relative_to(root).as_posix() not in registered_assets:
            errors.append(f'Unregistered diagram file: {p.name}')
    for item in data.get('assets',[]):
        p=root/item['path']; registered_assets.add(item['path'])
        if not p.is_file() or digest(p) != item['sha256']:
            errors.append(f'Missing or changed asset: {item["path"]}')
    for p in (root/'docs/assets').rglob('*'):
        if p.is_file() and p.relative_to(root).as_posix() not in registered_assets:
            errors.append(f'Unregistered document asset: {p.name}')
    # Root operational dependencies must remain local; source citations may name H:.
    for p in (root/'tools').glob('*.py'):
        if re.search(r'H:[/\\]Jarvis|sys\.path\.insert',read(p)):
            errors.append(f'Legacy/external code dependency: {p.name}')
    for path, required in data.get('required_anchors', {}).items():
        found=set(anchors(texts.get(path,'')))
        for anchor in required:
            if anchor not in found:
                errors.append(f'Required stable identifier missing: {path}#{anchor}')
    identifier_pattern = r'(?<![A-Z0-9])(?:R\d{2}|N\d{2}|H\d{2}|V-[A-Z]+-\d+)(?![A-Z0-9])'
    for path, required in data.get('required_identifiers', {}).items():
        found = set(re.findall(identifier_pattern, texts.get(path, '')))
        for ident in required:
            if ident not in found:
                errors.append(f'Required requirement/validation id missing: {path}: {ident}')
    return errors, {'documents':len(docs),'chapters':len(chapter_ids),'diagrams':len(data['generated_diagrams']),'local_links':link_count}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    args=p.parse_args()
    try:
        errors, counts=validate(args.root)
    except (OSError,ValueError,KeyError) as exc:
        print(f'ERROR {exc}');return 1
    for error in errors:
        print('ERROR '+error)
    print(('FAIL' if errors else 'OK')+' '+ ' '.join(f'{k}={v}' for k,v in counts.items())+f' errors={len(errors)}')
    return int(bool(errors))


if __name__=='__main__':
    raise SystemExit(main())
