"""Shared speech scope checks; no model inference and no independent task authority."""
import json
from control.paths import child
from host.learning_sources import active_chat,source_valid
from modules.dialogue.store import Dialogues
from modules.english_learning.store import Store as Learning
from modules.speech.store import Store
from sdk.protocol import CoreError,digest


def scope(root,purpose,chat_id,exercise_id=None,pending=True):
    if purpose not in ('chat','english-learning') or not isinstance(chat_id,str):raise CoreError('speech_scope','Unknown speech purpose')
    chats=Dialogues(root)
    try:
        if purpose=='english-learning':active_chat(chats,chat_id)
        else:
            chat=chats.read(chat_id)
            if chat['archived'] or chat['removed']:raise CoreError('chat_archived','Restore this chat before speech input')
            if chat['project_id']:
                from modules.workspace.store import Workspace
                projects=Workspace(root)
                try:projects.path(chat['project_id'])
                finally:projects.close()
        value={'purpose':purpose,'chat_id':chat_id,'exercise_id':exercise_id}
        if purpose=='chat':
            if exercise_id is not None:raise CoreError('speech_scope','Chat input has no learning exercise')
        else:
            with_learning=Learning(root)
            try:
                if not with_learning.config()['enabled']:raise CoreError('english_disabled','Learning is disabled')
                ex=with_learning.exercise(exercise_id)
                if ex['chat_id']!=chat_id or ex['withdrawn'] or not source_valid(chats,exercise_id,with_learning):raise CoreError('speech_stale','Learning source unavailable')
                value['exercise_digest']=digest(ex['body'])
                if pending:
                    if with_learning.db.execute('SELECT 1 FROM assessments WHERE exercise_id=?',(exercise_id,)).fetchone():raise CoreError('speech_stale','This exercise already has an answer')
                    if ex['body'].get('game'):
                        from host.english_game import check
                        check(with_learning,chats,ex['body']['game'],exercise_id)
            finally:with_learning.close()
        return value
    finally:chats.close()


def completed(root,ident,purpose,chat_id,exercise_id=None,pending=False):
    if not child(root,'state/speech.sqlite3').exists():raise CoreError('speech_missing','No speech result')
    with Store(root) as store:row=store.get(ident)
    body=row['body'];result=row['result']
    if row['state']!='SUCCEEDED' or body['operation']!='transcribe' or body['scope']!=scope(root,purpose,chat_id,exercise_id,pending):raise CoreError('speech_stale','Speech source changed')
    if not result or not result.get('text') or 'no_speech' in result.get('flags',[]):raise CoreError('speech_empty','No supported speech was recognized')
    from host.speech_audio import read
    raw,meta=read(root,body['audio_id'])
    if meta['context']!=body['scope'] or meta['sha256']!=result['audio_sha256']:raise CoreError('speech_stale','Audio source changed')
    return row,raw,meta


def learning_receipt(root,ident,chat_id,exercise_id,confirmed_text):
    row,raw,meta=completed(root,ident,'english-learning',chat_id,exercise_id,pending=True)
    if not isinstance(confirmed_text,str) or not 1<=len(confirmed_text.strip())<=3000:raise CoreError('speech_text','Confirm the words actually spoken')
    return {k:v for k,v in meta.items() if k!='context'}|{'storage':'speech','recognition':'offline_asr_user_confirmed','pronunciation_score':None,'asr':{'id':ident,'model':row['result']['model'],'raw_text':row['result']['text'],'corrected':confirmed_text!=row['result']['text'],'confirmed_text':confirmed_text,'result_digest':digest(row['result'])}}


from host.speech_receipts import learning_valid


def check_turn(root,ident,command):
    if not isinstance(ident,str) or not ident.startswith('voice-speech-'):return
    if not child(root,'state/speech.sqlite3').exists():raise CoreError('speech_stale','Missing speech source store')
    with Store(root) as store:
        r=store.db.execute('SELECT id FROM requests WHERE turn_id=?',(ident,)).fetchone()
        if not r:raise CoreError('speech_stale','Missing confirmed speech input')
        row=store.get(r['id'])
    completed(root,row['id'],'chat',command['chat_id'])
    if not row['confirmation'] or row['confirmation']['command_digest']!=digest(command):raise CoreError('speech_stale','Confirmed speech command changed')


def output_text(root,value):
    chat=value['chat_id'];purpose=value['purpose'];exercise=value.get('exercise_id')
    current=scope(root,purpose,chat,exercise,pending=False)
    if purpose=='chat':
        chats=Dialogues(root)
        try:
            r=chats.turn(value['source_id'])
            if r['chat_id']!=chat or r['status']!='SUCCEEDED' or not r['reply']:raise CoreError('speech_stale','Assistant reply unavailable')
            check_turn(root,r['id'],json.loads(r['request']))
            text=r['reply'][:450];current['output_digest']=digest(r['reply'])
        finally:chats.close()
    else:
        learning=Learning(root)
        try:
            ex=learning.exercise(exercise);body=ex['body']
            if value['source_id']=='npc' and body.get('game'):
                chats=Dialogues(root)
                try:
                    from host.english_game import verify,load
                    verify(learning,chats,load(learning,body['game']['session_id']))
                finally:chats.close()
                g=body['game'];text=g.get('history',[{}])[-1].get('npc_reply',g['lesson']['npc']) if g.get('history') else g['lesson']['npc']
            elif value['source_id']=='reference':
                a=learning.db.execute('SELECT body,disputed FROM assessments WHERE exercise_id=?',(exercise,)).fetchone()
                if not ex['exposed'] and not a:raise CoreError('speech_stale','Reveal reference before listening')
                if a:
                    chats=Dialogues(root)
                    try:
                        if a['disputed'] or not source_valid(chats,json.loads(a['body'])['answer_turn'],learning):raise CoreError('speech_stale','Evaluation unavailable')
                    finally:chats.close()
                text=json.loads(a['body'])['correction'] if a else body['reference']
            else:raise CoreError('speech_scope','Unknown learning speech source')
        finally:learning.close()
    return text,current
