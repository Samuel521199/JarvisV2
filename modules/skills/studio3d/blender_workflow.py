"""Blender workflow metadata and bounded edits to an immutable scene candidate."""
import copy

from modules.skills.studio3d.contract import CONTRACT, validate
from sdk.protocol import CoreError, digest

VERSION = '1.0.0'
WORKFLOW = {
    'version': VERSION,
    'name': 'Blender 3D 制作与修改',
    'stages': [
        {'name': '参考与目标', 'status': 'ready', 'detail': '登记参考图、尺寸、用途及来源；需要新图时复用图片工作室。'},
        {'name': '建立模型', 'status': 'ready', 'detail': 'Jarvis 模型输出受限曲面/网格数据，Blender 制作 .blend 和 GLB。'},
        {'name': '局部修改', 'status': 'ready', 'detail': '对本工作室的未烘焙数据模型修改部件尺寸、变换、材质或支持的修改器，保留原版。'},
        {'name': '渲染比较', 'status': 'ready', 'detail': '查看真实渲染与五视图；参考识图修正使用明确选择的视觉模型。'},
        {'name': '游戏资产', 'status': 'ready', 'detail': '现有高模→低模、静态 PBR 烘焙、LOD 流程；外观验收另行判断。'},
        {'name': '角色绑定、表情、VRM', 'status': 'external_only', 'detail': 'Charakuru 外部套件可用；尚未接入 Jarvis 的自动执行，不因安装而宣称完成。'},
    ],
    'outputs': ['model.blend', 'model.glb', 'preview.png', 'scene.json', 'report.json'],
    'edit_scope': '本工作室已交付、未烘焙的声明式模型；外部 GLB 仅支持原有导入渲染，任意 BLEND/FBX 编辑未接入。',
    'sources': [
        {'name': 'kokushin/charakuru-claude-code · 非官方流程参考', 'url': 'https://github.com/kokushin/charakuru-claude-code/tree/28eddac5fe4bcb8f78f0d375fd7aedc824d7becb', 'commit': '28eddac5fe4bcb8f78f0d375fd7aedc824d7becb', 'license': 'MIT'},
        {'name': 'Nano / Charakuru · 原始套件', 'url': 'https://github.com/nanocle/Charakuru/releases/tag/v1.1.0', 'version': '1.1.0', 'license': 'Charakuru Source-Available License；不随本工程分发'},
        {'name': 'Blender · 本地建模引擎', 'url': 'https://www.blender.org/', 'license': 'GPL-2.0-or-later'},
    ],
    'runtime': 'Jarvis Studio3D；不启动 Claude/Codex 子代理，不依赖 Tripo，不执行外来 Python。',
}

OBJECT_FIELDS = {'position', 'rotation', 'scale', 'params', 'modifiers', 'material', 'visible', 'shading', 'cap_material'}
MATERIAL_FIELDS = {'color', *CONTRACT['material']['optional']}


def apply_changes(original, changes):
    """Return a validated new scene and exact edit receipt, never mutate original."""
    before = validate(original)
    if any(k in before for k in ('asset', 'master', 'asset_pipeline')):
        raise CoreError('studio3d_invalid', 'Edit an unbaked declarative scene; imported/derived assets are not editable here')
    if not isinstance(changes, dict) or not changes or set(changes) - {'objects', 'materials'}:
        raise CoreError('studio3d_invalid', 'Expected object/material changes')
    scene = copy.deepcopy(before)
    touched = {'objects': [], 'materials': []}
    for group, allowed in (('objects', OBJECT_FIELDS), ('materials', MATERIAL_FIELDS)):
        updates = changes.get(group, [])
        if not isinstance(updates, list) or len(updates) > 32:
            raise CoreError('studio3d_invalid', 'At most 32 changes per group')
        targets = {item['id']: item for item in scene[group]}
        for patch in updates:
            if not isinstance(patch, dict) or set(patch) != {'id', 'set'} or not isinstance(patch['id'], str):
                raise CoreError('studio3d_invalid', 'Expected a named target and set fields')
            ident, values = patch['id'], patch['set']
            if ident not in targets or ident in touched[group]:
                raise CoreError('studio3d_invalid', 'Missing or duplicate edit target')
            if not isinstance(values, dict) or not values or set(values) - allowed:
                raise CoreError('studio3d_invalid', 'Unsupported edit fields')
            touched[group].append(ident)
            for key, value in values.items():
                if key in ('params', 'modifiers'):
                    if not isinstance(value, dict):
                        raise CoreError('studio3d_invalid', 'Expected geometry fields')
                    targets[ident][key] = {**targets[ident].get(key, {}), **copy.deepcopy(value)}
                else:
                    targets[ident][key] = copy.deepcopy(value)
    scene = validate(scene)
    if digest(scene) == digest(before):
        raise CoreError('studio3d_invalid', 'The edit does not change this model')
    # Material edits affect every referencing object, not just the UI's selected part.
    affected = [o['id'] for o in scene['objects'] if o['id'] in touched['objects'] or o['material'] in touched['materials'] or o.get('cap_material') in touched['materials']]
    unchanged = {o['id']: digest(o) for o in before['objects'] if o['id'] not in touched['objects']}
    audit = {'workflow_version': VERSION, 'changes': copy.deepcopy(changes), 'affected_objects': affected,
             'unchanged_object_data_sha256': unchanged, 'before_scene_sha256': digest(before),
             'after_scene_sha256': digest(scene), 'new_model_calls': 0, 'visual_acceptance': 'pending'}
    return scene, audit
