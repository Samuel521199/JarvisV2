"""Bounded local PCM recordings. Audio is not sent to the text model."""
import base64,hashlib,io,re,uuid,wave
from control.paths import child
from control.atomic import write_json
from sdk.protocol import CoreError,read_json

def inspect(raw):
    if not isinstance(raw,bytes) or not 100<=len(raw)<=1920100:raise CoreError('english_audio','Use 0.1–60 seconds mono 16kHz PCM WAV')
    try:
        with wave.open(io.BytesIO(raw),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getcomptype())!=(1,2,16000,'NONE'):raise ValueError()
            frames=audio.getnframes();data=audio.readframes(frames)
            if not 1600<=frames<=960000 or len(data)!=frames*2:raise ValueError()
    except (ValueError,EOFError,wave.Error):raise CoreError('english_audio','Invalid or truncated PCM WAV') from None
    return {'sha256':hashlib.sha256(raw).hexdigest(),'seconds':frames/16000,'bytes':len(raw),'format':'pcm16-mono-16000','recognition':'user_confirmed_transcript','pronunciation_score':None}

def save(root,encoded):
    if not isinstance(encoded,str) or len(encoded)>2560200:raise CoreError('english_audio','Audio exceeds bounded upload')
    try:raw=base64.b64decode(encoded,validate=True)
    except ValueError:raise CoreError('english_audio','Invalid audio encoding') from None
    meta=inspect(raw);ident='audio-'+uuid.uuid4().hex
    folder=child(root,'state/english-audio');folder.mkdir(exist_ok=True)
    (folder/(ident+'.wav')).write_bytes(raw);write_json(folder/(ident+'.json'),meta)
    return {'id':ident,**meta}

def read(root,ident):
    if not isinstance(ident,str) or not re.fullmatch('audio-[a-f0-9]{32}',ident):raise CoreError('english_audio','Unknown recording')
    folder=child(root,'state/english-audio');raw=(folder/(ident+'.wav')).read_bytes();meta=read_json(folder/(ident+'.json'))
    if inspect(raw)!=meta:raise CoreError('english_audio','Recording integrity changed')
    return raw,{'id':ident,**meta}
