"""Declarative scenes only: model text never becomes executable browser code."""
import json, math, re
from pathlib import Path
from sdk.protocol import CoreError
HOME=Path(__file__).resolve().parents[1]/'modules/skills/anatomy'
SCHEMA=json.loads((HOME/'scene-schema.json').read_text(encoding='utf-8'))
PRESETS=json.loads((HOME/'studio-presets.json').read_text(encoding='utf-8'))

def invalid():raise CoreError('anatomy_scene_invalid','Invalid scene: use registered components, bounded parameters and acyclic links')
def text(value,limit,empty=False):
    if not isinstance(value,str) or not (0 if empty else 1)<=len(value.strip())<=limit or any(ord(c)<32 and c not in '\n\t' for c in value):invalid()
    return value.strip()
def validate_parts(parts):
    contract=SCHEMA['parts_contract'];fields=set(contract['required']);ids={}
    if not isinstance(parts,list) or not 1<=len(parts)<=16:invalid()
    for part in parts:
        if not isinstance(part,dict) or set(part)!=fields:invalid()
        ident=part['id'];parent=part['parent']
        if not isinstance(ident,str) or not re.fullmatch('[a-z][a-z0-9-]{0,23}',ident) or ident in ids or not isinstance(parent,str):invalid()
        for k in ('shape','joint','axis','color'):
            if not isinstance(part[k],str) or part[k] not in contract[k]:invalid()
        for name,lo,hi in [('position',-150,150),('offset',-150,150),('size',2,100),('rotation',-180,180)]:
            v=part[name]
            if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi for x in v):invalid()
        if part['shape']=='cylinder' and part['size'][0]!=part['size'][1]:invalid()
        for name,maximum in [('amplitude',180 if part['joint']=='revolute' else 100 if part['joint']=='prismatic' else 0),('frequency',2),('phase',360)]:
            v=part[name]
            if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=maximum:invalid()
        ids[ident]=part
    active=set();done=set()
    def visit(ident):
        if ident in active or ident not in ids:invalid()
        if ident in done:return
        active.add(ident)
        if ids[ident]['parent']:visit(ids[ident]['parent'])
        active.remove(ident);done.add(ident)
    for ident in ids:visit(ident)
    return json.loads(json.dumps(parts,allow_nan=False))
def validate_scene(value):
    if not isinstance(value,dict) or set(value)!={'version','title','description','modules','links','unfulfilled'} or type(value['version']) is not int or value['version']!=1:invalid()
    result={'version':1,'title':text(value['title'],80),'description':text(value['description'],500,True)}
    modules=value['modules'];links=value['links'];missing=value['unfulfilled']
    if not isinstance(modules,list) or not 1<=len(modules)<=8 or not isinstance(links,list) or len(links)>8 or not isinstance(missing,list) or len(missing)>12:invalid()
    result['unfulfilled']=[text(v,200) for v in missing];result['modules']=[];result['links']=[];ids={}
    for m in modules:
        if not isinstance(m,dict) or set(m)!={'id','type','label','params','effects'} or not isinstance(m['id'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,23}',m['id']) or m['id'] in ids or not isinstance(m['type'],str) or m['type'] not in SCHEMA['types']:invalid()
        spec=SCHEMA['types'][m['type']];p=m['params'];effects=m['effects']
        if not isinstance(p,dict) or set(p)-set(spec['params']) or not isinstance(effects,list) or any(not isinstance(e,str) or e not in spec['effects'] for e in effects) or len(set(effects))!=len(effects):invalid()
        params={}
        for name,rule in spec['params'].items():
            v=p.get(name,rule['default'])
            if rule.get('kind')=='parts':v=validate_parts(v)
            elif 'enum' in rule:
                if not any(type(v) is type(x) and v==x for x in rule['enum']):invalid()
            elif type(v) not in (int,float) or not math.isfinite(v) or not rule['min']<=v<=rule['max'] or rule.get('integer') and type(v) is not int:invalid()
            params[name]=v
        normalized={'id':m['id'],'type':m['type'],'label':text(m['label'],50),'params':params,'effects':list(effects)}
        ids[m['id']]=normalized;result['modules'].append(normalized)
    incoming={};edges={key:[] for key in ids}
    for link in links:
        if not isinstance(link,dict) or set(link)!={'from','to','kind','ratio'}:invalid()
        a,b,k,r=link['from'],link['to'],link['kind'],link['ratio']
        if not all(isinstance(x,str) for x in (a,b,k)) or a not in ids or b not in ids or a==b or b in incoming or k not in SCHEMA['links']:invalid()
        spec=SCHEMA['links'][k]
        if ids[a]['type'] not in spec['from'] or ids[b]['type'] not in spec['to'] or type(r) not in (int,float) or not math.isfinite(r) or not 0.1<=abs(r)<=4 or k=='flow' and r<0:invalid()
        incoming[b]=link;edges[a].append(b);result['links'].append(dict(link))
    # Cycle detection and a conservative upper bound prevent runaway inherited speed.
    visited=set();active=set();bounds={}
    def visit(ident):
        if ident in active:invalid()
        if ident in visited:return bounds[ident]
        active.add(ident);m=ids[ident];p=m['params'];kind=m['type']
        rpm=abs(p.get('rpm',0))
        if kind=='motor':rpm=p['constant']*p['voltage']/(p['resistance']*0.0002+p['constant']**2)*60/(2*math.pi) if p['switch_closed'] else 0
        if ident in incoming:
            link=incoming[ident];source=visit(link['from'])
            if link['kind']=='shaft':rpm=source*abs(link['ratio'])
        if kind=='gear-pair':rpm*=p['teeth_a']/p['teeth_b']
        if rpm>24000:invalid()
        active.remove(ident);visited.add(ident);bounds[ident]=rpm;return rpm
    for ident in ids:visit(ident)
    return result
