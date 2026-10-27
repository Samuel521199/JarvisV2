"""Separate binary image port; ordinary chat retains its small text envelope."""
import json,os,subprocess,sys,time,threading
from adapters.models.vision import encode_png,validate_encoded
from adapters.models.image_transport import MAX_REPLY
from modules.image_generation.catalog import validate
from sdk.protocol import PROJECT,canonical
TIMEOUT_SECONDS=270

class ImageModel:
    def __init__(self,config,credential_loader):
        self.config=config;self.credential_loader=credential_loader
    def generate(self,value,reference_pngs=None,checkpoint=lambda:None):
        validate(value);images=validate_encoded([encode_png(x) for x in (reference_pngs or [])]);checkpoint()
        credential=self.credential_loader(self.config['id'],self.config.get('credential_id'))
        payload=canonical({'config':{'adapter':self.config['adapter']},'credential':credential,'request':value,'images':images}).encode()
        env={k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ}
        p=subprocess.Popen([sys.executable,'-I','-B',str(PROJECT/'adapters/models/image_transport.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+TIMEOUT_SECONDS
        expired=threading.Event()
        def terminate():
            expired.set()
            try:
                if p.poll() is None:p.kill()
            except OSError:pass
        watchdog=threading.Timer(TIMEOUT_SECONDS,terminate);watchdog.daemon=True;watchdog.start()
        try:
            while True:
                checkpoint()
                if time.monotonic()>deadline:return {'status':'UNKNOWN','code':'image_timeout'}
                try:
                    out,_=p.communicate(payload,timeout=.1)
                    if expired.is_set():return {'status':'UNKNOWN','code':'image_timeout'}
                    if p.returncode or len(out)>MAX_REPLY:return {'status':'UNKNOWN','code':'image_transport_limit'}
                    result=json.loads(out)
                    if not isinstance(result,dict) or result.get('status') not in {'SUCCEEDED','REJECTED','INVALID','UNKNOWN'}:return {'status':'UNKNOWN','code':'image_transport_reply'}
                    return result
                except subprocess.TimeoutExpired:payload=None
        finally:
            watchdog.cancel()
            if p.poll() is None:p.kill()
            p.communicate(timeout=5)
