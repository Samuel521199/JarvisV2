"""Explicit, bounded read unions. A union is never a writable memory domain."""
import re
from sdk.protocol import CoreError


def members(scope):
    if not isinstance(scope,str) or not scope.startswith('joint:'):return None
    values=scope[6:].split(',')
    if not 2<=len(values)<=4 or len(set(values))!=len(values) or any(not re.fullmatch('[A-Za-z0-9_.-]{1,100}',s) for s in values):
        raise CoreError('memory_invalid','Select two to four distinct explicit scopes')
    return values


def create(scopes):
    if not isinstance(scopes,list) or any(not isinstance(s,str) for s in scopes):raise CoreError('memory_invalid','Expected explicit scopes')
    value='joint:'+','.join(sorted(scopes));members(value);return value


def writable(scope):
    if members(scope):raise CoreError('memory_read_only','Choose one concrete scope before editing or saving a memory')
