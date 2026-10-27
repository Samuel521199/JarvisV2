"""Explicit one-time legacy Gmail credential migration, without importing legacy code."""
import argparse
import base64
from pathlib import Path
import sqlite3
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.credentials import crypt
from control.paths import data_root,reject_links
from modules.mail.store import MailStore
from sdk.mail import READ,COMPOSE,SEND,MODIFY,address,capabilities,client_configuration
from sdk.protocol import CoreError,decode,digest


def migrate(root,source):
    source=Path(source).absolute();reject_links(source)
    if not source.is_file() or source.stat().st_size>2000000:raise CoreError('mail_migration','Legacy connection file is unavailable')
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=3);db.row_factory=sqlite3.Row
    try:row=db.execute("SELECT id,label,encrypted,revision FROM accounts WHERE provider='gmail'").fetchone()
    finally:db.close()
    if not row or not row['encrypted']:raise CoreError('mail_migration','No connected legacy Gmail account was found')
    packet=decode(crypt(base64.b64decode(row['encrypted'],validate=True),decrypt=True))
    if packet.get('purpose')!='jarvis-mail-account-v1' or packet.get('provider')!='gmail' or packet.get('id')!=row['id']:
        raise CoreError('mail_migration','Legacy account envelope does not match its record')
    c=packet.get('credentials',{});client=client_configuration({'installed':{'client_id':c.get('client_id'),'client_secret':c.get('client_secret')}})
    if not isinstance(c.get('scope'),str) or not set(c['scope'].split())<={READ,COMPOSE,SEND,MODIFY} or not capabilities(c['scope'])['read']:
        raise CoreError('mail_scope','Legacy authorization contains unsupported permissions')
    if any(not isinstance(c.get(k),str) or not 1<=len(c[k])<=8192 for k in ('access_token','refresh_token')) or type(c.get('expires_at')) not in (int,float):
        raise CoreError('mail_migration','Legacy credentials are incomplete')
    credentials={**client,**{k:c[k] for k in ('access_token','refresh_token','expires_at','scope')}}
    email=address(row['label']);store=MailStore(data_root(root))
    try:
        with store.transaction():
            if store.get('legacy-gmail-migration',True):return {'migrated':False,'reason':'already_migrated','credentials_printed':False}
            if store.get('account',True):raise CoreError('mail_migration','A new-project account already exists; it was not overwritten')
            existing=store.get('client',True)
            if existing and existing['configuration']!=client:raise CoreError('conflict','New-project OAuth configuration differs')
            if not existing:store.put({'id':'client','kind':'client','configuration':client},0)
            store.put({'id':'account','kind':'account','email':email,'credentials':credentials,'generation':uuid.uuid4().hex,'health':'unchecked','checked_at':None},0)
            store.put({'id':'legacy-gmail-migration','kind':'migration','source_digest':digest({'id':row['id'],'revision':row['revision'],'cipher':row['encrypted']}),'migrated_at':time.time(),'scope':c['scope'],'mail_cache_copied':False},0)
        return {'migrated':True,'capabilities':capabilities(c['scope']),'mail_cache_copied':False,'credentials_printed':False}
    finally:store.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--data-root',type=Path,default=ROOT/'user-data');a=p.parse_args()
    try:
        import json
        print(json.dumps(migrate(a.data_root,a.source),ensure_ascii=False))
    except (CoreError,OSError,ValueError,sqlite3.Error) as exc:
        print(exc.code if isinstance(exc,CoreError) else 'mail_migration_failed',file=sys.stderr);raise SystemExit(1)
