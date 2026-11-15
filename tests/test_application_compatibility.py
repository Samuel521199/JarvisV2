"""Controller preflight must block destructive feature loss before old-host drain."""
from pathlib import Path
import json,socket,sqlite3,tempfile,unittest,uuid
from unittest.mock import patch
from adapters.application_host import WorkbenchProcess
from control.application_compatibility import require_compatible
from host.core import Core
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments
from modules.release_recovery.application import Applications,build
from sdk.protocol import CoreError


class Driver:
    def __init__(self):self.live=None;self.events=[];self.on_health=lambda selected:None
    def start(self,record,selected,epoch):self.events.append(('start',selected['build']));self.live=selected['build']
    def health(self,selected,epoch):self.on_health(selected)
    def drain(self,selected,epoch):self.events.append(('drain',selected['build']))
    def stop(self,selected,epoch):self.events.append(('stop',selected['build']));self.live=None
    def activate(self,*args):pass


class ApplicationCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'data';Core.initialize(self.root).close()
        self.app=Applications(self.root);self.driver=Driver()

    def candidate(self,name,commitments=False,chat=False,advice=False,goal_advice=False,repair=False):
        source=self.base/name;(source/'apps/workbench').mkdir(parents=True)
        (source/'VERSION').write_text(name);(source/'apps/workbench/server.py').write_text('# synthetic protocol fixture')
        files=['VERSION','apps/workbench/server.py']
        if commitments or chat or advice or goal_advice or repair:
            (source/'config').mkdir();(source/'config/runtime-compatibility.json').write_text(json.dumps(
                {'schema':1,'commitments_schema':int(commitments),'assistant_commitments':chat}))
            files.append('config/runtime-compatibility.json')
        if advice:
            (source/'config/conditional-advice-compatibility.json').write_text(json.dumps({'schema':1,'conditional_advice_schema':1}))
            files.append('config/conditional-advice-compatibility.json')
        if goal_advice:
            (source/'config/goal-advice-compatibility.json').write_text(json.dumps({'schema':1,'goal_advice_schema':int(goal_advice)}))
            files.append('config/goal-advice-compatibility.json')
        if repair:
            (source/'config/repair-return-compatibility.json').write_text(json.dumps({'schema':1,'repair_return_schema':1}))
            files.append('config/repair-return-compatibility.json')
        archive=self.base/(name+'.zip');ident=build(source,files,archive,name)
        self.app.stage(archive);self.app.validate(ident,lambda _: {'passed':True,'scope':'synthetic protocol fixture'})
        return ident

    def note(self):
        with Commitments(self.root) as store:
            return store.command({'action':'create','id':uuid.uuid4().hex,'request_id':uuid.uuid4().hex,
                'title':'survive rollback','source':'synthetic note','due_at':None})

    def test_no_feature_data_allows_legacy_and_empty_store(self):
        old=self.candidate('old');self.app.adopt(old,self.driver)
        with Commitments(self.root):pass
        self.assertTrue(require_compatible(self.root,self.app.record(old)['path'])['compatible'])

    def test_repair_history_blocks_legacy_before_drain_even_after_cancellation(self):
        old=self.candidate('old');current=self.candidate('current',repair=True)
        self.app.adopt(old,self.driver);self.app.adopt(current,self.driver)
        for status in ('AUTHORIZED','CLOSED','CANCELLED','REGRESSED'):
            with self.subTest(status=status):
                core=Core(self.root)
                try:
                    with core.db.transaction() as tx:
                        core.db.event(tx,None,'learning.repair_return',{'status':status,'development_id':'fixture'})
                finally:core.close()
                before=self.app.state();events=list(self.driver.events)
                with self.assertRaises(CoreError) as error:self.app.rollback(self.driver)
                self.assertEqual(error.exception.code,'application_data_compatibility')
                self.assertEqual(self.app.state(),before);self.assertEqual(self.driver.events,events)
                self.assertTrue(require_compatible(self.root,self.app.record(current)['path'])['compatible'])

    def test_unknown_repair_schema_blocks_even_declared_reader(self):
        current=self.candidate('current',repair=True);core=Core(self.root)
        try:
            with core.db.transaction() as tx:core.db.event(tx,None,'learning.repair_return',{'schema':2})
        finally:core.close()
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(current)['path'])

    def test_existing_records_block_legacy_before_drain(self):
        old=self.candidate('old');current=self.candidate('current',True,True)
        self.app.adopt(old,self.driver);self.app.adopt(current,self.driver);self.note()
        before=self.app.state();events=list(self.driver.events)
        with self.assertRaises(CoreError) as error:self.app.rollback(self.driver)
        self.assertEqual(error.exception.code,'application_data_compatibility')
        self.assertEqual(self.app.state(),before);self.assertEqual(self.driver.events,events)
        self.assertEqual(self.driver.live,current)

    def test_existing_record_accepts_current_declaration(self):
        current=self.candidate('current',True,True);self.note()
        state=self.app.adopt(current,self.driver);self.assertEqual(state['active']['build'],current)

    def test_unknown_store_version_rejects_even_current_package(self):
        current=self.candidate('current',True,True);self.note()
        db=sqlite3.connect(self.root/'state/commitments.sqlite3')
        try:db.execute('PRAGMA user_version=3');db.commit()
        finally:db.close()
        with self.assertRaises(CoreError):self.app.adopt(current,self.driver)
        self.assertEqual(self.driver.events,[])

    def test_new_chat_actions_require_chat_reader_not_just_store_reader(self):
        store_only=self.candidate('store-only',True,False)
        chats=Dialogues(self.root)
        try:
            chat=chats.create();chats.begin({'chat_id':chat,'request_id':'new-action','text':'synthetic','provider':'fixture','model':'fixture','reasoning':'default'},[])
            chats.finish('new-action',{'status':'SUCCEEDED','text':'candidate','assistant_action':{'kind':'commitment'}})
        finally:chats.close()
        with self.assertRaises(CoreError):self.app.adopt(store_only,self.driver)
        self.assertEqual(self.driver.events,[])

    def test_failed_candidate_cannot_restore_incompatible_baseline(self):
        old=self.candidate('old');new=self.candidate('new',True,True);self.app.adopt(old,self.driver)
        def fail(selected):
            if selected['build']==new:self.note();raise RuntimeError('synthetic candidate failure after state creation')
        self.driver.on_health=fail
        with self.assertRaises(CoreError):self.app.adopt(new,self.driver)
        self.assertEqual(self.app.state()['phase'],'blocked')
        self.assertEqual(self.app.state()['error'],'baseline_data_incompatible')
        self.assertIsNone(self.driver.live)
        self.assertEqual([e for e in self.driver.events if e==('start',old)],[('start',old)])

    def test_process_adapter_cannot_bypass_preflight(self):
        old=self.candidate('old');self.note()
        with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        driver=WorkbenchProcess(self.root,port)
        with patch('adapters.application_host.subprocess.Popen') as process,self.assertRaises(CoreError):
            driver.start(self.app.record(old),{'build':old,'slot':'A'},1)
        process.assert_not_called()

    def test_data_created_during_drain_is_rechecked_before_candidate_start(self):
        old=self.candidate('old');current=self.candidate('current',True,True)
        self.app.adopt(old,self.driver);self.app.adopt(current,self.driver)
        original=self.driver.drain
        def drain(selected,epoch):
            original(selected,epoch);self.note()
        self.driver.drain=drain
        state=self.app.rollback(self.driver)
        self.assertEqual(state['active']['build'],current)
        self.assertEqual(self.driver.live,current)
        self.assertEqual([e for e in self.driver.events if e==('start',old)],[('start',old)])
        with Commitments(self.root) as db:self.assertEqual(len(db.listing()),1)

    def test_malformed_declaration_and_unknown_action_fail_closed(self):
        current=self.candidate('current',True,True);package=Path(self.app.record(current)['path'])
        path=package/'config/runtime-compatibility.json';path.write_text('{}')
        with self.assertRaises(CoreError):require_compatible(self.root,package)

        path.write_text(json.dumps({'schema':1,'commitments_schema':1,'assistant_commitments':True}))
        chats=Dialogues(self.root)
        try:
            chat=chats.create();chats.begin({'chat_id':chat,'request_id':'future-action','text':'synthetic','provider':'fixture','model':'fixture','reasoning':'default'},[])
            chats.finish('future-action',{'status':'SUCCEEDED','text':'unknown','assistant_action':{'kind':'future-action'}})
        finally:chats.close()
        with self.assertRaises(CoreError):require_compatible(self.root,package)

    def test_non_object_declaration_and_boolean_schema_fail_closed(self):
        current=self.candidate('typed-declaration',True,True);package=Path(self.app.record(current)['path'])
        path=package/'config/runtime-compatibility.json'
        for value in [None,[],[{}],True,{'schema':True,'commitments_schema':1,'assistant_commitments':True}]:
            path.write_text(json.dumps(value))
            with self.subTest(value=value),self.assertRaises(CoreError):require_compatible(self.root,package)

    def method_source(self,schema='jarvis.method-card.v1'):
        from modules.context_knowledge.knowledge import Knowledge
        core=Core(self.root)
        try:return Knowledge(core.db).save({'id':'','scope':'personal','title':'Synthetic method',
            'text':json.dumps({'schema':schema}),'providers':['fixture'],'paused':False},0)
        finally:core.close()

    def test_method_card_blocks_old_reader_before_drain_and_accepts_declared_reader(self):
        old=self.candidate('old-advice');new=self.candidate('new-advice',advice=True)
        self.app.adopt(old,self.driver);self.app.adopt(new,self.driver);self.method_source()
        before=self.app.state();events=list(self.driver.events)
        with self.assertRaises(CoreError):self.app.rollback(self.driver)
        self.assertEqual(self.app.state(),before);self.assertEqual(self.driver.events,events)
        self.assertTrue(require_compatible(self.root,self.app.record(new)['path'])['compatible'])

    def test_historical_card_cannot_be_hidden_by_editing_current_source_to_plain_text(self):
        new=self.candidate('advice-history',advice=True);old=self.candidate('no-advice-history');saved=self.method_source()
        from modules.context_knowledge.knowledge import Knowledge
        core=Core(self.root)
        try:Knowledge(core.db).save({'id':saved['id'],'scope':'personal','title':'Changed to ordinary source','text':'Current plain text',
            'providers':['fixture'],'paused':False},1)
        finally:core.close()
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(old)['path'])
        self.assertTrue(require_compatible(self.root,self.app.record(new)['path'])['compatible'])

    def test_unknown_advice_version_and_boolean_declaration_are_not_compatible(self):
        new=self.candidate('future-advice',advice=True);self.method_source('jarvis.method-card.v2')
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(new)['path'])
        # A current v1 source also cannot be served by a boolean "version".
        other=self.base/'other';Core.initialize(other).close()
        from modules.context_knowledge.knowledge import Knowledge
        core=Core(other)
        try:Knowledge(core.db).save({'id':'','scope':'personal','title':'v1','text':'{"schema":"jarvis.method-card.v1"}',
            'providers':['fixture'],'paused':False},0)
        finally:core.close()
        path=Path(self.app.record(new)['path'])/'config/conditional-advice-compatibility.json'
        path.write_text('{"schema":true,"conditional_advice_schema":1}')
        with self.assertRaises(CoreError):require_compatible(other,self.app.record(new)['path'])

    def test_method_created_during_drain_restores_the_compatible_current_reader(self):
        old=self.candidate('old-advice-drain');new=self.candidate('new-advice-drain',advice=True)
        self.app.adopt(old,self.driver);self.app.adopt(new,self.driver)
        original=self.driver.drain
        def drain(selected,epoch):original(selected,epoch);self.method_source()
        self.driver.drain=drain
        result=self.app.rollback(self.driver)
        self.assertEqual(result['active']['build'],new);self.assertEqual(self.driver.live,new)
        self.assertEqual([e for e in self.driver.events if e==('start',old)],[('start',old)])

    def test_failed_candidate_cannot_restore_old_reader_after_new_method_data(self):
        old=self.candidate('old-advice-fail');new=self.candidate('new-advice-fail',advice=True)
        self.app.adopt(old,self.driver)
        def fail(selected):
            if selected['build']==new:self.method_source();raise RuntimeError('Synthetic failure after method creation')
        self.driver.on_health=fail
        with self.assertRaises(CoreError):self.app.adopt(new,self.driver)
        self.assertEqual(self.app.state()['phase'],'blocked');self.assertIsNone(self.driver.live)
        core=Core(self.root)
        try:self.assertEqual(core.db.one('SELECT count(*) AS n FROM knowledge_sources')["n"],1)
        finally:core.close()


    def goal_advice_context(self,version=1,historical=False):
        from modules.task_resource.plans import Plans
        from sdk.protocol import canonical
        core=Core(self.root)
        try:
            with core.db.transaction() as tx:
                ident,_=Plans(core.db).create({'request_id':'goal-advice-protocol-'+str(version),'goal':'Synthetic advice goal'},[],[],tx)
                view={'conditional_advice':{'version':version}};history=[]
                if historical:history=[view];view={'redacted':True}
                tx.execute('INSERT INTO goal_context VALUES(?,?,?,?,?)',(ident,'personal',1,canonical(view),canonical(history)))
        finally:core.close()

    def test_goal_advice_blocks_old_reader_before_drain_without_live_source_cards(self):
        old=self.candidate('old-goal-advice');new=self.candidate('new-goal-advice',goal_advice=True)
        self.app.adopt(old,self.driver);self.app.adopt(new,self.driver);self.goal_advice_context()
        before=self.app.state();events=list(self.driver.events)
        with self.assertRaises(CoreError):self.app.rollback(self.driver)
        self.assertEqual(self.app.state(),before);self.assertEqual(self.driver.events,events)
        self.assertTrue(require_compatible(self.root,self.app.record(new)['path'])['compatible'])

    def test_historical_goal_advice_retains_compatibility_requirement(self):
        old=self.candidate('old-goal-history');new=self.candidate('new-goal-history',goal_advice=True)
        self.goal_advice_context(historical=True)
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(old)['path'])
        self.assertEqual(require_compatible(self.root,self.app.record(new)['path'])['required']['goal_advice_schema'],1)

    def test_unknown_goal_advice_version_is_rejected(self):
        new=self.candidate('new-goal-unknown',goal_advice=True);self.goal_advice_context(version=5)
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(new)['path'])

    def test_boolean_goal_advice_declaration_is_rejected(self):
        new=self.candidate('new-goal-boolean',goal_advice=True);self.goal_advice_context()
        path=Path(self.app.record(new)['path'])/'config/goal-advice-compatibility.json'
        path.write_text('{"schema":1,"goal_advice_schema":true}')
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(new)['path'])

    def test_compact_data_blocks_v1_reader_before_drain_and_accepts_v2_reader(self):
        old=self.candidate('full-v1-reader',goal_advice=True);ident=self.candidate('compact-v2-reader',goal_advice=2)
        self.app.adopt(old,self.driver);self.app.adopt(ident,self.driver);self.goal_advice_context(version=2)
        before=self.app.state();events=list(self.driver.events)
        with self.assertRaises(CoreError):self.app.rollback(self.driver)
        self.assertEqual(self.app.state(),before);self.assertEqual(self.driver.events,events)
        self.assertEqual(require_compatible(self.root,self.app.record(ident)['path'])['required']['goal_advice_schema'],2)

    def test_historical_v2_requirement_survives_current_v1_and_redaction(self):
        from sdk.protocol import canonical
        old=self.candidate('history-v1-reader',goal_advice=True);self.goal_advice_context(version=2,historical=True)
        core=Core(self.root)
        try:
            with core.db.transaction() as tx:
                tx.execute('UPDATE goal_context SET view=?',(canonical({'conditional_advice':{'version':1}}),))
        finally:core.close()
        with self.assertRaises(CoreError):require_compatible(self.root,self.app.record(old)['path'])
        package=Path(self.app.record(old)['path']);marker=package/'config/goal-advice-compatibility.json'
        marker.write_text('{"schema":1,"goal_advice_schema":2}')
        self.assertEqual(require_compatible(self.root,package)['required']['goal_advice_schema'],2)
        for value in [True,5,0,'2']:
            marker.write_text(json.dumps({'schema':1,'goal_advice_schema':value}))
            with self.subTest(value=value),self.assertRaises(CoreError):require_compatible(self.root,package)
