import unittest
from unittest.mock import patch
import test_memory_development_ui as fixtures
from host.dialogue import DialogueHost
from host import memory
from modules.dialogue.store import Dialogues
from sdk.protocol import canonical,decode


class Capture(unittest.TestCase):
    setUp=fixtures.MemoryUI.setUp
    tearDown=fixtures.MemoryUI.tearDown

    def send(self,text,enabled=True,available=False):
        seen=[]
        class Client:
            def __init__(self,*args):pass
            def available(self):return available
            def complete(self,messages,checkpoint):
                seen.extend(messages);checkpoint();return {'status':'SUCCEEDED','text':'已整理为待核对候选。'}
        chat=self.chats.create();ident='capture-'+str(len(self.chats.db.execute('SELECT id FROM turns').fetchall()))
        request=dict(chat_id=chat,request_id=ident,text=text,provider='openai',model='test-model',reasoning='default',memory_enabled=enabled)
        host=DialogueHost(self.root)
        try:
            with patch('host.dialogue.NativeModel',Client):
                result=host.submit(request);host.pool.shutdown(wait=True)
            return result,request,seen
        finally:host.close()

    def test_explicit_request_is_durable_without_cloud_and_not_a_fact(self):
        result,request,_=self.send('请记住：我喜欢简短的技术说明。')
        self.assertEqual(result['memory_capture']['state'],'pending')
        rows=memory.command(self.root,{'action':'list','scope':'personal'})
        self.assertEqual(rows['facts'],[]);self.assertEqual(len(rows['candidates']),1)
        self.assertEqual(rows['candidates'][0]['source_id'],'turn:'+request['request_id'])
        self.assertEqual(memory.command(self.root,{'action':'propose','turn_id':request['request_id']})['id'],rows['candidates'][0]['id'])

    def test_disabled_quoted_negative_and_credentials_are_not_captured(self):
        for text,enabled in [('请记住：此消息不应该被保存',False),('不要记住我刚才的话',True),
                             ('“记住：我喜欢咖啡”是一句台词',True),('请记住：api_key=synthetic-testing-only',True),
                             ('请记住：不要保存这段话。',True),('Please remember not to save this message.',True),
                             ('请记住：我的密码是synthetic-only',True)]:
            result,_,_=self.send(text,enabled)
            self.assertNotEqual(result['memory_capture']['state'],'pending')
        self.assertEqual(self.memory.candidates('personal'),[])

    def test_host_reports_pending_state_to_reply_without_promoting(self):
        result,request,messages=self.send('Please remember that I prefer short explanations.',available=True)
        self.assertIn('尚未成为长期事实',canonical(messages))
        turn=self.chats.turn(request['request_id']);context=decode(turn['memory_context'])
        self.assertEqual(context['capture_candidate'],result['memory_capture']['id'])
        self.assertEqual(self.memory.list('personal'),[])

    def test_dismissed_request_id_is_not_recaptured(self):
        from host.memory_capture import capture
        result,request,_=self.send('记住：测试偏好。')
        row=self.memory.candidates('personal')[0];self.memory.dismiss(row['id'],row['revision'])
        self.assertEqual(capture(self.root,request)['state'],'dismissed')
        self.assertEqual(self.memory.candidates('personal'),[])

    def test_candidate_state_change_invalidates_pending_state_claim(self):
        from host.memory_capture import annotate
        from sdk.protocol import CoreError
        result,request,_=self.send('请记住：技术答复请简短。')
        view=memory.retrieve(self.root,'personal','openai',True,'技术答复')
        annotate(self.root,request['request_id'],view);memory.refresh_view(self.root,view)
        row=self.memory.candidates('personal')[0];self.memory.dismiss(row['id'],row['revision'])
        with self.assertRaises(CoreError):memory.refresh_view(self.root,view)

    def test_disabled_explicit_request_cannot_tell_model_that_it_was_saved(self):
        result,request,messages=self.send('请记住：不要保存这段话。',enabled=False,available=True)
        self.assertIn('未自动保存这条记住请求',canonical(messages))
        self.assertEqual(self.memory.candidates('personal'),[])

if __name__=='__main__':unittest.main()
