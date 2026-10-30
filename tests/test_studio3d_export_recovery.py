import copy,json,struct,unittest
from modules.skills.studio3d.export_materials import preserve_base_pbr,base_pbr
from modules.skills.studio3d.production_recovery import abandon_comparison,abandon_inspection,abandon_teaching_plan,new_request_allowed,quarantined

class ExportRecoveryTests(unittest.TestCase):
    def test_unknown_teaching_plan_is_never_replayed_or_executed(self):
        key='teaching-wheel-relief-02-redo-plan-v1'
        s={'calls':{key:{'status':'UNKNOWN','request_id':'t','signature':'s','error':'connection_failed'}},'best_iteration':'r25'}
        remote={'id':'t','status':'UNKNOWN','error':'connection_failed','reply':None}
        proof={'request_id':'t','local_transport_finished':True,'active_native_transports':0,'asset_lock_held':True,'implementation_sha256':'source-digest'}
        out=abandon_teaching_plan(s,key,remote,proof,'now')
        self.assertTrue(quarantined(out['calls'][key]));self.assertFalse(out['calls'][key]['recovery_disposition']['plan_executed'])
        self.assertNotIn('recovery_disposition',s['calls'][key]);new_request_allowed(out['calls'],'different-profile-case')
        with self.assertRaises(ValueError):new_request_allowed(out['calls'],'s')
        for bad in ({**remote,'status':'RUNNING'},{**remote,'reply':'late result'},{**remote,'error':'model_timeout'}):
            with self.assertRaises(ValueError):abandon_teaching_plan(s,key,bad,proof,'now')
        with self.assertRaises(ValueError):abandon_teaching_plan(s,key,remote,{**proof,'active_native_transports':1},'now')

    def test_terminal_inspection_does_not_accept_result_or_erase_cost_uncertainty(self):
        key='r25-inspection-review-1.0.0-left'
        s={'calls':{key:{'status':'UNKNOWN','request_id':'turn','signature':'sig'}},'best_iteration':'r25','status':'INTERRUPTED_OR_FAILED','iterations':[{'id':'r25','gate':{'model_based_near_match':False}}]}
        remote={'id':'turn','status':'UNKNOWN','error':'model_timeout','reply':None}
        proof={'request_id':'turn','local_transport_finished':True,'active_native_transports':0,'asset_lock_held':True,'implementation_sha256':'verified-source-digest'}
        out=abandon_inspection(s,key,remote,proof,'now');row=out['calls'][key]
        self.assertTrue(quarantined(row));self.assertEqual(row['status'],'UNKNOWN');self.assertFalse(row['recovery_disposition']['cost_known'])
        self.assertEqual(out['status'],s['status']);self.assertEqual(out['iterations'],s['iterations']);new_request_allowed(out['calls'],'distinct-teaching-input')
        with self.assertRaises(ValueError):new_request_allowed(out['calls'],'sig')
        for bad in ({**proof,'active_native_transports':1},{**proof,'local_transport_finished':False},{**proof,'asset_lock_held':False}):
            with self.assertRaises(ValueError):abandon_inspection(s,key,remote,bad,'now')
        for bad in ({**remote,'status':'RUNNING'},{**remote,'reply':'recovered output'},{**remote,'error':'network_timeout'}):
            with self.assertRaises(ValueError):abandon_inspection(s,key,bad,proof,'now')

    def test_new_request_never_passes_active_or_queued_turn(self):
        for status in ('CREATED','SUBMITTING','READY','RUNNING','UNKNOWN'):
            with self.assertRaises(ValueError):new_request_allowed({'x':{'status':status,'signature':'old'}},'new')

    def test_missing_procedural_pbr_is_explicit_dark_dielectric_and_binary_unchanged(self):
        doc={'asset':{'version':'2.0'},'materials':[{'name':'paint','extensions':{'KHR_materials_clearcoat':{'clearcoatFactor':.06}}},{'name':'rubber'}],'meshes':[{'name':'keep'}]}
        payload=json.dumps(doc).encode();payload+=b' '*(-len(payload)%4);tail=struct.pack('<II',4,0x004e4942)+b'1234'
        raw=struct.pack('<4sIIII',b'glTF',2,20+len(payload)+len(tail),len(payload),0x4e4f534a)+payload+tail
        row={'id':'paint','detail':'weathered_paint','color':'#303030','metallic':0,'roughness':.53}
        out,audit=preserve_base_pbr(raw,[row]);size=struct.unpack_from('<I',out,12)[0];result=json.loads(out[20:20+size])
        self.assertEqual(out[20+size:],tail);self.assertEqual(result['meshes'],doc['meshes']);self.assertEqual(result['materials'][1],doc['materials'][1])
        self.assertEqual(result['materials'][0]['pbrMetallicRoughness'],base_pbr(row));self.assertLess(base_pbr(row)['baseColorFactor'][0],.04)
        self.assertEqual(preserve_base_pbr(out,[row])[0],out);self.assertTrue(audit['binary_unchanged'])

    def state(self):
        return {'calls':{'r16-compare-r15-left-sheet-v1':{'status':'UNKNOWN','request_id':'turn','signature':'sig'}},'pending_iteration':'r16','best_iteration':'r15','iterations':[{'id':'r15','status':'REVIEWED'},{'id':'r16','status':'REVIEWED'}]}

    def test_abandon_preserves_unknown_and_rejects_replay_but_allows_distinct_work(self):
        state=self.state();out=abandon_comparison(state,'r16-compare-r15-left-sheet-v1',{'id':'turn','status':'UNKNOWN','error':'host_interrupted'},'now')
        row=next(iter(out['calls'].values()));self.assertTrue(quarantined(row));self.assertEqual(row['status'],'UNKNOWN');self.assertEqual(state['pending_iteration'],'r16')
        self.assertFalse(out['iterations'][1]['adoption']['accepted']);self.assertNotIn('pending_iteration',out)
        new_request_allowed(out['calls'],'different')
        with self.assertRaises(ValueError):new_request_allowed(out['calls'],'sig')

    def test_live_wrong_or_unproven_unknown_cannot_be_bypassed(self):
        state=self.state()
        with self.assertRaises(ValueError):new_request_allowed(state['calls'],'different')
        for change in ({'status':'RUNNING'},{'id':'other'},{'reply':'recovered result'},{'error':'network_timeout'}):
            remote={'id':'turn','status':'UNKNOWN','error':'host_interrupted',**change}
            with self.assertRaises(ValueError):abandon_comparison(state,'r16-compare-r15-left-sheet-v1',remote,'now')
        state['calls']['r16-review-left']=state['calls'].pop('r16-compare-r15-left-sheet-v1')
        with self.assertRaises(ValueError):abandon_comparison(state,'r16-review-left',{'id':'turn','status':'UNKNOWN','error':'host_interrupted'},'now')

if __name__=='__main__':unittest.main()
