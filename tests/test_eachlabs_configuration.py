"""Configured vendor selection, revoked credentials and media transport boundaries."""
import base64,copy,json,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch,Mock
from control.credentials import Credentials
from control.eachlabs_identity import owner_id
from host.core import Core
from modules.preferences.store import Preferences,resolve,fallback_routes
from modules.preferences.management import manage
from modules.image_generation import profiles,settings
from adapters.models import eachlabs,native_transport
from host import image_generation
from sdk.protocol import CoreError
from sdk.pricing import estimate
from test_image_generation import png


def metadata(model='image-fixture'):
    return {'slug':model,'title':'Eachlabs fixture','version':'1.0.0','request_schema':{'properties':{
        'resolution':{'enum':['1K']},'aspect_ratio':{'enum':['1:1']},'output_format':{},'num_images':{}}},'cost':None}


class EachlabsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        Core.initialize(self.root).close()
        self.catalog={'schema_version':1,'default_provider':'relay','automatic_fallback':True,'fallback_order':['relay','official'],
            'providers':{'relay':{'adapter':'eachlabs','model':'vendor/text','enabled':True,'models':{'vendor/text':{'enabled':True,'parameters':{}}}},
                         'official':{'adapter':'gemini','model':'old','enabled':True,'models':{'old':{'enabled':True}}}}}
        self.store=Preferences(self.root);self.store.install(copy.deepcopy(self.catalog),{});self.addCleanup(self.store.close)
        self.profile=profiles.from_remote(metadata(),metadata('edit-fixture'),.2)
        self.value={'model':'image-fixture','prompt':'Original synthetic test','size':'1K','aspect_ratio':'1:1'}

    def test_identity_is_stable_and_invalid_binding_is_not_replaced(self):
        first=owner_id(self.root);self.assertEqual(first,owner_id(self.root));self.assertEqual(len(first),45)
        (self.root/'config/eachlabs-owner.json').write_text('{"schema":9}')
        with self.assertRaises(CoreError):owner_id(self.root)

    def test_saved_policy_controls_explicit_default_and_fallback_routes(self):
        current=manage(self.store,{'action':'provider_policy','revision':1,'allowed_adapters':['eachlabs','local']})
        c=current['catalog'];self.assertEqual(resolve(c)['adapter'],'eachlabs');self.assertFalse(c['providers']['official']['enabled'])
        self.assertEqual(fallback_routes(c,resolve(c)),[])
        with self.assertRaises(CoreError):resolve(c,'official')
        with self.assertRaises(CoreError):manage(self.store,{'action':'add_connection','revision':2,'adapter':'gemini','label':'no','model':'no','base_url':'','region':''})

    @unittest.skipUnless(os.name=='nt','DPAPI credential retirement')
    def test_removed_connection_cannot_use_legacy_or_managed_credential(self):
        vault=Credentials(self.root);vault.save({'official':{'api_key':'synthetic-legacy'},'relay':{'api_key':'synthetic-relay'}})
        vault.put('official','managed-key',{'api_key':'synthetic-managed'})
        manage(self.store,{'action':'remove_connection','revision':1,'connection':'official'},vault)
        with self.assertRaises(CoreError):vault.get('official')
        with self.assertRaises(CoreError):vault.get('official','managed-key')
        self.assertEqual(vault.get('relay')['api_key'],'synthetic-relay');self.assertNotIn('official',self.store.read()['catalog']['providers'])

    def test_profile_revision_default_and_invalid_parameters(self):
        profiles.save(self.root,0,self.profile)
        with self.assertRaises(CoreError):profiles.save(self.root,0,self.profile)
        with self.assertRaises(CoreError):profiles.validate({**self.profile,'defaults':{'num_images':4}})
        body={**settings.read(self.root),'provider':'relay','model':'image-fixture','enabled_models':['image-fixture']}
        settings.save(self.root,body,profiles.read(self.root)['models'])
        self.assertEqual(image_generation.preview(self.root,{'id':uuid.uuid4().hex,'provider':'relay',**self.value})['quote']['planning_allowance'],.2)

    def test_missing_edit_endpoint_is_rejected_before_dispatch(self):
        profiles.save(self.root,0,{**self.profile,'edit_model':None,'edit_version':None})
        with self.assertRaises(CoreError) as caught:image_generation.image_quote(self.root,'eachlabs',self.value,[{'id':'explicit-reference'}])
        self.assertEqual(caught.exception.code,'image_invalid')

    def test_media_urls_reject_google_private_and_plaintext_without_fetch(self):
        for url in ('https://storage.googleapis.com/file.png','http://cdn.eachlabs.ai/file.png','https://user:secret@cdn.eachlabs.ai/f','https://example.com/f'):
            with self.assertRaises(ValueError):eachlabs.trusted_media(url)
        with patch.object(eachlabs.socket,'getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaises(ValueError):eachlabs.trusted_media('https://cdn.eachlabs.ai/a')

    def test_prediction_post_once_and_actual_cost_is_separate_from_allowance(self):
        progress=[]
        responses=[{'predictionID':'prediction-one'},{'status':'processing'},
            {'status':'success','output':['https://cdn.eachlabs.ai/result.png'],'metrics':{'cost':.08}}]
        with patch.object(eachlabs,'api',side_effect=responses) as api,patch.object(eachlabs,'trusted_media',side_effect=lambda u:u),patch.object(eachlabs,'fetch',return_value=(png(),'image/png')):
            result=eachlabs.image({'image_profile':self.profile,'end_user_id':'synthetic-internal-owner'}, {'api_key':'synthetic-key'},self.value,[],progress.append,sleep=lambda _:None)
        self.assertEqual(sum(call.args[0]=='/v1/prediction' for call in api.call_args_list),1)
        self.assertEqual(api.call_args_list[0].args[2]['model'],'image-fixture')
        self.assertEqual(result['usage']['provider_cost_usd'],.08);self.assertEqual(progress[0]['prediction_id'],'prediction-one')
        bill=estimate({'adapter':'eachlabs','price':None},result['usage'],0)
        self.assertEqual(bill['amount'],.08);self.assertEqual(bill['reason'],'provider_reported_cost')

    def test_edit_uses_configured_edit_slug_and_only_explicit_references(self):
        responses=[{'predictionID':'edit-one'},{'status':'success','output':'https://cdn.eachlabs.ai/out.png'}]
        with patch.object(eachlabs,'upload',return_value='https://cdn.eachlabs.ai/input.png') as upload,patch.object(eachlabs,'api',side_effect=responses) as api,patch.object(eachlabs,'trusted_media',side_effect=lambda u:u),patch.object(eachlabs,'fetch',return_value=(png(),'image/png')):
            eachlabs.image({'image_profile':self.profile,'end_user_id':'synthetic-internal-owner'},{'api_key':'synthetic'},self.value,[{'mimeType':'image/png','data':base64.b64encode(png()).decode()}])
        self.assertEqual(api.call_args_list[0].args[2]['model'],'edit-fixture');self.assertEqual(upload.call_count,1)

    def test_eachlabs_vision_payload_does_not_mutate_text_messages(self):
        messages=[{'role':'user','content':'Describe this synthetic image'}];original=copy.deepcopy(messages)
        config={'adapter':'eachlabs','model':'vendor/text','parameters':{},'max_output_tokens':64,'end_user_id':'synthetic-internal-owner'}
        url,headers,body=native_transport.request(config,{'api_key':'synthetic'},messages,False,[{'mimeType':'image/png','data':base64.b64encode(png()).decode()}])
        self.assertEqual(url,'https://api.eachlabs.ai/v1/chat/completions');self.assertEqual(messages,original)
        self.assertEqual(body['end_user_id'],'synthetic-internal-owner');self.assertTrue(body['messages'][-1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))

    def test_unknown_cost_is_not_zero_and_invalid_cost_not_accepted(self):
        self.assertIsNone(estimate({'adapter':'eachlabs','price':None},{},0)['amount'])
        self.assertIsNone(estimate({'adapter':'eachlabs','price':None},{'provider_cost_usd':-1},0)['amount'])


if __name__=='__main__':unittest.main()
