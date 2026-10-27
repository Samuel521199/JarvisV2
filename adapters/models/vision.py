"""Up to two explicit PNGs within one shared budget; no paths or URL fetches."""
import base64,struct
from sdk.protocol import CoreError

def encode_png(raw):
    if not isinstance(raw,bytes) or not 33<=len(raw)<=12*1024**2 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':
        raise CoreError('model_image_invalid','Expected one bounded PNG')
    w,h=struct.unpack_from('>II',raw,16)
    if not 1<=w<=8192 or not 1<=h<=8192 or w*h>16000000:raise CoreError('model_image_invalid','Image pixel budget exceeded')
    return {'mimeType':'image/png','data':base64.b64encode(raw).decode('ascii')}

def validate_encoded(images):
    if not isinstance(images,list) or len(images)>2:raise CoreError('model_image_invalid','At most two explicit PNGs')
    total=0;pixels=0
    for im in images:
        if not isinstance(im,dict) or set(im)!={'mimeType','data'} or im['mimeType']!='image/png' or not isinstance(im['data'],str) or len(im['data'])>16*1024**2:raise CoreError('model_image_invalid','Invalid image envelope')
        try:raw=base64.b64decode(im['data'],validate=True)
        except ValueError:raise CoreError('model_image_invalid','Invalid image encoding') from None
        encode_png(raw)
        total+=len(raw);w,h=struct.unpack_from('>II',raw,16);pixels+=w*h
    if total>12*1024**2 or pixels>16000000:raise CoreError('model_image_invalid','Combined image budget exceeded')
    return images
