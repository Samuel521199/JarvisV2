"""Stable cached-content identity, separate from mutable labels/classification."""
from sdk.protocol import digest

def fingerprint(message):
    return digest({key:message.get(key,'') for key in ('id','thread_id','from','subject','date','snippet','body')})
