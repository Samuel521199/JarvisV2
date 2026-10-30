"""Opt-in live read-only Gmail probe; evidence contains no email content or credentials."""
import argparse
import hashlib
import json
import time
import uuid
import urllib.request
from pathlib import Path

from control.local_access import install_client


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--origin',default='http://127.0.0.1:18282')
    parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:parser.error('Pass --live to explicitly permit bounded reading of the connected Gmail account.')
    if args.origin!='http://127.0.0.1:18282':parser.error('This probe is restricted to the local production workbench.')
    origin=args.origin;install_client(origin)
    def get(path):
        with urllib.request.urlopen(origin+path,timeout=30) as response:return json.load(response)
    session=get('/api/session')
    def post(value):
        request=urllib.request.Request(origin+'/api/mail',data=json.dumps(value).encode(),headers={
            'Origin':origin,'Content-Type':'application/json','X-Jarvis-Token':session['token']})
        with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
    def run(operation,payload):
        row=post({'action':'job','request_id':'companion-probe-'+uuid.uuid4().hex,'operation':operation,'payload':payload})
        end=time.monotonic()+65
        while row['status'] in {'READY','RUNNING'} and time.monotonic()<end:
            time.sleep(.4);row=post({'action':'detail','id':row['id']})
        if row['status']!='SUCCEEDED':raise RuntimeError('Read-only probe ended with '+row['status']+' / '+str(row.get('error')))
        return row
    sync=run('sync',{'query':'in:inbox','page':''});view=get('/api/mail/companion')
    assert view['status']=='connected' and len(view['items'])<=10
    assert type(view['unread_count']) is int and not any('body' in row for row in view['items'])
    assert 'credentials' not in view and 'url' not in view['authorization']
    detail=None
    if view['items']:detail=run('read',{'message_id':view['items'][0]['id']})
    result={'checked_at':time.time(),'status':view['status'],'message_count':len(view['items']),
            'inbox_unread_count':view['unread_count'],'count_scope':view['count_scope'],
            'detail_read':detail is not None,'detail_text_length':len((detail or {}).get('result',{}).get('body','')),
            'remote_writes':0,'model_calls_in_this_probe':0,'sync_job_id':sync['id'],
            'credentials_or_email_content_in_evidence':False}
    result['source_sha256']={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (
        'host/mailbox.py','sdk/mail.py','modules/mail/companion.py','apps/workbench/mail-companion.js','apps/workbench/mail-client.js')}
    path=Path('user-data/mail-proof/companion-live-verification.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
