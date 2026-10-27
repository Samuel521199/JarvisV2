"""Composable design briefs and human acceptance; no additional paid planner."""
from sdk.protocol import CoreError

RECIPES={
 'free':{'name':'自由绘图','icon':'🎨','rule':'Follow the brief without inventing extra text.','checks':['brief','composition','artifacts']},
 'product':{'name':'产品与机械效果图','icon':'🔩','rule':'Make material boundaries, assembly seams, silhouette and lighting readable. Preserve reference geometry; do not invent engineering precision.','checks':['brief','silhouette','materials','artifacts']},
 'poster':{'name':'海报与品牌视觉','icon':'🖼️','rule':'Build a clear headline / subject / supporting-copy hierarchy, generous margins, consistent palette. Render only explicitly requested copy.','checks':['brief','text','hierarchy','artifacts']},
 'infographic':{'name':'信息图与科普图解','icon':'📊','rule':'Use a consistent grid, legible labels, ordered steps and unambiguous connectors. Do not invent facts, values or scientific evidence.','checks':['brief','text','facts','hierarchy','artifacts']},
 'material':{'name':'材质底色参考','icon':'🧵','rule':'Create a flat evenly lit material color study, without baked directional shadows or specular highlights. Ask for seamless borders only if requested. This is not a validated PBR map set.','checks':['brief','lighting','seams','artifacts']},
 'reference3d':{'name':'3D 建模参考','icon':'🧊','rule':'Use consistent material zones, uncluttered background and explicit views. Keep silhouette, component placement and proportions coherent. Mark unseen construction as conceptual; no fabricated dimensional measurements.','checks':['brief','silhouette','views','materials','artifacts']},
}
CHECKS={'brief':'符合用途与要求','composition':'构图和留白合适','artifacts':'无明显畸形、重复或脏点','silhouette':'轮廓与关键部件正确','materials':'材质分区清楚','text':'文字逐字核对','hierarchy':'层级与阅读顺序清晰','facts':'数据和科学表述已核对','lighting':'底色未混入明显光照','seams':'边缘与接缝满足用途','views':'多视图比例和部件一致'}

def compile_brief(prompt,brief=None):
    if brief is None:brief={'preset':'free','audience':'','style':'','constraints':''}
    if not isinstance(brief,dict) or set(brief)!={'preset','audience','style','constraints'} or not isinstance(brief['preset'],str) or brief['preset'] not in RECIPES:raise CoreError('image_design_invalid','Choose a supported design brief')
    if any(not isinstance(brief[k],str) or len(brief[k])>1000 for k in ('audience','style','constraints')):raise CoreError('image_design_invalid','Brief fields too long')
    recipe=RECIPES[brief['preset']]
    text=prompt if brief['preset']=='free' and not any(brief[k] for k in ('audience','style','constraints')) else prompt+'\n\nDesign brief:\n'+recipe['rule']+'\nAudience: '+brief['audience']+'\nStyle: '+brief['style']+'\nRequired constraints: '+brief['constraints']
    if len(text)>8000:raise CoreError('image_design_invalid','Combined prompt exceeds 8000 characters')
    return text,{'brief':dict(brief),'checklist':[{'id':k,'label':CHECKS[k]} for k in recipe['checks']],'acceptance':'pending_human_review','planner':'local brief compiler; zero extra model calls'}
