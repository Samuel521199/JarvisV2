import base64,json,struct,time,unittest,uuid,zlib
from unittest.mock import patch
import test_image_generation as fixtures
from test_image_generation import reply,extract,value
from host import image_generation as host
from modules.image_generation.catalog import dimensions,validate,MODELS
from modules.image_generation import settings
from modules.image_generation.design import compile_brief
from modules.image_generation.rates import snapshot,quote
from sdk.pricing import estimate
from sdk.protocol import CoreError
from adapters.models.image_transport import raster
from modules.dialogue.store import Dialogues


class Accounting(unittest.TestCase):
    def test_transport_watchdog_reaps_a_real_stalled_child(self):
        import subprocess,sys
        from adapters.models.images import ImageModel
        real_popen=subprocess.Popen;children=[]
        def launch(*args,**kwargs):
            child=real_popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)'],**kwargs);children.append(child);return child
        with patch('adapters.models.images.subprocess.Popen',side_effect=launch),patch('adapters.models.images.TIMEOUT_SECONDS',.3):
            started=time.monotonic();result=ImageModel({'id':'g','adapter':'gemini'},lambda *a:{}).generate(value())
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['code'],'image_timeout')
        self.assertIsNotNone(children[0].poll());self.assertLess(time.monotonic()-started,4)

    def test_all_sizes_and_wide_dimensions(self):
        for model,data in MODELS.items():
            for size in data['sizes']:validate({**value(),'model':model,'size':size})
        self.assertEqual(dimensions('4K','16:9'),[5504,3072])
        self.assertEqual(dimensions('4K','8:1'),[12288,1536])
        for model in ('gemini-nano-banana-2.1','gemini-3.1-flash-lite-image'):
            with self.assertRaises(CoreError):validate({**value(),'model':model,'size':'512'})
        # Valid PNG wrapper verifies the raised pixel boundary, not image content.
        def chunk(k,p):return struct.pack('>I',len(p))+k+p+struct.pack('>I',zlib.crc32(k+p)&0xffffffff)
        def png(w,h):return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',b'x')+chunk(b'IEND',b'')
        self.assertEqual(raster(png(4096,4096),'image/png'),[4096,4096])
        self.assertEqual(raster(png(12288,1536),'image/png'),[12288,1536])
        with self.assertRaises(ValueError):raster(png(8192,8192),'image/png')

    def test_price_modalities_thinking_cache_and_unknown(self):
        p={'image_price':snapshot('vertex','gemini-nano-banana-2.1')}
        usage={'prompt_tokens':100,'completion_tokens':1125,'output_image_tokens':1120,'output_text_tokens':5,'reasoning_tokens':10,'reasoning_in_completion':False,'total_tokens':1235,'cache_read_tokens':20}
        r=estimate(p,usage,time.time());self.assertAlmostEqual(r['amount'],.0336+.00012+.000003+.0001125)
        self.assertEqual(r['reason'],'image_modality_rates');self.assertFalse(r['invoice_verified'])
        for altered in ({**usage,'output_image_tokens':2000},{**usage,'total_tokens':2000},{k:v for k,v in usage.items() if k!='output_image_tokens'}):self.assertIsNone(estimate(p,altered,time.time())['amount'])
        old={**p,'image_price':{**p['image_price'],'valid_until':'2020-01-01'}}
        self.assertEqual(estimate(old,usage,time.time())['reason'],'price_expired')

    def test_price_source_and_four_k_token_discrepancy(self):
        for adapter in ('vertex','gemini'):
            q=quote(adapter,{**value(),'size':'4K'},2)
            self.assertEqual(q['image_output_estimate'],.1134)
            self.assertGreater(q['planning_allowance'],q['image_output_estimate'])
            self.assertIn('cloud.google.com' if adapter=='vertex' else 'ai.google.dev',q['price']['source'])

    def test_design_preserves_constraints_without_extra_calls(self):
        brief={'preset':'poster','audience':'工程师','style':'蓝白','constraints':'Only exact text: PUMP'}
        prompt,design=compile_brief('一张水泵海报',brief)
        self.assertIn('Only exact text: PUMP',prompt);self.assertEqual(design['acceptance'],'pending_human_review')
        self.assertIn('text',[c['id'] for c in design['checklist']])
        with self.assertRaises(CoreError):compile_brief('x',{})


