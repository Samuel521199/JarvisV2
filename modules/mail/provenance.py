"""Stable cached-content identity, separate from mutable labels/classification."""
from sdk.protocol import digest

def fingerprint(message):
    return digest({key:message.get(key,'') for key in ('id','thread_id','from','subject','date','snippet','body')})


def merge_metadata(message,previous):
    """A metadata refresh must not silently remove an unchanged cached body."""
    keys=('id','thread_id','from','subject','date','snippet')
    if ('body' not in message and 'body' in previous
            and all(message.get(k,'')==previous.get(k,'') for k in keys)):
        return {**message,'body':previous['body']}
    return message
