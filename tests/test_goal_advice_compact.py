"""Versioned model projections preserve host evidence and recorded model inputs."""
import copy,hashlib,unittest
from unittest.mock import patch
import test_goal_advice as fixtures
from host import goals,goal_context
from host.completion import refresh,command as feedback
from host.planning_advice import PlanningAdvice,KEY
from modules.context_knowledge.methods import model_projection
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError,canonical,decode,digest


class CompactAdvice(unittest.TestCase):
    setUp=fixtures.GoalAdvice.setUp
    tearDown=fixtures.GoalAdvice.tearDown
    publish=fixtures.GoalAdvice.publish
    req=fixtures.GoalAdvice.req
    detail=fixtures.GoalAdvice.detail
    plan=fixtures.GoalAdvice.plan
    approve=fixtures.GoalAdvice.approve
    code=fixtures.GoalAdvice.code
    source=fixtures.GoalAdvice.source
    seed=fixtures.GoalAdvice.seed
    create=fixtures.GoalAdvice.create
    edit_source=fixtures.GoalAdvice.edit_source
    complete=fixtures.GoalAdvice.complete
    rules=fixtures.GoalAdvice.rules

    def version(self,ident,version):
        context=goal_context.get(self.core,ident);context['view'][KEY]['version']=version
        with self.core.db.transaction() as tx:
            tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ident))

    def waiting(self,ident):
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))

    def test_new_goal_compacts_only_model_card_not_host_receipts_or_current_facts(self):
        self.seed();ident=self.create();context=goal_context.get(self.core,ident)
        self.assertEqual(context['view'][KEY]['version'],2)
        methods=goal_context.advice(self.core,ident);before=copy.deepcopy(context['view'][KEY])
        _,provider=self.plan(ident);body=decode(provider.prompts[0].rsplit('\n',1)[1])
        projected=body['conditional_advice'];self.assertEqual(projected['format'],'compact-v2')
        keep={'id','recipe','requires','summary','counterexamples','source_id','source_revision'}
        for full,short in zip(methods,projected['methods']):
            self.assertEqual(set(short),keep)
            self.assertEqual(short,{k:full[k] for k in keep})
            self.assertIn('evidence',full);self.assertIn('expires',full);self.assertIn('lineage_group',full)
        after=goal_context.get(self.core,ident)['view'][KEY]
        self.assertEqual({k:v for k,v in after.items() if k!='dispatch'},before)
        self.assertEqual(body['input_text'],'Jarvis 中文');self.assertEqual(body['applicable_background'],context['view']['facts'])
        self.assertFalse(projected['execution_authorized']);self.assertFalse(projected['verified'])
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])

    def test_legacy_full_message_and_cached_resume_are_byte_identical(self):
        self.seed();ident=self.create();self.version(ident,1)
        methods=goal_context.advice(self.core,ident);_,provider=self.plan(ident);prompt=provider.prompts[0]
        prefix,data=prompt.rsplit('\n',1);data=decode(data)
        self.assertEqual(hashlib.sha256((prefix+'\n').encode()).hexdigest(),'6869b275f01e8e51ae46d13bc915d395d62ec26785e50d178e959486ec2a8ff8')
        self.assertEqual(data['conditional_advice'],{'methods':methods,'advisory_only':True,'verified':False,'execution_authorized':False})
        calls=self.core.db.all('SELECT * FROM model_calls');grants=self.core.db.all('SELECT * FROM grants')
        dispatch=goal_context.get(self.core,ident)['view'][KEY]['dispatch'];self.waiting(ident)
        result,unused=self.plan(ident);self.assertEqual(result['status'],'REVIEW');self.assertEqual(unused.prompts,[])
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls);self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)
        self.assertEqual(goal_context.get(self.core,ident)['view'][KEY]['dispatch'],dispatch)
        self.assertEqual(dispatch['input_digest'],digest({'prompt':prompt,'schema':'goal-plan'}))

    def test_both_versions_keep_unknown_call_until_explicit_retry(self):
        for version in (1,2):
            with self.subTest(version=version):
                if version==1:self.seed()
                ident=self.create(request_id='unknown-format-'+str(version));self.version(ident,version)
                result,p=self.plan(ident,[{'status':'UNKNOWN','code':'timeout'}]);prompt=p.prompts[0]
                self.assertEqual(result['status'],'WAITING');calls=self.core.db.all('SELECT * FROM model_calls WHERE run_id=?',(ident,))
                result,unused=self.plan(ident);self.assertEqual(unused.prompts,[])
                self.assertEqual(self.core.db.all('SELECT * FROM model_calls WHERE run_id=?',(ident,)),calls)
                result,retry=self.plan(ident,retry=True);self.assertEqual(result['status'],'REVIEW');self.assertEqual(retry.prompts,[prompt])

    def test_recorded_v1_call_cannot_be_silently_rebound_as_compact(self):
        self.seed();ident=self.create();self.version(ident,1);self.plan(ident)
        old=goal_context.get(self.core,ident)['view'][KEY]['dispatch'];calls=self.core.db.all('SELECT * FROM model_calls')
        self.waiting(ident);self.version(ident,2);result,unused=self.plan(ident)
        self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(unused.prompts,[])
        self.assertEqual(goal_context.get(self.core,ident)['view'][KEY]['dispatch'],old)
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls)

    def test_missing_assembly_stamp_does_not_override_model_ledger_binding(self):
        self.seed();ident=self.create();self.version(ident,1);self.plan(ident)
        context=goal_context.get(self.core,ident);context['view'][KEY].pop('dispatch');context['view'][KEY]['version']=2
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ident))
        self.waiting(ident);result,unused=self.plan(ident)
        self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(unused.prompts,[])
        self.assertNotIn('dispatch',goal_context.get(self.core,ident)['view'][KEY])

    def test_v2_still_blocks_withdrawn_evidence_before_request(self):
        evidence,_,_=self.seed();ident=self.create();self.edit_source(evidence['id'],paused=True)
        result,provider=self.plan(ident);self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(provider.prompts,[])

    def test_managed_writer_waits_for_validated_protocol3_and_invalid_pin_fails_closed(self):
        self.seed();marker=self.root/'deployment/controller-protocol.json';marker.parent.mkdir(exist_ok=True)
        marker.write_text('{"schema":1,"minimum":2}')
        for protocol,version in ((2,1),(3,2)):
            with patch('control.controller_pin.read',return_value={'controller_protocol':protocol}) as checked:
                ident=self.create(request_id='managed-writer-'+str(protocol))
                self.assertEqual(goal_context.get(self.core,ident)['view'][KEY]['version'],version);checked.assert_called_once_with(self.root)
        before=self.core.db.all('SELECT * FROM goal_context')
        with patch('control.controller_pin.read',side_effect=CoreError('controller_integrity','changed controller')):
            self.code('controller_integrity',self.create)
        self.assertEqual(self.core.db.all('SELECT * FROM goal_context'),before)

    def test_legacy_counterevidence_holds_v2_method_family_and_can_be_reviewed(self):
        self.seed();ident=self.create();self.version(ident,1);tid=self.complete(ident);result=refresh(self.core,tid)
        feedback(self.core,{'action':'completion_feedback','id':tid,'request_id':'v1-failure-v2-hold','fingerprint':result['fingerprint'],
            'kind':'reject','note':'Keep this unresolved counterexample across message formats'})
        self.assertIsNone(self.detail(self.create(request_id='v2-after-v1-failure'))['planning_advice'])
        result=refresh(self.core,tid)
        feedback(self.core,{'action':'completion_feedback','id':tid,'request_id':'v1-review-v2-release','fingerprint':result['fingerprint'],
            'kind':'withdraw','note':'Explicit independent review withdraws the issue'})
        self.assertEqual(self.detail(self.create(request_id='v2-after-v1-review'))['planning_advice']['version'],2)

    def test_inheritance_preserves_parent_format_and_rejects_format_mismatch(self):
        self.seed();ident=self.create();self.version(ident,1);parent=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident)
        with self.core.db.transaction() as tx:
            child,_=Plans(self.core.db).create(self.req(request_id='v1-inherited-under-v2-writer'),parent['catalog'],parent['routes'],tx)
            inherited=goal_context.inherit_advice(self.core,Plans(self.core.db).get(child),parent,context)
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(child,'personal',1,canonical(inherited)))
        self.assertEqual(inherited[KEY]['version'],1);self.assertEqual(goal_context.advice(self.core,child),[])
        self.version(child,2);self.code('goal_context_changed',goal_context.check,self.core,child)

    def test_explicit_new_round_keeps_legacy_history_and_binds_v2(self):
        self.seed();ident=self.create();self.version(ident,1);self.plan(ident)
        old=copy.deepcopy(goal_context.get(self.core,ident)['view'][KEY])
        goal_context.amend(self.core,ident,Plans(self.core.db).get(ident)['revision'],'将当前文本转为大写并保存','Jarvis 中文')
        context=goal_context.get(self.core,ident);self.assertEqual(context['history'][-1][KEY],old)
        self.assertEqual(context['view'][KEY]['version'],2);self.assertNotIn('dispatch',context['view'][KEY])

    def test_projection_rejects_unknown_versions_and_does_not_mutate_full_methods(self):
        self.seed();ident=self.create();methods=goal_context.advice(self.core,ident);before=copy.deepcopy(methods)
        model_projection(methods,2);self.assertEqual(methods,before)
        for version in (True,0,4,'2',None):
            with self.subTest(version=version),self.assertRaises(CoreError):model_projection(methods,version)
        self.version(ident,4);self.code('goal_context_changed',goal_context.check,self.core,ident)


if __name__=='__main__':unittest.main()
