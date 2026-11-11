"""Encrypted mailbox mandates and their bounded policy, not a second executor."""
from pathlib import Path
import re,sqlite3
from control.time_windows import quiet
from control.paths import child
from modules.mail.store import MailStore
from sdk.protocol import CoreError


KIND='mail_watch'


def present(root):
    path=child(Path(root),'private/mail.sqlite3')
    if not path.exists():return False
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    try:return db.execute("SELECT 1 FROM objects WHERE kind=? LIMIT 1",(KIND,)).fetchone() is not None
    finally:db.close()


def policy(value):
    bounds={'interval_seconds':(300,86400),'lookback_hours':(1,168),'due_delay_seconds':(60,604800),
        'followup_seconds':(900,604800),'max_followups':(0,5),'max_checks':(1,1000),'max_new_items':(1,100),
        'max_attempts':(1,3),'quiet_start':(0,1439),'quiet_end':(0,1439),
        'utc_offset_minutes':(-840,840),'notification_interval_seconds':(60,86400)}
    if not isinstance(value,dict) or set(value)!=set(bounds)|{'query'}:
        raise CoreError('mail_watch_invalid','Unexpected mailbox mandate policy')
    for key,(lo,hi) in bounds.items():
        if type(value[key]) is not int or not lo<=value[key]<=hi:
            raise CoreError('mail_watch_invalid','Invalid '+key)
    if not isinstance(value['query'],str) or not 1<=len(value['query'].strip())<=350 or any(c in value['query'] for c in '\x00\r\n'):
        raise CoreError('mail_watch_invalid','Provide a bounded Gmail search scope')
    return dict(value)


def identity(ident):
    if not isinstance(ident,str) or not re.fullmatch('mail-watch-[a-f0-9]{32}',ident):
        raise CoreError('mail_watch_invalid','Expected an existing mailbox mandate')
    return ident


def guard(store,job):
    owner=job.get('mail_watch')
    if not owner:return
    watch=store.get(owner['id'],True)
    if (not watch or watch.get('schema')!=1 or watch['status']!='ACTIVE'
            or watch['config_revision']!=owner['revision'] or watch['generation']!=job.get('generation')):
        raise CoreError('mail_cancelled','Mailbox mandate paused, replaced or revoked')


def rows(store):
    result=store.listing(KIND,6)
    if len(result)>5 or any(r.get('schema')!=1 for r in result):
        raise CoreError('mail_watch_schema','Mailbox mandate data needs a compatible reader')
    return result


def reminder_controls(root,now):
    if not present(root):return {}
    store=MailStore(root)
    try:return {e['todo_id']:quiet(w['policy'],now) for w in rows(store) for e in w['entries'].values() if e.get('todo_id')}
    finally:store.close()
