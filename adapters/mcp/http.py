"""Bounded Streamable HTTP subset. No redirects, ambient proxy, auth or retries.

No code from servers is executed. Each session is request-scoped. At most two
transport threads can remain in flight, including abandoned/cancelled requests.
"""
import queue
import re
import http.client
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from sdk.protocol import CoreError, canonical, decode

VERSIONS = {'2025-11-25', '2025-06-18', '2025-03-26'}
SLOTS = threading.BoundedSemaphore(2)
MAX_BYTES = 131072


def endpoint(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise CoreError('mcp_endpoint', 'Invalid endpoint')
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError:
        raise CoreError('mcp_endpoint', 'Invalid endpoint') from None
    if (u.scheme not in {'https', 'http'} or not u.hostname or u.username or u.password or u.query or u.fragment
            or u.scheme == 'http' and u.hostname not in {'127.0.0.1', '::1'} or port == 0):
        raise CoreError('mcp_endpoint', 'Use HTTPS or a literal loopback HTTP endpoint without credentials')
    return url


class Session:
    def __init__(self, url, checkpoint=lambda: None, timeout=25):
        self.url = endpoint(url)
        self.checkpoint = checkpoint
        self.deadline = time.monotonic() + timeout
        self.version = '2025-11-25'
        self.session = None
        self.sequence = 0

    def check(self):
        self.checkpoint()
        if time.monotonic() >= self.deadline:
            raise CoreError('mcp_timeout', 'Connector time limit reached')

    def exchange(self, payload):
        self.check()
        if not SLOTS.acquire(blocking=False):
            raise CoreError('mcp_busy', 'Connector transport capacity occupied')
        result = queue.Queue(maxsize=1)
        cancelled = threading.Event()
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': self.version}
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        data = canonical(payload).encode()
        uri = urlsplit(self.url)
        conn = (http.client.HTTPSConnection(uri.hostname, uri.port, timeout=5, context=ssl.create_default_context())
                if uri.scheme == 'https' else http.client.HTTPConnection(uri.hostname, uri.port, timeout=5))

        def work():
            try:
                if cancelled.is_set(): return
                conn.connect()
                # DNS/TLS can outlive cancellation. Never dispatch after they complete late.
                if cancelled.is_set() or time.monotonic() >= self.deadline: return
                conn.request('POST', uri.path or '/', body=data, headers=headers)
                with conn.getresponse() as response:
                    if 300 <= response.status < 400: raise CoreError('mcp_redirect', 'Register the new endpoint explicitly')
                    if response.status not in {200, 202}: raise CoreError('mcp_transport', 'Endpoint rejected HTTP request')
                    session = response.headers.get('Mcp-Session-Id')
                    if session is not None and not re.fullmatch(r'[\x21-\x7e]{1,256}', session):
                        raise CoreError('mcp_protocol', 'Invalid session identifier')
                    if 'id' not in payload:
                        if response.status != 202: raise CoreError('mcp_protocol', 'Notification not accepted')
                        result.put((None, session)); return
                    mime = response.headers.get_content_type()
                    if mime not in {'application/json', 'text/event-stream'}:
                        raise CoreError('mcp_protocol', 'Unsupported response format')
                    raw = bytearray(); event = []
                    while True:
                        if cancelled.is_set() or time.monotonic() >= self.deadline:
                            raise CoreError('mcp_timeout', 'Response interrupted')
                        chunk = response.readline(MAX_BYTES + 1) if mime == 'text/event-stream' else response.read1(8192)
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES: raise CoreError('mcp_output_limit', 'Response exceeds limit')
                        if mime == 'application/json':
                            if not chunk: result.put((decode(bytes(raw)), session)); return
                        else:
                            if not chunk: raise CoreError('mcp_protocol', 'SSE ended before a response')
                            line = chunk.decode('utf-8').rstrip('\r\n')
                            if line.startswith('data:'): event.append(line[5:].lstrip(' '))
                            if line == '' and event:
                                value = decode('\n'.join(event)); event = []
                                if isinstance(value, dict) and value.get('id') == payload['id']:
                                    result.put((value, session)); return
                                # Server requests are not supported. Notifications cannot grant access.
                                if not isinstance(value, dict) or 'id' in value:
                                    raise CoreError('mcp_protocol', 'Unexpected server request')
            except Exception as exc:
                result.put(exc if isinstance(exc, CoreError) else CoreError('mcp_transport', 'Endpoint did not return a usable response'))
            finally:
                conn.close()
                SLOTS.release()

        threading.Thread(target=work, daemon=True, name='jarvis-mcp-http').start()
        try:
            while True:
                self.check()
                try: value = result.get(timeout=.05); break
                except queue.Empty: continue
            self.check()
            if isinstance(value, Exception): raise value
            body, session = value
            if session:
                if self.session and self.session != session: raise CoreError('mcp_protocol', 'Session changed')
                self.session = session
            return body
        finally:
            cancelled.set()
            if conn.sock:
                try: conn.sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            conn.close()

    def request(self, method, params):
        self.sequence += 1
        body = self.exchange({'jsonrpc': '2.0', 'id': self.sequence, 'method': method, 'params': params})
        if (not isinstance(body, dict) or body.get('jsonrpc') != '2.0' or type(body.get('id')) is not int
                or body['id'] != self.sequence or ('result' in body) == ('error' in body)):
            raise CoreError('mcp_protocol', 'Invalid RPC response')
        if 'error' in body: raise CoreError('mcp_remote_error', 'Server rejected this RPC')
        if not isinstance(body['result'], dict): raise CoreError('mcp_protocol', 'Expected an object result')
        return body['result']

    def initialize(self):
        body = self.request('initialize', {'protocolVersion': self.version, 'capabilities': {},
                                         'clientInfo': {'name': 'jarvis', 'version': '0.2.0-dev.11'}})
        if body.get('protocolVersion') not in VERSIONS or not isinstance(body.get('capabilities'), dict) or 'tools' not in body['capabilities']:
            raise CoreError('mcp_protocol', 'Unsupported protocol or missing tools capability')
        self.version = body['protocolVersion']
        self.exchange({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return {'protocol': self.version, 'server': body.get('serverInfo', {})}

    def tools(self):
        found = []; cursor = None; seen = set()
        for _ in range(8):
            result = self.request('tools/list', {'cursor': cursor} if cursor else {})
            tools = result.get('tools')
            if not isinstance(tools, list): raise CoreError('mcp_protocol', 'Invalid tool list')
            found.extend(tools)
            if len(found) > 64 or len(canonical(found).encode()) > 65536:
                raise CoreError('mcp_output_limit', 'Tool discovery exceeds limit')
            cursor = result.get('nextCursor')
            if cursor is None: return found
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 512 or cursor in seen:
                raise CoreError('mcp_protocol', 'Invalid discovery cursor')
            seen.add(cursor)
        raise CoreError('mcp_output_limit', 'Too many discovery pages')
