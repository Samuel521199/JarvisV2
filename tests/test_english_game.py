"""Independent software boundary, free-answer binding and transactional progress."""
from pathlib import Path
import json,os,subprocess,sys,unittest
from unittest.mock import patch
import test_english_learning as base
from adapters.software_client import binding,invoke
from host import english_learning as learning
from modules.english_learning.store import Store
from sdk.protocol import CoreError,canonical
from tools.install_english_city import install

ROOT=Path(__file__).resolve().parents[1]
SOFTWARE_SOURCE=Path(os.environ.get('JARVIS_ENGLISH_CITY_SOURCE',ROOT.parent/'software/english-city/source'))

@unittest.skipUnless((SOFTWARE_SOURCE/'engine.py').exists(),'Independent English City source must be installed outside this repository for integration tests')
class GameFlow(unittest.TestCase):
    setUp_base=base.LearningFlow.setUp
    tearDown=base.LearningFlow.tearDown
    call=base.LearningFlow.call
    run_reply=base.LearningFlow.run_reply
    rating=base.LearningFlow.rating

    def setUp(self):
        self.setUp_base();self.installed=install(SOFTWARE_SOURCE,self.root/'independent-software',self.root)

    def begin(self,scene='cafe',ident='english-game-q'):
        self.call({'action':'game_start','request_id':ident,'chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','scene':scene,'mode':'text'})
        self.host.run(ident);state=self.call({'action':'status'})
        ex=next(x for x in state['exercises'] if x['id']==ident)
        self.assertIsNone(ex['assessment']);self.assertNotIn('reference',ex['exercise']);self.assertNotIn('requirements',str(ex['exercise']['game']))
        return state['games']['sessions'][0],ex

    def respond(self,question='english-game-q',ident='english-game-a',answer="I'd like a small hot coffee with no sugar, to go, please.",missing=None,intent='answer',focus=None,evidence=None):
        self.call({'action':'answer','request_id':ident,'chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':question,'answer':answer,'assistance':'independent'})
        job=learning.binding(self.root,ident);keys=job['body']['game']['lesson']['requirements']
        game={'requirements':{k:'missing' if k==missing else 'met' for k in keys},'evidence':evidence or {k:'' if k==missing else answer for k in keys},'intent':intent,'npc_reply':'Of course. Let me confirm your order.','focus_items':focus or []}
        self.run_reply(ident,{**self.rating(answer),'meaning':1 if missing else 2,'game':game})
        return self.call({'action':'status'})

    def next(self,s,ident='english-game-next'):
        return self.call({'action':'game_next','request_id':ident,'chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','session_id':s['id'],'revision':s['revision']})

    def test_independent_entry_runs_without_jarvis_imports_and_is_relocatable(self):
        folder=Path(self.installed['release'])
        result=subprocess.run([sys.executable,'-I','-B',str(folder/'engine.py')],input=canonical({'schema':1,'operation':'describe','arguments':{}}).encode(),capture_output=True,cwd=folder,timeout=10)
        self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)['result']['state_owner'],'client')
        text=(folder/'engine.py').read_text(encoding='utf-8');self.assertNotIn('from host',text);self.assertNotIn('from modules',text)

    def test_installer_refuses_putting_software_releases_inside_jarvis_project(self):
        with self.assertRaisesRegex(ValueError,'outside the Jarvis project'):
            install(SOFTWARE_SOURCE,ROOT/'software/forbidden-release',self.root)

    def test_local_question_has_no_paid_model_call_and_progress_is_idempotent(self):
        session,_=self.begin();self.assertEqual(self.calls,[])
        store=Store(self.root)
        try:self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],3)
        finally:store.close()
        self.assertEqual(self.chats.usage(),[])
        state=self.respond();session=state['games']['sessions'][0];self.assertEqual((session['node'],session['revision']),(1,1))
        self.call({'action':'status'});self.assertEqual(self.call({'action':'status'})['games']['sessions'][0]['node'],1)
        self.assertEqual(state['progress']['domains']['life']['attempts'],1)
        self.next(session);self.host.run('english-game-next');state=self.call({'action':'status'});self.assertEqual(state['games']['sessions'][0]['node'],1)

    def test_incomplete_answer_keeps_original_and_asks_for_repair(self):
        self.begin();state=self.respond(answer='A coffee, please.',missing='size')
        s=state['games']['sessions'][0];self.assertEqual((s['node'],s['attempt']),(0,1))
        ex=state['exercises'][0];self.assertEqual(ex['assessment']['answer'],'A coffee, please.')
        self.next(s);self.host.run('english-game-next');state=self.call({'action':'status'})
        self.assertIn('接续 1',state['exercises'][0]['exercise']['prompt'])

    def test_pause_resume_keeps_prepared_question_and_blocks_late_answer(self):
        s,_=self.begin();state=self.call({'action':'game_pause','session_id':s['id'],'revision':s['revision']});s=state['games']['sessions'][0]
        self.assertEqual(s['state'],'PAUSED')
        with self.assertRaises(CoreError):self.respond()
        state=self.call({'action':'game_resume','session_id':s['id'],'revision':s['revision']});s=state['games']['sessions'][0]
        self.assertEqual(s['state'],'ACTIVE')

    def test_dispute_and_source_removal_stop_dependent_continuation(self):
        self.begin();state=self.respond();s=state['games']['sessions'][0]
        self.call({'action':'dispute','assessment_id':'english-game-a'})
        with self.assertRaises(CoreError):self.next(s)
        self.assertEqual(self.call({'action':'status'})['games']['sessions'][0]['state'],'SOURCE_OR_SOFTWARE_UNAVAILABLE')

    def test_short_repair_can_use_original_user_information_without_repeating_everything(self):
        self.begin();state=self.respond(answer='A coffee, please.',missing='size')
        self.next(state['games']['sessions'][0]);self.host.run('english-game-next')
        answer='Small, hot, no sugar, to go, please.'
        evidence={'drink':'coffee','size':'Small','temperature':'hot','sugar':'no sugar','service':'to go'}
        state=self.respond(question='english-game-next',ident='english-game-repair-a',answer=answer,evidence=evidence)
        self.assertEqual(state['games']['sessions'][0]['node'],1)
        latest=next(e['assessment'] for e in state['exercises'] if e['id']=='english-game-next')
        self.assertEqual(latest['game']['evidence_sources']['drink'],'english-game-a')
        original=next(e['assessment'] for e in state['exercises'] if e['id']=='english-game-q')
        self.assertEqual(original['meaning'],1)

    def test_unknown_answer_blocks_next_and_pause_without_repeating_paid_call(self):
        s,_=self.begin()
        value={'action':'answer','request_id':'english-game-a','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-game-q','answer':'A coffee, please.','assistance':'independent'}
        self.call(value);self.chats.finish('english-game-a',{'status':'UNKNOWN','code':'model_timeout'})
        state=self.call({'action':'status'});s=state['games']['sessions'][0]
        with self.assertRaises(CoreError):self.next(s)
        with self.assertRaises(CoreError):self.call({'action':'game_pause','session_id':s['id'],'revision':s['revision']})
        self.call(value);self.assertEqual(self.calls,[])

    def test_npc_speech_does_not_expose_answer_or_count_as_hint(self):
        _,ex=self.begin()
        with patch('adapters.models.local_speech.synthesize',return_value='synthetic-audio'):
            self.call({'action':'speak_npc','exercise_id':ex['id']})
        current=self.call({'action':'status'})['exercises'][0]
        self.assertEqual(current['hints'],0);self.assertFalse(current['exposed']);self.assertNotIn('reference',current['exercise'])

    def test_vocabulary_is_source_bound_and_disputed_observation_is_withheld(self):
        self.begin();state=self.respond(answer='A coffee, please.',missing='size',focus=[{'word':'coffee','quote':'coffee','suggestion':'Include the size for this task.','reason':'Missing task information, not a claim that coffee is wrong.'}])
        self.assertEqual(len(state['games']['vocabulary_observations']),1)
        self.call({'action':'withdraw','exercise_id':'english-game-q'})
        self.assertEqual(self.call({'action':'status'})['games']['vocabulary_observations'],[])

    def test_software_disable_does_not_break_ordinary_learning_status(self):
        self.begin();path=self.root/'config/software.json';cfg=json.loads(path.read_text());cfg['software']['english-city']['enabled']=False;path.write_text(json.dumps(cfg))
        state=self.call({'action':'status'});self.assertFalse(state['games']['available']);self.assertEqual(state['games']['sessions'][0]['state'],'SOURCE_OR_SOFTWARE_UNAVAILABLE')

    def test_user_can_disable_and_explicitly_rebind_same_software_without_losing_progress(self):
        s,_=self.begin();state=self.call({'action':'status'});policy=state['games']['policy']
        self.call({'action':'software_configure','enabled':False,'revision':policy['revision']})
        state=self.call({'action':'status'});self.assertFalse(state['games']['available']);policy=state['games']['policy']
        state=self.call({'action':'software_configure','enabled':True,'revision':policy['revision']})
        self.assertEqual(state['games']['sessions'][0]['state'],'SOURCE_OR_SOFTWARE_UNAVAILABLE')
        state=self.call({'action':'game_rebind','session_id':s['id'],'revision':s['revision']})
        self.assertEqual(state['games']['sessions'][0]['state'],'ACTIVE');self.assertEqual(state['games']['sessions'][0]['node'],0)
        self.assertEqual(state['games']['sessions'][0]['exercise_id'],'english-game-q')

    def test_game_oral_mode_requires_recording_and_retains_existing_oral_assessment(self):
        import base64,io,wave
        self.call({'action':'game_start','request_id':'english-oral-game-q','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','scene':'cafe','mode':'oral'})
        self.host.run('english-oral-game-q')
        value={'action':'answer','request_id':'english-oral-game-a','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-oral-game-q','answer':'A coffee, please.','assistance':'independent'}
        with self.assertRaises(CoreError):self.call(value)
        raw=io.BytesIO()
        with wave.open(raw,'wb') as audio:audio.setparams((1,2,16000,16000,'NONE','not compressed'));audio.writeframes(b'\x00\x00'*16000)
        saved=self.call({'action':'record','audio':base64.b64encode(raw.getvalue()).decode()})['recording']
        self.call({**value,'action':'oral_answer','audio_id':saved['id']})
        job=learning.binding(self.root,value['request_id']);keys=job['body']['game']['lesson']['requirements']
        game={'requirements':{k:'missing' for k in keys},'evidence':{k:'' for k in keys},'intent':'answer','npc_reply':'What size would you like?','focus_items':[]}
        self.run_reply(value['request_id'],{**self.rating(value['answer']),'meaning':1,'game':game})
        state=self.call({'action':'status'});self.assertEqual(state['oral_progress']['domains']['life']['attempts'],1);self.assertEqual(state['progress']['domains']['life']['attempts'],0)
        self.assertTrue(state['exercises'][0]['assessment']['speech'])

    def test_release_tampering_is_rejected_before_execution(self):
        path=Path(self.installed['release'])/'engine.py';path.write_bytes(path.read_bytes()+b'\n# corruption\n')
        with self.assertRaises(CoreError):invoke(self.root,'describe',{})

    def test_model_cannot_forge_requirement_quotes_or_skip_to_later_node(self):
        self.begin();answer='A coffee, please.'
        self.call({'action':'answer','request_id':'english-game-a','chat_id':self.chat,'provider':'openai','model':'gpt-test','reasoning':'default','exercise_id':'english-game-q','answer':answer,'assistance':'independent'})
        job=learning.binding(self.root,'english-game-a');keys=job['body']['game']['lesson']['requirements']
        value={**self.rating(answer),'game':{'requirements':{k:'met' for k in keys},'evidence':{k:'invented quote' for k in keys},'intent':'answer','npc_reply':'Done','focus_items':[]}}
        self.run_reply('english-game-a',value)
        self.assertEqual(self.chats.turn('english-game-a')['status'],'FAILED')
        self.assertEqual(self.call({'action':'status'})['games']['sessions'][0]['node'],0)

if __name__=='__main__':unittest.main()
