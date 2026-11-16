"""Versioned learning evidence and conservative, inspectable review selection."""
import json
import sqlite3
import time
from control.paths import child
from sdk.protocol import CoreError, canonical

SCHEMA=3
DAY=86400
INTERVALS=(1,3,7,14,30)
TARGETS={
    'life.request':('life','礼貌地请求物品或帮助'),
    'communication.clarify':('communication','没听清时请求重说并核对意思'),
    'work.notice':('work','读懂工作通知的行动、时间与限制'),
    'life.directions':('life','问路并确认地点'),
    'communication.arrange':('communication','商量时间并确认安排'),
    'work.email':('work','写简短清晰的工作回复'),
    'life.problem':('life','说明日常遇到的问题并请求处理'),
    'communication.opinion':('communication','表达意见并礼貌询问对方'),
    'work.explain':('work','用自己的话解释工作资料的关键意思'),
}


class Store:
    def __init__(self,root):
        self.root=root
        self.db=sqlite3.connect(child(root,'state/english-learning.sqlite3'),timeout=5,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0,1,2,SCHEMA):
            self.db.close();raise CoreError('english_schema','Unknown English learning data version')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exercises(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,body TEXT NOT NULL,withdrawn INTEGER NOT NULL DEFAULT 0,hints INTEGER NOT NULL DEFAULT 0,exposed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS assessments(id TEXT PRIMARY KEY,exercise_id TEXT UNIQUE NOT NULL,body TEXT NOT NULL,disputed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,candidate TEXT,reply_digest TEXT);
CREATE TABLE IF NOT EXISTS software_sessions(id TEXT PRIMARY KEY,body TEXT NOT NULL);

''')
        self.db.execute('PRAGMA user_version='+str(3 if version==3 else 2))
        self.db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(canonical({'enabled':False,'revision':0,'domains':['life','communication','work']}),))

    def close(self):self.db.close()
    def config(self):return json.loads(self.db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
    def configure(self,enabled,revision):
        old=self.config()
        if type(enabled) is not bool or type(revision) is not int or old['revision']!=revision:raise CoreError('conflict','Learning settings changed')
        value={**old,'enabled':enabled,'revision':revision+1}
        if not self.db.execute('UPDATE settings SET body=? WHERE id=1 AND body=?',(canonical(value),canonical(old))).rowcount:
            raise CoreError('conflict','Learning settings changed concurrently')
        return value
    def job(self,ident):
        row=self.db.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
        if not row:return None
        return {**dict(row),'body':json.loads(row['body']),'candidate':json.loads(row['candidate']) if row['candidate'] else None}
    def exercise(self,ident):
        row=self.db.execute('SELECT * FROM exercises WHERE id=?',(ident,)).fetchone()
        if not row:raise CoreError('english_missing','Unknown exercise')
        return {**dict(row),'body':json.loads(row['body'])}
    def add_job(self,ident,chat,kind,body):
        previous=self.job(ident)
        if previous:
            if previous['chat_id']!=chat or previous['kind']!=kind or previous['body']!=body:raise CoreError('conflict','Learning request ID reused')
            return previous
        self.db.execute('INSERT INTO jobs(id,chat_id,kind,body,state) VALUES(?,?,?,?,?)',(ident,chat,kind,canonical(body),'PENDING'))
        return self.job(ident)
    def stage(self,ident,payload,reply_digest):
        changed=self.db.execute("UPDATE jobs SET candidate=?,reply_digest=? WHERE id=? AND state='PENDING' AND candidate IS NULL",(canonical(payload),reply_digest,ident)).rowcount
        old=self.job(ident)
        if not changed and (old['candidate']!=payload or old['reply_digest']!=reply_digest):raise CoreError('conflict','Learning result already recorded')
    def commit(self,job,now,model_receipt=None):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current=self.job(job['id'])
            if current['state']!='PENDING':self.db.execute('COMMIT');return
            body=current['body'];value=current['candidate']
            if self.config()['revision']!=body['revision'] or not self.config()['enabled']:raise CoreError('english_stale','Learning permission changed')
            if current['kind']=='question':
                content={**value,'target':body['target'],'difficulty':body['difficulty'],'created':now,'question_turn':job['id'],'material_origin':body['material_origin'],'practice_mode':body.get('practice_mode','text')}
                self.db.execute('INSERT INTO exercises(id,chat_id,body) VALUES(?,?,?)',(job['id'],job['chat_id'],canonical(content)))
            else:
                exercise=self.exercise(body['exercise_id'])
                if exercise['withdrawn'] or exercise['hints']!=body['hints'] or exercise['exposed']!=body['exposed']:raise CoreError('english_stale','Exercise changed during evaluation')
                content={**value,'answer':body['answer'],'assistance':body['assistance'],'hints':body['hints'],'exposed':body['exposed'],
                    'created':now,'answer_turn':job['id'],'chat_id':job['chat_id'],'target':exercise['body']['target'],'difficulty':exercise['body']['difficulty'],
                    'prompt':exercise['body']['prompt'],'judge':'model_provisional','model_receipt':model_receipt,'schema':1}
                if body.get('speech'):content['speech']=body['speech']
                if body.get('game'):
                    game=body['game'];s=json.loads(self.db.execute('SELECT body FROM software_sessions WHERE id=?',(game['session_id'],)).fetchone()[0])
                    if s['revision']!=game['revision'] or s['exercise_id']!=body['exercise_id'] or s['state']!='ACTIVE':raise CoreError('english_stale','Software session changed during evaluation')
                    content['game']=value['game'];transition=value['game']['transition']
                    s.update(node=transition['node'],attempt=transition['attempt'],state=transition['state'],revision=s['revision']+1,exercise_id=None,dependencies=s['dependencies']+[body['exercise_id'],job['id']])
                    self.db.execute('UPDATE software_sessions SET body=? WHERE id=?',(canonical(s),s['id']))
                self.db.execute('INSERT INTO assessments(id,exercise_id,body) VALUES(?,?,?)',(job['id'],body['exercise_id'],canonical(content)))
            self.db.execute("UPDATE jobs SET state='RECORDED' WHERE id=?",(job['id'],));self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise


def independent(row):
    return row['assistance']=='independent' and row['hints']==0 and not row['exposed']


def success(row):
    return row['meaning']==2 and row['form']>=1 and row['appropriacy']>=1 and row['confidence'] in ('medium','high')


def recall_key(row):
    game=row.get('game')
    if game:
        # A changed repair label/NPC reply is still the same fixed software task.
        return ('software-task',game['software'].get('id','english-city'),game['scene'],game['node'])
    return ('prompt',row['prompt'])


def schedule(records,now=None):
    """Compute solely from valid evidence; same-day repetitions cannot inflate stage."""
    now=time.time() if now is None else now;result={}
    for key,(domain,label) in TARGETS.items():
        rows=sorted((r for r in records if r['target']==key),key=lambda r:(r['created'],r['answer_turn']))
        stage=0;last_credit=None;last_prompt=None
        for row in rows:
            if not independent(row) or not success(row):stage=0;last_credit=None;last_prompt=None;continue
            if last_credit is None or row['created']-last_credit>=DAY and recall_key(row)!=last_prompt:
                stage=min(stage+1,len(INTERVALS));last_credit=row['created'];last_prompt=recall_key(row)
        due=rows[-1]['created']+DAY*INTERVALS[max(stage-1,0)] if rows else None
        result[key]={'target':key,'domain':domain,'label':label,'count':len(rows),'stage':stage,'due':due,'due_now':due is not None and due<=now,
                     'difficulty':min(3,1+stage//2),'reason':'due_review' if due is not None and due<=now else 'new' if not rows else 'optional_practice'}
    return result


def progress(records,now=None):
    plans=schedule(records,now);domains={}
    for domain in ('life','communication','work'):
        rows=[r for r in records if TARGETS[r['target']][0]==domain];solo=[r for r in rows if independent(r)]
        delayed=[]
        for row in solo:
            if any(old['target']==row['target'] and old['difficulty']==row['difficulty'] and row['created']-old['created']>=DAY and recall_key(old)!=recall_key(row) for old in records):delayed.append(row)
        domains[domain]={'attempts':len(rows),'independent':len(solo),'assisted':len(rows)-len(solo),'delayed_variants':len(delayed),
            'delayed_successes':sum(success(r) for r in delayed),'delayed_success_rate':sum(success(r) for r in delayed)/len(delayed) if delayed else None,
            'interpretation':'AI estimates on text tasks; not certified proficiency or causal learning gains'}
    # Require disjoint early/later samples for the same target and difficulty.
    trends=[]
    for key in TARGETS:
        for level in (1,2,3):
            rows=sorted((r for r in records if r['target']==key and r['difficulty']==level and independent(r) and r['confidence']!='low'),key=lambda r:r['created'])
            unique=[];seen=set()
            for row in rows:
                if recall_key(row) not in seen:unique.append(row);seen.add(recall_key(row))
            if len(unique)<6 or unique[-3]['created']-unique[2]['created']<DAY:continue
            early=unique[:3];late=unique[-3:]
            score=lambda group:round(sum(r['meaning']+r['form']+r['appropriacy'] for r in group)/len(group),2)
            trends.append({'target':key,'difficulty':level,'earlier_mean_out_of_6':score(early),'later_mean_out_of_6':score(late),'sample_sizes':[3,3],
                'interpretation':'Descriptive model-rated trend; generated variants are not psychometrically equated or an independent control.'})
    return {'domains':domains,'review':list(plans.values()),'trends':trends,'trend_state':'descriptive_only' if trends else 'insufficient_comparable_samples','certified_level':None}
