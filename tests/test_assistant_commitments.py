"""Chat admission uses original user text, current scope and durable local receipts."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from host.core import Core
from host import assistant, commitments
from host.assistant_commitments import record_id
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments
from modules.task_resource.commitment_intent import resolve
from sdk.protocol import CoreError, canonical, decode


class AssistantCommitments(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);Core.initialize(self.root).close()
        store=Dialogues(self.root)
        try:self.chat=store.create()
        finally:store.close()

    def turn(self,text,*,title='回邮件',operation='create',target='',basis='',chat=None,quote=None):
        chat=chat or self.chat;ident='turn-'+uuid.uuid4().hex
        payload={'schema':'jarvis.assistant-turn.v1','reply':'模型说已保存，这句话不能当回执',
            'action':{'kind':'commitment','goal':'','input_text':'','target':target,'commitment':{
                'operation':operation,'title':title,'quote':text if quote is None else quote,
                'due_at':'2099-01-01T15:00:00+08:00','time_text':'模型猜的时间','basis_turn':basis}}}
        reply,action=assistant.parse(canonical(payload),assistant.context(self.root,chat))
        self.assertNotIn('已保存',reply)
        store=Dialogues(self.root)
        try:
            store.begin({'chat_id':chat,'request_id':ident,'text':text,'provider':'fixture','model':'fixture',
                'reasoning':'default','assistant_mode':True},[])
            store.finish(ident,{'status':'SUCCEEDED','text':reply,'assistant_action':action})
        finally:store.close()
        return ident

    def test_explicit_time_auto_saved_once_and_model_clock_ignored(self):
        ident=self.turn('2030-01-01T12:00:00+08:00提醒我回邮件')
        result=assistant.commitment_from_turn(self.root,ident)
        self.assertEqual(result['mode'],'APPLIED');self.assertEqual(result['receipt']['current']['due_text'],'2030-01-01T12:00:00+08:00')
        again=assistant.accept(self.root,{'turn_id':ident})
        self.assertEqual(again['receipt']['id'],result['receipt']['id'])
        detail=commitments.detail(self.root,result['receipt']['id'])
        self.assertEqual(detail['source_kind'],'chat_turn');self.assertEqual(detail['conversation_origin']['turn_id'],ident)
        with Commitments(self.root) as store:
            self.assertEqual(len(store.listing()),1);self.assertEqual(len(store.history(result['receipt']['id'])),1)
            self.assertEqual(store.origin(result['receipt']['id'])['chat_id'],self.chat)

    def test_plain_todo_without_time_is_not_fake_timed_reminder(self):
        ident=self.turn('帮我记个待办：整理资料',title='整理资料')
        result=assistant.commitment_from_turn(self.root,ident)
        self.assertEqual(result['mode'],'APPLIED');self.assertIsNone(result['receipt']['current']['due_at'])

    def test_local_english_and_existing_target_wrappers_keep_literal_authority(self):
        for text in ['Remind me locally at 2036-06-11T10:35:00-04:00 to verify the plant labels.',
                     'Set a local reminder for 2036-06-11T10:35:00-04:00 to verify the plant labels.']:
            ident=self.turn(text,title='verify the plant labels')
            receipt=assistant.commitment_from_turn(self.root,ident)
            self.assertEqual(receipt['mode'],'APPLIED')
            target=receipt['receipt']['id']
            edited=self.turn('Cancel the existing to-do verify the plant labels.',title='verify the plant labels',operation='cancel',target=target)
            self.assertEqual(assistant.commitment_from_turn(self.root,edited)['receipt']['current']['status'],'CANCELLED')
        created=self.turn('记个待办：核对植物标签',title='核对植物标签')
        target=assistant.commitment_from_turn(self.root,created)['receipt']['id']
        moved=self.turn('将“核对植物标签”的时间重新安排为 2036-07-19T17:40:00+05:30。',title='核对植物标签',operation='reschedule',target=target)
        self.assertEqual(assistant.commitment_from_turn(self.root,moved)['mode'],'APPLIED')
        stopped=self.turn('请取消现有的待办事项“核对植物标签”。',title='核对植物标签',operation='cancel',target=target)
        self.assertEqual(assistant.commitment_from_turn(self.root,stopped)['receipt']['current']['status'],'CANCELLED')

    def test_new_wrappers_do_not_authorize_negation_conditions_or_extra_actions(self):
        from modules.task_resource.commitment_intent import interpret
        for text in ['Do not cancel the existing to-do verify the plant labels.',
                     'If ready cancel the existing to-do verify the plant labels.',
                     '请不要取消现有的待办事项“核对植物标签”。',
                     '请取消现有的待办事项“核对植物标签”，然后发送邮件。']:
            decision=interpret(text,'cancel','核对植物标签',0,target_title='核对植物标签',active_count=1)
            self.assertNotEqual(decision['mode'],'AUTO')

    def test_vague_time_does_not_default_to_model_clock(self):
        ident=self.turn('明天下午提醒我回邮件')
        result=assistant.commitment_from_turn(self.root,ident)
        self.assertEqual(result['mode'],'NEEDS_TIME');self.assertFalse(commitments.exists(self.root))
        with self.assertRaises(CoreError):assistant.confirm_commitment(self.root,{'turn_id':ident,'due_at':None})

    def test_clarification_links_original_request_and_cannot_duplicate(self):
        parent=self.turn('明天下午提醒我回邮件')
        first=self.turn('15:00 UTC+08:00',basis=parent)
        competing=self.turn('16:00 UTC+08:00',basis=parent)
        result=assistant.commitment_from_turn(self.root,first)
        self.assertEqual(result['mode'],'APPLIED');self.assertEqual(result['receipt']['id'],record_id(parent))
        self.assertTrue(result['receipt']['current']['due_text'].endswith('T15:00:00+08:00'))
        self.assertEqual(assistant.commitment_from_turn(self.root,parent)['mode'],'APPLIED')
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,competing)
        with Commitments(self.root) as store:self.assertEqual(len(store.listing()),1)

    def test_quoted_negative_and_conditional_messages_do_not_auto_execute(self):
        for text in ['不要记个待办：回邮件','例如“2030-01-01T12:00:00+08:00提醒我回邮件”',
                     '如果明天有空再提醒我回邮件','解释提醒我回邮件是什么意思']:
            with self.subTest(text=text):
                ident=self.turn(text)
                self.assertNotEqual(assistant.commitment_from_turn(self.root,ident)['mode'],'APPLIED')
        self.assertFalse(commitments.exists(self.root))

    def test_forged_source_quote_is_rejected_before_write(self):
        ident=self.turn('这是一个例子',quote='2030-01-01T12:00:00+08:00提醒我回邮件')
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,ident)
        self.assertFalse(commitments.exists(self.root))

    def test_personal_only_archived_and_redacted_source_rejected(self):
        ident=self.turn('帮我记个待办：回邮件')
        store=Dialogues(self.root)
        try:store.update(self.chat,{'archived':True})
        finally:store.close()
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,ident)
        store=Dialogues(self.root)
        try:
            store.update(self.chat,{'archived':False});store.db.execute('UPDATE chats SET project_id=? WHERE id=?',('unregistered-project',self.chat))
        finally:store.close()
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,ident)
        store=Dialogues(self.root)
        try:
            store.db.execute("UPDATE chats SET project_id='' WHERE id=?",(self.chat,))
            store.db.execute('UPDATE turns SET assistant_action=NULL WHERE id=?',(ident,))
        finally:store.close()
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,ident)
        self.assertFalse(commitments.exists(self.root))

    def test_reschedule_and_cancel_current_same_chat_commitment(self):
        original=self.turn('2030-01-01T12:00:00+08:00提醒我回邮件')
        row=assistant.commitment_from_turn(self.root,original)['receipt']['current']
        edit=self.turn('把回邮件改到2031-01-01T12:00:00+08:00',operation='reschedule',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,edit)['receipt']['current']['revision'],2)
        cancel=self.turn('取消回邮件',operation='cancel',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,cancel)['receipt']['current']['status'],'CANCELLED')
        self.assertEqual(assistant.commitment_from_turn(self.root,original)['receipt']['current']['status'],'CANCELLED')

    def test_stale_model_edit_cannot_overwrite_manual_reschedule(self):
        original=self.turn('2030-01-01T12:00:00+08:00提醒我回邮件')
        row=assistant.commitment_from_turn(self.root,original)['receipt']['current']
        edit=self.turn('取消回邮件',operation='cancel',target=row['id'])
        commitments.command(self.root,{'action':'reschedule','id':row['id'],'request_id':uuid.uuid4().hex,
            'revision':row['revision'],'due_at':'2032-01-01T12:00:00+08:00'})
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,edit)

    def test_other_chat_target_not_exposed_or_accepted(self):
        original=self.turn('帮我记个待办：回邮件');row=assistant.commitment_from_turn(self.root,original)['receipt']['current']
        store=Dialogues(self.root)
        try:other=store.create()
        finally:store.close()
        with self.assertRaises(CoreError):self.turn('取消回邮件',operation='cancel',target=row['id'],chat=other)

    def test_explicit_time_form_resolves_vague_request(self):
        ident=self.turn('明天下午提醒我回邮件')
        result=assistant.confirm_commitment(self.root,{'turn_id':ident,'due_at':'2030-01-01T15:00:00+08:00'})
        self.assertEqual(result['mode'],'APPLIED')

    def test_source_changed_after_acceptance_cannot_reuse_old_receipt(self):
        ident=self.turn('帮我记个待办：回邮件');assistant.commitment_from_turn(self.root,ident)
        store=Dialogues(self.root)
        try:
            request=decode(store.turn(ident)['request']);request['text']='帮我记个待办：其它事'
            store.db.execute('UPDATE turns SET request=? WHERE id=?',(canonical(request),ident))
        finally:store.close()
        with self.assertRaises(CoreError):assistant.commitment_from_turn(self.root,ident)

    def test_relative_clock_uses_explicit_offset_and_original_reference(self):
        reference=datetime(2030,11,8,18,0,tzinfo=timezone.utc).timestamp()
        self.assertEqual(resolve('明天下午3点UTC+08:00',reference),'2030-11-10T15:00:00+08:00')
        self.assertIsNone(resolve('明天下午',reference))

    def test_real_dialogue_host_callback_persists_only_durable_local_receipt(self):
        from host.dialogue import DialogueHost
        from test_preferences_dialogue import fixture
        core=Core(self.root)
        try:core.preferences.install(fixture(),{})
        finally:core.close()
        text='2030-01-01T12:00:00+08:00提醒我回邮件'
        payload={'schema':'jarvis.assistant-turn.v1','reply':'已完成','action':{'kind':'commitment',
            'goal':'','input_text':'','target':'','commitment':{'operation':'create','title':'回邮件','quote':text,
            'due_at':'','time_text':'','basis_turn':''}}}
        class Client:
            def __init__(self,*args):pass
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();return {'status':'SUCCEEDED','text':canonical(payload)}
        host=DialogueHost(self.root)
        try:
            with patch('host.dialogue.NativeModel',Client):
                host.submit({'chat_id':self.chat,'request_id':'actual-dialogue','text':text,'provider':'openai',
                    'model':'test-model','reasoning':'default','assistant_mode':True})
                host.pool.shutdown(wait=True)
            store=Dialogues(self.root)
            try:
                turn=store.turn('actual-dialogue');self.assertEqual(turn['status'],'SUCCEEDED')
                projection=assistant.projection(self.root,store.read(self.chat))['turns'][-1]
            finally:store.close()
            self.assertEqual(projection['commitment_action']['mode'],'APPLIED')
            self.assertNotIn('已完成',turn['reply'])
        finally:host.close()

    def test_invalid_prior_time_does_not_break_later_context(self):
        ident=self.turn('2030-02-30T12:00:00+08:00提醒我回邮件')
        self.assertNotEqual(assistant.commitment_from_turn(self.root,ident)['mode'],'APPLIED')
        self.assertIsInstance(assistant.context(self.root,self.chat),list)

    def test_ambiguous_pronoun_with_multiple_items_needs_review(self):
        first=self.turn('帮我记个待办：回邮件');row=assistant.commitment_from_turn(self.root,first)['receipt']['current']
        second=self.turn('帮我记个待办：整理资料',title='整理资料');assistant.commitment_from_turn(self.root,second)
        cancel=self.turn('取消这个提醒',operation='cancel',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,cancel)['mode'],'REVIEW')
        with Commitments(self.root) as store:self.assertEqual(store.read(row['id'])['status'],'OPEN')

    def test_confirmation_retry_binds_original_time_and_reports_current_version(self):
        ident=self.turn('明天下午提醒我回邮件')
        accepted={'turn_id':ident,'due_at':'2030-01-01T15:00:00+08:00'}
        row=assistant.confirm_commitment(self.root,accepted)['receipt']['current']
        with self.assertRaises(CoreError):
            assistant.confirm_commitment(self.root,{'turn_id':ident,'due_at':'2031-01-01T15:00:00+08:00'})
        commitments.command(self.root,{'action':'reschedule','id':row['id'],'request_id':uuid.uuid4().hex,
            'revision':row['revision'],'due_at':'2032-01-01T15:00:00+08:00'})
        result=assistant.confirm_commitment(self.root,accepted)['receipt']
        self.assertEqual(result['current']['revision'],2)
        self.assertEqual(result['accepted']['due_text'],accepted['due_at'])
        self.assertEqual(result['current']['due_text'],'2032-01-01T15:00:00+08:00')

    def test_compound_request_cannot_be_silently_reduced_to_one_reminder(self):
        text='2031-06-18T09:10:00+08:00提醒我核对订单，然后删除附件'
        ident=self.turn(text,title='核对订单，然后删除附件')
        self.assertEqual(assistant.commitment_from_turn(self.root,ident)['mode'],'REVIEW')
        self.assertFalse(commitments.exists(self.root))

    def test_evening_twelve_needs_day_boundary_clarification(self):
        ident=self.turn('明天晚上12点UTC+08:00提醒我出发',title='出发')
        self.assertNotEqual(assistant.commitment_from_turn(self.root,ident)['mode'],'APPLIED')
        self.assertFalse(commitments.exists(self.root))

    def test_dont_forget_prefix_is_affirmative_but_not_a_negation_bypass(self):
        positive=self.turn('别忘了2031-06-18T09:10:00+08:00提醒我回邮件')
        self.assertEqual(assistant.commitment_from_turn(self.root,positive)['mode'],'APPLIED')
        negative=self.turn('别忘了不要在2031-06-18T09:10:00+08:00提醒我回邮件')
        self.assertEqual(assistant.commitment_from_turn(self.root,negative)['mode'],'NOT_REQUEST')
        with Commitments(self.root) as store:self.assertEqual(len(store.listing()),1)

    def test_polite_alternate_reminder_and_literal_book_title_are_persisted(self):
        cases=[('麻烦你在2031-06-18T09:10:00+08:00提醒我核对订单','核对订单'),
               ('帮我记个待办：阅读“用户手册”','阅读“用户手册”'),
               ('给我加一条待办，整理收据','整理收据'),
               ('2031-06-18T09:10:00+08:00，提醒一下我预约体检','预约体检')]
        for text,title in cases:
            with self.subTest(text=text):
                ident=self.turn(text,title=title);result=assistant.commitment_from_turn(self.root,ident)
                self.assertEqual(result['mode'],'APPLIED');self.assertEqual(result['receipt']['current']['title'],title)

    def test_explicit_24_hour_afternoon_is_not_shifted_by_twelve_hours(self):
        ident=self.turn('2031-06-18下午14:30UTC+08:00提醒我办理退货',title='办理退货')
        row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        self.assertEqual(row['due_text'],'2031-06-18T14:30:00+08:00')
        self.assertIsNone(resolve('2031-06-18晚上14:30UTC+08:00',0))

    def test_english_create_edit_and_complete_share_receipts_and_revisions(self):
        ident=self.turn('Please remind me to check the invoice at 2031-06-18T09:10:00+08:00.',title='check the invoice')
        row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        edit=self.turn('Move the reminder for check the invoice to 2031-06-19T10:00:00+08:00.',
            title='check the invoice',operation='reschedule',target=row['id'])
        moved=assistant.commitment_from_turn(self.root,edit)['receipt']['current']
        self.assertEqual(moved['revision'],2);self.assertEqual(moved['due_text'],'2031-06-19T10:00:00+08:00')
        done=self.turn('Mark check the invoice as done.',title='check the invoice',operation='complete',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,done)['receipt']['current']['status'],'DONE')

    def test_reschedule_alias_does_not_allow_wrong_label_or_competing_pronoun(self):
        ident=self.turn('帮我记个待办：核对订单',title='核对订单')
        row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        edit=self.turn('把核对订单的提醒挪到2031-06-19T10:00:00+08:00',title='核对订单',operation='reschedule',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,edit)['receipt']['current']['revision'],2)
        wrong=self.turn('把另一件事的提醒挪到2031-06-20T10:00:00+08:00',title='核对订单',operation='reschedule',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,wrong)['mode'],'REVIEW')

    def test_english_negation_condition_and_quoted_whole_instruction_are_not_requests(self):
        for text in ['Do not remind me to回邮件 at 2031-06-18T09:10:00+08:00.',
                     'If ready, remind me to 回邮件 at 2031-06-18T09:10:00+08:00.',
                     '“帮我记个待办：回邮件”',
                     'Remind me to 回邮件 and then delete files at 2031-06-18T09:10:00+08:00.']:
            with self.subTest(text=text):
                ident=self.turn(text)
                self.assertNotEqual(assistant.commitment_from_turn(self.root,ident)['mode'],'APPLIED')
        self.assertFalse(commitments.exists(self.root))

    def test_explicit_reminder_and_list_wrappers_preserve_exact_literal_title(self):
        cases=[('请帮我设置一个本地提醒：2033-05-10T09:25:00+09:00 归还投影仪。','归还投影仪'),
               ('请在 2033-05-11T10:25:00+09:00 提醒我“核对实验记录”。','核对实验记录'),
               ('请在待办清单里添加一项：“阅读「天文入门」”。','阅读「天文入门」'),
               ('Please add read the trail guide to my to-do list.','read the trail guide')]
        for text,title in cases:
            with self.subTest(text=text):
                row=assistant.commitment_from_turn(self.root,self.turn(text,title=title))['receipt']['current']
                self.assertEqual(row['title'],title)
        wrong=self.turn('请在 2033-05-11T10:25:00+09:00 提醒我“核对实验记录”。',title='核对银行卡')
        self.assertNotEqual(assistant.commitment_from_turn(self.root,wrong)['mode'],'APPLIED')

    def test_quoted_target_wrappers_do_not_change_scope_or_literal_identity(self):
        title='核对实验记录';ident=self.turn('帮我记个待办：'+title,title=title)
        row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        edit=self.turn('请把待办事项“核对实验记录”改期到 2033-07-19T17:40:00+05:30。',title=title,operation='reschedule',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,edit)['receipt']['current']['revision'],2)
        for text in ['请取消待办事项“另一个事项”。','Please cancel this reminder.']:
            if text.startswith('Please'):assistant.commitment_from_turn(self.root,self.turn('帮我记个待办：读书',title='读书'))
            bad=self.turn(text,title=title,operation='cancel',target=row['id'])
            self.assertNotEqual(assistant.commitment_from_turn(self.root,bad)['mode'],'APPLIED')

    def test_title_before_time_and_colloquial_completion_remain_literal(self):
        ident=self.turn('请提醒我“寄回露营灯”，时间定在2034-05-10T09:25:00+09:00。',title='寄回露营灯')
        row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        self.assertEqual(row['due_text'],'2034-05-10T09:25:00+09:00')
        done=self.turn('我完成了“寄回露营灯”，请标记一下。',title='寄回露营灯',operation='complete',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,done)['receipt']['current']['status'],'DONE')

    def test_multiple_explicit_clocks_are_not_silently_collapsed(self):
        title='看地图，2034-05-11T09:25:00+09:00提醒我看天气'
        text='2034-05-10T09:25:00+09:00提醒我'+title
        self.assertEqual(assistant.commitment_from_turn(self.root,self.turn(text,title=title))['mode'],'REVIEW')

    def test_anchor_frames_require_every_remaining_word_to_be_request_syntax(self):
        title='归还录音设备'
        for text in ['请提醒我归还录音设备，时间设为 2035-05-10T09:25:00+09:00。',
                     '设置一个提醒：归还录音设备，时间是 2035-05-10T09:25:00+09:00。']:
            self.assertEqual(assistant.commitment_from_turn(self.root,self.turn(text,title=title))['mode'],'APPLIED')
        for text in ['据说请提醒我归还录音设备，时间设为 2035-05-10T09:25:00+09:00。',
                     '请提醒我归还录音设备，时间设为 2035-05-10T09:25:00+09:00，这句话合理吗？',
                     '请提醒我归还录音设备，时间设为 2035-05-10T09:25:00+09:00并删除文件',
                     '“设置一个提醒：归还录音设备，时间是 2035-05-10T09:25:00+09:00。”']:
            self.assertNotEqual(assistant.commitment_from_turn(self.root,self.turn(text,title=title))['mode'],'APPLIED')

    def test_unique_current_conversation_reference_remains_automatic(self):
        ident=self.turn('帮我记个待办：回邮件');row=assistant.commitment_from_turn(self.root,ident)['receipt']['current']
        cancel=self.turn('取消这个提醒',operation='cancel',target=row['id'])
        self.assertEqual(assistant.commitment_from_turn(self.root,cancel)['receipt']['current']['status'],'CANCELLED')


if __name__=='__main__':unittest.main()
