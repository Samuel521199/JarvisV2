"""Deliberately small, bounded MCP input vocabulary, not general JSON Schema.

Unspecified object fields are narrowed to declared properties; unsupported
constraints reject the tool instead of silently ignoring them. No regex/ref.
"""
from sdk.protocol import CoreError, canonical, validate


def normalize(schema, depth=0):
    allowed = {'type', 'title', 'description', '$schema', 'properties', 'required', 'additionalProperties',
               'items', 'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum', 'enum', 'const'}
    if not isinstance(schema, dict) or set(schema) - allowed or depth > 8 or len(canonical(schema).encode()) > 8192:
        raise CoreError('mcp_schema', 'Unsupported or oversized tool input schema')
    out = dict(schema); kind = out.get('type')
    if kind not in {'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'}:
        raise CoreError('mcp_schema', 'Explicit simple type required')
    for k in ('minItems', 'maxItems', 'minLength', 'maxLength'):
        if k in out and (type(out[k]) is not int or out[k] < 0): raise CoreError('mcp_schema', 'Invalid limit')
    for k in ('minimum', 'maximum'):
        if k in out and (type(out[k]) not in {int, float}): raise CoreError('mcp_schema', 'Invalid numeric bound')
    if 'enum' in out and (not isinstance(out['enum'], list) or not 1 <= len(out['enum']) <= 64):
        raise CoreError('mcp_schema', 'Invalid enum')
    if kind == 'object':
        props = out.get('properties', {}); required = out.get('required', [])
        if (not isinstance(props, dict) or len(props) > 32 or not isinstance(required, list)
                or any(not isinstance(x, str) or x not in props for x in required)
                or out.get('additionalProperties', False) is not False):
            raise CoreError('mcp_schema', 'Object must have declared bounded fields')
        out.update(properties={k: normalize(v, depth+1) for k, v in props.items()}, additionalProperties=False)
    if kind == 'array':
        out['items'] = normalize(out.get('items'), depth+1)
        out['maxItems'] = min(out.get('maxItems', 64), 64)
    if kind == 'string': out['maxLength'] = min(out.get('maxLength', 8000), 8000)
    return out


def arguments(schema, value):
    if not isinstance(value, dict) or len(canonical(value).encode()) > 12000:
        raise CoreError('mcp_arguments', 'Arguments must be a bounded object')
    try: validate(normalize(schema), value)
    except CoreError as exc: raise CoreError('mcp_arguments', 'Arguments do not match the admitted input schema') from exc
    return value
