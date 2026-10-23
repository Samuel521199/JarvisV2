import http.client
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.workbench.server import Handler
from host.core import Core
from sdk.protocol import decode
from sdk.protocol import canonical
from modules.preferences.store import Preferences
from test_preferences_dialogue import fixture


class WorkbenchCase(unittest.TestCase):
    def test_settings_require_origin_nonce_and_revision_and_persist_locally(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-settings-http-') as path:
            Core.initialize(path).close();prefs=Preferences(Path(path));prefs.install(fixture(),{})
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=path;server.nonce='test-nonce'
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                origin='http://127.0.0.1:'+str(server.server_port)
                body={'revision':1,'provider':'openai','model':'test-model','reasoning':'high','automatic_fallback':False,'fallback_order':['openai','bailian']}
                def post(headers):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    conn.request('POST','/api/settings',body=canonical(body).encode(),headers={'Content-Type':'application/json',**headers})
                    response=conn.getresponse();value=response.read();conn.close();return response.status,decode(value)
                self.assertEqual(post({'Origin':origin})[0],403)
                self.assertEqual(post({'Origin':'https://evil.test','X-Jarvis-Token':'test-nonce'})[0],403)
                code,value=post({'Origin':origin,'X-Jarvis-Token':'test-nonce'})
                self.assertEqual(code,200);self.assertFalse(value['settings']['automatic_fallback'])
                self.assertNotIn('credential_id',canonical(value));self.assertNotIn('api_key',canonical(value))
                self.assertEqual(post({'Origin':origin,'X-Jarvis-Token':'test-nonce'})[0],409)
                self.assertEqual(prefs.read()['catalog']['providers']['openai']['models']['test-model']['parameters']['reasoning_effort'],'high')
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2);prefs.close()

    def test_local_read_only_api_rejects_cross_origin_host_and_mutation(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-ui-") as path:
            Core.initialize(path).close()
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); server.data_root = path
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                def get(path, headers=None, method="GET"):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    conn.request(method, path, headers=headers or {})
                    response = conn.getresponse(); body = response.read(); conn.close()
                    return response, body
                response, body = get("/api/snapshot")
                self.assertEqual(response.status, 200)
                self.assertEqual(decode(body)["status"]["identity"]["owner_id"], "owner.local")
                self.assertNotIn(b'client_secret', body)
                self.assertEqual(get("/api/snapshot", {"Origin": "https://evil.example"})[0].status, 403)
                self.assertEqual(get("/api/snapshot", {"Host": "evil.example"})[0].status, 403)
                self.assertEqual(get("/api/snapshot", {"Sec-Fetch-Site": "cross-site"})[0].status, 403)
                self.assertEqual(get("/api/snapshot", method="POST")[0].status, 403)
                self.assertEqual(get("/../user-data/state/core.sqlite3")[0].status, 404)
                response, body = get("/")
                self.assertEqual(response.status, 200)
                self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__": unittest.main()
