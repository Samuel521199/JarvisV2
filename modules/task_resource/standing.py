"""Durable standing work metadata; original goals/tasks remain effect authority."""
import math
import re
from datetime import datetime, timezone
from sdk.protocol import CoreError, canonical, decode, digest
from control.time_windows import quiet


def invalid(message): raise CoreError('standing_invalid', message)


def timestamp(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)',value):
        invalid('An exact time with UTC offset is required')
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if not 2000<=dt.year<=2100: invalid('Time outside supported range')
        return dt.timestamp()
    except ValueError: invalid('Invalid time')


def policy(value):
    keys={'start_at','interval_seconds','max_runs','max_action_units','max_attempts','quiet_start','quiet_end',
          'utc_offset_minutes','notification_interval_seconds','cloud_model_budget_usd'}
    if not isinstance(value,dict) or set(value)!=keys: invalid('Unexpected standing-work policy fields')
    timestamp(value['start_at'])
    bounds={'interval_seconds':(0,86400*30),'max_runs':(1,100),'max_action_units':(1,1000),
            'max_attempts':(1,3),'quiet_start':(0,1439),'quiet_end':(0,1439),'utc_offset_minutes':(-840,840),
            'notification_interval_seconds':(60,86400)}
    for key,(lo,hi) in bounds.items():
        if type(value[key]) is not int or not lo<=value[key]<=hi: invalid('Invalid '+key)
    if 0<value['interval_seconds']<60: invalid('Recurring interval must be at least 60 seconds')
    if type(value['cloud_model_budget_usd']) not in (int,float) or not math.isfinite(value['cloud_model_budget_usd']) or value['cloud_model_budget_usd']!=0:
        invalid('Standing execution has a zero cloud-model budget; new model planning requires separate approval')
    return dict(value)


def acceptance(rules,steps):
    """Narrow preflight; original Completion.configure validates again at admission."""
    from modules.task_resource.coverage import validate
    if set(rules)!={'coverage','criteria','requirements'} or not 1<=len(rules['criteria'])<=16:
        invalid('Declare bounded literal acceptance')
    allowed={'step-'+str(i+1) for i in range(len(steps))};seen=set()
    for c in rules['criteria']:
        if (not isinstance(c,dict) or set(c)!={'id','step_id','check','expected'} or any(not isinstance(v,str) for v in c.values())
            or not 1<=len(c['id'])<=80 or c['id'] in seen or c['step_id'] not in allowed or c['check']!='text_equals' or len(c['expected'])>12000):
            invalid('Standing work currently requires explicit exact-text checks')
        seen.add(c['id'])
    validate(rules)
    if any(r['kind']!='literal' or not r['criterion_ids'] for r in rules['requirements']):invalid('All declared requirements need literal checks')


