"""Actual HTTP framing must accept declared audio bounds without widening JSON elsewhere."""
import base64,http.client,io,json,threading,tempfile,unittest,wave
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from apps.workbench.server import Handler
from host.core import Core
from sdk.protocol import decode,CoreError


class SpeechHTTPBounds(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        Core.initialize(self.root).close();self.received=[]
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.data_root=str(self.root);self.server.nonce='synthetic-speech-bounds'
        self.server.speech=SimpleNamespace(command=self.command)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def command(self,body):self.received.append(body);return {'received':True}
    def post(self,body,*,route='/api/speech',nonce=True,declared=None):
        raw=body if isinstance(body,bytes) else json.dumps(body).encode()
        headers={'Origin':'http://127.0.0.1:'+str(self.server.server_port),'Content-Type':'application/json'}
        if nonce:headers['X-Jarvis-Token']=self.server.nonce
        if declared is not None:headers['Content-Length']=str(declared)
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request('POST',route,raw,headers);response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()
    def recording(self,seconds):
        output=io.BytesIO()
        with wave.open(output,'wb') as audio:
            audio.setparams((1,2,16000,seconds*16000,'NONE','none'));audio.writeframes(b'\0\0'*(seconds*16000))
        return {'action':'record','id':'audio-'+'1'*32,'audio':base64.b64encode(output.getvalue()).decode(),'purpose':'chat','chat_id':'synthetic-chat','exercise_id':None}
    def test_seven_second_and_sixty_second_audio_cross_actual_decoder(self):
        for seconds in (7,60):
            body=self.recording(seconds)
            self.assertGreater(len(json.dumps(body)),262144)
            code,value=self.post(body);self.assertEqual(code,200,value);self.assertEqual(self.received[-1],body)
    def test_oversized_framing_rejected_before_domain_service(self):
        code,value=self.post(b'{}',declared=3000001);self.assertEqual(code,413,value);self.assertFalse(self.received)
    def test_nonce_still_required_for_audio_route(self):
        self.assertEqual(self.post({'action':'status'},nonce=False)[0],403);self.assertFalse(self.received)
    def test_duplicate_keys_nonfinite_and_surrogates_still_rejected(self):
        for raw in (b'{"action":"status","action":"record"}',b'{"action":"status","x":NaN}',b'{"action":"status","x":"\\ud800"}'):
            code,value=self.post(raw);self.assertEqual(code,400,value)
        self.assertFalse(self.received)
    def test_ordinary_http_routes_keep_original_small_bound(self):
        code,value=self.post(b'{}',route='/api/chat/submit',declared=300000)
        self.assertEqual(code,413,value);self.assertFalse(self.received)
    def test_standard_json_default_is_unchanged(self):
        with self.assertRaises(CoreError) as error:decode(json.dumps({'text':'x'*300000}))
        self.assertEqual(error.exception.code,'message_too_large')


if __name__=='__main__':unittest.main()
