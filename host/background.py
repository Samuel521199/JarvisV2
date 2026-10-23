"""One shared bounded model-work lane; foreground chat keeps its own slots."""
from concurrent.futures import ThreadPoolExecutor
import threading
from sdk.protocol import CoreError


class BackgroundLane:
    def __init__(self):
        self.lock=threading.Lock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='jarvis-background-model')
        self.future=None;self.active=None;self.kind=None;self.closed=False

    def submit(self, kind, ident, fn, *args):
        with self.lock:
            if self.closed or self.future is not None and not self.future.done():raise CoreError('development_busy','Background model lane is occupied')
            self.kind=kind;self.active=ident;self.future=self.pool.submit(fn,*args)
        return {'status':'running','id':ident,'kind':kind}

    def state(self):
        with self.lock:
            if self.future is None:return {'status':'idle'}
            base={'id':self.active,'kind':self.kind}
            if not self.future.done():return {**base,'status':'running'}
            try:
                result=self.future.result()
                return {**base,'status':'finished','result':{k:result[k] for k in ('status','phase','error','task_id','release_id') if k in result}}
            except Exception as exc:return {**base,'status':'failed','error':exc.code if isinstance(exc,CoreError) else 'local_execution_failed'}

    def close(self):
        with self.lock:self.closed=True
        self.pool.shutdown(wait=True)
