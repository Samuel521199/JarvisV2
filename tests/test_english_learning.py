"""Actual answer binding, cross-chat scheduling, revocation and queue preservation."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from host.core import Core
from host.dialogue import DialogueHost
from host import english_learning as learning
from modules.dialogue.store import Dialogues
from modules.english_learning.store import Store,DAY,progress,schedule
from modules.preferences.store import resolve
from modules.skills.catalog import Skills
from sdk.protocol import CoreError,canonical
from test_preferences_dialogue import fixture


def record(ident,when,**kwargs):
    return {'target':'life.request','difficulty':1,'created':when,'answer_turn':ident,'prompt':'prompt '+ident,'assistance':'independent','hints':0,'exposed':0,'meaning':2,'form':2,'appropriacy':2,'confidence':'high',**kwargs}


class Scheduling(unittest.TestCase):
    def test_same_day_repetition_does_not_expand_review_or_prove_progress(self):
        rows=[record(str(i),100+i) for i in range(8)]
        self.assertEqual(schedule(rows,200)['life.request']['stage'],1)
        self.assertEqual(progress(rows)['trend_state'],'insufficient_comparable_samples')
        self.assertEqual(progress(rows)['domains']['life']['delayed_variants'],0)
    def test_delayed_variants_advance_and_assistance_never_counts_as_independent(self):
        rows=[record('a',100),record('b',DAY+100)]
        self.assertEqual(schedule(rows)['life.request']['stage'],2)
        rows.append(record('c',2*DAY+100,hints=1))
        self.assertEqual(schedule(rows)['life.request']['stage'],0)
        self.assertEqual(progress(rows)['domains']['life']['independent'],2)
        self.assertEqual(progress(rows)['domains']['life']['assisted'],1)
    def test_progress_requires_disjoint_comparable_delayed_samples(self):
        rows=[record(str(i),DAY*i) for i in range(6)]
        self.assertEqual(len(progress(rows)['trends']),1)
        self.assertEqual(progress(rows)['trends'][0]['sample_sizes'],[3,3])
        rows[-1]['difficulty']=2
        self.assertFalse(progress(rows)['trends'])
    def test_repeated_exact_prompt_cannot_raise_spaced_stage(self):
        rows=[record(str(i),DAY*i,prompt='same') for i in range(6)]
        self.assertEqual(schedule(rows)['life.request']['stage'],1)
        self.assertFalse(progress(rows)['trends'])


    def test_repair_wording_does_not_make_the_same_software_task_a_new_delayed_variant(self):
        rows=[record(str(i),DAY*i,prompt='repair wording '+str(i),game={'software':{'id':'english-city'},'scene':'cafe','node':0}) for i in range(6)]
        self.assertEqual(schedule(rows)['life.request']['stage'],1)
        self.assertEqual(progress(rows)['domains']['life']['delayed_variants'],0)
        self.assertFalse(progress(rows)['trends'])


class LearningFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-english-');self.root=Path(self.temp.name)
        self.core=Core.initialize(self.root);self.settings=fixture();self.core.preferences.install(self.settings,{})
        self.host=DialogueHost(self.root);self.chats=Dialogues(self.root);self.chat=self.chats.create();self.calls=[]
        outer=self
        class Runner:
            def submit(self,command):
                skills=Skills(outer.root)
                try:outer.chats.begin(command,[resolve(outer.settings,'openai')],skills.select('english-coach',command['text']))
                finally:skills.close()
                return {'request_id':command['request_id']}
        self.runner=Runner()
        self.call({'action':'configure','enabled':True,'revision':0})
    def tearDown(self):
        self.host.close();self.chats.close();self.core.close();self.temp.cleanup()
    def call(self,body):return learning.command(self.root,body,self.runner)
    def start(self,ident='english-question',chat=None,**kwargs):
        return self.call({'action':'start','request_id':ident,'chat_id':chat or self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','domain':'life','study_text':'',**kwargs})
    def answer(self,ident='english-answer',question='english-question',text='Could I have a box, please?',**kwargs):
        return self.call({'action':'answer','request_id':ident,'chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':question,'answer':text,'assistance':'independent',**kwargs})
    def run_reply(self,ident,payload):
        seen=self.calls
        class Client:
            def __init__(self,*args):pass
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();seen.append(messages)
                return {'status':'SUCCEEDED','text':canonical(payload),'usage':{'total_tokens':12}}
        with patch('host.dialogue.NativeModel',Client):self.host.run(ident)
    def question(self,ident='english-question',prompt='请用英语礼貌请求打包盒。'):
        self.start(ident);self.run_reply(ident,{'schema':learning.FORMAT,'prompt':prompt,'reference':'Could I have a box, please?','hint':'先表达请求，再说需要的物品。'})
    def rating(self,text='Could I have a box, please?',**kwargs):
        return {'schema':learning.FORMAT,'answer_quote':text,'meaning':2,'form':2,'appropriacy':2,'confidence':'high','feedback':'意思清楚，表达礼貌。','correction':'Could I have a box, please?','memory_cue':'把请求句与点餐情境联想。','error_tags':[],**kwargs}
    def test_cross_chat_reopen_keeps_real_answer_and_does_not_create_tasks(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating())
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],1)
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        fresh=Store(self.root)
        try:self.assertEqual(json.loads(fresh.db.execute('SELECT body FROM assessments').fetchone()[0])['answer'],'Could I have a box, please?')
        finally:fresh.close()
        second=self.chats.create();self.start('english-second',chat=second)
        self.assertTrue(learning.binding(self.root,'english-second'))
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],1)
    def test_hint_reveal_and_user_assistance_cannot_count_independent(self):
        self.question();self.call({'action':'hint','exercise_id':'english-question'})
        self.call({'action':'reveal','exercise_id':'english-question'})
        self.answer();self.run_reply('english-answer',self.rating())
        stats=self.call({'action':'status'})['progress']['domains']['life']
        self.assertEqual((stats['independent'],stats['assisted']),(0,1))
    def test_fabricated_quote_and_bool_score_rejected_without_losing_cost_receipt(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating('invented answer'))
        self.assertEqual(self.chats.turn('english-answer')['status'],'FAILED')
        self.assertEqual(self.chats.db.execute('SELECT usage FROM attempts WHERE turn_id=?',('english-answer',)).fetchone()[0],canonical({'total_tokens':12}))
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],0)
        job=learning.binding(self.root,'english-answer')
        with self.assertRaises(CoreError):learning.parse(canonical(self.rating(meaning=True)),job)
    def test_same_request_id_is_idempotent_and_different_body_conflicts(self):
        self.question();self.answer();self.answer()
        self.assertEqual(self.chats.db.execute("SELECT count(*) FROM turns WHERE id='english-answer'").fetchone()[0],1)
        with self.assertRaises(CoreError):self.answer(text='Different')
        self.run_reply('english-answer',self.rating());self.answer()
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],1)
    def test_dispute_withdraw_and_removed_source_exclude_rating(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating())
        self.call({'action':'dispute','assessment_id':'english-answer'})
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],0)
        self.call({'action':'withdraw','exercise_id':'english-question'})
        self.assertEqual(self.call({'action':'status'})['exercises'],[])
    def test_deleted_chat_invalidates_learning_sources(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating());self.chats.update(self.chat,{'removed':True})
        state=self.call({'action':'status'});self.assertEqual(state['progress']['domains']['life']['attempts'],0);self.assertFalse(state['exercises'])
    def test_redacted_source_reply_invalidates_rating_and_cross_chat_context(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating())
        self.chats.db.execute("UPDATE turns SET reply='[withdrawn source]' WHERE id='english-question'")
        state=self.call({'action':'status'});self.assertEqual(state['progress']['domains']['life']['attempts'],0)
        self.start('english-new',chat=self.chats.create())
        job=learning.binding(self.root,'english-new')
        self.assertFalse(job['body']['background']);self.assertFalse(job['body']['previous_prompts'])
    def test_unseen_work_example_must_be_labelled_and_memory_is_bounded(self):
        self.start('english-work',domain='work')
        job=learning.binding(self.root,'english-work')
        with self.assertRaises(CoreError):learning.parse(canonical({'schema':learning.FORMAT,'prompt':'Read this company memo.','reference':'Friday','hint':'Check the deadline.'}),job)
        value,reply=learning.parse(canonical({'schema':learning.FORMAT,'prompt':'教学示例：The meeting is on Friday. What day?','reference':'Friday','hint':'找表示日期的词。'}),job)
        self.assertNotIn('参考答案',reply)
    def test_low_confidence_retains_original_answer_but_does_not_schedule_as_failure(self):
        self.question();self.answer();self.run_reply('english-answer',self.rating(confidence='low'))
        state=self.call({'action':'status'});self.assertEqual(state['withheld_assessments'],1)
        self.assertEqual(state['exercises'][0]['assessment']['answer'],'Could I have a box, please?')
        self.assertEqual(state['progress']['domains']['life']['attempts'],0)
    def test_no_actual_answer_never_counts_as_studied(self):
        self.question();self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],0)
        with self.assertRaises(CoreError):self.answer(text='   ')
        with self.assertRaises(CoreError):self.start('english-review',domain='mistakes')
    def test_disable_or_hint_during_call_discards_late_grade(self):
        self.question();self.answer();self.call({'action':'hint','exercise_id':'english-question'})
        self.run_reply('english-answer',self.rating())
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],0)
        self.assertNotEqual(self.chats.turn('english-answer')['status'],'SUCCEEDED')
    def test_reconcile_after_delivery_crash_never_calls_model_twice(self):
        self.question();self.answer()
        with patch('host.english_learning.completed',side_effect=OSError('crash after durable reply')):self.run_reply('english-answer',self.rating())
        self.assertEqual(learning.binding(self.root,'english-answer')['state'],'PENDING')
        self.assertEqual(self.call({'action':'status'})['progress']['domains']['life']['attempts'],1)
        self.assertEqual(len(self.calls),2)
    def test_unknown_answer_is_not_replayed_or_graded(self):
        self.question();self.answer();self.chats.finish('english-answer',{'status':'UNKNOWN','code':'interrupted'})
        state=self.call({'action':'status'});self.assertEqual(state['progress']['domains']['life']['attempts'],0)
        with self.assertRaises(CoreError):self.answer(ident='english-new-answer')
    def test_old_package_is_rejected_even_when_learning_disabled(self):
        from control.application_compatibility import require_compatible
        self.call({'action':'configure','enabled':False,'revision':1})
        package=self.root/'old-package';package.mkdir()
        with self.assertRaises(CoreError) as error:require_compatible(self.root,package)
        self.assertEqual(error.exception.code,'application_data_compatibility')
    def test_compatible_reader_and_unknown_schema_fail_closed(self):
        from control.application_compatibility import require_compatible
        package=self.root/'reader';(package/'config').mkdir(parents=True)
        declaration=package/'config/english-learning-compatibility.json'
        declaration.write_text('{"schema":1,"english_learning_schema":3}')
        self.assertTrue(require_compatible(self.root,package)['compatible'])
        declaration.write_text('{"schema":true,"english_learning_schema":3}')
        with self.assertRaises(CoreError):require_compatible(self.root,package)
        store=Store(self.root)
        store.db.execute('PRAGMA user_version=99');store.close()
        with self.assertRaises(CoreError):Store(self.root)
    def test_controller6_cannot_write_new_learning_records_in_managed_installation(self):
        (self.root/'deployment').mkdir(exist_ok=True)
        (self.root/'deployment/launcher.json').write_text('{}')
        with patch('control.controller_pin.read',return_value={'controller_protocol':6}):
            with self.assertRaises(CoreError):self.call({'action':'status'})
    def test_unrelated_chat_does_not_open_a_broken_learning_store(self):
        store=Store(self.root);store.db.execute('PRAGMA user_version=99');store.close()
        self.assertIsNone(learning.binding(self.root,'ordinary-user-turn'))
    def test_withdrawn_question_is_rechecked_before_using_its_variant_context(self):
        self.question();self.start('english-variant')
        self.call({'action':'withdraw','exercise_id':'english-question'})
        with self.assertRaises(CoreError):learning.context(self.root,self.chats.turn('english-variant'))
    def test_learning_context_obeys_the_actual_native_gateway_contract(self):
        from adapters.models.native import NativeModel
        self.start()
        messages=learning.context(self.root,self.chats.turn('english-question'))
        def unavailable(*args):raise CoreError('credential_missing','No test credentials')
        model=NativeModel({'adapter':'openai','id':'not-configured'},unavailable)
        self.assertEqual(model.complete(messages)['code'],'credential_unavailable')
        self.assertLessEqual(len(canonical(messages).encode()),24000)
    def test_supplied_work_source_cannot_be_replaced_by_an_unrelated_notice(self):
        source='Please submit your report by Thursday at 3 p.m.'
        self.start('english-source',domain='work',study_text=source)
        job=learning.binding(self.root,'english-source')
        value={'schema':learning.FORMAT,'prompt':'When is the report due?','reference':'By Thursday at 3 p.m.','hint':'Look for the deadline.','source_quote':'Thursday at 3 p.m.'}
        result,reply=learning.parse(canonical(value),job)
        self.assertIn(source,result['prompt']);self.assertIn(source,reply)
        value['source_quote']='Friday at 8 p.m.'
        with self.assertRaises(CoreError):learning.parse(canonical(value),job)

    def test_oral_recording_bound_to_answer_separate_from_written_progress(self):
        import base64,io,wave
        raw=io.BytesIO()
        with wave.open(raw,'wb') as audio:
            audio.setparams((1,2,16000,16000,'NONE','not compressed'));audio.writeframes(b'\x00\x00'*16000)
        saved=self.call({'action':'record','audio':base64.b64encode(raw.getvalue()).decode()})['recording']
        self.question()
        self.call({'action':'oral_answer','request_id':'english-spoken-answer','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-question','answer':'Could I have a box, please?','assistance':'independent','audio_id':saved['id']})
        self.run_reply('english-spoken-answer',self.rating())
        state=self.call({'action':'status'})
        self.assertEqual(state['progress']['domains']['life']['attempts'],0)
        self.assertEqual(state['oral_progress']['domains']['life']['attempts'],1)
        self.assertIsNone(state['exercises'][0]['assessment']['speech']['pronunciation_score'])
        restored=self.call({'action':'recording','exercise_id':'english-question'})
        self.assertEqual(base64.b64decode(restored['audio']),raw.getvalue())
        self.assertNotIn(saved['sha256'],str(self.calls))
        original=self.chats.turn('english-spoken-answer')['reply']
        self.chats.db.execute('UPDATE turns SET reply=? WHERE id=?',('redacted','english-spoken-answer'))
        with self.assertRaises(CoreError):self.call({'action':'recording','exercise_id':'english-question'})
        with self.assertRaises(CoreError):self.call({'action':'speak','exercise_id':'english-question'})
        self.chats.db.execute('UPDATE turns SET reply=? WHERE id=?',(original,'english-spoken-answer'))
        self.call({'action':'withdraw','exercise_id':'english-question'})
        with self.assertRaises(CoreError):self.call({'action':'recording','exercise_id':'english-question'})
        self.assertEqual(self.call({'action':'status'})['oral_progress']['domains']['life']['attempts'],0)

    def test_invalid_audio_and_recording_paths_rejected(self):
        from host.english_audio import inspect,read
        with self.assertRaises(CoreError):inspect(b'not wave')
        with self.assertRaises(CoreError):read(self.root,'../../private/key')

if __name__=='__main__':unittest.main()
