"""Local synthetic MCP server; never accesses accounts, files or the internet."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time


class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        method = body['method']; self.server.methods.append(method)
        if self.server.mode == 'redirect':
            self.send_response(307); self.send_header('Location', '/other'); self.end_headers(); return
        if 'id' not in body:
            self.send_response(202); self.end_headers(); return
        if method == 'initialize':
            result = {'protocolVersion': '2025-11-25', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'Jarvis local fixture', 'version': '1'}}
        elif method == 'tools/list':
            result = {'tools': [{'name': 'echo', 'description': '本机模拟回显：返回输入文字，不读写外部系统。' + self.server.description,
                                  'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']},
                                  'annotations': {'readOnlyHint': True}}]}
            if self.server.mode == 'unsupported': result['tools'][0]['inputSchema']['oneOf'] = []
            if self.server.mode == 'cursor': result['nextCursor'] = 'repeat'
            if self.server.mode == 'duplicate': result['tools'] *= 2
        elif method == 'tools/call':
            self.server.calls += 1; self.server.called.set()
            if self.server.mode == 'slow': time.sleep(.8)
            if self.server.mode == 'disconnect': self.close_connection = True; return
            result = {'content': [{'type': 'text', 'text': body['params']['arguments']['text']}], 'isError': self.server.mode == 'error'}
            if self.server.mode == 'oversize': result['content'][0]['text'] = 'x' * 140000
            if self.server.mode == 'image': result['content'] = [{'type': 'image', 'data': 'untrusted'}]
        else: result = {}
        message = {'jsonrpc': '2.0', 'id': body['id'], 'result': result}
        if self.server.mode == 'bad_id': message['id'] = 999
        raw = json.dumps(message, ensure_ascii=False).encode()
        sse = self.server.mode == 'sse'
        if sse: raw = b'data: ' + raw + b'\n\n'
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream' if sse else 'application/json')
        self.send_header('Mcp-Session-Id', 'fixture-session'); self.send_header('Content-Length', str(len(raw))); self.end_headers()
        try: self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass


def server(port=0):
    srv = ThreadingHTTPServer(('127.0.0.1', port), MCPHandler)
    srv.mode = ''; srv.description = ''; srv.calls = 0; srv.methods = []; srv.called = threading.Event()
    return srv


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=18383); args = parser.parse_args()
    server(args.port).serve_forever()
