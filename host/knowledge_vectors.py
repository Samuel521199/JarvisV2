"""Composition of optional local encoder and persistent projection; no downloads."""
import time

from host.local_models import MANAGERS
from modules.context_knowledge.vectors import Vectors
from sdk.protocol import CoreError


def build(root,db,checkpoint,progress):
    manager=MANAGERS.get(str(root))
    if not manager:raise CoreError('model_not_loaded','Local model manager unavailable')
    info=manager.knowledge_encoder()
    def encode(texts):
        until=time.monotonic()+30
        while True:
            checkpoint()
            try:return manager.encode_knowledge(texts,'passage',info['space'],checkpoint)
            except CoreError as exc:
                if exc.code!='model_busy' or time.monotonic()>until:raise
                time.sleep(.05)
    return Vectors(db).build(info['space'],info['dimension'],encode,checkpoint,progress)


def search(root,db,scope,provider,query):
    manager=MANAGERS.get(str(root))
    if not manager:return [],{'status':'model_not_loaded'}
    if len(query)>160:return [],{'status':'long_query'}
    # An absent/stale model space must not spend any inference.
    state=Vectors(db).status()
    if not state['active']:return [],{'status':'not_built'}
    if not state['recipe_current']:return [],{'status':'recipe_changed'}
    deadline=time.monotonic()+.35
    try:
        info=manager.knowledge_encoder()
        if info['space']!=state['active']['model_space']:return [],{'status':'space_changed'}
        vector=manager.encode_knowledge([query],'query',info['space'],wait_seconds=.25)[0]
        if time.monotonic()>deadline:return [],{'status':'timeout'}
        rows,status=Vectors(db).search(scope,provider,info['space'],vector,deadline)
        return rows,{**status,'model':info['model']}
    except Exception as exc:
        return [],{'status':exc.code if isinstance(exc,CoreError) else 'unavailable'}
