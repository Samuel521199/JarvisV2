"""Register tool evidence and bounded visual observations for this character."""
import json
from pathlib import Path
from modules.context_knowledge.character_experience import record,get_episode
from modules.skills.studio3d.character_contract import FAMILY
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'user-data/artifacts/studio3d-character/character-authoring-hair-03'
receipt=json.loads((folder/'receipt.json').read_text(encoding='utf8'))
episode=record(ROOT/'user-data',family=FAMILY,asset_id='character-silverhair-01',
    iteration='character-authoring-hair-03-tool-evidence',evidence_sha256=receipt['candidate_sha256'],reviews={
        'method':'blender-character-authoring: explicit guide plan -> closed hair clump meshes -> four real renders -> saved mesh readback',
        'facts':{'created_objects':len(receipt['created']),'protected_mesh_readback':receipt['protected_mesh_readback'],
                 'source_sha256':receipt['source_sha256'],'plan_sha256':receipt['plan_sha256']},
        'author_observations':['上版平直发片已替换为有厚度的曲线发束与贴脸侧发',
                               '第一轮发尾回折与根部露底已调整；仍有发根帽壳感和规则后发层',
                               '整体发型及脸部还未达到概念参考，不是用户验收'],
        'conditions':['引导线为作者按当前人物坐标手工输入，不是自动图像重建',
                      '仅对当前骨骼做刚性头部绑定，未做头发动态或碰撞验证'],
        'not_verified':['表情、动画、VRM 导出','高质量相似度','Jarvis 独立建模或模型权重训练']})
assert get_episode(ROOT/'user-data',family=FAMILY,asset_id='character-silverhair-01',
    iteration='character-authoring-hair-03-tool-evidence')==episode
print('Recorded asset candidate; not promoted.')
