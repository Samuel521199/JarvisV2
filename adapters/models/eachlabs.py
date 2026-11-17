"""Bounded Eachlabs API and media transport; no redirects or model POST retries."""
import base64,ipaddress,json,math,re,socket,time,urllib.request
from urllib.parse import urlsplit

API='https://api.eachlabs.ai'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def trusted_media(url):
    uri=urlsplit(url)
    if uri.scheme!='https' or uri.username or uri.password or uri.port not in (None,443) or uri.fragment:
        raise ValueError('eachlabs_media_url')
    host=(uri.hostname or '').lower()
    if not any(host==suffix or host.endswith('.'+suffix) for suffix in (
            'eachlabs.ai','eachlabs.run','amazonaws.com','r2.cloudflarestorage.com','replicate.delivery','fal.media')):
        raise ValueError('eachlabs_media_host')
    if any(not ipaddress.ip_address(row[4][0]).is_global for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)):
        raise ValueError('eachlabs_media_address')
    return url


def fetch(url,*,method='GET',data=None,headers=None,limit=4*1024**2,timeout=20):
    request=urllib.request.Request(url,data=data,headers=headers or {},method=method)
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=timeout) as response:
        raw=response.read(limit+1);mime=response.headers.get_content_type()
        if len(raw)>limit:raise ValueError('eachlabs_reply_limit')
        return raw,mime


def api(path,key=None,body=None,*,method=None,timeout=20):
    if not isinstance(path,str) or not path.startswith('/v1/') or '..' in path or '#' in path:
        raise ValueError('eachlabs_path')
    headers={'Content-Type':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    raw,_=fetch(API+path,method=method or ('POST' if body is not None else 'GET'),
        data=json.dumps(body,allow_nan=False).encode() if body is not None else None,headers=headers,timeout=timeout)
    return json.loads(raw)


def slug(value):
    if not isinstance(value,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,100}',value):raise ValueError('eachlabs_model')
    return value


def upload(key,image):
    raw=base64.b64decode(image['data'],validate=True)
    info=api('/v1/upload/presign',key,{'content_type':image['mimeType'],'file_type':'image','expires_in_seconds':3600})
    url=trusted_media(info['presigned_url']);public=trusted_media(info['public_url'])
    headers=info.get('required_headers',{})
    if not isinstance(headers,dict) or any(k.lower()!='content-type' and not k.lower().startswith('x-amz-') for k in headers):
        raise ValueError('eachlabs_upload_headers')
    fetch(url,method='PUT',data=raw,headers=headers,limit=65536,timeout=30)
    return public


def image(config,credential,value,images,progress=lambda _:None,*,clock=time.monotonic,sleep=time.sleep):
    profile=config['image_profile'];key=credential['api_key'];owner=config.get('end_user_id')
    if not isinstance(owner,str) or not 1<=len(owner)<=240:raise ValueError('eachlabs_owner_required')
    params={**profile['defaults'],**profile['input_by_choice'][value['size']][value['aspect_ratio']],'prompt':value['prompt']}
    model=profile['model']
    if images:
        model=profile.get('edit_model')
        if not model:raise ValueError('eachlabs_edit_not_configured')
        params['image_urls']=[upload(key,im) for im in images]
    result=api('/v1/prediction',key,{'model':slug(model),'version':profile['edit_version'] if images else profile['version'],'input':params,'end_user_id':owner})
    ident=result.get('predictionID')
    if not isinstance(ident,str) or not re.fullmatch('[A-Za-z0-9_-]{1,120}',ident):raise ValueError('eachlabs_prediction_reply')
    progress({'prediction_id':ident,'status':'submitted','provider':'eachlabs'});deadline=clock()+240
    while clock()<deadline:
        result=api('/v1/prediction/'+ident,key,timeout=15);state=result.get('status')
        metrics={k:v for k,v in result.get('metrics',{}).items() if k in ('cost','predict_time') and type(v) in (int,float) and math.isfinite(v)}
        progress({'prediction_id':ident,'status':state,'metrics':metrics,'provider':'eachlabs'})
        if state=='success':break
        if state in {'failed','cancelled'}:
            cost=metrics.get('cost');usage={'provider_cost_usd':cost} if type(cost) in (int,float) and cost>=0 else {}
            return {'status':'REJECTED','code':'eachlabs_'+state,'prediction_id':ident,'usage':usage}
        sleep(2)
    else:return {'status':'UNKNOWN','code':'eachlabs_timeout','prediction_id':ident}
    output=result.get('output');urls=output if isinstance(output,list) else [output]
    if len(urls)!=1 or not isinstance(urls[0],str):raise ValueError('eachlabs_image_output')
    raw,mime=fetch(trusted_media(urls[0]),limit=64*1024**2,timeout=30)
    from adapters.models.image_transport import raster
    resolution=raster(raw,mime);usage={'output_images':1}
    cost=result.get('metrics',{}).get('cost')
    if type(cost) in (int,float) and math.isfinite(cost) and cost>=0:usage['provider_cost_usd']=cost
    return {'status':'SUCCEEDED','text':'','images':[{'mimeType':mime,'data':base64.b64encode(raw).decode(),'resolution':resolution}],
        'usage':usage,'prediction_id':ident}
