"""A configured Eachlabs grant stays a text-only proxy, never a secret export."""
import copy,os,secrets,tempfile,unittest
from pathlib import Path
from host.core import Core
from host.development_bridge import Bridge
from host.development_sharing import configure
from control.atomic import write_json
from control.development_profile import write_secret,client_secret
from modules.preferences.store import Preferences
from sdk.protocol import CoreError


@unittest.skipUnless(os.name=='nt','Windows DPAPI pairing')
class SharingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);base=Path(self.temp.name).resolve()
        self.root=base/'daily';self.dev=base/'development';Core.initialize(self.root).close();Core.initialize(self.dev).close()
        self.catalog={'schema_version':1,'default_provider':'each','automatic_fallback':False,'fallback_order':[],
            'providers':{'each':{'adapter':'eachlabs','model':'vendor/text','enabled':True,'credential_id':'private-reference','keys':{'private-reference':{'masked':'masked'}},'models':{'vendor/text':{'parameters':{},'enabled':True}}}}}
        for root in (self.root,self.dev):
            p=Preferences(root);p.install(copy.deepcopy(self.catalog),{});p.close()
        self.grant={'client_id':secrets.token_hex(16),'token':secrets.token_hex(32),'allowed_providers':['old'],
            'daily_call_limit':8,'max_output_tokens':512}
        for root in (self.root,self.dev):write_secret(root/'private/development-bridge.dpapi',self.grant)
        write_json(self.dev/'config/development.json',{'schema':1,'kind':'development','client_id':self.grant['client_id'],
            'bridge_origin':'http://127.0.0.1:18482','allowed_providers':['old'],'external_actions':False,'production_data':str(self.root)})
        self.command={'revision':0,'settings_revision':1,'development_data':str(self.dev),'providers':['each']}

    def test_eachlabs_projection_removes_key_references_and_old_grant_is_revoked(self):
        old=Bridge(self.root,factory=lambda _:None)
        result=configure(self.root,self.command);self.assertTrue(result['restart_required'])
        with self.assertRaises(CoreError):old.require_current_grant()
        self.assertEqual(client_secret(self.dev)['allowed_providers'],['each']);self.assertEqual(client_secret(self.dev)['token'],self.grant['token'])
        self.assertFalse((self.dev/'private/model-credentials.dpapi').exists())
        p=Preferences(self.dev)
        try:projected=p.read()['catalog']['providers']['each']
        finally:p.close()
        self.assertNotIn('keys',projected);self.assertNotIn('credential_id',projected)

    def test_stale_settings_or_wrong_pair_does_not_modify_grant(self):
        before=(self.root/'private/development-bridge.dpapi').read_bytes()
        with self.assertRaises(CoreError):configure(self.root,{**self.command,'settings_revision':0})
        self.assertEqual(before,(self.root/'private/development-bridge.dpapi').read_bytes())
        write_secret(self.dev/'private/development-bridge.dpapi',{**self.grant,'token':'different'})
        with self.assertRaises(CoreError):configure(self.root,self.command)
        self.assertEqual(before,(self.root/'private/development-bridge.dpapi').read_bytes())


if __name__=='__main__':unittest.main()
