"""Owner-selected media profiles, separate from immutable legacy model history."""
from datetime import date,timedelta
import math,re
from control.atomic import write_json
from control.paths import child
from control.recovery.gate import RunLock
from sdk.protocol import CoreError,read_json
from modules.image_generation.catalog import RATIOS,dimensions


def read(root):
    path=child(root,'config/image-profiles.json')
    if not path.exists():return {'schema':1,'revision':0,'configured':False,'models':{}}
    value=read_json(path)
    if value.get('schema')!=1 or type(value.get('revision')) is not int or not isinstance(value.get('models'),dict):
        raise CoreError('image_catalog','Unknown media profile catalog')
    for key,profile in value['models'].items():
        validate(profile)
        if key!=profile['model']:raise CoreError('image_catalog','Profile model mismatch')
    return {**value,'configured':True}


def validate(p):
    expected={'adapter','model','edit_model','version','edit_version','name','source','sizes','ratios','defaults','input_by_choice','dimensions','price'}
    if not isinstance(p,dict) or set(p)!=expected or p['adapter']!='eachlabs':raise CoreError('image_catalog','Invalid media profile')
    for name in ('model','version'):
        if not isinstance(p[name],str) or not re.fullmatch('[A-Za-z0-9._-]{1,100}',p[name]):raise CoreError('image_catalog','Invalid model/version')
    if p['edit_model'] is not None and not re.fullmatch('[A-Za-z0-9_-]{1,100}',p['edit_model']):raise CoreError('image_catalog','Invalid edit model')
    if p['edit_model'] and (not isinstance(p['edit_version'],str) or not re.fullmatch('[A-Za-z0-9._-]{1,100}',p['edit_version'])):
        raise CoreError('image_catalog','Invalid edit version')
    if not isinstance(p['name'],str) or len(p['name'])>160 or not p['source'].startswith('https://docs.eachlabs.ai/'):
        raise CoreError('image_catalog','Invalid model metadata')
    if not p['sizes'] or any(s not in ('512','1K','2K','4K') for s in p['sizes']) or not p['ratios'] or any(r not in RATIOS for r in p['ratios']):
        raise CoreError('image_catalog','Invalid media choices')
    for size in p['sizes']:
        for ratio in p['ratios']:
            params={**p['defaults'],**p['input_by_choice'][size][ratio]};pixels=p['dimensions'][size][ratio]
            if set(params)-{'resolution','aspect_ratio','image_size','output_format','num_images'} or params.get('num_images',1)!=1 or params.get('output_format','png')!='png':
                raise CoreError('image_catalog','Only one PNG generation is permitted')
            if any(not isinstance(v,(str,int)) or isinstance(v,bool) for v in params.values()):raise CoreError('image_catalog','Invalid input mapping')
            if len(pixels)!=2 or any(type(x) is not int or not 1<=x<=12288 for x in pixels) or pixels[0]*pixels[1]>20_000_000:
                raise CoreError('image_catalog','Invalid image dimensions')
    price=p['price'];amount=price.get('planning_usd')
    if type(amount) not in (int,float) or not math.isfinite(amount) or not .001<=amount<=100:
        raise CoreError('image_catalog','Configure an explicit positive planning allowance')
    if price.get('currency')!='USD' or price.get('basis')!='owner_planning_allowance' or not price.get('source','').startswith('https://docs.eachlabs.ai/'):
        raise CoreError('image_catalog','Invalid planning price source')
    date.fromisoformat(price['valid_until']);return p


def from_remote(meta,edit,planning):
    props=meta.get('request_schema',{}).get('properties',{})
    sizes=[s for s in props.get('resolution',{}).get('enum',['1K']) if s in ('512','1K','2K','4K')]
    ratios=[r for r in props.get('aspect_ratio',{}).get('enum',[]) if r in RATIOS]
    preset={'1:1':('square_hd',[1024,1024]),'3:4':('portrait_4_3',[768,1024]),'9:16':('portrait_16_9',[576,1024]),
        '4:3':('landscape_4_3',[1024,768]),'16:9':('landscape_16_9',[1024,576])}
    if not ratios and 'image_size' in props:ratios=[r for r,(name,_) in preset.items() if name in props['image_size'].get('enum',[])]
    mapping={};pixels={}
    for size in sizes:
        mapping[size]={};pixels[size]={}
        for ratio in ratios:
            mapping[size][ratio]=({'resolution':size,'aspect_ratio':ratio} if 'resolution' in props else
                {'image_size':preset[ratio][0]} if 'image_size' in props else {'aspect_ratio':ratio})
            pixels[size][ratio]=preset[ratio][1] if 'image_size' in props else dimensions(size,ratio)
    defaults={k:v for k,v in {'output_format':'png','num_images':1}.items() if k in props}
    p={'adapter':'eachlabs','model':meta['slug'],'edit_model':edit['slug'] if edit else None,'version':meta.get('version') or '1.0.0','edit_version':(edit.get('version') or '1.0.0') if edit else None,
        'name':meta.get('title',meta['slug']),'source':'https://docs.eachlabs.ai/each-api/get-model','sizes':sizes,'ratios':ratios,
        'defaults':defaults,'input_by_choice':mapping,'dimensions':pixels,
        'price':{'currency':'USD','basis':'owner_planning_allowance','planning_usd':planning,'checked_at':date.today().isoformat(),
            'valid_until':(date.today()+timedelta(days=30)).isoformat(),'source':'https://docs.eachlabs.ai/each-api/get-model','provider_cost':meta.get('cost')}}
    return validate(p)


def save(root,revision,profile):
    validate(profile)
    with RunLock(root,'software-config'):
        current=read(root)
        if type(revision) is not int or current['revision']!=revision:raise CoreError('conflict','Media catalog changed')
        models={**current['models'],profile['model']:profile}
        if len(models)>32:raise CoreError('image_catalog','Too many media models')
        value={'schema':1,'revision':revision+1,'models':models};write_json(child(root,'config/image-profiles.json'),value)
    return read(root)
