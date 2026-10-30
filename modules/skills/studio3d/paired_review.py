"""Direct visual change verification; ordinal issue counts remain diagnostic.

This is a model opinion backed by actual renders, not quantitative similarity,
historical validation, or user acceptance. All five views must agree that no
visible regression was introduced, with at least one evidenced improvement.
"""
import json
import hashlib
from modules.skills.studio3d.hard_surface_review import VIEWS
from modules.skills.studio3d.production_loop import decode

VERSION='1.0.0'


def make_sheet(before,after,destination):
    """Lossless layout of two renders; no resampling, repainting or inference."""
    from PIL import Image,ImageDraw
    sources=[]
    for path in (before,after):
        with Image.open(path) as im:
            if im.format!='PNG' or im.width*im.height>4000000:raise ValueError('Unexpected render evidence')
            sources.append(im.convert('RGB'))
    if sources[0].size!=sources[1].size:raise ValueError('Compare equal-resolution renders')
    w,h=sources[0].size;sheet=Image.new('RGB',(w,2*h+64),(245,245,245));draw=ImageDraw.Draw(sheet)
    for i,(im,label) in enumerate(zip(sources,('BEFORE - retained model','AFTER - candidate model'))):
        top=i*(h+32);draw.text((8,top+8),label,fill=(0,0,0));sheet.paste(im,(0,top+32))
        if sheet.crop((0,top+32,w,top+32+h)).tobytes()!=im.tobytes():raise ValueError('Evidence pixels changed')
    sheet.save(destination)
    return {'composition':'top BEFORE / bottom AFTER, original RGB pixels, no resizing','source_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in (before,after)],'sheet_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'size':list(sheet.size)}


def prompt(view, actions, policy):
    if view not in VIEWS:raise ValueError('Unknown paired view')
    return '''You are Jarvis's independent visual-change checker for a game prop.
IMAGE 1 = target reference. IMAGE 2 = a lossless two-row comparison sheet.
Image 2 TOP row labelled BEFORE = previous retained ACTUAL Blender render.
Image 2 BOTTOM row labelled AFTER = new candidate ACTUAL Blender render.
Same model view and original pixels, no resampling or generated image edits.
Compare BEFORE with AFTER against image 1. Inspect silhouettes, attachment integrity, material,
and changed detail shapes. Existing defects can remain, but do not describe an
unchanged old defect as a newly introduced regression. Improvements must be
visibly closer to image 1, not simply more detailed. Differences due solely to
camera/light must be described separately. Render engine may change to support
the coating; judge the resulting appearance against the target.
Return strict JSON, under 1300 Chinese characters:
{"view":"VIEW","change":"better|same|worse|uncertain","confidence":"high|medium|low",
"improvements":["visible before/after evidence"],"regressions":["visible newly worse area"],
"remaining":["unresolved reference mismatch"],"caveat":"camera/occlusion limitations"}
Any meaningful new defect makes change=worse even if another area improved.
Do not claim image similarity percentages, user approval, or hidden mechanics.
''' .replace('"VIEW"',json.dumps(view))+'\nPLANNED_ACTIONS:'+json.dumps(actions,ensure_ascii=False)[:3300]+'\nASSET_POLICY:'+json.dumps(policy,ensure_ascii=False)


def parse(raw, view):
    v=decode(raw)
    if not isinstance(v,dict) or v.get('view')!=view or view not in VIEWS:raise ValueError('Wrong paired review identity')
    if v.get('change') not in ('better','same','worse','uncertain') or v.get('confidence') not in ('high','medium','low'):raise ValueError('Invalid change conclusion')
    for k in ('improvements','regressions','remaining'):
        if not isinstance(v.get(k),list) or len(v[k])>8 or any(not isinstance(x,str) or not 1<=len(x)<=800 for x in v[k]):raise ValueError('Unbounded visual evidence')
    if not isinstance(v.get('caveat'),str) or len(v['caveat'])>1200:raise ValueError('Invalid caveat')
    if v['change']=='better' and not v['improvements']:raise ValueError('Improvement needs visible evidence')
    if v['regressions']:v['change']='worse'
    return v


def decide(reviews):
    by={r['view']:r for r in reviews}
    out={'accepted':False,'method':'direct_three_image_five_view_comparison','user_approval':False,'lod_authorized':False,
         'metric_scope':'visual model opinion; no numeric similarity claim'}
    if len(reviews)!=5 or set(by)!=set(VIEWS):return {**out,'reason':'missing_or_duplicate_views'}
    if any(r['change']=='worse' or r['regressions'] for r in reviews):return {**out,'reason':'visible_paired_regression'}
    if any(r['change']=='uncertain' or r['confidence']=='low' for r in reviews):return {**out,'reason':'uncertain_paired_comparison'}
    if not any(r['change']=='better' and r['improvements'] for r in reviews):return {**out,'reason':'no_evidenced_improvement'}
    return {**out,'accepted':True,'reason':'visible_improvement_without_paired_regression','improved_views':[v for v,r in by.items() if r['change']=='better']}