class Workflow(unittest.TestCase):
    setUp=fixtures.Host.setUp
    wait=fixtures.Host.wait

    def test_defaults_revision_disabled_and_budget_before_dispatch(self):
        original=settings.read(self.root)
        next={**original,'provider':'google','model':'gemini-3.1-flash-lite-image','enabled_models':['gemini-3.1-flash-lite-image'],'max_estimate_usd':.01}
        saved=host.configure(self.root,next);self.assertEqual(settings.read(self.root),saved)
        with self.assertRaises(CoreError):host.configure(self.root,next)
        with patch('host.image_generation.ImageModel.generate') as model:
            with self.assertRaises(CoreError) as error:host.start(self.root,self.body)
            self.assertEqual(error.exception.code,'image_model_disabled')
            with self.assertRaises(CoreError) as error:host.start(self.root,{**self.body,'model':next['model']})
            self.assertEqual(error.exception.code,'image_budget');model.assert_not_called()

    def test_receipt_ledger_invoice_revisions_and_unknown_counts(self):
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())):
            host.start(self.root,self.body);row=self.wait(self.body['id'])
        self.assertIsNotNone(row['billing']['amount']);self.assertFalse(row['receipt']['technical_checks']['resolution_matches'])
        d=Dialogues(self.root)
        try:call=d.usage()[0];profile=json.loads(call['billing_profile']);usage=json.loads(call['usage'])
        finally:d.close()
        self.assertEqual(estimate(profile,usage,call['created'])['amount'],row['billing']['amount'])
        body={'id':row['id'],'kind':'invoice','revision':0,'value':{'amount':.04,'currency':'USD','reference':'synthetic test invoice'}}
        row=host.annotate(self.root,body);self.assertEqual(row['invoice']['revision'],1)
        with self.assertRaises(CoreError):host.annotate(self.root,body)
        host.annotate(self.root,{**body,'revision':1,'value':{**body['value'],'amount':.03}})
        total=host.summary(self.root)['groups'][0];self.assertEqual(total['invoice_usd'],.03);self.assertEqual(total['tasks'],1)
        d=host.db(self.root)
        try:self.assertEqual(d.execute('SELECT COUNT(*) FROM annotations').fetchone()[0],2)
        finally:d.close()
        with patch('host.image_generation.ImageModel.generate',return_value={'status':'UNKNOWN','code':'image_timeout'}):
            second={**self.body,'id':uuid.uuid4().hex};host.start(self.root,second);self.wait(second['id'])
        self.assertEqual(host.summary(self.root)['groups'][0]['unknown'],1)

    def test_review_and_edit_parent_provenance(self):
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())):
            host.start(self.root,self.body);row=self.wait(self.body['id'])
            checks={c['id']:True for c in row['design']['checklist']}
            annotation={'id':row['id'],'kind':'review','revision':0,'value':{'verdict':'accepted','checks':checks,'notes':'fixture'}}
            with self.assertRaises(CoreError):host.annotate(self.root,annotation)
            receipt=row['receipt'];receipt['technical_checks']['resolution_matches']=True
            host.update(self.root,row['id'],receipt=json.dumps(receipt))
            row=host.annotate(self.root,annotation);self.assertEqual(row['review']['verdict'],'accepted');self.assertFalse(row['review']['model_scored'])
            ref=host.reference(self.root,row['id'])
            next={**self.body,'id':uuid.uuid4().hex,'derived_from':row['id'],'references':[ref['id']],'prompt':'Make it red'}
            host.start(self.root,next);second=self.wait(next['id']);self.assertEqual(second['receipt']['derived_from'],row['id'])
            with self.assertRaises(CoreError):host.start(self.root,{**next,'id':uuid.uuid4().hex,'references':[]})

    def test_orphan_recovery_also_closes_only_its_call_ledger(self):
        with patch('host.image_generation.ImageModel.generate',return_value=extract(reply())):
            host.start(self.root,self.body);row=self.wait(self.body['id'])
        ledger=Dialogues(self.root)
        try:
            ledger.db.execute("UPDATE attempts SET status='DISPATCHING' WHERE turn_id=?",(row['turn_id'],))
            ledger.db.execute("UPDATE turns SET status='RUNNING' WHERE id=?",(row['turn_id'],))
        finally:ledger.close()
        host.update(self.root,row['id'],status='RUNNING',receipt=None)
        with patch('host.image_generation.ImageModel.generate') as model:
            self.assertEqual(host.state(self.root,row['id'])['status'],'UNKNOWN');model.assert_not_called()
        ledger=Dialogues(self.root)
        try:self.assertEqual(ledger.usage()[0]['status'],'UNKNOWN');self.assertEqual(ledger.turn(row['turn_id'])['status'],'UNKNOWN')
        finally:ledger.close()

if __name__=='__main__':unittest.main()
