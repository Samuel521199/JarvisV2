"""Reviewed image-only routes. Never used as default conversational models."""
from sdk.protocol import CoreError

VERSION='1.1.0'
CHECKED='2026-10-25'
MODELS={
 'gemini-nano-banana-2.1':{'name':'Nano Banana 2.1','role':'最新主线 · 推荐','released':'2026-10-06','sizes':['1K','2K','4K'],'status':'GA','source':'https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1'},
 'gemini-3.1-flash-lite-image':{'name':'Nano Banana 2 Lite','role':'按发布时间次新 · 轻量分支','released':'2026-06-30','sizes':['1K'],'status':'GA','source':'https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image'},
 'gemini-3.1-flash-image':{'name':'Nano Banana 2','role':'上一代主线 · 兼容比较','released':'2026-05-28','sizes':['512','1K','2K','4K'],'status':'deprecated_no_shutdown_announced','source':'https://ai.google.dev/gemini-api/docs/changelog'},
}
BASE_PIXELS={'1:1':[1024,1024],'2:3':[848,1264],'3:2':[1264,848],'3:4':[896,1200],'4:3':[1200,896],'4:5':[928,1152],'5:4':[1152,928],'9:16':[768,1376],'16:9':[1376,768],'21:9':[1584,672],'1:4':[512,2048],'4:1':[2048,512],'1:8':[384,3072],'8:1':[3072,384]}
RATIOS=list(BASE_PIXELS)

def dimensions(size,ratio):
    scale={'512':.5,'1K':1,'2K':2,'4K':4}[size]
    # Official half-resolution 3:4 rounds independently.
    if size=='512' and ratio in ('3:4','4:3'):return [448,600] if ratio=='3:4' else [600,448]
    return [int(n*scale) for n in BASE_PIXELS[ratio]]


def validate(value):
    if not isinstance(value,dict) or set(value)!={'model','prompt','size','aspect_ratio'}:
        raise CoreError('image_invalid','Expected explicit image request')
    if not isinstance(value['model'],str) or value['model'] not in MODELS:
        raise CoreError('image_invalid','Choose a reviewed Nano Banana model')
    if not isinstance(value['prompt'],str) or not 1<=len(value['prompt'].strip())<=8000:
        raise CoreError('image_invalid','Image prompt must contain 1..8000 characters')
    if not isinstance(value['size'],str) or not isinstance(value['aspect_ratio'],str):raise CoreError('image_invalid','Expected size and ratio strings')
    if value['size'] not in MODELS[value['model']]['sizes'] or value['aspect_ratio'] not in RATIOS:
        raise CoreError('image_invalid','Unsupported size or aspect ratio')
    return dict(value)
