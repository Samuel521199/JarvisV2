import base64,json,struct,tempfile,time,unittest,uuid,zlib
from pathlib import Path
from unittest.mock import patch
from adapters.models.image_transport import request,extract,raster
from adapters.models.images import ImageModel
from modules.image_generation.catalog import validate,MODELS
from host import image_generation as host
from host.core import Core
from modules.preferences.store import Preferences
from modules.skills.catalog import Skills
from modules.dialogue.store import Dialogues
from control.network import NetworkGate
from sdk.protocol import CoreError

def png():
    def chunk(k,p):return struct.pack('>I',len(p))+k+p+struct.pack('>I',zlib.crc32(k+p)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\x80\xff'))+chunk(b'IEND',b'')
def value():return {'model':'gemini-nano-banana-2.1','prompt':'A blue mechanical wheel','size':'1K','aspect_ratio':'1:1'}
def reply():return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'inlineData':{'mimeType':'image/png','data':base64.b64encode(png()).decode()}}]}}],'usageMetadata':{'promptTokenCount':8,'candidatesTokenCount':1120,'candidatesTokensDetails':[{'modality':'IMAGE','tokenCount':1120}]}}

class Wire(unittest.TestCase):
    def test_models_and_scoped_sizes(self):
        for model in MODELS:validate({**value(),'model':model})
        for k,v in [('model','gemini-4-argon'),('size','8K'),('aspect_ratio','../'),('prompt','')]:
            with self.assertRaises(CoreError):validate({**value(),k:v})
        with self.assertRaises(CoreError):validate({**value(),'model':'gemini-3.1-flash-lite-image','size':'2K'})
    def test_api_key_and_vertex_auth(self):
        url,h,b=request({'adapter':'gemini','parameters':{'thinking_level':'HIGH'}},{'api_key':'test'},value(),[])
        self.assertIn('generativelanguage.googleapis.com',url);self.assertEqual(h,{'x-goog-api-key':'test'})
        self.assertNotIn('systemInstruction',b);self.assertEqual(b['generationConfig']['responseModalities'],['TEXT','IMAGE'])
        for key in ('thinkingConfig','responseMimeType','temperature'):self.assertNotIn(key,b['generationConfig'])
        with patch('adapters.models.image_transport.vertex_token',return_value=('test-token','test-project')):
            url,h,b=request({'adapter':'vertex'},{'service_account':{}},value(),[])
        self.assertIn('/locations/global/',url);self.assertEqual(h,{'Authorization':'Bearer test-token'})
    def test_png_edit_parts(self):
        encoded={'mimeType':'image/png','data':base64.b64encode(png()).decode()}
        _,_,b=request({'adapter':'gemini'},{'api_key':'test'},value(),[encoded]);self.assertEqual(b['contents'][0]['parts'][1],{'inlineData':encoded})
        with self.assertRaises(CoreError):request({'adapter':'gemini'},{'api_key':'test'},value(),[encoded]*3)
    def test_image_only_is_success_and_usage_modality_retained(self):
        r=extract(reply());self.assertEqual(r['status'],'SUCCEEDED');self.assertEqual(r['text'],'');self.assertEqual(r['usage']['output_image_tokens'],1120)
    def test_text_only_blocked_and_partial_not_success(self):
        for data in ({'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[{'finishReason':'MAX_TOKENS'}]},{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'I can make an image'}]}}]}):self.assertEqual(extract(data)['status'],'INVALID')
    def test_thought_images_not_delivered(self):
        data=reply();data['candidates'][0]['content']['parts'][0]['thought']=True;self.assertEqual(extract(data)['status'],'INVALID')
    def test_multiple_and_external_images_rejected(self):
        data=reply();parts=data['candidates'][0]['content']['parts'];parts.append(parts[0]);self.assertEqual(extract(data)['status'],'INVALID')
        data=reply();data['candidates'][0]['content']['parts'].append({'fileData':{'fileUri':'https://external'}});self.assertEqual(extract(data)['status'],'INVALID')
    def test_corrupt_or_svg_binary_rejected(self):
        raw=png();self.assertEqual(raster(raw,'image/png'),[1,1])
        for raw,mime in [(raw[:-1], 'image/png'),(raw[:-15]+b'broken'+raw[-9:],'image/png'),(b'<svg>'+b'x'*80,'image/svg+xml')]:
            with self.assertRaises(ValueError):raster(raw,mime)
    def test_cancel_before_spawn(self):
        def stop():raise CoreError('stopped','stop')
        with patch('subprocess.Popen') as process,self.assertRaises(CoreError):ImageModel({'adapter':'gemini','id':'g'},lambda *a:{}).generate(value(),checkpoint=stop)
        process.assert_not_called()

class Host(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);Core.initialize(self.root).close()
        p=Preferences(self.root)
        p.install({'schema_version':1,'default_provider':'google','automatic_fallback':False,'fallback_order':[],'providers':{'google':{'adapter':'gemini','model':'text-model','enabled':True,'models':{'text-model':{'enabled':True}}}}},{})
        p.close();self.body={'id':uuid.uuid4().hex,'provider':'google',**value()}
        self.avail=patch('host.image_generation.Credentials.available',return_value=True);self.avail.start();self.addCleanup(self.avail.stop)
    def wait(self,key):
        for _ in range(200):
            r=host.state(self.root,key)
            if r['status'] in host.TERMINAL and (str(self.root),key) not in host.ACTIVE:return r
            time.sleep(.01)
        self.fail('image worker did not finish')
    def test_generated_file_ledger_idempotence_and_tamper(self):
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())) as client:
            host.start(self.root,self.body);r=self.wait(self.body['id']);self.assertEqual(r['status'],'SUCCEEDED',r)
            self.assertTrue(host.start(self.root,self.body)['existing']);self.assertEqual(client.call_count,1)
            with self.assertRaises(CoreError):host.start(self.root,{**self.body,'prompt':'Different'})
        raw,mime=host.file(self.root,r['id'],'image.png');self.assertEqual(raw,png());self.assertEqual(mime,'image/png')
        ledger=Dialogues(self.root)
        try:usage=ledger.usage();self.assertEqual(usage[0]['status'],'SUCCEEDED');self.assertEqual(json.loads(usage[0]['billing_profile'])['price'],None)
        finally:ledger.close()
        (self.root/'artifacts/image-generation'/r['id']/'image.png').write_bytes(b'bad')
        with self.assertRaises(CoreError):host.file(self.root,r['id'],'image.png')
    def test_failed_call_never_retries(self):
        with patch('host.image_generation.ImageModel.generate',return_value={'status':'REJECTED','code':'http_404'}) as client:
            host.start(self.root,self.body);r=self.wait(self.body['id']);self.assertEqual(r['status'],'FAILED');self.assertEqual(client.call_count,1)
            self.assertTrue(host.start(self.root,self.body)['existing']);self.assertEqual(client.call_count,1)
    def test_offline_and_disabled_skill_prevent_call(self):
        gate=NetworkGate(self.root);gate.update({'revision':gate.read()['revision'],'blocked':True})
        with patch('host.image_generation.ImageModel.generate') as client,self.assertRaises(CoreError):host.start(self.root,self.body)
        client.assert_not_called();gate.update({'revision':gate.read()['revision'],'blocked':False})
        skills=Skills(self.root);skills.enable('image-studio',False);skills.close()
        with self.assertRaises(CoreError):host.start(self.root,self.body)
    def test_no_freeform_endpoint_or_fallback(self):
        for key,val in [('url','https://external'),('python','print(1)'),('auto',True)]:
            with self.assertRaises(CoreError):host.start(self.root,{**self.body,key:val})
        with self.assertRaises(CoreError):host.start(self.root,{**self.body,'provider':'auto'})
    def test_cancel_keeps_usage(self):
        def generated(*a):
            host.cancel(self.root,self.body['id']);return extract(reply())
        with patch('host.image_generation.ImageModel.generate',side_effect=generated):
            host.start(self.root,self.body);r=self.wait(self.body['id']);self.assertEqual(r['status'],'CANCELLED');self.assertIsNone(r['receipt'])
        ledger=Dialogues(self.root)
        try:self.assertEqual(json.loads(ledger.usage()[0]['usage'])['output_images'],1)
        finally:ledger.close()
    def test_png_reference_bridge(self):
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())):
            host.start(self.root,self.body);self.wait(self.body['id'])
        r=host.reference(self.root,self.body['id']);self.assertEqual(r['resolution'],[1,1]);self.assertFalse(r['provenance_verified'])
    def test_interruption_marked_unknown_without_call(self):
        d=host.db(self.root);d.execute('INSERT INTO jobs(id,signature,status,request,created) VALUES(?,?,?,?,?)',(self.body['id'],'x','RUNNING',json.dumps(self.body),0));d.close()
        self.assertEqual(host.state(self.root,self.body['id'])['status'],'UNKNOWN')

    def test_image_edit_intake_independent_of_studio3d(self):
        skills=Skills(self.root);skills.enable('studio3d',False);skills.close()
        body={'name':'reference.png','source':'test input','license':'original fixture','data':base64.b64encode(png()).decode()}
        uploaded=host.upload(self.root,body)
        self.body['references']=[uploaded['id']]
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())) as model:
            host.start(self.root,self.body);self.assertEqual(self.wait(self.body['id'])['status'],'SUCCEEDED')
            self.assertEqual(model.call_args.args[1],[png()])
        with self.assertRaises(CoreError):host.reference(self.root,self.body['id'])
        skills=Skills(self.root);skills.enable('image-studio',False);skills.close()
        with self.assertRaises(CoreError):host.upload(self.root,body)

    def test_http_generation_download_reference_and_nonce(self):
        import http.client,threading
        from http.server import ThreadingHTTPServer
        from apps.workbench.server import Handler
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='image-test'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def request(method,path,body=None,nonce=True,cross=False):
            headers={'Origin':'http://invalid.example' if cross else origin,'Content-Type':'application/json'}
            if nonce:headers['X-Jarvis-Token']=server.nonce
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            c.request(method,path,json.dumps(body).encode() if body is not None else None,headers)
            r=c.getresponse();result=(r.status,r.read(),dict(r.getheaders()));c.close();return result
        try:
            ready=json.loads(request('GET','/api/image-studio')[1]);self.assertEqual(len(ready['models']),3)
            saved=request('POST','/api/image-studio/settings',{**ready['settings'],'provider':'google'})
            self.assertEqual(saved[0],200);self.assertEqual(json.loads(saved[1])['revision'],1)
            quoted=json.loads(request('POST','/api/image-studio/preview',self.body)[1]);self.assertTrue(quoted['allowed']);self.assertGreater(quoted['quote']['image_output_estimate'],0)
            self.assertEqual(request('GET','/settings-images.js')[0],200)
            self.assertEqual(request('POST','/api/image-studio/jobs',self.body,nonce=False)[0],403)
            self.assertEqual(request('POST','/api/image-studio/jobs',self.body,cross=True)[0],403)
            with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())) as model:
                self.assertEqual(request('POST','/api/image-studio/jobs',self.body)[0],202)
                row=self.wait(self.body['id']);self.assertEqual(row['status'],'SUCCEEDED')
                self.assertEqual(request('POST','/api/image-studio/jobs',self.body)[0],202)
                self.assertEqual(model.call_count,1)
            code,raw,headers=request('GET',row['receipt']['file']['url'])
            self.assertEqual((code,raw),(200,png()));self.assertEqual(headers['Content-Type'],'image/png')
            self.assertEqual(json.loads(request('GET','/api/image-studio/jobs/'+self.body['id'])[1])['status'],'SUCCEEDED')
            self.assertEqual(len(json.loads(request('GET','/api/image-studio/jobs')[1])),1)
            self.assertEqual(request('POST','/api/image-studio/reference',{'id':self.body['id']})[0],201)
            body={'name':'test.png','source':'synthetic','license':'test','data':base64.b64encode(png()).decode()}
            self.assertEqual(request('POST','/api/image-studio/references',body)[0],201)
            annotation={'id':self.body['id'],'kind':'invoice','revision':0,'value':{'amount':.03,'currency':'USD','reference':'HTTP test fixture'}}
            self.assertEqual(request('POST','/api/image-studio/annotation',annotation)[0],200)
            self.assertEqual(json.loads(request('GET','/api/image-studio/billing')[1])['groups'][0]['invoice_usd'],.03)
            self.assertEqual(request('GET','/api/image-studio/files/'+self.body['id']+'/receipt.json')[0],400)
        finally:
            server.shutdown();server.server_close();thread.join(2)
            if hasattr(server,'family'):server.family.close()

if __name__=='__main__':unittest.main()
