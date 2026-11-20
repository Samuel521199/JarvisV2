"""Daily personal RSS briefs, using the managed host's existing idle and worker lanes."""
from contextlib import contextmanager
from datetime import datetime
import json
import re
import sqlite3
import threading
import time

from control.application_runtime import require_accepting
from control.network import NetworkGate
from control.paths import child, data_root
from control.recovery.gate import StopGate
from host.news_feeds import FEEDS, collect, select_items
from sdk.protocol import CoreError, digest
from host.news_topics import PRESETS

DEFAULT = dict(enabled=False, at='08:00', sources=list(FEEDS), exclude=[], interest='', limit=12, topics=[], custom_topics=[])
TOPIC_FIELDS = {'topics','custom_topics'}
LOCK = threading.RLock()
POLL = {}


@contextmanager
def store(root):
    db = sqlite3.connect(child(root, 'config/news-brief.sqlite3'), timeout=5)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY, rev INTEGER, body TEXT, attempt REAL, status TEXT)')
            db.execute('INSERT OR IGNORE INTO preferences VALUES(1,0,?,0,?)',(json.dumps(DEFAULT),'尚未生成'))
            db.execute('CREATE TABLE IF NOT EXISTS briefs(day TEXT PRIMARY KEY, edition TEXT, seen TEXT, body TEXT)')
            yield db
    finally:
        db.close()


def checked(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT):
        raise CoreError('invalid_request','Invalid news preferences')
    sources, exclude, interest = value['sources'],value['exclude'],value['interest']
    topics, custom = value['topics'], value['custom_topics']
    if (not isinstance(topics,list) or len(topics)>len(PRESETS)
        or any(not isinstance(t,str) or t not in PRESETS for t in topics)
        or not isinstance(custom,list) or len(custom)>20
        or any(not isinstance(t,str) or not 1<=len(t.strip())<=48 for t in custom)):
        raise CoreError('invalid_request','Invalid news topics')
    if (type(value['enabled']) is not bool or not isinstance(value['at'],str)
        or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value['at'])
        or type(value['limit']) is not int or not 1<=value['limit']<=30
        or not isinstance(sources,list) or not sources or len(sources)>len(FEEDS)
        or any(not isinstance(s,str) or s not in FEEDS for s in sources) or len(set(sources))!=len(sources)
        or not isinstance(exclude,list) or len(exclude)>40
        or any(not isinstance(s,str) or not 1<=len(s.strip())<=60 for s in exclude)
        or not isinstance(interest,str) or len(interest)>160):
        raise CoreError('invalid_request','Invalid news filters or delivery time')
    return {**value,'topics':list(dict.fromkeys(topics)), 'custom_topics':list(dict.fromkeys(t.strip() for t in custom)),
            'exclude':[w.strip() for w in exclude],'interest':interest.strip()}


def snapshot(root, badge=False):
    with store(root) as db:
        unread = db.execute('SELECT COUNT(*) FROM briefs WHERE seen!=edition').fetchone()[0]
        if badge:
            return {'unread':unread}
        prefs = db.execute('SELECT * FROM preferences').fetchone()
        return {'unread':unread, 'settings':{**DEFAULT,**json.loads(prefs['body'])}, 'topics':list(PRESETS), 'revision':prefs['rev'],
                'status':prefs['status'], 'attempt':prefs['attempt'],
                'catalog':[dict(id=k,name=v[0],region=v[1],topic=v[2]) for k,v in FEEDS.items()],
                'briefs':[{**json.loads(r['body']),'edition':r['edition'],'unread':r['edition']!=r['seen']}
                          for r in db.execute('SELECT * FROM briefs ORDER BY day DESC LIMIT 30')]}


def checkpoint(root):
    require_accepting(root)
    StopGate(root).require_running()
    NetworkGate(root).require_online()


