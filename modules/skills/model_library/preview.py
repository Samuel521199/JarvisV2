"""Resolve an explicit preview request against registered, immutable library variants."""
import json
import re
import unicodedata
from difflib import SequenceMatcher

from modules.skills.model_library.store import Library


_PREFIX = (r'(?:请\s*)?(?:(?:帮我|给我)\s*)?(?:打开|预览|查看|展示|看看|显示)\s*(?:一下\s*)?'
           r'(?:模型库[中里内]的?\s*)?(.{1,120}?)\s*(?:的\s*)?')
_END = r'(?:\s*(?:版本|模型|预览))*[。！!]?$'
_LOD = r'l\s*o\s*d'
_LEVELS = dict(zip('0123零一二两三', '012301223'))
_LEVELS.update(zero='0', one='1', two='2', three='3')
_REQUEST = re.compile(_PREFIX + _LOD + r'\s*[-_ ]?([0-3零一二两三])' + _END, re.I)
# These letter fragments were observed on the local STT engines. They are
# accepted only when offering suggestions, never as an executable LOD request.
_SPEECH_HINT = re.compile(
    _PREFIX + r'(?<![A-Za-z])(?:' + _LOD + r'|l\s*[od]|ln|lon|vlog|l)'
    + r'\s*[-_ ]?([0-3零一二两三]|zero|one|two|three)' + _END, re.I)
_DIGITS = '零一二三四五六七八九'
_ENGLISH_ONES = dict(zip('one two three four five six seven eight nine'.split(), '123456789'))
_ENGLISH_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), '23456789'))
_SPOKEN_TENS = re.compile(
    r'\b(' + '|'.join(_ENGLISH_TENS) + r')(?:[ -]+(' + '|'.join(_ENGLISH_ONES) + r'))?\b', re.I)


def _parse(text, pattern):
    if not isinstance(text, str) or len(text) > 180:
        return None
    match = pattern.fullmatch(unicodedata.normalize('NFKC', text.strip()))
    if not match:
        return None
    name = match[1].strip().removesuffix('的').strip().strip(' “”「」《》"')
    if not name or re.search(r'[\n，,。；;！？?!]|然后|并且|顺便', name):
        return None
    return name, 'lod' + _LEVELS[match[2].casefold()]


def preview_request(command):
    if (not command.get('assistant_mode') or command.get('attachments') or
            any(key in command for key in ('reference_image', 'reference_images', 'delivery_basis', 'delivery_format'))):
        return None
    return _parse(command.get('text'), _REQUEST)


def _key(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def _level_variants(asset, level):
    variants = asset['variants']
    selected = [variant for variant in variants if variant['id'].casefold() == level]
    if not selected:
        selected = [variant for variant in variants if re.search(
            rf'(?<![a-z0-9])lod[\s_-]*{level[-1]}(?![0-9])', variant['label'], re.I)]
    return [variant for variant in selected if variant['file']['meta']['inventory'].get('preview_supported', True)]


def _speech_key(text):
    def tens(match):
        return str(_DIGITS.index(match[1]) if match[1] else 1) + str(_DIGITS.index(match[2]) if match[2] else 0)

    text = re.sub(r'([一二三四五六七八九]?)十([零一二三四五六七八九]?)', tens, text)
    text = text.translate(str.maketrans(_DIGITS + '两', '01234567892'))
    text = _SPOKEN_TENS.sub(lambda match: _ENGLISH_TENS[match[1].lower()]
                           + _ENGLISH_ONES.get((match[2] or '').lower(), '0'), text)
    return _key(text.removesuffix('模型').strip())


def speech_candidates(root, text):
    """Suggest bounded, registered LOD choices without rewriting the draft."""
    strict = _parse(text, _REQUEST)
    parsed = strict or _parse(text, _SPEECH_HINT)
    if not parsed:
        return {'choices': [], 'needs_confirmation': False}
    name, level = parsed
    needle = _speech_key(name)
    if not needle:
        return {'choices': [], 'needs_confirmation': False}
    matches = []
    with Library(root) as library:
        for row in library.db.execute('SELECT body FROM assets ORDER BY id'):
            asset = json.loads(row['body'])
            keys = {_speech_key(asset['id']), _speech_key(asset['name'])}
            rank = max((_name_similarity(needle, key) for key in keys), default=0)
            if rank:
                matches.append((rank, asset))
        best = max((rank for rank, _ in matches), default=0)
        if best >= 2:
            matches = [(rank, asset) for rank, asset in matches if rank == best]
        choices = []
        for _, asset in sorted(matches, key=lambda match: -match[0])[:5]:
            selected = _level_variants(library.detail(asset['id']), level)
            if len(selected) != 1:
                continue
            variant = selected[0]
            choices.append({'asset': asset['id'], 'title': asset['name'], 'label': variant['label'],
                            'text': f"打开 {asset['id']} 的 {level.upper()}"})
    return {'choices': choices, 'needs_confirmation': strict is None}


def _name_similarity(needle, key):
    if needle == key:
        return 3
    if len(needle) >= 2 and needle in key:
        return 2
    if min(len(needle), len(key)) < 2 or needle[0] != key[0]:
        return 0
    similarity = SequenceMatcher(None, needle, key, autojunk=False).ratio()
    return similarity if similarity >= (.5 if len(needle) == len(key) == 2 else .65) else 0


def resolve_preview(root, name, level):
    needle = _key(name)
    short_name = _key(name.removesuffix('模型').strip()) or needle
    matches = []
    with Library(root) as library:
        for row in library.db.execute('SELECT body FROM assets ORDER BY id'):
            asset = json.loads(row['body'])
            keys = [_key(asset['id']), _key(asset['name'])]
            if name.casefold() == asset['id']:
                matches.append((4, asset))
            elif needle in keys:
                matches.append((3, asset))
            elif short_name in keys:
                matches.append((2, asset))
            elif short_name and any(short_name in key for key in keys):
                matches.append((1, asset))
        best = max((rank for rank, _ in matches), default=0)
        matches = [asset for rank, asset in matches if rank == best]
        choices = []
        for asset in matches[:12]:
            detail = library.detail(asset['id'])
            variants = detail['variants']
            for variant in _level_variants(detail, level):
                choices.append({'asset': asset['id'], 'version': variant['id'], 'sha256': variant['file']['sha256'],
                                'title': ' · '.join([asset['name'], variant['label']] + ([asset['id']] if len(matches) > 1 else []))})
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
