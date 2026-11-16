"""First-party 16 kHz log-mel/LFR frontend, derived from the public feature contract."""
import numpy as np


def fbank(samples):
    values=np.asarray(samples,dtype=np.float32)
    if values.ndim!=1 or len(values)<400 or not np.isfinite(values).all():raise ValueError('audio_samples')
    count=1+(len(values)-400)//160
    frames=np.lib.stride_tricks.sliding_window_view(values,400)[::160][:count].copy()
    frames-=frames.mean(axis=1,keepdims=True)
    previous=np.concatenate((frames[:,:1],frames[:,:-1]),axis=1)
    frames=(frames-.97*previous)*np.hamming(400).astype(np.float32)
    power=np.abs(np.fft.rfft(frames,n=512,axis=1))**2
    mel=lambda hz:1127*np.log1p(hz/700)
    points=np.linspace(mel(20),mel(8000),82)
    bins=mel(np.arange(257)*16000/512)
    up=(bins[None,:]-points[:-2,None])/(points[1:-1,None]-points[:-2,None])
    down=(points[2:,None]-bins[None,:])/(points[2:,None]-points[1:-1,None])
    filters=np.maximum(0,np.minimum(up,down))
    return np.log(np.maximum(power@filters.T,np.finfo(np.float32).eps)).astype(np.float32)


def features(samples,metadata):
    samples=np.asarray(samples,dtype=np.float32)
    if metadata.get('normalize_samples','0')=='0':samples=samples*32768
    frames=fbank(samples)
    width=int(metadata['lfr_window_size']);shift=int(metadata['lfr_window_shift'])
    if width!=7 or shift!=6:raise ValueError('unsupported_frontend')
    positions=np.arange((len(frames)+shift-1)//shift)[:,None]*shift+np.arange(width)[None,:]-(width-1)//2
    result=frames[np.clip(positions,0,len(frames)-1)].reshape(-1,width*80)
    if 'neg_mean' in metadata:
        mean=np.fromstring(metadata['neg_mean'],sep=',',dtype=np.float32)
        scale=np.fromstring(metadata['inv_stddev'],sep=',',dtype=np.float32)
        if mean.shape!=(560,) or scale.shape!=(560,):raise ValueError('cmvn_shape')
        result=(result+mean)*scale
    return result.astype(np.float32)
