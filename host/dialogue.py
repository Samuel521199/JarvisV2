"""Durable input queues; two foreground slots and a separate background slot."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import threading
import sqlite3
import time

from adapters.models.native import NativeModel
from control.paths import child
from control.recovery.gate import StopGate, RunLock
from control.credentials import Credentials
from modules.preferences.store import Preferences, fallback_routes, resolve
from modules.dialogue.store import Dialogues
from modules.skills.catalog import Skills
from modules.skills.model_library.preview import preview_request, resolve_preview
from sdk.protocol import CoreError, decode
from host import memory
from host import session_workspace


class DialogueHost:
    def __init__(self, root, on_goal=None):
        self.root = root
        self.on_goal=on_goal
        self.lease = RunLock(root, 'dialogue'); self.lease.__enter__()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='jarvis-dialogue')
        self.background_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='jarvis-background-replies')
        self.lock = threading.RLock(); self.active = set(); self.closing = threading.Event()
        self.pending = {}; self.running = {}; self.delays = deque(maxlen=800)
        self.closed = False
        try:
            store = Dialogues(root)
            try:
                store.recover(preserve_queued=True)
                for row in store.db.execute("SELECT id,chat_id,lane FROM turns WHERE status='READY' ORDER BY created,rowid"):
                    self.pending[row['id']] = {'chat_id': row['chat_id'], 'lane': row['lane'], 'queued': time.monotonic()}
                    self.active.add(row['id'])
            finally: store.close()
            with self.lock: self._pump()
        except BaseException:
            self.pool.shutdown(wait=True); self.background_pool.shutdown(wait=True); self.lease.__exit__(None, None, None); raise

    def submit(self, command):
        return self._submit(command, 'foreground')

    def submit_background(self, command):
        return self._submit(command, 'background')

    def _submit(self, command, lane):
        StopGate(self.root).require_running()
        prefs = Preferences(self.root); store = Dialogues(self.root)
        try:
            if not isinstance(command, dict): raise CoreError('chat_invalid', 'Expected a conversation request')
            from host.speech_sources import check_turn as check_speech_turn
            check_speech_turn(self.root,command.get('request_id'),command)
            selected = command.get('provider', 'auto')
            local_preview = lane == 'foreground' and preview_request(command)
            if local_preview:
                from control.application_runtime import coordination
                if coordination(self.root) is not None:
                    from control.application_compatibility import declares_library_preview
                    from control.controller_pin import read as pinned_controller
                    if declares_library_preview(pinned_controller(self.root)['controller']) is not True:
                        raise CoreError('controller_protocol','Managed model-library previews need a compatible rollback controller')
            routes = []
            if not local_preview:
                settings = prefs.read()
                if not settings: raise CoreError('settings_missing', 'Configure model connections first')
                cfg = settings['catalog']
                route = resolve(cfg, selected, command.get('model') or None, command.get('reasoning', 'default'))
                routes = [route]
                if selected == 'auto': routes.extend(fallback_routes(cfg, route))
            if 'reference_image' in command or 'reference_images' in command:
                from host.studio3d_reference import record
                from host.studio3d import enabled
                enabled(self.root)
                ids=command.get('reference_images',[command.get('reference_image')])
                if 'reference_image' in command and 'reference_images' in command or not isinstance(ids,list) or not 1<=len(ids)<=2:raise CoreError('chat_invalid','Expected explicit image IDs')
                from adapters.models.vision import encode_png,validate_encoded
                validate_encoded([encode_png(record(self.root,i)[1]) for i in ids])
                if selected=='auto' or route['adapter'] not in {'vertex','gemini','eachlabs'} or command.get('assistant_mode',False):raise CoreError('model_vision_unsupported','Select an explicit supported image route')
            with self.lock:
                if self.closing.is_set(): raise CoreError('chat_capacity', 'Dialogue host is closing')
                existing = store.db.execute('SELECT 1 FROM turns WHERE id=?', (command.get('request_id'),)).fetchone()
                queued = sum(r['lane'] == lane for r in self.pending.values()) + sum(r['lane'] == lane for r in self.running.values())
                if not existing and queued >= (32 if lane == 'foreground' else 8):
                    raise CoreError('chat_capacity', 'Input queue is full; keep the draft and retry')
                skills = Skills(self.root)
                try: guidance = skills.select(command.get('skill', 'none'), command.get('text', ''))
                finally: skills.close()
                session_workspace.ensure(self.root,store.read(command.get('chat_id','')),write=True)
                fresh = store.begin(command, routes, guidance, allow_queue=True, lane=lane)
                capture={'state':'not_requested'}
                if fresh:
                    from host.memory_capture import capture as capture_memory
                    if lane == 'foreground' and not local_preview: capture=capture_memory(self.root,command)
                    self.active.add(command['request_id'])
                    self.pending[command['request_id']] = {'chat_id': command['chat_id'], 'lane': lane, 'queued': time.monotonic()}
                    self._pump()
                queued = command['request_id'] in self.pending
            return {'request_id': command['request_id'], 'existing': not fresh,'memory_capture':capture,
                    'status': 'queued' if queued else 'running', 'persisted': True, 'lane': lane}
        finally: store.close(); prefs.close()

    def _pump(self):
        from control.application_runtime import accepting
        if not accepting(self.root): return
        if self.closing.is_set(): return
        chats = {v['chat_id'] for v in self.running.values()}
        counts = {lane: sum(v['lane'] == lane for v in self.running.values()) for lane in ('foreground', 'background')}
        for ident, entry in list(self.pending.items()):
            lane = entry['lane']
            if entry['chat_id'] in chats or counts[lane] >= (2 if lane == 'foreground' else 1): continue
            self.running[ident] = entry; del self.pending[ident]
            chats.add(entry['chat_id']); counts[lane] += 1
            (self.pool if lane == 'foreground' else self.background_pool).submit(self.run, ident)

    def state(self):
        with self.lock:
            return {'running': [{'id': i, 'chat_id': r['chat_id'], 'lane': r['lane']} for i, r in self.running.items()],
                    'queued': [{'id': i, 'chat_id': r['chat_id'], 'lane': r['lane']} for i, r in self.pending.items()],
                    'limits': {'foreground': 2, 'background': 1, 'foreground_queue': 32, 'background_queue': 8},
                    'dispatch_delay_ms': list(self.delays)}

    def cancel(self, ident):
        with self.lock:
            store = Dialogues(self.root)
            try:
                changed = store.cancel(ident)
                if ident in self.pending:
                    store.finish(ident, {'status': 'CANCELLED', 'code': 'chat_cancelled'})
                    del self.pending[ident]; self.active.discard(ident)
                    self._pump()
                return changed
            finally: store.close()

    def run(self, ident):
        store = Dialogues(self.root); attempt = None; result = None; view = None; memory_db = None
        from host import english_learning
        learning_job=None
        try:
            learning_job=english_learning.binding(self.root,ident)
            with self.lock:
                entry = self.running.get(ident)
                if entry and entry['lane'] == 'foreground':
                    self.delays.append(round((time.monotonic()-entry['queued'])*1000, 3))
            def checkpoint():
                if self.closing.is_set(): raise CoreError('chat_cancelled', 'Server is closing')
                StopGate(self.root).require_running(); store.checkpoint(ident)
                from host.speech_sources import check_turn as check_speech_turn
                check_speech_turn(self.root,ident,decode(store.turn(ident)['request']))
                if learning_job:english_learning.checkpoint(self.root,ident)
                if view is not None:memory.refresh_view(self.root,view,chats=store,memory_db=memory_db)
            checkpoint()
            turn = store.turn(ident)
            routes = decode(turn['routes'])
            if not routes and turn['lane'] == 'foreground':
                preview = preview_request(decode(turn['request']))
                if preview:
                    session_workspace.ensure(self.root, store.header(turn['chat_id']), write=True)
                    result = resolve_preview(self.root, *preview)
            for route in routes:
                checkpoint()
                if learning_job and learning_job['body'].get('fixed_question'):
                    from sdk.protocol import canonical
                    result=english_learning.materialize(self.root,ident,{'status':'SUCCEEDED','text':canonical(learning_job['body']['fixed_question']),'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0},'provider':'local-software','model':learning_job['body']['game']['software']['version']})
                    break
                client = NativeModel(route, Credentials(self.root).get, child(self.root, 'temp'))
                if not client.available():
                    result = {'status': 'REJECTED', 'code': 'local_runtime_not_prepared' if route['adapter'] == 'local' else 'credential_unavailable'}
                    continue
                turn = store.turn(ident); request = decode(turn['request'])
                view = memory.dialogue_view(self.root, store.read(turn['chat_id']), route, request.get('memory_enabled', True),request['text'])
                if memory_db is None:memory_db, _ = memory.open_memory(self.root)
                from host.memory_capture import annotate
                annotate(self.root,ident,view,request)
                with memory.LOCK:
                    if request.get('assistant_mode',False):
                        from host import assistant
                        instruction,items=assistant.instructions(self.root,turn['chat_id'],route['id'],request.get('memory_enabled',True),decode(turn['guidance']) if turn.get('guidance') else None)
                        view['dependencies']=[{'id':r['id'],'revision':r['revision']} for r in view['facts']]
                        view['dependencies'].extend(r for item in items for r in item.get('memory_dependencies',[]))
                    memory.refresh_view(self.root,view,chats=store,memory_db=memory_db);messages = store.context(ident, view)
                learning_messages=english_learning.context(self.root,store.turn(ident)) if learning_job else None
                if learning_messages is not None:messages=learning_messages
                checkpoint()
                attempt = store.start_attempt(ident, route)
                if learning_messages is not None:
                    result=client.complete(messages,checkpoint,json_mode=True)
                    try:result=english_learning.materialize(self.root,ident,result)
                    except CoreError as exc:result={**result,'status':'INVALID','code':exc.code}
                elif request.get('assistant_mode',False):
                    messages[-1]['content']+='\n\n'+instruction
                    result=client.complete(messages,checkpoint,json_mode=True)
                    if result['status']=='SUCCEEDED':
                        try:
                            reply,action=assistant.parse(result['text'],items)
                            result={**result,'text':reply,'assistant_action':action}
                        except CoreError:result={'status':'INVALID','code':'assistant_invalid','usage':result.get('usage',{})}
                elif request.get('reference_image') or request.get('reference_images'):
                    from host.studio3d_reference import record
                    from host.studio3d import enabled
                    enabled(self.root);pairs=[record(self.root,i) for i in request.get('reference_images',[request.get('reference_image')])]
                    result=client.complete(messages,checkpoint,**({'reference_png':pairs[0][1]} if 'reference_image' in request else {'reference_pngs':[raw for _,raw in pairs]}))
                    image_receipts=[{'id':row['id'],'sha256':row['sha256'],'sent_to_provider':route['id']} for row,_ in pairs]
                    result['reference_images']=image_receipts
                    if 'reference_image' in request:result['reference_image']=image_receipts[0]
                else:result = client.complete(messages, checkpoint)
                store.attempt_result(attempt, result); attempt = None
                result.update(provider=route['id'], model=route['model'])
                if result['status'] in {'SUCCEEDED', 'UNKNOWN'}: break
            if result is None: result = {'status': 'FAILED', 'code': 'model_unavailable'}
            if result['status'] in {'REJECTED', 'INVALID'}: result['status'] = 'FAILED'
            with memory.LOCK:
                from host.delivery_review import observe as observe_delivery,materialize as materialize_delivery
                delivery_turn=store.turn(ident)
                result,rendering=materialize_delivery(delivery_turn,result)
                result['delivery_review']=observe_delivery(delivery_turn,result)
                if rendering and result['delivery_review'] is not None:result['delivery_review']['rendering']=rendering
                checkpoint(); store.finish(ident, result)
                if learning_job:
                    try:english_learning.completed(self.root,ident)
                    except (CoreError,OSError,sqlite3.Error):pass  # Reconcile the durable reply on the next learning view; never repeat the paid call.
                try:
                    turn=store.turn(ident)
                    session_workspace.publish_reply(self.root,store.read(turn['chat_id']),turn)
                except (CoreError,OSError,sqlite3.Error) as exc:
                    session_workspace.pending(self.root,turn['chat_id'],exc)
                if result.get('assistant_action',{}).get('kind')=='commitment':
                    try:
                        from host.assistant import commitment_from_turn
                        commitment_from_turn(self.root,ident)
                    except (CoreError,OSError,sqlite3.Error):pass  # Candidate remains available; only a durable receipt proves acceptance.
                if result.get('assistant_action',{}).get('kind')=='goal':
                    try:
                        from host.assistant import goal_from_turn
                        linked=goal_from_turn(self.root,ident)
                        if self.on_goal:self.on_goal(linked['id'])
                    except (CoreError,OSError,sqlite3.Error):pass  # Successful reply and durable proposal remain available for explicit retry.
        except BaseException as exc:
            code = exc.code if isinstance(exc, CoreError) else 'local_response_error'
            if attempt is not None: store.attempt_result(attempt, {'status': 'UNKNOWN', 'code': code})
            store.finish(ident, {'status': 'CANCELLED' if code == 'chat_cancelled' else 'UNKNOWN', 'code': code})
        finally:
            if memory_db is not None: memory_db.close()
            store.close()
            with self.lock:
                self.active.discard(ident); self.running.pop(ident, None); self._pump()

    def close(self):
        if self.closed: return
        self.closed = True
        self.closing.set()
        try:
            self.pool.shutdown(wait=True); self.background_pool.shutdown(wait=True)
        finally: self.lease.__exit__(None, None, None)
