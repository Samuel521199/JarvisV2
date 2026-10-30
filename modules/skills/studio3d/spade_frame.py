"""Asset-scoped exterior frame repair; not a general mechanical assembly tool."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate

SCHEMA = 'jarvis.studio3d.spade-frame.v1'
SIDES = ('left', 'right')
TARGETS = tuple(p+'-'+s for s in SIDES for p in ('spade-seat','spade-pivot-seat','spade-lever'))
SUPPORTS = tuple(p+'-'+s for s in SIDES for p in ('spade-seat','spade-pivot-seat'))
ANCHORS = tuple(p+'-'+s for s in SIDES for p in ('spade-blade','spade-catches','spade-retainer'))

def validate(c, names):
    fields = {'schema','author','evidence','source_sha256','bindings','components','corner_offset','inspection'}
    if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA:
        raise ValueError('Unexpected spade frame contract')
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:
        raise ValueError('Declared author and exterior evidence required')
    def sha(x):
        return isinstance(x,str) and len(x)==64 and all(v in '0123456789abcdef' for v in x)
    if not sha(c['source_sha256']):raise ValueError('Full source binding required')
    if not isinstance(c['bindings'],dict) or set(c['bindings'])!=set(TARGETS+ANCHORS):
        raise ValueError('Bind six targets and six unchanged anchors')
    for n,row in c['bindings'].items():
        if n not in names or not isinstance(row,dict) or set(row)!={'base','dependency'} or not all(sha(v) for v in row.values()):
            raise ValueError('Invalid object/dependency binding')
    if type(c['corner_offset']) not in (int,float) or not math.isfinite(c['corner_offset']) or not .03<=c['corner_offset']<=.04:
        raise ValueError('Frame corner envelope')
    if not isinstance(c['components'],dict) or set(c['components'])!=set(SIDES):raise ValueError('Two component bindings required')
    for row in c['components'].values():
        if not isinstance(row,dict) or set(row)!={'seat','pivot_plate','pivot_cylinder'}:raise ValueError('Explicit components required')
        for key,size in (('seat',8),('pivot_plate',8),('pivot_cylinder',194)):
            ids=row[key]
            if not isinstance(ids,list) or len(ids)!=size or len(set(ids))!=size or any(type(x)is not int or not 0<=x<334 for x in ids):
                raise ValueError('Complete bounded component indices required')
        if set(row['pivot_plate'])&set(row['pivot_cylinder']):raise ValueError('Overlapping component indices')
    inspect_validate(c['inspection'],names)
    if c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:
        raise ValueError('Fixed two-view resource budget')
    return c
