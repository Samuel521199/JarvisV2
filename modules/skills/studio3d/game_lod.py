"""Bounded game LOD derivation from an explicitly approved current high."""
VERSION='1.2.0'
def validate(value):
    required={'level','triangle_budget','texture_size','ray_distance'}
    if not isinstance(value,dict) or not required<=set(value) or set(value)-required-{'geometry_mode'}:raise ValueError('Explicit LOD controls required')
    if type(value['level']) is not int or value['level'] not in range(4):raise ValueError('LOD0-3 only')
    mode=value.get('geometry_mode','reduce')
    if mode not in ('reduce','silhouette','structured') or mode=='silhouette' and value['level']!=3 or mode=='structured' and value['level']!=2:raise ValueError('Structured is LOD2; silhouette is LOD3 only')
    low,high=(100,2000) if mode=='silhouette' else (1000,4000) if mode=='structured' else (1000,100000)
    if type(value['triangle_budget']) is not int or not low<=value['triangle_budget']<=high:raise ValueError('Triangle budget outside mode bounds')
    if type(value['texture_size']) is not int or value['texture_size'] not in (512,1024,2048):raise ValueError('Unsupported atlas size')
    if type(value['ray_distance']) not in (int,float) or not .001<=value['ray_distance']<=.1:raise ValueError('Ray distance outside bounds')
    return dict(value)
