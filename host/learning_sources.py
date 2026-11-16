"""Shared source checks for personal learning and AI-mediated software."""
from sdk.protocol import CoreError,digest

def active_chat(chats,ident):
    chat=chats.read(ident)
    if chat['removed'] or chat['archived']:raise CoreError('chat_archived','Restore this chat before practicing')
    if chat['project_id']:raise CoreError('english_scope','Use a personal chat for the personal learning record')
    return chat


def source_valid(chats,ident,store):
    row=chats.db.execute('SELECT t.status,c.removed,t.request,t.reply,t.digest FROM turns t JOIN chats c ON c.id=t.chat_id WHERE t.id=?',(ident,)).fetchone()
    job=store.job(ident)
    from host.speech_receipts import learning_valid
    speech_ok=not job or learning_valid(store.root,{**job['body'],'chat_id':job['chat_id']})
    return bool(speech_ok and row and job and job['state']=='RECORDED' and row['status']=='SUCCEEDED' and not row['removed'] and row['digest']==job['body']['command_digest'] and digest(row['reply'])==job['reply_digest'])