def produce(root, rev, rank=None, *, reader=collect, clock=time.time):
    def check():
        checkpoint(root)
        with store(root) as db:
            if db.execute('SELECT rev FROM preferences').fetchone()[0]!=rev:
                raise CoreError('conflict','Subscription changed')
    try:
        check()
        now=clock()
        day=datetime.fromtimestamp(now).date().isoformat()
        with store(root) as db:
            prefs=json.loads(db.execute('SELECT body FROM preferences').fetchone()[0])
        feeds=reader(prefs['sources'],now,check)
        failures={key:error for key,_,error in feeds if error}
        if len(failures)==len(feeds):
            raise CoreError('news_unreachable','All selected feeds failed')
        items,method=select_items([r for _,rows,_ in feeds for r in rows],prefs,rank)
        check()
        brief=dict(day=day,created=now,items=items,method=method,failures=failures)
        status='已整理' if items else '近 24 小时没有符合条件的新闻'
        with LOCK,store(root) as db:
            if not db.execute('UPDATE preferences SET status=? WHERE rev=?',(status,rev)).rowcount:
                raise CoreError('conflict','Subscription changed')
            edition=digest([items,method,failures])
            db.execute("INSERT INTO briefs VALUES(?,?,'',?) ON CONFLICT(day) DO UPDATE SET edition=excluded.edition,body=excluded.body",
                       (day,edition,json.dumps(brief,ensure_ascii=False)))
            db.execute('DELETE FROM briefs WHERE day NOT IN (SELECT day FROM briefs ORDER BY day DESC LIMIT 30)')
        return {'status':status}
    except Exception as exc:
        error=exc.code if isinstance(exc,CoreError) else 'news_failed'
        with store(root) as db:
            db.execute('UPDATE preferences SET status=? WHERE rev=?',(error,rev))
        raise


def start(server, automatic=False):
    root=data_root(server.data_root)
    now=time.time()
    local=datetime.fromtimestamp(now)
    with LOCK,store(root) as db:
        row=db.execute('SELECT * FROM preferences').fetchone()
        prefs=json.loads(row['body'])
        if not prefs['enabled']:
            if automatic:return
            raise CoreError('news_disabled','News subscription is paused')
        if automatic and (local.strftime('%H:%M')<prefs['at']
                or now-row['attempt']<1800 or db.execute('SELECT 1 FROM briefs WHERE day=?',(local.date().isoformat(),)).fetchone()):
            return
        checkpoint(root)
        rank=getattr(getattr(server,'local_models',None),'rank_memory',None)
        result=server.background_lane.submit('news',local.date().isoformat(),produce,root,row['rev'],rank)
        db.execute('UPDATE preferences SET attempt=?,status=?',(now,'正在采集'))
        return result


def advance(server):
    root=data_root(server.data_root)
    now=time.monotonic()
    if now<POLL.get(root,0):
        return
    POLL[root]=now+60
    if child(root,'config/news-brief.sqlite3').exists():
        start(server,automatic=True)


def command(server,value):
    if not isinstance(value,dict):
        raise CoreError('invalid_request','Expected a news command')
    root=data_root(server.data_root)
    if value=={'action':'generate'}:
        return start(server)
    with LOCK,store(root) as db:
        if set(value)=={'action','revision','settings'} and value['action']=='save' and type(value['revision']) is int:
            proposed=value['settings']
            if isinstance(proposed,dict) and set(proposed)==set(DEFAULT)-TOPIC_FIELDS:
                saved=json.loads(db.execute('SELECT body FROM preferences').fetchone()[0])
                proposed={**proposed,**{k:saved.get(k,[]) for k in TOPIC_FIELDS}}
            prefs=checked(proposed)
            if not db.execute("UPDATE preferences SET body=?,rev=rev+1,attempt=0,status='设置已保存' WHERE rev=?",
                              (json.dumps(prefs),value['revision'])).rowcount:
                raise CoreError('conflict','News preferences changed')
        elif set(value)=={'action','revision','enabled'} and value['action']=='toggle' and type(value['revision']) is int and type(value['enabled']) is bool:
            current=db.execute('SELECT body FROM preferences WHERE rev=?',(value['revision'],)).fetchone()
            if not current:
                raise CoreError('conflict','News preferences changed')
            prefs={**json.loads(current[0]),'enabled':value['enabled']}
            db.execute('UPDATE preferences SET body=?,rev=rev+1,attempt=0,status=? WHERE rev=?',
                       (json.dumps(prefs),'已启用' if prefs['enabled'] else '已停用',value['revision']))
        elif set(value)=={'action','day','edition'} and value['action']=='read' and all(isinstance(value[k],str) for k in ('day','edition')):
            if not db.execute('UPDATE briefs SET seen=edition WHERE day=? AND edition=?',(value['day'],value['edition'])).rowcount:
                raise CoreError('conflict','News edition changed')
        else:
            raise CoreError('invalid_request','Unknown news command')
    return {'status':'ok'}
