"""Offline JSON-lines worker. No Hub loader, pickle, shell or remote model code."""
import json
import os
import sys
import time
from pathlib import Path


def memory():
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ('peak','rss','peak_pool','pool','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
        c=Counters();c.cb=ctypes.sizeof(c)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):return {'rss_bytes':c.rss,'peak_rss_bytes':c.peak,'gpu_bytes':0,'sampled_at':time.time()}
    return {'rss_bytes':None,'peak_rss_bytes':None,'gpu_bytes':0,'sampled_at':time.time()}


def send(value):print(json.dumps(value,ensure_ascii=False,allow_nan=False),flush=True)


def main():
    sys.stdin.reconfigure(encoding='utf-8',errors='strict')
    sys.stdout.reconfigure(encoding='utf-8',errors='strict')
    # Python networking is unnecessary in a local file-only worker. Native-library
    # isolation still needs OS-level verification on each supported platform.
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('offline_worker')
    sys.addaudithook(offline)
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    ort.disable_telemetry_events()
    root=Path(sys.argv[1]);options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(root/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'));tokenizer.enable_padding()
    send({'ready':True,'dimension':384,'runtime':{'onnxruntime':ort.__version__,'numpy':np.__version__},'memory':memory()})
    for line in sys.stdin:
        ident=None
        try:
            body=json.loads(line);texts=body['texts'];role=body['role'];ident=body.get('id')
            if role not in ('query','passage') or not isinstance(texts,list) or not 1<=len(texts)<=8 or any(not isinstance(x,str) or not x.strip() or len(x)>8000 for x in texts):raise ValueError('input')
            start=time.monotonic();encoded=tokenizer.encode_batch([role+': '+x for x in texts])
            if any(len(e.ids)>512 for e in encoded):raise ValueError('split_long_input')
            arrays={'input_ids':np.array([e.ids for e in encoded],dtype=np.int64),'attention_mask':np.array([e.attention_mask for e in encoded],dtype=np.int64),'token_type_ids':np.array([e.type_ids for e in encoded],dtype=np.int64)}
            output=session.run(None,{i.name:arrays[i.name] for i in session.get_inputs()})[0]
            mask=arrays['attention_mask'][...,None];vectors=(output*mask).sum(axis=1)/mask.sum(axis=1)
            vectors=vectors/np.linalg.norm(vectors,axis=1,keepdims=True)
            send({'id':ident,'vectors':vectors.tolist(),'dimension':384,'elapsed_seconds':time.monotonic()-start,'memory':memory(),
                  'workload':{'batch':len(texts),'max_tokens':max(sum(e.attention_mask) for e in encoded)}})
        except Exception as exc:send({'id':ident,'error':str(exc)[:120]})


if __name__=='__main__':main()
