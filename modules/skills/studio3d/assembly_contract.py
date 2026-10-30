"""Explicit local high-poly reference assembly; no generated Python or CAD claims."""
import copy
import math
import re

VERSION = '1.0.0'
LIMITS = {'part_bytes': 96*1024**2, 'parts': 8, 'triangles': 20000000,
          'wall_seconds': 1200, 'memory_bytes': 16*1024**3, 'output_bytes': 3*1024**3, 'threads': 4}


def validate(value):
    if not isinstance(value,dict) or set(value)!={'schema','title','parts','views','mode'} or value['schema']!='jarvis.studio3d.assembly.v1':
        raise ValueError('Assembly contract fields')
    if not isinstance(value['title'],str) or not 1<=len(value['title'])<=160 or value['mode'] not in ('inspect','assemble'):
        raise ValueError('Assembly title/mode')
    if not isinstance(value['parts'],list) or not 1<=len(value['parts'])<=LIMITS['parts']:
        raise ValueError('Assembly part budget')
    names=set()
    for part in value['parts']:
        if not isinstance(part,dict) or set(part)!={'id','source','parent','position','rotation','scale'}:
            raise ValueError('Part fields')
        if not isinstance(part['id'],str) or not re.fullmatch('[a-z][a-z0-9_-]{0,59}',part['id']) or part['id'] in names:
            raise ValueError('Part identity')
        if not isinstance(part['source'],str) or not re.fullmatch('[a-z][a-z0-9_-]{0,59}',part['source']):raise ValueError('Source identity')
        if part['parent'] is not None and part['parent'] not in names:raise ValueError('Parent must precede child')
        for key in ('position','rotation','scale'):
            a=part[key]
            bound=360 if key=='rotation' else 100
            if not isinstance(a,list) or len(a)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>bound for x in a):raise ValueError('Bounded finite transform')
        if any(abs(x)<.001 for x in part['scale']):raise ValueError('Singular scale')
        names.add(part['id'])
    if not isinstance(value['views'],list) or not 1<=len(value['views'])<=8 or len(set(value['views']))!=len(value['views']) or set(value['views'])-{'hero','rear','front','back','left','right','top','exploded'}:
        raise ValueError('Assembly views')
    return copy.deepcopy(value)
