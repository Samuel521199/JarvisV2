"""Local workbench: bounded settings writes and asynchronous text conversations."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import re
import secrets
import sqlite3
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core import Core
from host import assistant
from host import connectors
from host.dialogue import DialogueHost
from host.settings_operations import command as settings_command, TaskRunner
from host import workbench
from host.memory import command as memory_command
from host.development import command as development_command, DevelopmentRunner, list_runs
from host.tools import command as tools_command, catalog as tools_catalog
from host.goals import command as goals_command, listing as goal_listing, GoalRunner
from host.background import BackgroundLane
from host.goal_growth import command as growth_command, GrowthRunner
from modules.workspace.store import Workspace
from modules.preferences.store import Preferences
from modules.preferences.management import manage
from modules.registry_composer.extensions import Extensions
from modules.dialogue.store import Dialogues
from control.credentials import Credentials
from control.network import NetworkGate
from adapters.desktop.resources import sample as resource_sample
from control.paths import child, data_root
from control.recovery.gate import StopGate
from sdk.protocol import CoreError, canonical, decode, read_json
from sdk.pricing import estimate

ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css"), "/brand/core.png": ("brand/core.png", "image/png"),
          "/brand/icon.png": ("brand/icon.png", "image/png")}
ASSETS['/settings'] = ('settings.html', 'text/html')
ASSETS['/brand/'] = ('brand-preview.html', 'text/html')
for asset in Path(__file__).parent.glob('*'):
    if asset.suffix in {'.js', '.css', '.svg'}:
        ASSETS['/' + asset.name] = (asset.name, {'.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml'}[asset.suffix])


def snapshot(root):
    core = Core(root)
    try:
        status = core.status()
        tasks = core.db.all("SELECT id,status,revision,spent,error,body FROM tasks ORDER BY created DESC LIMIT 100")
        for row in tasks: row['goal']=decode(row.pop('body'))['goal']
        developments = core.db.all("SELECT id,status,phase,attempt,task_id,release_id,error FROM development_runs ORDER BY created DESC LIMIT 40")
        packages = core.db.all("SELECT id,capability,status,report FROM packages ORDER BY created DESC LIMIT 40")
        calls = core.db.all("SELECT id,run_id,phase,provider,model,status,usage,error,created,billing_profile FROM model_calls ORDER BY created DESC LIMIT 10000")
        for row in calls:
            row['usage']=decode(row['usage']) if row['usage'] else {}
            if 'input_tokens' in row['usage'] and 'prompt_tokens' not in row['usage']:
                from adapters.models.codex_cli import normalize_usage
                row['usage']=normalize_usage(row['usage'])
            profile=decode(row['billing_profile']) if row['billing_profile'] else None
            row.pop('billing_profile',None)
            row['billing']=estimate(profile,row['usage'],row['created'])
            row['key_label']=(profile or {}).get('key_label','')
            row['connection_label']=(profile or {}).get('connection_label',row['provider'])
        for row in packages: row["report"] = decode(row["report"]) if row["report"] else None
        settings = core.preferences.public(core.credentials.available)
        import shutil
        settings['coding']={**settings.get('coding',{}),'adapter_state':'candidate_only','available':bool(shutil.which('codex.exe'))}
        checks_path = child(core.root, 'config/model-probes.json')
        checks = read_json(checks_path) if checks_path.exists() else None
        return {"status": status, "tasks": tasks, "developments": developments, "packages": packages, "calls": calls,
                'settings': settings, 'connection_checks': checks}
    finally: core.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def origin_allowed(self, write=False):
        origin = "http://127.0.0.1:" + str(self.server.server_port)
        return (self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
                and self.headers.get('Origin', '' if write else origin) == origin
                and self.headers.get('Sec-Fetch-Site') != 'cross-site')

    def json(self, value, status=200):
        self.reply(status, canonical(value).encode(), 'application/json')

    def do_GET(self):
        if not self.origin_allowed():
            return self.reply(403, b"Forbidden", "text/plain")
        route = urlsplit(self.path)
        if route.query: return self.reply(400, b"Unexpected query", "text/plain")
        if route.path.startswith('/api/anatomy/artifacts/'):
            try:
                from host.anatomy import artifact
                return self.reply(200,artifact(data_root(self.server.data_root),route.path.rsplit('/',1)[-1]),'text/html',anatomy=True)
            except (CoreError,OSError,ValueError):return self.json({'error':'artifact_unavailable'},404)
        if route.path == '/api/anatomy/compositions' or route.path.startswith('/api/anatomy/compositions/'):
            try:
                from host.anatomy_composer import listing,state
                return self.json(listing(data_root(self.server.data_root)) if route.path=='/api/anatomy/compositions' else state(data_root(self.server.data_root),route.path.rsplit('/',1)[-1]))
            except (CoreError,OSError,ValueError,sqlite3.Error):return self.json({'error':'anatomy_missing'},404)
        if route.path == '/api/task-runner':return self.json(self.server.task_runner.state())
        if route.path == '/api/connectors':
            try:return self.json(connectors.listing(data_root(self.server.data_root)))
            except (CoreError,OSError,ValueError,sqlite3.Error):return self.json({'error':'core_unavailable'},503)
        if route.path == '/api/goals':
            try:return self.json(goal_listing(data_root(self.server.data_root)))
            except (CoreError,OSError,ValueError,sqlite3.Error):return self.json({'error':'core_unavailable'},503)
        if route.path == '/api/tools':
            try: return self.json(tools_catalog(data_root(self.server.data_root)))
            except (CoreError, OSError, ValueError, sqlite3.Error): return self.json({'error': 'core_unavailable'}, 503)
        if route.path == '/api/development-runner': return self.json(self.server.development_runner.state())
        if route.path == '/api/developments': return self.json(list_runs(data_root(self.server.data_root)))
        if route.path == '/api/extensions':
            store=Extensions(data_root(self.server.data_root))
            try:return self.json(store.list())
            finally:store.close()
        if route.path == '/api/network':return self.json(NetworkGate(data_root(self.server.data_root)).read())
        if route.path == '/api/resources':return self.json(resource_sample())
        if route.path == '/api/health':
            return self.json({'control': StopGate(data_root(self.server.data_root)).state()})
        if route.path == "/api/snapshot":
            try: return self.reply(200, canonical(snapshot(self.server.data_root)).encode(), "application/json")
            except (CoreError, OSError, ValueError, sqlite3.Error): return self.reply(503, b'{"error":"core_unavailable"}', "application/json")
        if route.path == '/api/session':
            return self.json({'token': getattr(self.server, 'nonce', ''), 'data_root': str(self.server.data_root)})
        if route.path in {'/api/projects', '/api/skills', '/api/usage'}:
            try: return self.json(workbench.read(data_root(self.server.data_root), route.path))
            except (CoreError, OSError, ValueError, sqlite3.Error): return self.json({'error': 'local_io_or_config'}, 503)
        if route.path == '/api/chats' or re.fullmatch(r'/api/chats/chat-[0-9a-f]{32}', route.path):
            store = Dialogues(data_root(self.server.data_root))
            try:
                return self.json(store.list() if route.path == '/api/chats' else assistant.projection(data_root(self.server.data_root),store.read(route.path.rsplit('/', 1)[-1])))
            except CoreError as exc: return self.json({'error': exc.code}, 404)
            finally: store.close()
        if route.path not in ASSETS: return self.reply(404, b"Not found", "text/plain")
        filename, mime = ASSETS[route.path]
        self.reply(200, (Path(__file__).parent / filename).read_bytes(), mime)

    def do_POST(self):
        token = self.headers.get('X-Jarvis-Token', '')
        if (not self.origin_allowed(write=True) or not token or not token.isascii()
            or not getattr(self.server, 'nonce', '') or not secrets.compare_digest(token, self.server.nonce)):
            return self.json({'error': 'page_session'}, 403)
        route = urlsplit(self.path)
        if route.query or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json':
            return self.json({'error': 'invalid_request'}, 400)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            limit = 1600000 if route.path == '/api/project/write' else 200000
            if not 0 < size <= limit: return self.json({'error': 'request_size'}, 413)
            self.connection.settimeout(10)
            raw = self.rfile.read(size)
            if len(raw) != size: return self.json({'error': 'request_size'}, 400)
            body = decode(raw); root = data_root(self.server.data_root)
            if route.path == '/api/anatomy/compose':
                from host.anatomy_composer import submit
                return self.json(submit(root,body,self.server.dialogues),202)
            if route.path in ('/api/anatomy/finish','/api/anatomy/cancel'):
                from host.anatomy_composer import finish,cancel
                if not isinstance(body,dict) or set(body)!={'id'}:raise CoreError('anatomy_scene_invalid','Expected scene request ID')
                return self.json((finish if route.path.endswith('/finish') else cancel)(root,body['id']))
            if route.path == '/api/anatomy/render':
                from host.anatomy import render
                return self.json(render(root,body),201)
            if route.path == '/api/assistant/action':return self.json(assistant.accept(root,body))
            if route.path == '/api/connectors':return self.json(connectors.command(root,body))
            if route.path == '/api/connectors/run':return self.json(self.server.task_runner.start_connector(body),202)
            if route.path == '/api/connectors/discover':
                if not isinstance(body,dict) or set(body)!={'id','revision'} or not isinstance(body['id'],str) or type(body['revision']) is not int:
                    raise CoreError('mcp_invalid','Invalid discovery request')
                return self.json(self.server.development_runner.lane.submit('connector',body['id'],connectors.command,root,{'action':'discover',**body}),202)
            if route.path == '/api/memory': return self.json(memory_command(root, body))
            if route.path == '/api/tools': return self.json(tools_command(root, body))
            if route.path == '/api/tools/run': return self.json(self.server.task_runner.start_tool(body), 202)
            if route.path == '/api/goal-growth':return self.json(growth_command(root,body))
            if route.path == '/api/goal-growth/run':return self.json(self.server.growth_runner.start(body),202)
            if route.path == '/api/goals': return self.json(goals_command(root,body))
            if route.path == '/api/goals/plan': return self.json(self.server.goal_runner.start(body),202)
            if route.path == '/api/goals/run': return self.json(self.server.task_runner.start_goal(body),202)
            if route.path == '/api/development': return self.json(development_command(root, body))
            if route.path == '/api/development-runner': return self.json(self.server.development_runner.start(body), 202)
            if route.path == '/api/extensions':
                store=Extensions(root)
                try:return self.json(store.command(body))
                finally:store.close()
            if route.path == '/api/operations':return self.json(settings_command(root,body))
            if route.path == '/api/task-runner':return self.json(self.server.task_runner.start(body),202)
            if route.path == '/api/network':return self.json(NetworkGate(root).update(body))
            if route.path.startswith(('/api/project/', '/api/skill/')) or route.path in {'/api/chat/update','/api/chat/workspace'}:
                return self.json(workbench.command(root, route.path, body))
            if route.path in {'/api/settings', '/api/preferences', '/api/settings/manage'}:
                store = Preferences(root)
                try:
                    if route.path == '/api/settings/manage':
                        StopGate(root).require_running(); manage(store,body,Credentials(root))
                        return self.json({'ok': True, 'settings': store.public(Credentials(root).available)})
                    if route.path == '/api/settings':
                        StopGate(root).require_running(); store.update(body)
                        return self.json({'ok': True, 'settings': store.public(Credentials(root).available)})
                    return self.json({'ok': True, 'ui': store.save_ui(body)})
                finally: store.close()
            if route.path == '/api/chat/send':
                return self.json(self.server.dialogues.submit(body), 202)
            if route.path == '/api/chats' or route.path == '/api/chat/cancel':
                store = Dialogues(root)
                try:
                    if route.path == '/api/chats':
                        if not isinstance(body, dict) or set(body) - {'project_id'}: raise CoreError('chat_invalid', 'Unexpected creation fields')
                        project_id = body.get('project_id', '')
                        if project_id:
                            projects = Workspace(root)
                            try: projects.path(project_id)
                            finally: projects.close()
                        return self.json({'id': workbench.session_workspace.create(root,project_id)}, 201)
                    if not isinstance(body, dict) or set(body) != {'request_id'}: raise CoreError('chat_invalid', 'Invalid cancellation')
                    return self.json({'cancel_requested': store.cancel(body['request_id'])})
                finally: store.close()
            return self.json({'error': 'not_found'}, 404)
        except CoreError as exc: return self.json({'error': exc.code}, 409 if exc.code in {'conflict','chat_busy','chat_capacity'} else 400)
        except (OSError, ValueError, TypeError, sqlite3.Error): return self.json({'error': 'local_io_or_config'}, 400)

    def reply(self, status, body, mime, anatomy=False):
        self.send_response(status)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/json" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", ("sandbox allow-scripts allow-downloads; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'" if anatomy else "default-src 'self'; connect-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"))
        self.end_headers(); self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(ROOT / "user-data")); parser.add_argument("--port", type=int, default=18282)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error("port out of range")
    snapshot(args.data_root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.data_root = data_root(args.data_root)
    server.nonce = secrets.token_urlsafe(32)
    try:
        server.dialogues = DialogueHost(server.data_root)
        server.task_runner = TaskRunner(server.data_root)
        server.background_lane = BackgroundLane()
        server.development_runner = DevelopmentRunner(server.data_root,server.background_lane)
        server.goal_runner = GoalRunner(server.data_root,server.background_lane)
        server.growth_runner = GrowthRunner(server.data_root,server.background_lane)
        server.dialogues.on_goal=lambda ident:server.goal_runner.start({'id':ident,'retry_unknown':False})
    except BaseException: server.server_close(); raise
    print("Jarvis core workbench: http://127.0.0.1:" + str(server.server_port), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close(); server.dialogues.close(); server.task_runner.close(); server.development_runner.close(); server.background_lane.close()


if __name__ == "__main__": main()
