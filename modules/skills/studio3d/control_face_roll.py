"""Bound one exterior case front roll; no functional mechanism or dimensional claim."""
import math
from modules.skills.studio3d.render_inspection import validate as inspection_validate

SCHEMA = 'jarvis.studio3d.control-face-roll.v1'
NAMES = {'control-seated-castings', 'connected-control-housing', 'control-seated-trim',
         'handwheel-left', 'fasteners-controls', 'rear-cover-mounts', 'sight-mounted'}

def front_stations(width):
    if type(width) not in (int, float) or not math.isfinite(width) or not .010 <= width <= .012:
        raise ValueError('Front roll must remain within the demonstrated visual range')
    return [(width*(1-math.cos(math.pi*j/32)), width*(1-math.sin(math.pi*j/32))) for j in range(16)]

def validate(c, names):
    fields = {'schema', 'author', 'evidence', 'source_sha256', 'dependencies', 'component_vertices', 'width', 'inspection'}
    if not isinstance(c, dict) or set(c) != fields or c['schema'] != SCHEMA:
        raise ValueError('Unexpected exterior case contract')
    sha = lambda x: isinstance(x, str) and len(x) == 64 and all(v in '0123456789abcdef' for v in x)
    if c['author'] not in ('Codex', 'Jarvis') or not isinstance(c['evidence'], str) or not 1 <= len(c['evidence']) <= 1600:
        raise ValueError('Explicit author and actual evidence required')
    if not sha(c['source_sha256']) or not isinstance(c['dependencies'], dict) or set(c['dependencies']) != NAMES or not all(sha(x) for x in c['dependencies'].values()):
        raise ValueError('Exact original source and seven complete local dependencies required')
    ids = c['component_vertices']
    if not isinstance(ids, list) or len(ids) != 152 or ids != sorted(set(ids)) or any(type(i) != int or not 0 <= i < 2296 for i in ids):
        raise ValueError('Complete original evaluated lower-case component required')
    if not NAMES <= set(names):
        raise ValueError('Bound original semantic inventory required')
    front_stations(c['width'])
    inspection_validate(c['inspection'], names)
    v = c['inspection']
    if v.get('focus_region') != 'controlcase' or v['regions'] != {'controlcase':['control-seated-castings','connected-control-housing','handwheel-left']} or v['bounds'] != [[-.8,.16,.62],[-.20,.65,1.35]] or v['resolution'] != [960,640] or v['samples'] != 12 or len(v['views']) != 2:
        raise ValueError('Fixed local paired evidence frame required')
    return c
