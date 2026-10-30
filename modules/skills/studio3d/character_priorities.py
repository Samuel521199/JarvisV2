"""Bounded, asset-scoped priorities for the user's character review."""
import hashlib
import json
from pathlib import Path

SCHEMA='jarvis.studio3d.character.priorities.v1'
FAMILY='stylized_character'
DEFAULT={
    'schema':SCHEMA,'family':FAMILY,'asset_id':'character-silverhair-01',
    'priorities':['整体形体与正侧轮廓','腰臀和四肢自然过渡','脸型与眼神','刘海、侧发和后发细节'],
    'rules':['逐视图分清形体、相机、遮挡与光照',
             '头身、姿势、关节和身体侧面曲线分别检查',
             '眼形、脸型、鼻嘴和发束层次分别检查',
             '不把参数变化或格式通过当作视觉改善',
             '已有FBX及人工修改必须说明来源，不能称为模型自主重建'],
    'origin':'用户对本人物的明确指令','automatic_promotion':False}


def validate(value,asset_id):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT):raise ValueError('Unexpected priority fields')
    if value['schema']!=SCHEMA or value['family']!=FAMILY or value['asset_id']!=asset_id:
        raise ValueError('Character priority scope mismatch')
    if value['automatic_promotion'] is not False:raise ValueError('Asset priority cannot auto-promote')
    for name in ('priorities','rules'):
        if not isinstance(value[name],list) or not 1<=len(value[name])<=12 or any(not isinstance(s,str) or not 1<=len(s)<=150 for s in value[name]):
            raise ValueError('Invalid priority items')
    if not isinstance(value['origin'],str) or not 1<=len(value['origin'])<=100:raise ValueError('Invalid priority origin')
    return value


def load(path,asset_id):
    raw=Path(path).read_bytes()
    return validate(json.loads(raw.decode('utf-8')),asset_id),hashlib.sha256(raw).hexdigest()
