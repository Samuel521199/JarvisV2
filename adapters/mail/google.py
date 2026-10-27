"""Bounded fixed-host Google APIs. No links or instructions from mail are executed."""
import json
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
import re

from sdk.protocol import CoreError
from sdk.mail import capabilities,identifier,message,READ,COMPOSE,SEND,MODIFY

TOKEN='https://oauth2.googleapis.com/token'
BASE='https://gmail.googleapis.com/gmail/v1/users/me'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def request(url,guard,*,body=None,form=None,token=None,method='GET'):
    if not (url==TOKEN or url.startswith(BASE+'/')):raise CoreError('mail_endpoint','Unsupported Google endpoint')
    guard();headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    raw=None
    if form is not None:raw=urlencode(form).encode();headers['Content-Type']='application/x-www-form-urlencoded'
    elif body is not None:raw=json.dumps(body,separators=(',',':')).encode();headers['Content-Type']='application/json'
    req=Request(url,data=raw,headers=headers,method=method)
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            result=bytearray();deadline=time.monotonic()+25
            while True:
                chunk=response.read1(32768);guard()
                if time.monotonic()>deadline:raise CoreError('mail_network','Google response deadline exceeded')
                if not chunk:break
                result.extend(chunk)
                if len(result)>2000000:raise CoreError('mail_response','Google response exceeds the size limit')
            return json.loads(result)
    except HTTPError as exc:
        data=exc.read(16384)
        try:value=json.loads(data)
        except (ValueError,UnicodeError):value={}
        if exc.code==401 or value.get('error') in ('invalid_grant','invalid_token'):
            raise CoreError('mail_auth_required','Google authorization needs to be renewed') from None
        if exc.code==403:
            reasons=str(value.get('error',{}))
            code='mail_api_disabled' if 'accessNotConfigured' in reasons or 'SERVICE_DISABLED' in reasons else 'mail_scope'
            raise CoreError(code,'Google refused this operation; check API enablement and granted scopes') from None
        if exc.code==429:raise CoreError('mail_rate_limit','Google rate limit; no automatic write retry') from None
        if exc.code in {400,404,409,413}:raise CoreError('mail_google_rejected','Google rejected the request before accepting it') from None
        raise CoreError('mail_google_error','Google returned HTTP '+str(exc.code)) from None
    except (URLError,OSError,TimeoutError):raise CoreError('mail_network','Google connection failed or timed out') from None
    except (ValueError,UnicodeError):raise CoreError('mail_response','Invalid Google JSON response') from None


def token_result(value,previous=None):
    previous=previous or {}
    if (not isinstance(value,dict) or not isinstance(value.get('access_token'),str) or not value['access_token']
            or len(value['access_token'])>8192 or value.get('token_type','Bearer').lower()!='bearer'
            or type(value.get('expires_in')) not in (int,float) or not 0<value['expires_in']<=86400):
        raise CoreError('mail_response','Invalid OAuth token response')
    refresh=value.get('refresh_token') or previous.get('refresh_token')
    if not isinstance(refresh,str) or not 1<=len(refresh)<=8192:raise CoreError('mail_auth_required','Google did not issue an offline refresh token')
    scope=value.get('scope',previous.get('scope',''))
    if not isinstance(scope,str) or not set(scope.split())<=set(previous.get('scope','').split())<={READ,COMPOSE,SEND,MODIFY}:
        raise CoreError('mail_scope','OAuth response changed the requested permission boundary')
    if not capabilities(scope)['read']:raise CoreError('mail_scope','Gmail read permission was not granted')
    return {**previous,'access_token':value['access_token'],'refresh_token':refresh,'scope':scope,'expires_at':time.time()+value['expires_in']}


class Gmail:
    def __init__(self,credentials,guard):self.credentials=credentials;self.guard=guard
    def api(self,path,*,params=None,body=None,method='GET',needed='read'):
        if not capabilities(self.credentials.get('scope',''))[needed]:raise CoreError('mail_scope','This operation needs additional Gmail permission')
        allowed=path=='/profile' or path=='/messages' or path=='/messages/send' or path=='/drafts' or re.fullmatch(r'/messages/[A-Za-z0-9_-]{1,180}(/modify|/trash|/untrash)?',path)
        if not allowed or method not in {'GET','POST'}:raise CoreError('mail_endpoint','Unsupported Gmail operation')
        url=BASE+path+('?' +urlencode(params,doseq=True) if params else '')
        try:return request(url,self.guard,body=body,token=self.credentials['access_token'],method=method)
        except CoreError as exc:
            if exc.code!='mail_auth_required':raise
            # A definitive HTTP 401 has no successful write effect. Refresh once only.
            self.refresh(True)
            return request(url,self.guard,body=body,token=self.credentials['access_token'],method=method)
    def refresh(self,force=False):
        if not force and self.credentials.get('expires_at',0)>time.time()+60:return self.credentials
        value=request(TOKEN,self.guard,method='POST',form={'client_id':self.credentials['client_id'],'client_secret':self.credentials['client_secret'],
                       'refresh_token':self.credentials['refresh_token'],'grant_type':'refresh_token'})
        self.credentials=token_result(value,self.credentials);return self.credentials
    def profile(self):
        value=self.api('/profile')
        from sdk.mail import address
        return {'email':address(value.get('emailAddress')),'messages_total':value.get('messagesTotal',0),'history_id':value.get('historyId','')}
    def listing(self,query='',page=''):
        if not isinstance(query,str) or len(query)>500 or not isinstance(page,str) or len(page)>1000:raise CoreError('mail_invalid','Search parameters are too long')
        params={'maxResults':10,'q':query}
        if page:params['pageToken']=page
        value=self.api('/messages',params=params);rows=[]
        for item in value.get('messages',[])[:10]:rows.append(self.read(item['id'],False))
        return {'messages':rows,'next_page':value.get('nextPageToken','')}
    def read(self,ident,full=True):
        identifier(ident);params=[('format','full' if full else 'metadata')]
        if not full:params.extend(('metadataHeaders',h) for h in ['Subject','From','To','Reply-To','Date','Message-ID'])
        return message(self.api('/messages/'+ident,params=params),full)
    def modify(self,ident,remove,add):
        identifier(ident)
        self.api('/messages/'+ident+'/modify',method='POST',body={'removeLabelIds':remove,'addLabelIds':add},needed='modify')
        try:return self.read(ident,False)
        except Exception:raise CoreError('mail_confirmation_unknown','Google accepted the change, but its resulting state could not be verified') from None
    def trash(self,ident,undo=False):
        identifier(ident)
        self.api('/messages/'+ident+('/untrash' if undo else '/trash'),method='POST',body={},needed='modify')
        try:return self.read(ident,False)
        except Exception:raise CoreError('mail_confirmation_unknown','Google accepted the change, but its resulting state could not be verified') from None
    def send(self,raw,as_draft=False):
        value=self.api('/drafts' if as_draft else '/messages/send',method='POST',body={'message':{'raw':raw}} if as_draft else {'raw':raw},needed='draft' if as_draft else 'send')
        if not isinstance(value,dict) or not value.get('id'):raise CoreError('mail_response','Google did not return a message or draft ID')
        return {'remote_id':value['id'],'message_id':value.get('message',{}).get('id',value['id'])}
