"""Single Google image request. Fixed official endpoints; no redirects or retries."""
import base64,json,socket,ssl,struct,sys,urllib.error,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.models.native_transport import post,vertex_token
from adapters.models.vision import validate_encoded
from modules.image_generation.catalog import validate

MAX_REPLY=96*1024**2

def raster(raw,mime):
    if not isinstance(raw,bytes) or not 32<=len(raw)<=64*1024**2:raise ValueError('image_bytes')
    if mime=='image/png':
        if raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':raise ValueError('image_png')
        width,height=struct.unpack_from('>II',raw,16);pos=8;ended=False;pixels=False
        while pos+12<=len(raw):
            n=int.from_bytes(raw[pos:pos+4],'big');kind=raw[pos+4:pos+8]
            if n>64*1024**2 or pos+12+n>len(raw):raise ValueError('png_chunk')
            if zlib.crc32(raw[pos+4:pos+8+n])&0xffffffff!=int.from_bytes(raw[pos+8+n:pos+12+n],'big'):raise ValueError('png_crc')
            pixels|=kind==b'IDAT';pos+=n+12
            if kind==b'IEND':ended=True;break
        if not ended or not pixels or pos!=len(raw):raise ValueError('png_incomplete')
    elif mime=='image/jpeg':
        if raw[:2]!=b'\xff\xd8' or raw[-2:]!=b'\xff\xd9':raise ValueError('image_jpeg')
        width=height=0;pos=2
        while pos+9<len(raw) and raw[pos]==255:
            marker=raw[pos+1];n=int.from_bytes(raw[pos+2:pos+4],'big')
            if marker in (0xc0,0xc1,0xc2):height,width=struct.unpack_from('>HH',raw,pos+5);break
            if n<2:break
            pos+=n+2
    else:raise ValueError('image_mime')
    if not 1<=width<=12288 or not 1<=height<=12288 or width*height>20000000:raise ValueError('image_pixels')
    return [width,height]

def request(config,credential,value,images):
    v=validate(value);images=validate_encoded(images);adapter=config['adapter']
    if adapter=='vertex':
        token,project=vertex_token(credential['service_account'])
        url=f'https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{v["model"]}:generateContent'
        headers={'Authorization':'Bearer '+token}
    elif adapter=='gemini':
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{v["model"]}:generateContent'
        headers={'x-goog-api-key':credential['api_key']}
    else:raise ValueError('image_route')
    # Image routes intentionally do not inherit text thinking/JSON/sampling parameters.
    generation={'responseModalities':['TEXT','IMAGE'],'imageConfig':{'aspectRatio':v['aspect_ratio'],'imageSize':v['size']},'candidateCount':1,'maxOutputTokens':4096 if 'lite-image' in v['model'] else 8192}
    parts=[{'text':v['prompt']}]+[{'inlineData':i} for i in images]
    return url,headers,{'contents':[{'role':'user','parts':parts}],'generationConfig':generation}

def extract(data):
    metadata=data.get('usageMetadata',{});usage={}
    for old,new in [('promptTokenCount','prompt_tokens'),('candidatesTokenCount','completion_tokens'),('totalTokenCount','total_tokens'),('thoughtsTokenCount','reasoning_tokens'),('cachedContentTokenCount','cache_read_tokens')]:
        if type(metadata.get(old)) is int and metadata[old]>=0:usage[new]=metadata[old]
    usage['reasoning_in_completion']=False
    details=metadata.get('candidatesTokensDetails',[])
    for kind,name in [('IMAGE','output_image_tokens'),('TEXT','output_text_tokens')]:
        counts=[d['tokenCount'] for d in details if isinstance(d,dict) and d.get('modality')==kind and type(d.get('tokenCount')) is int and d['tokenCount']>=0]
        if counts:usage[name]=sum(counts)
    candidates=data.get('candidates',[])
    if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':return {'status':'INVALID','code':'image_blocked_or_incomplete','usage':usage}
    parts=candidates[0].get('content',{}).get('parts',[]);images=[];texts=[]
    for p in parts:
        if p.get('thought'):continue
        if p.get('functionCall') or p.get('fileData'):return {'status':'INVALID','code':'image_unexpected_part','usage':usage}
        if isinstance(p.get('text'),str):texts.append(p['text'])
        if 'inlineData' in p:
            im=p['inlineData']
            try:
                raw=base64.b64decode(im['data'],validate=True);size=raster(raw,im['mimeType'])
                images.append({'mimeType':im['mimeType'],'data':im['data'],'resolution':size})
            except (ValueError,KeyError,TypeError):return {'status':'INVALID','code':'image_invalid_binary','usage':usage}
    if len(images)!=1:return {'status':'INVALID','code':'image_missing_or_multiple','usage':usage}
    usage['output_images']=1
    return {'status':'SUCCEEDED','text':'\n'.join(texts)[:16000],'images':images,'usage':usage}

def run():
    raw=sys.stdin.buffer.read(17*1024**2+1)
    if len(raw)>17*1024**2:return {'status':'REJECTED','code':'image_input_limit'}
    p=json.loads(raw)
    try:url,headers,body=request(p['config'],p['credential'],p['request'],p.get('images',[]))
    except Exception:return {'status':'REJECTED','code':'image_config_or_auth'}
    try:return extract(post(url,body,headers,timeout=240,max_bytes=MAX_REPLY))
    except urllib.error.HTTPError as e:return {'status':'REJECTED' if 400<=e.code<500 else 'UNKNOWN','code':'http_'+str(e.code)}
    except (TimeoutError,socket.timeout):return {'status':'UNKNOWN','code':'image_timeout'}
    except urllib.error.URLError:return {'status':'UNKNOWN','code':'image_network'}
    except Exception:return {'status':'UNKNOWN','code':'image_transport'}

if __name__=='__main__':
    try:r=run()
    except Exception:r={'status':'UNKNOWN','code':'image_transport'}
    sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(r,ensure_ascii=False,allow_nan=False))
