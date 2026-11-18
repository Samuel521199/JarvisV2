"""Shared receipts, original queue adoption, cancellation and learning provenance."""
import base64,hashlib,io,json,sys,time,wave
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_english_learning as learning_fixture
from host.speech import Speech
from host import speech_sources
from modules.speech.store import Store
from modules.english_learning.store import Store as Learning
from control.recovery.gate import StopGate
from sdk.protocol import CoreError,digest


def wav():
    output=io.BytesIO()
    with wave.open(output,'wb') as w:w.setparams((1,2,16000,3200,'NONE','none'));w.writeframes(b'\x10\x01'*3200)
    return output.getvalue()


class SpeechFlow(unittest.TestCase):
    setUpLearning=learning_fixture.LearningFlow.setUp
    call=learning_fixture.LearningFlow.call;start=learning_fixture.LearningFlow.start;run_reply=learning_fixture.LearningFlow.run_reply;question=learning_fixture.LearningFlow.question;rating=learning_fixture.LearningFlow.rating
    def setUp(self):
        self.setUpLearning();outer=self
        class Model:
            def pinned(self):return {'id':'fixture-stt','revision':1,'fingerprint':'f'*64,'kind':'stt','source_revision':'a'*40}
            def transcribe(self,raw,language,check,expected):
                check()
                if getattr(outer,'during',None):outer.during()
                check();return {'text':getattr(outer,'recognition','Could I have a box, please?'),'audio_sha256':hashlib.sha256(raw).hexdigest(),'model':expected,'flags':[],'network':False}
            def start(self,item):pass
        self.speech=Speech(self.root,SimpleNamespace(speech=Model()),self.runner)
    def tearDown(self):
        self.speech.close();learning_fixture.LearningFlow.tearDown(self)
    def recognize(self,ident='speech-one',purpose='chat',exercise=None):
        self.speech.command({'action':'record','id':'audio-11111111111111111111111111111111','audio':base64.b64encode(wav()).decode(),'purpose':purpose,'chat_id':self.chat,'exercise_id':exercise})
        command={'action':'transcribe','id':ident,'audio_id':'audio-11111111111111111111111111111111','purpose':purpose,'chat_id':self.chat,'exercise_id':exercise,'language':'auto'}
        self.speech.command(command);self.speech.futures[ident].result(timeout=5)
        with Store(self.root) as s:return s.get(ident),command
    def test_receipt_replay_conflict_and_no_implicit_dialogue(self):
        row,cmd=self.recognize();self.assertEqual(row['state'],'SUCCEEDED')
        self.assertFalse(self.chats.db.execute("SELECT 1 FROM turns WHERE id='voice-speech-one'").fetchone())
        self.speech.command(cmd)
        with self.assertRaises(CoreError):self.speech.command({**cmd,'language':'en'})
        with self.assertRaises(CoreError):speech_sources.completed(self.root,row['id'],'english-learning',self.chat,'different')
    def test_confirm_original_queue_restart_reader_and_withdrawal(self):
        row,_=self.recognize();command={'request_id':'unused','chat_id':self.chat,'text':'Could I have a box, please?','provider':'openai','model':'gpt-test','reasoning':'default','skill':'english-coach','memory_enabled':False,'assistant_mode':False}
        result=self.speech.command({'action':'submit','id':row['id'],'command':command})
        self.assertEqual(result['submission']['request_id'],'voice-speech-one')
        with Store(self.root) as s:
            saved=s.get(row['id']);self.assertEqual(saved['turn_id'],'voice-speech-one')
        actual={**command,'request_id':'voice-speech-one'}
        speech_sources.check_turn(self.root,'voice-speech-one',actual)
        self.speech.close();self.speech=Speech(self.root,SimpleNamespace(speech=self.speech.models.speech),self.runner)
        speech_sources.check_turn(self.root,'voice-speech-one',actual)
        with self.assertRaises(CoreError):speech_sources.check_turn(self.root,'voice-speech-one',{**actual,'text':'changed'})
        self.speech.command({'action':'withdraw','id':row['id']})
        with self.assertRaises(CoreError):speech_sources.check_turn(self.root,'voice-speech-one',actual)
        speech_sources.check_turn(self.root,'ordinary-text',{'text':'normal'})
    def test_cancel_late_result_cannot_commit(self):
        self.during=lambda:self.speech.command({'action':'cancel','id':'speech-one'})
        row,_=self.recognize();self.assertEqual(row['state'],'CANCELLED');self.assertIsNone(row['result'])
    def test_disabled_confirmation_and_unknown_restart_never_resends(self):
        row,_=self.recognize();self.speech.command({'action':'configure','enabled':False,'revision':0})
        with self.assertRaises(CoreError):self.speech.command({'action':'submit','id':row['id'],'command':{'text':'hello'}})
        with Store(self.root) as s:s.add('speech-interrupted',row['body'])
        self.speech.close();self.speech=Speech(self.root,self.speech.models,self.runner)
        with Store(self.root) as s:self.assertEqual(s.get('speech-interrupted')['state'],'UNKNOWN')
        self.assertFalse(self.speech.futures)
    def test_asr_confirmed_learning_preserves_raw_and_withdraws_from_statistics(self):
        self.question();row,_=self.recognize(purpose='english-learning',exercise='english-question')
        corrected='Could I have a box please?'
        self.call({'action':'asr_answer','request_id':'english-asr','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-question','answer':corrected,'assistance':'independent','speech_id':row['id']})
        self.run_reply('english-asr',self.rating(corrected))
        store=Learning(self.root)
        try:
            self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],4)
            record=json.loads(store.db.execute("SELECT body FROM assessments WHERE id='english-asr'").fetchone()[0]);self.assertEqual(record['speech']['asr']['raw_text'],row['result']['text']);self.assertEqual(record['answer'],corrected);self.assertTrue(record['speech']['asr']['corrected']);self.assertTrue(speech_sources.learning_valid(self.root,record))
        finally:store.close()
        self.speech.command({'action':'withdraw','id':row['id']});self.assertFalse(speech_sources.learning_valid(self.root,record))
        view=self.call({'action':'status'});self.assertEqual(view['oral_progress']['domains']['life']['attempts'],0)
    def test_confirmed_transcription_opens_library_without_model_dispatch(self):
        from test_library_preview import add_display_asset
        add_display_asset(self.root)
        self.recognition='打开纸船的 L O D 二'
        row,_=self.recognize();self.speech.runner=self.host
        command={'text':self.recognition,'provider':'auto','model':'','reasoning':'default','assistant_mode':True}
        with patch.object(self.host,'_pump'),patch('host.dialogue.NativeModel') as provider:
            submission=self.speech.command({'action':'submit','id':row['id'],'command':command})['submission']
            self.host.run(submission['request_id'])
            turn=self.chats.read(self.chat)['turns'][-1]
            self.assertEqual(turn['assistant_action']['choices'][0]['version'],'lod2')
            self.assertEqual(turn['provider'],'local-library')
            provider.assert_not_called()

    def test_real_dialogue_submit_dedup_and_withdraw_before_provider(self):
        row,_=self.recognize();self.speech.runner=self.host
        command={'request_id':'unused','chat_id':self.chat,'text':'Could I have a box, please?','provider':'openai','model':'test-model','reasoning':'default','skill':'none','memory_enabled':False,'assistant_mode':False}
        with patch.object(self.host,'_pump',lambda:None):
            first=self.speech.command({'action':'submit','id':row['id'],'command':command})
            second=self.speech.command({'action':'submit','id':row['id'],'command':command})
        self.assertFalse(first['submission']['existing']);self.assertTrue(second['submission']['existing'])
        self.assertEqual(self.chats.db.execute("SELECT count(*) FROM turns WHERE id='voice-speech-one'").fetchone()[0],1)
        self.speech.command({'action':'withdraw','id':row['id']});calls=[]
        class Client:
            def __init__(self,*args):pass
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):checkpoint();calls.append(messages);return {'status':'SUCCEEDED','text':'hello','usage':{'total_tokens':1}}
        with patch('host.dialogue.NativeModel',Client),patch.object(self.host,'_pump',lambda:None):
            self.host.pending.pop('voice-speech-one',None)
            self.host.run('voice-speech-one');self.assertEqual(calls,[])
            with patch.object(self.host,'_pump',lambda:None):self.host.submit({**command,'request_id':'ordinary-message','text':'hello'})
            self.host.pending.pop('ordinary-message',None)
            self.host.run('ordinary-message')
        self.assertEqual(len(calls),1);self.assertEqual(self.chats.turn('ordinary-message')['status'],'SUCCEEDED')

    def test_project_chat_uses_shared_speech_but_cannot_write_personal_learning(self):
        import tempfile
        from modules.workspace.store import Workspace
        with tempfile.TemporaryDirectory(dir=self.root.parent) as folder:
            workspace=Workspace(self.root)
            try:
                project=workspace.open(folder);project_chat=self.chats.create(project['id'])
                scope=speech_sources.scope(self.root,'chat',project_chat);self.assertEqual(scope['chat_id'],project_chat)
                with self.assertRaises(CoreError):speech_sources.scope(self.root,'english-learning',project_chat,'english-question')
                workspace.update(project['id'],{'removed':True})
                with self.assertRaises(CoreError):speech_sources.scope(self.root,'chat',project_chat)
            finally:workspace.close()

    def test_disabling_learning_during_asr_prevents_late_result(self):
        self.question();self.during=lambda:self.call({'action':'configure','enabled':False,'revision':1})
        row,_=self.recognize(purpose='english-learning',exercise='english-question');self.assertEqual(row['state'],'FAILED');self.assertIsNone(row['result'])

    def test_stop_during_recognition_withholds_result(self):
        self.during=lambda:StopGate(self.root).stop()
        row,_=self.recognize();self.assertEqual(row['state'],'FAILED');self.assertIsNone(row['result'])

