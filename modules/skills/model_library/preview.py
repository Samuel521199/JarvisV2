"""Resolve an explicit preview request against registered, immutable library variants."""
import json
import re
import unicodedata

from modules.skills.model_library.store import Library


_REQUEST = re.compile(
    r'(?:请\s*)?(?:(?:帮我|给我)\s*)?(?:打开|预览|查看|展示|看看|显示)\s*(?:一下\s*)?'
    r'(?:模型库[中里内]的?\s*)?(.{1,120}?)\s*(?:的\s*)?'
    r'l\s*o\s*d\s*[-_ ]?([0-3零一二两三])(?:\s*(?:版本|模型|预览))*[。！!]?$', re.I)


def preview_request(command):
    if (not command.get('assistant_mode') or command.get('attachments') or
            any(key in command for key in ('reference_image', 'reference_images', 'delivery_basis', 'delivery_format'))):
        return None
    text = command.get('text')
    if not isinstance(text, str) or len(text) > 180:
        return None
    text = unicodedata.normalize('NFKC', text.strip())
    match = _REQUEST.fullmatch(text)
    if not match:
        return None
    name = match[1].strip().removesuffix('的').strip().strip(' “”「」《》"')
    if not name or re.search(r'[\n，,。；;！？?!]|然后|并且|顺便', name):
        return None
    level = match[2].translate(str.maketrans('零一二两三', '01223'))
    return name, 'lod' + level


def _key(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def resolve_preview(root, name, level):
    needle = _key(name)
    short_name = _key(name.removesuffix('模型').strip()) or needle
    matches = []
    with Library(root) as library:
        for row in library.db.execute('SELECT body FROM assets ORDER BY id'):
            asset = json.loads(row['body'])
            keys = [_key(asset['id']), _key(asset['name'])]
            if needle in keys:
                matches.append((3, asset))
            elif short_name in keys:
                matches.append((2, asset))
            elif short_name and any(short_name in key for key in keys):
                matches.append((1, asset))
        best = max((rank for rank, _ in matches), default=0)
        matches = [asset for rank, asset in matches if rank == best]
        choices = []
        for asset in matches[:12]:
            variants = library.detail(asset['id'])['variants']
            selected = [v for v in variants if v['id'].casefold() == level]
            if not selected:
                selected = [v for v in variants if re.search(
                    rf'(?<![a-z0-9])lod[\s_-]*{level[-1]}(?![0-9])', v['label'], re.I)]
            for v in selected:
                if v['file']['meta']['inventory'].get('preview_supported', True):
                    choices.append({'asset': asset['id'], 'version': v['id'], 'sha256': v['file']['sha256'],
                                    'title': ' · '.join([asset['name'], v['label']] + ([asset['id']] if len(matches) > 1 else []))})
        if not matches:
            reply = f'模型库里没有找到“{name}”。请告诉我登记名称或资产编号。'
        elif len(matches) > 1:
            reply = f'“{name}”匹配到 {len(matches)} 项。请选择要预览的 {level.upper()}，或用完整资产名再试。'
            if not choices:
                reply += '列出的候选中没有可预览的这一档，请用完整资产名缩小范围。'
        elif not choices:
            available = '、'.join(v['label'] for v in variants if v['file']['meta']['inventory'].get('preview_supported', True))
            reply = f'{asset["name"]} 没有可预览的 {level.upper()}。可预览版本：{available or "暂无"}。'
        elif len(choices) > 1:
            reply = '找到多个符合要求的版本，请选择一个。'
        else:
            reply = '已找到 ' + choices[0]['title'] + '。'
        return {'status': 'SUCCEEDED', 'provider': 'local-library', 'model': '本机模型库', 'text': reply,
                'assistant_action': {'kind': 'library_preview', 'choices': choices,
                                     'auto_open': len(matches) == 1 and len(choices) == 1}}
