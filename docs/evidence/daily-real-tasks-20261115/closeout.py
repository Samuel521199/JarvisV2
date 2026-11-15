"""Record final scope/accounting and make the existing learning chat findable."""
import json
from session import Client,DATA,OUT,write
from tools.observe_task_trial import observe

def main():
    assert not (OUT/'accounting-r2.json').exists(),'Preserve prior closeout'
    coach=json.loads((OUT/'english-coach-result.json').read_text())
    title='实用英语 · 生活、沟通与工作资料'
    result=Client().call('/api/chat/update',{'id':coach['chat_id'],'patch':{'title':title}})
    assert result['title']==title
    write(OUT/'english-chat-entry.json',{'chat_id':coach['chat_id'],'title':title,'selected_skill':'english-coach','url':'http://127.0.0.1:18282/#chat='+coach['chat_id'],'requires_local_login':True,'browser_skill_selection':'Select 英语学习与练习 when continuing; API skill snapshot does not set browser draft preferences.'})
    for label in ('','english-'):
        selection=json.loads((OUT/(label+'selection.json')).read_text())
        selection['turn_ids'].append(coach['request_id'])
        selection['interventions']['additional_user_scope_clarification']='Jarvis-native English learning, not buying a service'
        selection['interventions']['operator_runtime_decisions'].append({'kind':'start_existing_english_coach_and_label_chat','evidence':'english-coach-start.json'})
        write(OUT/(label+'selection-r2.json'),selection)
        value=observe(DATA,selection);write(OUT/(label+'accounting-r2.json'),value)
        print(json.dumps({'label':label,'work_tokens':value['work_tokens'],'shared_setup_tokens':value['shared_setup_tokens']},ensure_ascii=False))
    write(OUT/'scope-update.json',{'supersedes_quote_interpretation':True,'user_request':'基于这个AI系统的英语学习','quote_trial':'deferred; no genuine quote use case supplied; English-service shopping removed from current scope','actual_learner_answers':0,'knowledge_policy':'Trial drafting did not promote unreviewed content into long-term memory; same-chat history and reply files persist. Cross-session review store not implemented by this trial.'})
    write(OUT/'checks.json',{'observer_tests':{'passed':6,'command':'python -X utf8 -B -m unittest discover -s tests -p test_task_trial_observer.py -v'},'existing_personal_workflow_tests':{'passed':4,'command':'python -X utf8 -B -m unittest discover -s tests -p test_personal_workflows.py -v'},'scope':'Existing personal workflow tests use mocks; the coach opening separately used the real daily model. No actual learner answer or speech test.'})

if __name__=='__main__':main()
