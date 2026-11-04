"""Content-free activity projection shared by UI and managed handoff.

Queued durable work is retained for the next host. Live workers and authorization
callbacks must finish before a managed shutdown; an inspection failure blocks it.
"""
from control.paths import data_root


def snapshot(root, server):
    root = str(data_root(root))
    rows = []

    def inspect(name, reader):
        try:
            count = reader()
            rows.append({'id': name, 'state': 'busy' if count else 'idle', 'active': int(count)})
        except Exception:
            rows.append({'id': name, 'state': 'unknown', 'active': None})

    def service(name, reader):
        obj = getattr(server, name, None)
        inspect(name, lambda: reader(obj)) if obj is not None else rows.append(
            {'id': name, 'state': 'not_started', 'active': 0})

    service('request_activity', lambda obj: obj.count())
    service('dialogues', lambda obj: len(obj.state()['running']))
    service('task_runner', lambda obj: len(obj.state()['active']))
    service('background_lane', lambda obj: int(obj.state()['status'] == 'running'))

    def mailbox(obj):
        with obj.lock:
            future = (obj.auth or {}).get('future')
            return len(obj.active) + int(future is not None and not future.done())

    def family(obj):
        with obj.lock:
            return len(obj.active)

    def models(obj):
        with obj.lock:
            return sum(future is not None and not future.done()
                       for future in (obj.future, obj.recall_future))

    service('mailbox', mailbox)
    service('family', family)
    manager = getattr(server, 'local_models', None)
    if manager is not None and not hasattr(manager, 'lock'):
        rows.append({'id': 'local_models', 'state': 'not_started', 'active': 0})
    else:
        service('local_models', models)

    from host import studio3d, studio3d_learning, image_generation, knowledge, knowledge_extraction

    def jobs(module):
        with module.GUARD:
            return sum(key[0] == root for key in module.ACTIVE)

    def indexing():
        with knowledge.JOBS_LOCK:
            return int((knowledge.JOBS.get(root) or {}).get('state') in {'queued', 'running'})

    def extraction():
        with knowledge_extraction.LOCK:
            future = knowledge_extraction.ACTIVE.get(root)
            return int(future is not None and not future.done())

    inspect('studio3d', lambda: jobs(studio3d))
    def learning():
        with studio3d_learning.ADMISSION:
            return sum(key[0] == root for key in studio3d_learning.ACTIVE)
    inspect('studio3d_learning', learning)
    inspect('images', lambda: jobs(image_generation))
    inspect('knowledge', indexing)
    inspect('knowledge_extraction', extraction)
    return {'drained': all(row['state'] in {'idle', 'not_started'} for row in rows),
            'participants': rows,
            'scope': 'managed host workers and HTTP requests; external processes are not controlled'}