class SpeechGameFlow(unittest.TestCase):
    setUpLearning=learning_fixture.LearningFlow.setUp
    call=SpeechFlow.call;start=SpeechFlow.start;run_reply=SpeechFlow.run_reply;question=SpeechFlow.question;rating=SpeechFlow.rating;recognize=SpeechFlow.recognize
    def setUp(self):
        SpeechFlow.setUp(self)
        from tools.install_english_city import install
        from test_english_game import SOFTWARE_SOURCE
        source=SOFTWARE_SOURCE
        if not (source/'engine.py').exists():self.skipTest('Independent English City is not available')
        install(source,self.root/'independent-software',self.root)
    tearDown=SpeechFlow.tearDown
    def begin_game(self):
        self.call({'action':'game_start','request_id':'english-oral-game-q','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','scene':'cafe','mode':'oral'})
        self.host.run('english-oral-game-q');return self.call({'action':'status'})['games']['sessions'][0]
    def test_confirmed_asr_advances_external_game_once_and_withdrawal_blocks_continuation(self):
        session=self.begin_game();self.recognition="I'd like a small hot coffee with no sugar, to go, please."
        row,_=self.recognize(purpose='english-learning',exercise='english-oral-game-q')
        self.call({'action':'asr_answer','request_id':'english-asr-game-a','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-oral-game-q','answer':self.recognition,'assistance':'independent','speech_id':row['id']})
        import host.english_learning as learning
        keys=learning.binding(self.root,'english-asr-game-a')['body']['game']['lesson']['requirements']
        game={'requirements':{k:'met' for k in keys},'evidence':{k:self.recognition for k in keys},'intent':'answer','npc_reply':'Of course. Let me confirm.','focus_items':[]}
        self.run_reply('english-asr-game-a',{**self.rating(self.recognition),'game':game})
        state=self.call({'action':'status'});session=state['games']['sessions'][0]
        self.assertEqual(session['node'],1);self.assertEqual(state['oral_progress']['domains']['life']['attempts'],1);self.assertEqual(state['progress']['domains']['life']['attempts'],0)
        self.call({'action':'game_start','request_id':'english-second-game','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','scene':'work','mode':'text'})
        store=Learning(self.root)
        try:self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],4)
        finally:store.close()
        self.speech.command({'action':'withdraw','id':row['id']})
        state=self.call({'action':'status'});original=next(s for s in state['games']['sessions'] if s['id']==session['id']);self.assertEqual(original['state'],'SOURCE_OR_SOFTWARE_UNAVAILABLE')
        with self.assertRaises(CoreError):self.call({'action':'game_next','request_id':'english-after-withdraw','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','session_id':session['id'],'revision':session['revision']})
    def test_game_pause_during_asr_prevents_late_commit(self):
        session=self.begin_game();self.during=lambda:self.call({'action':'game_pause','session_id':session['id'],'revision':session['revision']})
        row,_=self.recognize(purpose='english-learning',exercise='english-oral-game-q');self.assertEqual(row['state'],'FAILED');self.assertIsNone(row['result'])

if __name__=='__main__':unittest.main()
