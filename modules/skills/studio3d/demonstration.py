"""Bounded first-party demonstration contract; no model-authored code."""
import copy
import math
import re

VERSION = '1.1.0'
SCHEMA = 'jarvis.studio3d.demonstration.v1'


def _vector(value):
    if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 100 for x in value):
        raise ValueError('Expected a finite bounded vector')
    return value


def validate(raw, names):
    if not isinstance(raw, dict) or set(raw) != {'schema', 'author', 'goal', 'evidence', 'actions', 'views', 'resolution', 'samples'}:
        raise ValueError('Invalid demonstration fields')
    c = copy.deepcopy(raw)
    if c['schema'] != SCHEMA or c['author'] not in ('Codex', 'Jarvis'):
        raise ValueError('Declare demonstration schema and actual author')
    for key in ('goal', 'evidence'):
        if not isinstance(c[key], str) or not 1 <= len(c[key]) <= 1600:
            raise ValueError('Declare bounded goal and evidence')
    if not isinstance(c['actions'], list) or not 1 <= len(c['actions']) <= 2:
        raise ValueError('Use one or two bounded local actions')
    targets = set()
    for a in c['actions']:
        fields={'tool', 'target', 'center', 'axis', 'radial_u', 'inner', 'outer', 'amplitude', 'lobes', 'phase', 'reason'}
        if isinstance(a,dict) and a.get('tool')=='radial_reprofile':
            fields |= {'crown_fraction','shoulder_fraction','end_blend'}
        if not isinstance(a, dict) or set(a) != fields:
            raise ValueError('Invalid demonstration action')
        if a['tool'] not in ('radial_relief','radial_reprofile') or a['target'] not in names or a['target'] in targets:
            raise ValueError('Unknown tool, target or duplicate target')
        targets.add(a['target'])
        for key in ('center', 'axis', 'radial_u'):
            _vector(a[key])
        for key in ('axis', 'radial_u'):
            if abs(sum(x*x for x in a[key]) - 1) > 1e-6:
                raise ValueError('Direction must be normalized')
        if abs(sum(x*y for x, y in zip(a['axis'], a['radial_u']))) > 1e-6:
            raise ValueError('Local frame must be orthogonal')
        for key in ('inner', 'outer', 'amplitude', 'phase'):
            if type(a[key]) not in (int, float) or not math.isfinite(a[key]):
                raise ValueError('Invalid numeric parameter')
        if not 0 < a['inner'] < a['outer'] <= 5 or not 0 < a['amplitude'] <= min(.06, .15*(a['outer']-a['inner'])) or abs(a['phase']) > math.tau:
            raise ValueError('Relief exceeds local displacement bounds')
        if type(a['lobes']) is not int or not 3 <= a['lobes'] <= 16 or not isinstance(a['reason'], str) or not 1 <= len(a['reason']) <= 800:
            raise ValueError('Invalid lobes or reason')
        if a['tool']=='radial_reprofile':
            for key in ('crown_fraction','shoulder_fraction','end_blend'):
                if type(a[key]) not in (int,float) or not math.isfinite(a[key]):raise ValueError('Invalid profile parameter')
            if not .05<=a['crown_fraction']<=.35 or not .10<=a['shoulder_fraction']<=.45 or a['crown_fraction']+a['shoulder_fraction']>.75:
                raise ValueError('Profile must leave a separated valley')
            if not .03*(a['outer']-a['inner'])<=a['end_blend']<=.45*(a['outer']-a['inner']):raise ValueError('Invalid end blend')
    if not isinstance(c['views'], list) or not 1 <= len(c['views']) <= 3:
        raise ValueError('Declare one to three actual views')
    seen = set()
    for view in c['views']:
        if not isinstance(view, dict) or set(view) != {'id', 'center', 'direction', 'ortho_scale'}:
            raise ValueError('Invalid camera view')
        if not isinstance(view['id'], str) or not re.fullmatch('[a-z][a-z0-9-]{0,40}', view['id']) or view['id'] in seen:
            raise ValueError('Unsafe or duplicate view identity')
        seen.add(view['id']); _vector(view['center']); _vector(view['direction'])
        if sum(x*x for x in view['direction']) < .01 or type(view['ortho_scale']) not in (int,float) or not math.isfinite(view['ortho_scale']) or not .1 <= view['ortho_scale'] <= 20:
            raise ValueError('Invalid camera extent')
    if not isinstance(c['resolution'], list) or len(c['resolution']) != 2 or any(type(v) is not int or not 256 <= v <= 1536 for v in c['resolution']):
        raise ValueError('Invalid actual render resolution')
    if type(c['samples']) is not int or not 8 <= c['samples'] <= 48:
        raise ValueError('Invalid render sample budget')
    return c


def displacement(point, action):
    """Local radial relief, zero outside its annulus; two faces stay separated."""
    p = [x-y for x,y in zip(point, action['center'])]
    axis, u = action['axis'], action['radial_u']
    v = [axis[1]*u[2]-axis[2]*u[1], axis[2]*u[0]-axis[0]*u[2], axis[0]*u[1]-axis[1]*u[0]]
    z = sum(x*y for x,y in zip(p, axis))
    x = sum(a*b for a,b in zip(p,u)); y = sum(a*b for a,b in zip(p,v))
    radius = math.hypot(x,y)
    if not action['inner'] < radius < action['outer'] or abs(z) < 1e-6:
        return [0.,0.,0.]
    t = (radius-action['inner'])/(action['outer']-action['inner'])
    envelope = math.sin(math.pi*t)**.8
    wave = max(0., math.cos(action['lobes']*(math.atan2(y,x)-action['phase'])))**1.1
    amount = math.copysign(action['amplitude']*envelope*wave,z)
    return [a*amount for a in axis]
