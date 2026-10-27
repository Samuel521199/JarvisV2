import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.workbench.server import Handler
from host.core import Core
from host.local_models import LocalModels
from modules.local_models.catalog import builtin
from sdk.protocol import canonical, decode


class LocalModelsHTTPCase(unittest.TestCase):
    def test_contract_nonce_revision_and_background_does_not_block_reads(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-model-api-') as temp:
            Core.initialize(temp).close()
            manager=LocalModels(temp)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            server.data_root=temp;server.nonce='local-test';server.local_models=manager
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            entered=threading.Event();release=threading.Event()
            try:
                origin='http://127.0.0.1:'+str(server.server_port)
                def request(method,path,body=None,nonce=True):
                    headers={'Origin':origin,'Content-Type':'application/json'}
                    if nonce:headers['X-Jarvis-Token']='local-test'
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                    conn.request(method,path,canonical(body).encode() if body is not None else None,headers)
                    response=conn.getresponse();data=decode(response.read());conn.close()
                    return response.status,data
                code,state=request('GET','/api/local-models')
                self.assertEqual(code,200);self.assertEqual(state['schema'],'jarvis.local-models.v1')
                self.assertIn('assessment',state['models'][0]);self.assertEqual(state['manager']['state_schema'],2)
                body={'action':'register','manifest':builtin()[0],'revision':state['revision']}
                self.assertEqual(request('POST','/api/local-models',body,nonce=False)[0],403)
                old=manager._run
                def slow(body,job):
                    entered.set();release.wait(3);return old(body,job)
                manager._run=slow
                self.assertEqual(request('POST','/api/local-models',body)[0],202)
                self.assertTrue(entered.wait(1))
                started=time.monotonic()
                self.assertEqual(request('GET','/api/snapshot')[0],200)
                self.assertEqual(request('GET','/api/local-models')[1]['job']['status'],'running')
                self.assertLess(time.monotonic()-started,2)
                self.assertEqual(request('POST','/api/local-models',body)[1]['error'],'model_busy')
                release.set();self.assertEqual(manager.future.result(timeout=5)['status'],'succeeded')
                self.assertEqual(request('POST','/api/local-models',body)[0],409)
                self.assertEqual(request('GET','/api/local-models/result')[1]['status'],'succeeded')
            finally:
                release.set();server.shutdown();server.server_close();thread.join(timeout=2);manager.close()


if __name__=='__main__':unittest.main()
