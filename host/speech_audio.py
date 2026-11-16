"""Shared microphone audio store; unrelated to English software or model weights."""
import base64,re
from control.paths import child
from control.atomic import write_json
from adapters.models.audio_pcm import inspect_pcm
from sdk.protocol import CoreError,read_json


def read(root,ident):
    if not isinstance(ident,str) or not re.fullmatch(r'audio-[a-f0-9]{32}',ident):raise CoreError('speech_audio','Invalid recording ID')
    folder=child(root,'state/speech-audio');raw=(folder/(ident+'.wav')).read_bytes();meta=read_json(folder/(ident+'.json'))
    try:actual=inspect_pcm(raw)
    except ValueError:raise CoreError('speech_audio','Recording is damaged') from None
    if actual!={k:meta.get(k) for k in actual}:raise CoreError('speech_audio','Recording digest changed')
    return raw,{'id':ident,**meta}


def save(root,ident,encoded,context):
    if not isinstance(ident,str) or not re.fullmatch(r'audio-[a-f0-9]{32}',ident) or not isinstance(encoded,str) or len(encoded)>2560200:raise CoreError('speech_audio','Invalid bounded recording')
    try:raw=base64.b64decode(encoded,validate=True);meta={**inspect_pcm(raw),'context':context}
    except ValueError:raise CoreError('speech_audio','Use 0.1–60 seconds mono 16kHz PCM WAV') from None
    folder=child(root,'state/speech-audio');folder.mkdir(exist_ok=True);path=folder/(ident+'.wav');description=folder/(ident+'.json')
    if path.exists():
        if path.read_bytes()!=raw:raise CoreError('conflict','Recording ID reused')
        if description.exists():
            if read_json(description)!=meta:raise CoreError('conflict','Recording context changed')
            return {'id':ident,**meta}
    else:
        with path.open('xb') as stream:stream.write(raw)
    write_json(description,meta)
    return {'id':ident,**meta}