def guard_task(db,task_id,now):
    if not db.one("SELECT 1 FROM meta WHERE key='standing_schema'"):return None
    link=db.one('SELECT c.* FROM standing_children c JOIN goal_plans p ON p.id=c.goal_id WHERE p.task_id=?',(task_id,))
    if not link:return None
    row=Standing(db).get(link['work_id'])
    if row['status']!='ACTIVE' or quiet(row['policy'],now):
        raise CoreError('module_disabled','Standing work paused, withdrawn or inside quiet hours')
    source=db.one('SELECT * FROM goal_plans WHERE id=?',(link['source_goal'],))
    plan=next(p for p in row['plans'] if p['id']==link['source_goal'])
    if not source or source['cancel']:raise CoreError('plan_source_changed','Standing source stopped')
    if source['task_id']:
        feedback=db.one('SELECT kind FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(source['task_id'],))
        if feedback and feedback['kind']=='reject':raise CoreError('experience_changed','Standing source method was withdrawn')
    proposal=decode(source['proposal']) if source['proposal'] else None
    used={s['capability'] for s in plan['proposal']['steps']}
    refs=[r for r in decode(source['catalog']) if r['capability'] in used]
    revision=db.one('SELECT root_goal FROM work_revisions WHERE goal_id=?',(link['source_goal'],));origin=revision['root_goal'] if revision else link['source_goal']
    chat=db.one('SELECT chat_id FROM chat_goals WHERE goal_id=?',(origin,))
    current={'id':source['id'],'root_goal':origin,'request':decode(source['request']),'proposal':proposal,'catalog':refs,'chat_id':chat['chat_id'] if chat else None}
    if digest(current)!=plan['fingerprint']:raise CoreError('plan_source_changed','Standing source changed before action dispatch')
    for ref in refs:
        slot=db.one('SELECT * FROM release_slots WHERE capability=?',(ref['capability'],))
        if not slot or not slot['enabled'] or slot['active']!=ref['active'] or slot['revision']!=ref['revision']:
            raise CoreError('package_changed','Standing tool version changed; review new scope')
    return link['source_goal']


class Standing:
    def __init__(self,db):
        self.db=db
        row=db.one("SELECT value FROM meta WHERE key='standing_schema'")
        if row:
            if row['value']!='1': raise CoreError('standing_schema','Unknown standing-work schema')
            return
        with db.transaction() as tx:
            tx.execute('CREATE TABLE IF NOT EXISTS standing_work(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            tx.execute('CREATE TABLE IF NOT EXISTS standing_runs(id TEXT PRIMARY KEY,work_id TEXT NOT NULL,ordinal INTEGER NOT NULL,body TEXT NOT NULL,UNIQUE(work_id,ordinal))')
            tx.execute('CREATE TABLE IF NOT EXISTS standing_operations(id TEXT PRIMARY KEY,digest TEXT NOT NULL,result TEXT NOT NULL)')
            tx.execute('CREATE TABLE IF NOT EXISTS standing_children(goal_id TEXT PRIMARY KEY,work_id TEXT NOT NULL,run_id TEXT NOT NULL,source_goal TEXT NOT NULL)')
            tx.execute('CREATE TABLE IF NOT EXISTS standing_chat_controls(turn_id TEXT PRIMARY KEY,work_id TEXT NOT NULL,result TEXT NOT NULL)')
            tx.execute("INSERT INTO meta VALUES('standing_schema','1')")

    def get(self,ident):
        row=self.db.one('SELECT body FROM standing_work WHERE id=?',(ident,))
        if not row:raise CoreError('standing_missing','Standing work is unavailable')
        return decode(row['body'])

    def listing(self):return [decode(r['body']) for r in self.db.all('SELECT body FROM standing_work ORDER BY rowid DESC LIMIT 100')]
    def runs(self,ident):return [decode(r['body']) for r in self.db.all('SELECT body FROM standing_runs WHERE work_id=? ORDER BY ordinal DESC LIMIT 100',(ident,))]
    def put(self,row):
        raw=canonical(row)
        if len(raw.encode())>200000:raise CoreError('standing_capacity','Choose fewer or smaller plans')
        self.db.connection.execute('INSERT INTO standing_work VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(row['id'],raw))
        return row
    def run(self,row):
        self.db.connection.execute('INSERT INTO standing_runs VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(row['id'],row['work_id'],row['ordinal'],canonical(row)))
        return row

    def save(self,row,run=None):
        with self.db.transaction():
            if run is not None:self.run(run)
            self.put(row)

    def operation(self,ident,signature):
        row=self.db.one('SELECT * FROM standing_operations WHERE id=?',(ident,))
        if row and row['digest']!=signature:raise CoreError('conflict','Standing request ID changed')
        return decode(row['result']) if row else None

    def record(self,ident,signature,result):
        self.db.connection.execute('INSERT INTO standing_operations VALUES(?,?,?)',(ident,signature,canonical(result)))

    def begin(self,row,now):
        number=row['runs_started']+1
        if self.db.one('SELECT COUNT(*) AS n FROM standing_runs')['n']>=5000:raise CoreError('standing_capacity','Review standing-work history before adding runs')
        run={'id':row['id']+'-'+str(number),'work_id':row['id'],'ordinal':number,'status':'RUNNING','cursor':0,
             'attempt':0,'retries_used':0,'next_at':now,'attempts':{},'goals':[],'error':None,'created':now,'updated':now}
        row.update(runs_started=number,current_run=run['id'])
        self.save(row,run);return run

    def reserve(self,row,run,key,units,now):
        if key in run['attempts']:return
        if row['reserved_units']+units>row['policy']['max_action_units']:
            raise CoreError('standing_budget','Standing action-unit budget exhausted')
        row['reserved_units']+=units;run['attempts'][key]={'units':units,'goal_id':None,'task_id':None};run['updated']=now
        self.save(row,run)
