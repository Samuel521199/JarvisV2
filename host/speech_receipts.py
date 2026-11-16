"""Read-only validity of a speech receipt, independent of learning/game orchestration."""
from control.paths import child
from host.speech_audio import read
from modules.speech.store import Store
from sdk.protocol import CoreError,digest


def learning_valid(root,record):
    receipt=record.get('speech',{});asr=receipt.get('asr')
    if not asr:return True
    if not child(root,'state/speech.sqlite3').exists():return False
    try:
        with Store(root) as store:row=store.get(asr['id'])
        body=row['body'];result=row['result'];scope=body['scope']
        if row['state']!='SUCCEEDED' or body['operation']!='transcribe' or scope['purpose']!='english-learning' or scope['chat_id']!=record['chat_id'] or not scope['exercise_id'] or record.get('exercise_id',scope['exercise_id'])!=scope['exercise_id']:return False
        _,meta=read(root,body['audio_id'])
        return (digest(result)==asr['result_digest'] and asr['confirmed_text']==record['answer'] and asr['raw_text']==result['text'] and asr['model']==result['model'] and receipt['id']==body['audio_id'] and meta['context']==scope and meta['sha256']==receipt['sha256']==result['audio_sha256'])
    except (CoreError,OSError,ValueError,KeyError,TypeError):return False
