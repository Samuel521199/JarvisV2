"""Failed trial -> fresh bounded development -> private rejection/review/delivery."""
import unittest
from unittest.mock import patch
from host import development
from host.completion import refresh
from host.lesson_validation import run
from host.settings_operations import command
from host.lesson_repair import EVENT
from modules.model_gateway.routed import RoutedModels
from sdk.protocol import CoreError,canonical,decode
from test_development import Provider,candidate,plan
import test_lesson_validation as fixture
TOOLS=fixture.TOOLS

ROUTES={p:[{'provider':'openai','model':'test-model','reasoning':'default'}] for p in ('plan','code')}

class LessonRepairTests(unittest.TestCase):
    def failed(self,domain='practice'):
        ident,tid=self.candidate(domain,overfit=True);self.enable()
        self.assertEqual(run(self.root,tid)['status'],'FAILED')
        return ident,tid

    def prepare_repair(self,tid):return command(self.root,{'action':'lesson_repair_prepare','id':tid})

    def begin_repair(self,tid,draft,**changes):
        return command(self.root,{'action':'lesson_repair_begin','id':tid,'key':draft['key'],'fingerprint':draft['fingerprint'],'reviewed':True,'routes':ROUTES,**changes})

    def bind_repair(self,ident,source):
        spec=self.core.development.get(ident)['spec']
        provider=Provider([{**plan(),'capability':spec['capability']},candidate(source),candidate(source)])
        self.core.development.models=RoutedModels(self.core.db,{'primary':provider},['primary'])
        return provider

    def test_three_repairs_pass_hidden_cases_wait_for_review_and_deliver_separately(self):
        for domain,(_,_,logic) in TOOLS.items():
            with self.subTest(domain=domain):
                _,tid=self.failed(domain);oldbindings=self.core.tasks.get(tid)['bindings']
                before={t:self.core.db.all('SELECT * FROM '+t) for t in ('grants','model_calls','development_runs')}
                draft=self.prepare_repair(tid)
                for table,value in before.items():self.assertEqual(value,self.core.db.all('SELECT * FROM '+table))
                ident=self.begin_repair(tid,draft)['id'];spec=self.core.development.get(ident)['spec']
                self.assertFalse({c['input'] for c in spec['public_cases']}&{c['input'] for c in spec['evaluation_cases']})
                source="import json\ndef run(text):\n    v=json.loads(text)\n    "+logic+"\n    return json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))\n"
                provider=self.bind_repair(ident,source)
                result=self.core.development.execute(ident,True)
                self.assertEqual((result['status'],result['phase'],result['error']),('WAITING','verified','review_required'))
                for prompt in provider.prompts:
                    brief=decode(prompt)['instruction']['brief']
                    self.assertEqual(set(brief),{'goal','capability','contract','examples'})
                    self.assertEqual(brief['examples'],spec['public_cases'])
                self.assertIsNone(self.core.packages.slot(spec['capability']))
                for cap,binding in oldbindings.items():self.assertEqual(self.core.registry.binding(cap),binding)
                projection=refresh(self.core,tid)['learning_candidate']
                self.assertEqual(projection['repair']['id'],ident);self.assertEqual(projection['validation']['trial']['result']['status'],'FAILED')
                development.command(self.root,{'action':'approve','id':ident,'package_id':result['release_id']})
                done=self.core.development.execute(ident,True);self.assertEqual(done['status'],'SUCCEEDED')
                for cap,binding in oldbindings.items():self.assertEqual(self.core.registry.binding(cap),binding)
                self.assertFalse(refresh(self.core,tid)['learning_candidate']['repair']['original_tool_replaced'])

    def test_memorizing_public_counterexamples_is_rejected_by_private_inputs(self):
        _,tid=self.failed();draft=self.prepare_repair(tid);ident=self.begin_repair(tid,draft)['id']
        table={c['input']:c['expected'] for c in draft['public_cases']}
        self.bind_repair(ident,'def run(text):\n    return '+repr(table)+'.get(text,\'{}\')\n')
        result=self.core.development.execute(ident,True)
        self.assertEqual((result['status'],result['error']),('FAILED','development_attempts'))
        self.assertIsNone(self.core.packages.slot(draft['capability']))

    def test_idempotency_cancel_and_expired_original_grant_do_not_reset_authority(self):
        _,tid=self.failed();draft=self.prepare_repair(tid)
        original=self.core.tasks.get(tid)['body']['grant_id'];self.core.grants.revoke(original)
        # All outgoing material is host-generated synthetic data. A new explicit
        # development authorization never renews or executes the source grant.
        ident=self.begin_repair(tid,draft)['id'];snapshot=self.core.db.all('SELECT * FROM grants')
        self.assertEqual(self.begin_repair(tid,draft),{'id':ident,'existing':True})
        self.assertEqual(snapshot,self.core.db.all('SELECT * FROM grants'))
        development.command(self.root,{'action':'revoke','id':ident})
        self.assertEqual(self.begin_repair(tid,draft)['id'],ident)
        self.assertEqual(self.core.development.get(ident)['status'],'CANCELLED')
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(original,))['revoked'],1)
        self.assertEqual(len(self.core.db.all('SELECT * FROM events WHERE kind=?',(EVENT,))),1)

    def test_changed_or_withdrawn_source_rejects_new_development_before_grant(self):
        goal,tid=self.failed();draft=self.prepare_repair(tid);before=self.core.db.all('SELECT * FROM grants')
        for changes in ({'fingerprint':'stale'},{'reviewed':False}):
            with self.assertRaises(CoreError):self.begin_repair(tid,draft,**changes)
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET enabled=0 WHERE goal_id=?',(goal,))
        with self.assertRaises(CoreError):self.begin_repair(tid,draft)
        self.assertEqual(before,self.core.db.all('SELECT * FROM grants'));self.assertFalse(self.core.db.all('SELECT * FROM development_runs'))

    def test_provenance_failure_rolls_back_run_control_and_grant(self):
        _,tid=self.failed();draft=self.prepare_repair(tid)
        from host.lesson_repair import begin
        before={t:self.core.db.all('SELECT * FROM '+t) for t in ('grants','development_runs','development_controls')}
        event=self.core.db.event
        def fail(tx,task,kind,data):
            if kind==EVENT:raise RuntimeError('fixture audit failure')
            return event(tx,task,kind,data)
        with patch.object(self.core.db,'event',fail),self.assertRaises(RuntimeError):
            begin(self.core,{'id':tid,'key':draft['key'],'fingerprint':draft['fingerprint'],'routes':ROUTES,'reviewed':True})
        for table,rows in before.items():self.assertEqual(rows,self.core.db.all('SELECT * FROM '+table))
        self.assertFalse(self.begin_repair(tid,draft)['existing'])

    def test_missing_review_control_cannot_publish_repair_grant(self):
        _,tid=self.failed();draft=self.prepare_repair(tid);ident=self.begin_repair(tid,draft)['id']
        with self.core.db.transaction() as tx:tx.execute('DELETE FROM development_controls WHERE run_id=?',(ident,))
        with self.assertRaises(CoreError) as raised:self.core._publication_check(ident,'unused')
        self.assertEqual(raised.exception.code,'review_required')

    def test_managed_native_repair_uses_model_gate_without_external_action_gate(self):
        from control.network import NetworkGate
        _,tid=self.failed();draft=self.prepare_repair(tid);ident=self.begin_repair(tid,draft)['id']
        logic=TOOLS['practice'][2]
        source="import json\ndef run(text):\n    v=json.loads(text)\n    "+logic+"\n    return json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))\n"
        provider=self.bind_repair(ident,source)
        with patch('host.core.NativeModel',return_value=provider),patch.object(NetworkGate,'require_online',side_effect=AssertionError('external gate used')),patch.object(NetworkGate,'require_model_online',autospec=True) as gate:
            result=self.core.develop(ident,True)
        self.assertEqual(result['error'],'review_required');self.assertGreaterEqual(gate.call_count,2)

    def test_missing_optional_repair_run_does_not_invalidate_original_assessment(self):
        _,tid=self.failed();draft=self.prepare_repair(tid);self.begin_repair(tid,draft)
        with patch.object(self.core.development,'get',side_effect=CoreError('not_found','Missing repair run')):
            result=refresh(self.core,tid)
        self.assertEqual(result['condition_score'],100)
        self.assertEqual(result['learning_candidate']['repair']['status'],'UNAVAILABLE')
        self.assertEqual(result['learning_candidate']['validation']['trial']['result']['status'],'FAILED')

for name in ('setUp','tearDown','publish','req','detail','plan','code','source','seed','create','edit_source','rules','candidate','enable'):
    setattr(LessonRepairTests,name,getattr(fixture.LessonValidationTests,name))

if __name__=='__main__':unittest.main()
