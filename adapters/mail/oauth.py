"""System-browser PKCE on a temporary IPv4 loopback callback."""
import base64
import hashlib
from http.server import HTTPServer,BaseHTTPRequestHandler
import secrets
import time
from urllib.parse import urlencode,urlsplit,parse_qs
import webbrowser

from adapters.mail.google import request,TOKEN,token_result
from sdk.mail import LEVELS
from sdk.protocol import CoreError


def authorize(client,level,guard,*,login_hint='',opener=None,ready=None,timeout=240):
    if level not in LEVELS:raise CoreError('mail_scope','Unknown authorization level')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48);result={}
    class Handler(BaseHTTPRequestHandler):
        def setup(self):super().setup();self.connection.settimeout(2)
        def log_message(self,*args):pass
        def do_GET(self):
            parsed=urlsplit(self.path);query=parse_qs(parsed.query,keep_blank_values=True)
            valid=(not result and len(self.path)<8192 and not parsed.scheme and parsed.path=='/callback'
                and self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
                and query.get('state')==[state] and (('code' in query)^('error' in query)))
            if valid:
                key='code' if 'code' in query else 'error'
                valid=len(query[key])==1 and 0<len(query[key][0])<=4096
                if valid:result[key]=query[key][0]
            raw=('Google 授权响应已收到，Jarvis 正在核对并保存连接。可返回工作台。' if valid else '授权回调无效，请返回 Jarvis 重试。').encode()
            self.send_response(200 if valid else 400);self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'");self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    class Server(HTTPServer):
        def handle_error(self,*args):pass
    server=Server(('127.0.0.1',0),Handler);server.timeout=.2
    redirect='http://127.0.0.1:'+str(server.server_port)+'/callback'
    params={'client_id':client['client_id'],'redirect_uri':redirect,'response_type':'code','scope':' '.join(sorted(LEVELS[level])),
            'access_type':'offline','prompt':'consent','include_granted_scopes':'false','state':state,
            'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),'code_challenge_method':'S256'}
    if login_hint:params['login_hint']=login_hint
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params)
    try:
        guard()
        if ready:ready(url)
        if not (opener or webbrowser.open)(url):raise CoreError('mail_browser','System browser could not be opened')
        deadline=time.monotonic()+timeout
        while not result:
            guard()
            if time.monotonic()>deadline:raise CoreError('mail_auth_timeout','Google authorization timed out; other tasks continue')
            server.handle_request()
    finally:server.server_close()
    guard()
    if 'code' not in result:raise CoreError('mail_auth_denied','Google authorization was denied or cancelled')
    value=request(TOKEN,guard,method='POST',form={**client,'code':result['code'],'code_verifier':verifier,'redirect_uri':redirect,'grant_type':'authorization_code'})
    return token_result(value,{**client,'scope':' '.join(sorted(LEVELS[level]))})
