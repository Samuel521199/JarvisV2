"""Character-only data contract; never accepts a rigid-asset recipe or code."""
import copy
import math
import re

VERSION = '1.0.0'
FAMILY = 'stylized_character'
VIEWS = ('front', 'rear', 'right', 'left')
BOUNDS = {'height':(1.5,1.85,1.68), 'head_scale':(.88,1.15,1.),
          'shoulder_scale':(.85,1.15,1.), 'waist_scale':(.85,1.15,1.),
          'hip_scale':(.85,1.15,1.), 'leg_scale':(.85,1.15,1.),
          'arm_scale':(.85,1.15,1.), 'depth_scale':(.85,1.15,1.),
          'eye_scale':(.85,1.2,1.), 'hair_length':(.88,1.18,1.),
          'hair_volume':(.9,1.15,1.), 'face_width':(.9,1.12,1.)}
COLORS = {'skin_color':'#D7C1B5','hair_color':'#B8B5C9','iris_color':'#80664E'}


def parameters():
    return {**{k:v[2] for k,v in BOUNDS.items()}, **COLORS}


def validate_parameters(raw):
    if not isinstance(raw,dict) or set(raw) != set(parameters()):
        raise ValueError('Character parameters must exactly match the fixed contract')
    for key,(lo,hi,_) in BOUNDS.items():
        val=raw[key]
        if type(val) not in (int,float) or not math.isfinite(val) or not lo<=val<=hi:
            raise ValueError('Invalid character parameter: '+key)
    for key in COLORS:
        if not isinstance(raw[key],str) or not re.fullmatch('#[0-9A-Fa-f]{6}',raw[key]):
            raise ValueError('Invalid character color')
    return copy.deepcopy(raw)


def validate(raw):
    if not isinstance(raw,dict) or set(raw)!={'schema','family','asset_id','parameters','reference_sha256','stage'}:
        raise ValueError('Unknown character input fields')
    if raw['schema']!='jarvis.studio3d.character.v1' or raw['family']!=FAMILY or raw['stage']!='static_base':
        raise ValueError('Character domain/stage mismatch')
    if not isinstance(raw['asset_id'],str) or not re.fullmatch('character-[a-z0-9-]{1,64}',raw['asset_id']):
        raise ValueError('Character identity required')
    refs=raw['reference_sha256']
    if not isinstance(refs,dict) or set(refs)!=set(VIEWS) or any(not isinstance(s,str) or not re.fullmatch('[0-9a-f]{64}',s) for s in refs.values()):
        raise ValueError('Four frozen character reference identities required')
    validate_parameters(raw['parameters'])
    return copy.deepcopy(raw)


def patch(base, proposed):
    """Small, bounded model-selected updates, never arbitrary scene operations."""
    if not isinstance(proposed,dict) or len(proposed)>4 or set(proposed)-set(parameters()):
        raise ValueError('At most four known character updates')
    candidate=validate_parameters(base)
    for key,value in proposed.items():
        if key in BOUNDS and (type(value) not in (int,float) or abs(value-base[key])>.081):
            raise ValueError('Character update exceeds per-round step')
        candidate[key]=value
    return validate_parameters(candidate)
