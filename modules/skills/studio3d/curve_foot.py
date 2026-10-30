"""A bound visible grip-to-cover repair; not a physical mechanism model."""
import math
from modules.skills.studio3d.render_inspection import validate as inspection_validate
SCHEMA='jarvis.studio3d.curve-foot.v1'
NAMES={'breech-top-grip','breech-top-cover','rear-cover-body','rear-upper-latch'}

def foot_shift(gaps,embed):
    if type(embed) not in (int,float) or not math.isfinite(embed) or not .0004<=embed<=.0008:
        raise ValueError('Bounded visual overlap required')
    if not gaps or any(type(g) not in (int,float) or not math.isfinite(g) for g in gaps):
        raise ValueError('Actual finite foot samples required')
    if min(gaps)<0 or max(gaps)-min(gaps)>1e-6 or max(gaps)>.012-embed:
        raise ValueError('Unsupported foot gap or nonplanar support')
    return -max(gaps)-embed

def validate(c,names):
    fields={'schema','author','evidence','source_sha256','dependencies','boundary_vertices','embed','inspection'}
    if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA:raise ValueError('Unexpected cosmetic foot contract')
    sha=lambda s:isinstance(s,str) and len(s)==64 and all(v in '0123456789abcdef' for v in s)
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Explicit author and actual evidence required')
    if not sha(c['source_sha256']) or not isinstance(c['dependencies'],dict) or set(c['dependencies'])!=NAMES or not all(sha(v) for v in c['dependencies'].values()):raise ValueError('Exact source and complete local dependencies required')
    ids=c['boundary_vertices']
    if not isinstance(ids,list) or len(ids)!=20 or any(type(i)!=int or not 0<=i<370 for i in ids) or ids!=sorted(set(ids)):raise ValueError('Complete two original open rims required')
    if not NAMES<=set(names):raise ValueError('Original visible inventory required')
    foot_shift([.006]*20,c['embed']);inspection_validate(c['inspection'],names)
    v=c['inspection']
    if v.get('focus_region')!='upper-grip' or v['regions']!={'upper-grip':['breech-top-grip','breech-top-cover']} or v['resolution']!=[960,640] or v['samples']!=12 or len(v['views'])!=2:raise ValueError('Bounded actual paired views required')
    return c
