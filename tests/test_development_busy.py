import io,unittest,urllib.error
from pathlib import Path
from unittest.mock import Mock,patch
from adapters.development_bridge import exchange,complete
from sdk.protocol import CoreError


class DevelopmentBusyTests(unittest.TestCase):
    def error(self,status,body):return urllib.error.HTTPError('http://127.0.0.1:18482/model',status,'fixture',{},io.BytesIO(body))
    def request(self,status,body):
        profile={'client_id':'fixture','bridge_origin':'http://127.0.0.1:18482'}
        opener=Mock();opener.open.side_effect=self.error(status,body)
        with patch('adapters.development_bridge.read',return_value=profile),patch('adapters.development_bridge.client_secret',return_value={'client_id':'fixture','token':'fixture-only'}),patch('adapters.development_bridge.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(CoreError) as raised:exchange(Path('unused'),'/model',{'fixture':True})
        self.assertEqual(opener.open.call_count,1);return raised.exception
    def test_only_exact_pinned_pre_dispatch_busy_response_has_busy_code(self):
        self.assertEqual(self.request(409,b'{"error":"development_busy"}').code,'development_busy')
        for status,body in [(500,b'{"error":"development_busy"}'),(409,b'{"error":"other"}'),(409,b'not-json'),
            (409,b'{"error":"other","error":"development_busy"}'),(409,b'x'*4097)]:
            self.assertEqual(self.request(status,body).code,'development_bridge_rejected')
    def test_busy_is_zero_dispatch_rejection_and_never_automatically_retried(self):
        route={'id':'vertex','model':'fixture','parameters':{}};checkpoint=Mock()
        with patch('adapters.development_bridge.read',return_value={'allowed_providers':['vertex']}),patch('adapters.development_bridge.NetworkGate') as gate,patch('adapters.development_bridge.exchange',side_effect=CoreError('development_busy','fixture')) as call:
            gate.return_value.read.return_value={'blocked':False}
            result=complete(Path('unused'),route,[{'role':'user','content':'fixture'}],checkpoint)
        self.assertEqual(result['status'],'REJECTED');self.assertFalse(result['dispatched'])
        self.assertEqual(result['usage']['total_tokens'],0);self.assertEqual(call.call_count,1)
    def test_other_transport_or_http_errors_remain_uncertain(self):
        route={'id':'vertex','model':'fixture','parameters':{}}
        with patch('adapters.development_bridge.read',return_value={'allowed_providers':['vertex']}),patch('adapters.development_bridge.NetworkGate') as gate,patch('adapters.development_bridge.exchange',side_effect=CoreError('development_bridge_rejected','fixture')):
            gate.return_value.read.return_value={'blocked':False}
            with self.assertRaises(CoreError) as raised:complete(Path('unused'),route,[{'role':'user','content':'fixture'}],lambda:None)
        self.assertEqual(raised.exception.code,'development_bridge_rejected')
