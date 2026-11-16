"""Long audio uses a route-local bound; ordinary JSON and strict parsing stay intact."""
import base64,http.client,io,threading,unittest,wave
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_shared_speech as fixture
from apps.workbench.server import Handler
from sdk.protocol import CoreError,decode,canonical,MAX_MESSAGE_BYTES

class SpeechHTTP(unittest.TestCase):
    setUpLearning=fixture.SpeechFlow.setUpLearning
    call=fixture.SpeechFlow.call
    def setUp(self):
        fixture.SpeechFlow.setUp(self);self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.data_root=self.root;self.server.nonce='fixture';self.server.speech=self.speech;self.server.dialogues=self.runner
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);fixture.SpeechFlow.tearDown(self)
    def request(self,path,raw,declared_length=None):
        origin='http://127.0.0.1:'+str(self.server.server_port);connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Origin':origin,'Content-Type':'application/json','X-Jarvis-Token':'fixture'}
        if declared_length is not None:headers['Content-Length']=str(declared_length)
        connection.request('POST',path,raw,headers);response=connection.getresponse();code=response.status;body=decode(response.read());connection.close();return code,body
    def test_full_sixty_second_recording_and_legacy_oral_upload(self):
        output=io.BytesIO()
        with wave.open(output,'wb') as w:w.setparams((1,2,16000,960000,'NONE','none'));w.writeframes(b'\x00\x00'*960000)
        audio=base64.b64encode(output.getvalue()).decode();raw=canonical({'action':'record','id':'audio-'+'2'*32,'audio':audio,'purpose':'chat','chat_id':self.chat,'exercise_id':None}).encode();self.assertGreater(len(raw),MAX_MESSAGE_BYTES)
        code,body=self.request('/api/speech',raw);self.assertIn(code,(200,202));self.assertEqual(body['recording']['seconds'],60)
        code,body=self.request('/api/english-learning',canonical({'action':'record','audio':audio}).encode());self.assertIn(code,(200,202));self.assertEqual(body['recording']['seconds'],60)
        self.assertEqual(self.request('/api/chat/send',b'',declared_length=len(raw))[0],413)
    def test_decoder_bounds_and_duplicate_nonfinite_surrogate_are_preserved(self):
        large=canonical({'audio':'x'*300000}).encode()
        with self.assertRaises(CoreError):decode(large)
        self.assertEqual(len(decode(large,max_bytes=3000000)['audio']),300000)
        for raw in (b'{"action":"status","action":"status"}',b'{"n":NaN}',b'{"n":Infinity}',b'{"n":"\\ud800"}'):
            for route in ('/api/speech','/api/english-learning'):
                code,body=self.request(route,raw);self.assertEqual(code,400);self.assertEqual(body['error'],'invalid_json')
        self.assertEqual(self.request('/api/speech',b'',declared_length=3000001)[0],413)

if __name__=='__main__':unittest.main()
