"""Explicit dialogue document format; a presentation contract, not execution authority."""
import re

FORMAT='source_excerpt_markdown_v1'
INSTRUCTION=('本轮明确选择来源摘录文档。输出JSON对象，包含evidence和document；若使用助手外层协议，'
    '将该JSON放入reply字符串。evidence恰含facts、plans、suggestions。facts和plans为数组，'
    '每项恰含source和quote：source使用当前核对依据的F/P编号，quote逐字引用对应原文。'
    '保留全部当前事实与已确认计划，不引用旧版本或新增未确认条目。suggestions为最多5条单行建议，'
    '尚未采纳。document留空，由程序在来源与范围核对通过后按事实、已确认计划、建议三个段落生成正文。'
    '其余业务字段按本轮要求回答；此文档选择不授予任何执行权限。')


def context_basis(basis,text):
    """Keep current source meaning; omit duplicate quotes only for exact ID lines."""
    lines={};duplicates=set()
    for key,quote in re.findall(r'^(F\d+|P\d+)：([^\n]+)$',text,flags=re.MULTILINE):
        if key in lines:duplicates.add(key)
        lines[key]=quote
    referenced=bool(basis['entries']) and all(x['id'] not in duplicates and lines.get(x['id'])==x['quote'] for x in basis['entries'])
    entries=[{k:x[k] for k in (('id','kind') if referenced else ('id','kind','quote'))} for x in basis['entries']]
    result={k:basis[k] for k in ('revision','digest','source_time_utc','relative_time_resolution') if k in basis}
    return {**result,'entries':entries,'quote_locations':'visible_message_id_lines' if referenced else 'entries'}
