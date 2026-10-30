"""Bounded supplemental render/crop contract for immutable native assets."""
import math,re

VERSION='1.2.1'
VIEWS=('left','right','front','rear','top')
LIGHTING=('source','neutral','grazing-left','grazing-right')
CHANNELS=('base_color','roughness','metallic','bevel_delta','edge_mask','damage_mask')


def validate(value,names):
    required={'views','bounds','resolution','samples','regions'}
    if not isinstance(value,dict) or not required<=set(value) or set(value)-required-{'focus_region'}:raise ValueError('Unexpected inspection fields')
    if value['resolution'] not in ([960,640],[1536,1024],[2048,1536]):raise ValueError('Inspection resolution budget')
    if type(value['samples']) is not int or not 8<=value['samples']<=32:raise ValueError('Inspection sample budget')
    bounds=value['bounds']
    def vec(v):return isinstance(v,list) and len(v)==3 and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<=30 for x in v)
    if not isinstance(bounds,list) or len(bounds)!=2 or not all(vec(v) for v in bounds) or any(bounds[1][i]-bounds[0][i]<.001 for i in range(3)):raise ValueError('Invalid fixed frame')
    views=value['views']
    if not isinstance(views,list) or not 1<=len(views)<=5:raise ValueError('Inspection view budget')
    seen=set()
    for view in views:
        if not isinstance(view,dict) or not {'id','direction'}<=set(view) or set(view)-{'id','direction','lighting','surface_probe'} or view['id'] not in VIEWS or view['id'] in seen:raise ValueError('Invalid inspection view')
        if view.get('lighting','source') not in LIGHTING:raise ValueError('Unknown fixed lighting preset')
        if 'surface_probe' in view and (view['surface_probe'] not in CHANNELS or view.get('lighting','source')!='source' or 'focus_region' not in value):raise ValueError('Surface probe requires a declared focus, supported channel and source lighting')
        seen.add(view['id'])
        if not vec(view['direction']) or not .1<=sum(x*x for x in view['direction'])<=20:raise ValueError('Invalid direction')
    regions=value['regions']
    if not isinstance(regions,dict) or len(regions)>12:raise ValueError('Region budget')
    for key,members in regions.items():
        if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9-]{0,39}',key):raise ValueError('Invalid region ID')
        if not isinstance(members,list) or not members or len(members)>128 or len(set(members))!=len(members) or any(n not in names for n in members):raise ValueError('Invalid region membership')
    if 'focus_region' in value and (not isinstance(value['focus_region'],str) or value['focus_region'] not in regions):raise ValueError('Focus must name a declared region')
    return value
