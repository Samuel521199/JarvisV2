"""Two foreground request slots, separate from development/Worker locks."""
from concurrent.futures import ThreadPoolExecutor
import threading
import sqlite3
import time

from adapters.models.native import NativeModel
from control.paths import child
from control.recovery.gate import StopGate, RunLock
from control.credentials import Credentials
from modules.preferences.store import Preferences, resolve
from modules.dialogue.store import Dialogues
from modules.skills.catalog import Skills
from sdk.protocol import CoreError, decode
from host import memory
from host import session_workspace


class DialogueHost:
    def __init__(self, root, on_goal=None):
        self.root = root
        self.on_goal=on_goal
        self.lease = RunLock(root, 'dialogue'); self.lease.__enter__()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='jarvis-dialogue')
        self.lock = threading.Lock(); self.active = set(); self.closing = threading.Event()
        try:
            store = Dialogues(root)
            try: store.recover()
            finally: store.close()
        except BaseException:
            self.pool.shutdown(wait=True); self.lease.__exit__(None, None, None); raise

    def submit(self, command):
        StopGate(self.root).require_running()
        prefs = Preferences(self.root); store = Dialogues(self.root)
        try:
            settings = prefs.read()
            if not settings: raise CoreError('settings_missing', 'Configure model connections first')
            cfg = settings['catalog']
            if not isinstance(command, dict): raise CoreError('chat_invalid', 'Expected a conversation request')
            selected = command.get('provider', 'auto')
            route = resolve(cfg, selected, command.get('model') or None, command.get('reasoning', 'default'))
            routes = [route]
            if selected == 'auto' and cfg['automatic_fallback']:
                for name in cfg['fallback_order']:
                    if name != route['id'] and cfg['providers'][name].get('enabled', True): routes.append(resolve(cfg, name))
            with self.lock:
                if self.closing.is_set(): raise CoreError('chat_capacity', 'Dialogue host is closing')
                if len(self.active) >= 2: raise CoreError('chat_capacity', 'Two foreground responses are already active')
                skills = Skills(self.root)
                try: guidance = skills.select(command.get('skill', 'none'), command.get('text', ''))
                finally: skills.close()
                session_workspace.ensure(self.root,store.read(command.get('chat_id','')),write=True)
                fresh = store.begin(command, routes, guidance)
                if fresh:
                    self.active.add(command['request_id'])
                    self.pool.submit(self.run, command['request_id'])
            return {'request_id': command['request_id'], 'existing': not fresh}
        finally: store.close(); prefs.close()

    def run(self, ident):
        store = Dialogues(self.root); attempt = None; result = None; epoch = None; valid_until = None
        try:
            def checkpoint():
                if self.closing.is_set(): raise CoreError('chat_cancelled', 'Server is closing')
                StopGate(self.root).require_running(); store.checkpoint(ident)
                if epoch is not None and memory.current_epoch(self.root) != epoch: raise CoreError('memory_changed', 'Memory changed during this response')
                if valid_until and time.time() >= valid_until: raise CoreError('memory_changed', 'Context fact expired')
            checkpoint()
            for route in decode(store.turn(ident)['routes']):
                checkpoint()
                client = NativeModel(route, Credentials(self.root).get, child(self.root, 'temp'))
                if not client.available():
                    result = {'status': 'REJECTED', 'code': 'local_runtime_not_prepared' if route['adapter'] == 'local' else 'credential_unavailable'}
                    continue
                with memory.LOCK:
                    turn = store.turn(ident); request = decode(turn['request'])
                    view = memory.dialogue_view(self.root, store.read(turn['chat_id']), route, request.get('memory_enabled', True))
                    epoch = view['epoch']; valid_until = view['valid_until']; messages = store.context(ident, view)
                attempt = store.start_attempt(ident, route)
                if request.get('assistant_mode',False):
                    from host import assistant
                    instruction,items=assistant.instructions(self.root,turn['chat_id'],route['id'])
                    messages[-1]['content']+='\n\n'+instruction
                    result=client.complete(messages,checkpoint,json_mode=True)
                    if result['status']=='SUCCEEDED':
                        try:
                            reply,action=assistant.parse(result['text'],items)
                            result={**result,'text':reply,'assistant_action':action}
                        except CoreError:result={'status':'INVALID','code':'assistant_invalid','usage':result.get('usage',{})}
                else:result = client.complete(messages, checkpoint)
                store.attempt_result(attempt, result); attempt = None
                result.update(provider=route['id'], model=route['model'])
                if result['status'] in {'SUCCEEDED', 'UNKNOWN'}: break
            if result is None: result = {'status': 'FAILED', 'code': 'model_unavailable'}
            if result['status'] in {'REJECTED', 'INVALID'}: result['status'] = 'FAILED'
            with memory.LOCK:
                checkpoint(); store.finish(ident, result)
                try:
                    turn=store.turn(ident)
                    session_workspace.publish_reply(self.root,store.read(turn['chat_id']),turn)
                except (CoreError,OSError,sqlite3.Error) as exc:
                    session_workspace.pending(self.root,turn['chat_id'],exc)
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
            store.close()
            with self.lock: self.active.discard(ident)

    def close(self):
        self.closing.set()
        try: self.pool.shutdown(wait=True)
        finally: self.lease.__exit__(None, None, None)
