"""Resumable, bounded HTTPS downloads; data only, never run repository code."""
import hashlib
import re
import urllib.request
from urllib.parse import urlsplit
from sdk.protocol import CoreError
from control.paths import reject_links


def allowed(url):
    u=urlsplit(url)
    return u.scheme=='https' and not u.username and not u.password and u.port in (None,443) and (u.hostname=='huggingface.co' or (u.hostname or '').endswith('.huggingface.co') or (u.hostname or '').endswith('.hf.co'))


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        if not allowed(url):raise CoreError('model_source','Unapproved download redirect')
        return super().redirect_request(req,fp,code,msg,headers,url)


def valid(path, artifact, check=lambda:None):
    if not path.is_file() or path.stat().st_size!=artifact['bytes']:return False
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):check();h.update(chunk)
    return h.hexdigest()==artifact['sha256']


def fetch(url, path, artifact, check, progress):
    if not allowed(url):raise CoreError('model_source','HTTPS source required')
    path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_suffix(path.suffix+'.part');reject_links(part);offset=part.stat().st_size if part.exists() else 0
    if offset>=artifact['bytes']:
        if valid(part,artifact,check):part.replace(path);return
        part.unlink();offset=0
    headers={'User-Agent':'Jarvis-local-models/1','Accept-Encoding':'identity'}
    if offset:headers['Range']=f'bytes={offset}-'
    check()
    with urllib.request.build_opener(Redirect()).open(urllib.request.Request(url,headers=headers),timeout=15) as response:
        if response.status==206:
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
            if not match or int(match[1])!=offset or int(match[3])!=artifact['bytes']:raise CoreError('model_range','Invalid resumed response')
        elif response.status==200:offset=0
        else:raise CoreError('model_download','Unexpected response')
        with part.open('ab' if offset else 'wb') as stream:
            while chunk:=response.read(256*1024):
                check();offset+=len(chunk)
                if offset>artifact['bytes']:raise CoreError('model_size','Download exceeds declared size')
                stream.write(chunk);progress(offset)
    if not valid(part,artifact,check):
        part.unlink(missing_ok=True)
        raise CoreError('model_digest','Artifact verification failed')
    part.replace(path)
