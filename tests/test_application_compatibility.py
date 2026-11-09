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

    def candidate(self,name,commitments=False,chat=False):
        source=self.base/name;(source/'apps/workbench').mkdir(parents=True)
        (source/'VERSION').write_text(name);(source/'apps/workbench/server.py').write_text('# synthetic protocol fixture')
        files=['VERSION','apps/workbench/server.py']
        if commitments or chat:
            (source/'config').mkdir();(source/'config/runtime-compatibility.json').write_text(json.dumps(
                {'schema':1,'commitments_schema':int(commitments),'assistant_commitments':chat}))
            files.append('config/runtime-compatibility.json')
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
