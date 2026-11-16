"""File-only CPU STT worker; JSON lines, no Hub loaders or user supplied code."""
import base64,hashlib,importlib.util,io,json,os,re,sys,time,wave
from pathlib import Path


def memory():
    import ctypes as c
    from ctypes import wintypes as w
    class Counters(c.Structure):
        _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,c.c_size_t) for n in ('peak','rss','peak_pool','pool','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    value=Counters();value.cb=c.sizeof(value)
    kernel=c.WinDLL('kernel32');kernel.GetCurrentProcess.restype=w.HANDLE
    api=c.WinDLL('psapi').GetProcessMemoryInfo;api.argtypes=[w.HANDLE,c.c_void_p,w.DWORD]
    if not api(kernel.GetCurrentProcess(),c.byref(value),value.cb):return {'gpu_bytes':0}
    return {'rss_bytes':value.rss,'peak_rss_bytes':value.peak,'private_bytes':value.private,'gpu_bytes':0}


def send(value):print(json.dumps(value,ensure_ascii=False,allow_nan=False),flush=True)


def main():
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('offline_worker')
    sys.addaudithook(offline)
    import socket
    blocked=False
    try:socket.getaddrinfo('offline-probe.invalid',443)
    except RuntimeError as exc:blocked=str(exc)=='offline_worker'
    if not blocked:raise RuntimeError('offline_guard_failed')
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    spec=importlib.util.spec_from_file_location('speech_features',Path(__file__).with_name('speech_features.py'))
    frontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)
    folder=Path(sys.argv[1]);options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    started=time.monotonic();session=ort.InferenceSession(str(folder/'model.int8.onnx'),options,providers=['CPUExecutionProvider'])
    meta=session.get_modelmeta().custom_metadata_map
    if meta.get('model_type')!='sense_voice_ctc':raise ValueError('model_contract')
    nano='blank_id' in meta;vocabulary={}
    for line in (folder/'tokens.txt').read_text(encoding='utf-8').splitlines():
        token,number=line.rsplit(' ',1)
        if nano:token=base64.b64decode(token,validate=True)
        vocabulary[int(number)]=token
    if len(vocabulary)!=int(meta['vocab_size']):raise ValueError('vocabulary_contract')
    send({'ready':True,'kind':'stt','load_seconds':time.monotonic()-started,'memory':memory(),'network':False,'python_network_guard_verified':True,'os_network_sandbox':False})
    while line:=sys.stdin.readline(2700001):
        ident=None
        try:
            if len(line)>2700000:raise ValueError('input_limit')
            value=json.loads(line);ident=value['id']
            if set(value)!={'id','audio','language'} or value['language'] not in ('auto','zh','en'):raise ValueError('request')
            raw=base64.b64decode(value['audio'],validate=True)
            if not 100<=len(raw)<=1920100:raise ValueError('audio_limit')
            with wave.open(io.BytesIO(raw),'rb') as audio:
                if (audio.getframerate(),audio.getsampwidth(),audio.getnchannels(),audio.getcomptype())!=(16000,2,1,'NONE'):raise ValueError('audio_format')
                samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(np.float32)/32768
            if not 1600<=len(samples)<=960000 or not np.isfinite(samples).all():raise ValueError('audio_length')
            begin=time.monotonic();centered=samples-samples.mean();rms=float(np.sqrt(np.mean(centered**2)))
            text='';flags=[];language=None
            if rms<.003:flags=['no_speech']
            else:
                x=frontend.features(samples,meta)[None,:,:];inputs={'x':x}
                if not nano:inputs.update(x_length=np.array([x.shape[1]],dtype=np.int32),language=np.array([int(meta['lang_'+value['language']])],dtype=np.int32),text_norm=np.array([int(meta['without_itn'])],dtype=np.int32))
                logits=session.run(None,inputs)[0];indices=np.argmax(logits[0],axis=-1);blank=int(meta.get('blank_id',0));tokens=[];previous=None
                for index in indices:
                    index=int(index)
                    if index!=previous and index!=blank:tokens.append(vocabulary[index])
                    previous=index
                if not nano:
                    language=tokens[0] if tokens else None;tokens=tokens[4:]
                text=b''.join(tokens).decode('utf-8') if nano else ''.join(tokens)
                text=re.sub(r'<[^>]+>','',text).replace('▁',' ').strip()
                if not text:flags.append('empty_transcript')
                if np.mean(np.abs(samples)>.999)>.02:flags.append('clipped_audio')
                if len(text)>3000:raise ValueError('output_limit')
            send({'id':ident,'text':text,'language':language,'flags':flags,'audio_sha256':hashlib.sha256(raw).hexdigest(),'seconds':len(samples)/16000,'inference_seconds':time.monotonic()-begin,'memory':memory(),'network':False,'confidence':None,'pronunciation_score':None})
        except Exception as exc:send({'id':ident,'error':str(exc)[:120] if isinstance(exc,ValueError) else type(exc).__name__})


if __name__=='__main__':main()
