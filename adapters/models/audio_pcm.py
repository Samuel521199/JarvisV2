"""Shared bounded PCM interchange. No microphone, inference or network authority."""
import hashlib,io,wave


def inspect_pcm(raw):
    if not isinstance(raw,bytes) or not 100<=len(raw)<=1920100:raise ValueError('audio_limit')
    try:
        with wave.open(io.BytesIO(raw),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getcomptype())!=(1,2,16000,'NONE'):raise ValueError('audio_format')
            frames=audio.getnframes();data=audio.readframes(frames)
            if not 1600<=frames<=960000 or len(data)!=frames*2:raise ValueError('audio_length')
    except (EOFError,wave.Error):raise ValueError('audio_format') from None
    return {'sha256':hashlib.sha256(raw).hexdigest(),'seconds':frames/16000,'bytes':len(raw),'format':'pcm16-mono-16000'}
