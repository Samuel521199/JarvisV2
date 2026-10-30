"""Preserve unchanged geometry across recipe upgrades and local art edits."""
import copy
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.production_loop import digest

VERSION='1.1.0'


def merge(source,source_semantics,candidate,candidate_semantics,actions):
    if not actions:raise ValueError('A local update requires declared actions')
    groups=set();material=False;render=False
    for action in actions:
        group=action['group'];name=action['parameter']
        if group=='finish':material=True;render|=name=='finish_detail'
        elif group=='lighting':render=True
        elif group=='wheels':groups.update(('wheel-left','wheel-right'))
        elif group=='trails':groups.update(('trail-left','trail-right'))
        elif group in ('shield','barrel','cradle','breech','controls'):groups.add(group)
        else:raise ValueError('Unknown mutation group')
        if name=='track':groups.add('carriage')
        if name=='assembly_detail':groups.add('carriage')
        if name=='barrel_height':groups.update(('barrel','cradle','breech','controls'))
    old=source_semantics['groups'];new=candidate_semantics['groups']
    if set(old)!={o['id'] for o in source['objects']} or set(new)!={o['id'] for o in candidate['objects']}:raise ValueError('Incomplete semantic inventory')
    retained=[copy.deepcopy(o) for o in source['objects'] if old[o['id']] not in groups]
    replacement=[copy.deepcopy(o) for o in candidate['objects'] if new[o['id']] in groups]
    result=copy.deepcopy(source);result['objects']=retained+replacement
    if material:result['materials']=copy.deepcopy(candidate['materials'])
    if render:result['render']=copy.deepcopy(candidate['render'])
    result=validate(result)
    sem=copy.deepcopy(candidate_semantics)
    sem['groups']={o['id']:old[o['id']] for o in retained}|{o['id']:new[o['id']] for o in replacement}
    sem['motion_owners']={o['id']:source_semantics['motion_owners'][o['id']] for o in retained}|{o['id']:candidate_semantics['motion_owners'][o['id']] for o in replacement}
    before={o['id']:digest(o) for o in source['objects']};after={o['id']:digest(o) for o in result['objects']}
    for o in retained:
        if before[o['id']]!=after[o['id']]:raise ValueError('Undeclared geometry mutation')
    receipt={'version':VERSION,'source_scene_sha256':digest(source),'result_scene_sha256':digest(result),'declared_groups':sorted(groups),
             'changed_objects':sorted(n for n in before.keys()&after.keys() if before[n]!=after[n]),'added_objects':sorted(after.keys()-before.keys()),
             'removed_objects':sorted(before.keys()-after.keys()),'unchanged_objects':sorted(n for n in before.keys()&after.keys() if before[n]==after[n]),
             'materials_changed':material and source['materials']!=result['materials'],'render_changed':render and source['render']!=result['render'],
             'scope':'Scene-data identity; shared lighting/shadows can still affect unchanged surfaces in the actual render'}
    sem['mutation_receipt']=receipt
    return result,sem
