"""Store bounded, asset-specific observations from the hair trial."""
import hashlib
from pathlib import Path
from modules.context_knowledge.character_experience import record, get_episode
from modules.skills.studio3d.character_contract import FAMILY

root=Path(__file__).resolve().parents[1]
data=root/'user-data'
candidate=data/'artifacts/studio3d-character/silver-hair-rebuild-study-03/candidate.blend'
digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
iteration='silver-hair-rebuild-study-03-observations'
episode=record(data,family=FAMILY,asset_id='character-silverhair-01',iteration=iteration,
    evidence_sha256=digest,reviews={
        'source':'用户长发概念图以及 Blender 四角度实际渲染；参考为概念图而非网格',
        'visible_issues':['刘海过于均匀，缺少参考中的交错走向',
                          '侧发层间存在生硬的片状轮廓和交叠',
                          '后发偏直、缺乏参考中的宽松流动与细层',
                          '发饰未制作，脸部仍未达到参考'],
        'static_readback':'脸网格与形态键数据摘要一致，骨骼名称一致；发型是单独集合',
        'not_verified':['视觉未验收','动画、碰撞、物理和导出未测试'],
        'interpretation':'记录观察供本人物试作参考；不是自动训练、自动推广或用户验收'})
assert get_episode(data,family=FAMILY,asset_id='character-silverhair-01',iteration=iteration)==episode
print('Asset-scoped candidate observation saved and read back; not promoted.')
