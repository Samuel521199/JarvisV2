import unittest
from host.studio3d_view_control import ViewerInspection, validate_view
from sdk.protocol import CoreError


class LiveInspection(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.checked = []
        self.hub = ViewerInspection(None, verify=lambda *args: self.checked.append(args), clock=lambda: self.now)
        self.bound = {'client_id': 'a'*32, 'asset_id': 'b'*32, 'sha256': 'c'*64}
        self.hub.command({'action': 'register', **self.bound, 'objects': ['shield', 'wheel-left']})

    def request(self, **patch):
        return self.hub.command({'action': 'request', 'id': 'd'*32, **self.bound, 'view': {'mode': 'wire', 'camera': 'left', 'part': 'wheel-left', 'isolate': True}, 'capture': False, **patch})

    def ack(self, **patch):
        result = {'asset_id': self.bound['asset_id'], 'sha256': self.bound['sha256'], 'applied': self.hub.requests['d'*32]['view']}
        return self.hub.command({'action': 'ack', **self.bound, 'id': 'd'*32, 'result': result, **patch})

    def test_registration_validates_real_source(self):
        self.assertEqual(len(self.checked), 1)
        self.assertEqual(self.checked[0][1:], (self.bound['asset_id'], self.bound['sha256']))

    def test_wire_part_execute_once(self):
        self.request()
        r = self.hub.command({'action': 'poll', **self.bound})['request']
        self.assertEqual(r['status'], 'DISPATCHED')
        self.assertIsNone(self.hub.command({'action': 'poll', **self.bound})['request'])
        self.assertEqual(self.ack()['status'], 'SUCCEEDED')
        with self.assertRaises(CoreError): self.ack()
        with self.assertRaises(CoreError): self.request()

    def test_changed_source_and_wrong_client_rejected(self):
        for patch in [{'sha256': 'e'*64}, {'asset_id': 'f'*32}, {'client_id': 'e'*32}]:
            with self.assertRaises(CoreError): self.request(**patch)

    def test_controls_are_finite_and_no_code_or_mutation(self):
        for view in [{'code': 'alert(1)'}, {'mode': 'unknown'}, {'part': '../other'}, {'clip': float('nan')}, {'zoom': 10}, {'exposure': True}, {'isolate': True}, {'camera': 'path/to/file'}, {'overlay': 1}]:
            with self.assertRaises(CoreError): validate_view(view, ['shield'])

    def test_key_angle_is_bounded_without_changing_other_controls(self):
        for angle in (-180, 0, 180, 53.25):
            self.assertEqual(validate_view({'light_angle': angle}, ['shield']), {'light_angle': angle})
        for angle in (-181, 181, float('nan'), float('inf'), True, '180'):
            with self.assertRaises(CoreError): validate_view({'light_angle': angle}, ['shield'])

    def test_key_angle_requires_actual_observation(self):
        self.request(view={'light_angle': 180})
        self.hub.command({'action': 'poll', **self.bound})
        result = {'asset_id': self.bound['asset_id'], 'sha256': self.bound['sha256'], 'applied': {'light_angle': 180}}
        for wrong in (None, 0, '180', True):
            with self.assertRaises(CoreError): self.ack(result={**result, 'light_angle': wrong})
        self.assertEqual(self.ack(result={**result, 'light_angle': 180})['status'], 'SUCCEEDED')

    def test_owner_and_capture_binding(self):
        self.request(capture=True)
        self.hub.command({'action': 'poll', **self.bound})
        with self.assertRaises(CoreError): self.ack(client_id='e'*32)
        with self.assertRaises(CoreError): self.ack()  # missing capture
        with self.assertRaises(CoreError): self.ack(result={'asset_id': 'f'*32, 'sha256': self.bound['sha256']})

    def test_applied_controls_required(self):
        self.request(); self.hub.command({'action': 'poll', **self.bound})
        with self.assertRaises(CoreError): self.ack(result={'asset_id': self.bound['asset_id'], 'sha256': self.bound['sha256'], 'applied': {}})

    def test_disconnect_does_not_replay_unknown(self):
        self.request(); self.hub.command({'action': 'poll', **self.bound})
        self.hub.command({'action': 'stop', **self.bound})
        self.assertEqual(self.hub.command({'action': 'status', 'id': 'd'*32})['status'], 'UNKNOWN')

    def test_queued_stop_cancels_without_dispatch(self):
        self.request(); self.hub.command({'action': 'stop', **self.bound})
        self.assertEqual(self.hub.requests['d'*32]['status'], 'CANCELLED')

    def test_expiry_and_one_pending_request(self):
        self.request()
        with self.assertRaises(CoreError): self.request(id='e'*32)
        self.now = 61
        self.assertEqual(self.hub.command({'action': 'status', 'id': 'd'*32})['status'], 'EXPIRED')
        self.assertEqual(self.hub.command({'action': 'list', **{k:self.bound[k] for k in ('asset_id','sha256')}})['sessions'], [])


if __name__ == '__main__': unittest.main()
