"""Controller-owned preflight for the new local data and assistant action shape.

Read-only inspection, no migration or business restore. Candidate declarations
are provenance-bound by normal package inspection and reviewed-source tests;
they are not proof of arbitrary third-party code compatibility.
"""
import json
from itertools import chain
from pathlib import Path
import sqlite3
from control.paths import child,reject_links
from sdk.protocol import CoreError


def required(root):
    root=Path(root).resolve();needs={'commitments_schema':0,'assistant_commitments':False}
    for name in ('commitments','dialogue'):
        path=child(root,'state/'+name+'.sqlite3')
        if not path.exists():continue
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            if name=='commitments':
                version=db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (1,2):
                    raise CoreError('application_data_compatibility','Unknown commitment database version')
                if version==2 or db.execute('SELECT 1 FROM commitments LIMIT 1').fetchone():needs['commitments_schema']=version
            elif db.execute("SELECT 1 FROM sqlite_master WHERE name='turns'").fetchone():
                columns={row[1] for row in db.execute('PRAGMA table_info(turns)')}
                if 'assistant_action' not in columns:continue
                for row in db.execute('SELECT assistant_action FROM turns WHERE assistant_action IS NOT NULL ORDER BY rowid DESC'):
                    action=json.loads(row[0])
                    if not isinstance(action,dict) or action.get('kind') not in {'chat','goal','amend','cancel','resume','commitment'}:
                        raise CoreError('application_data_compatibility','Unknown persisted assistant action')
                    if action['kind']=='commitment':needs['assistant_commitments']=True
                    if 'standing' in action:needs['standing_schema']=1
                    if str(action.get('target','')).startswith('standing-'):needs['standing_schema']=1
        finally:db.close()
    path=child(root,'state/core.sqlite3')
    if path.exists():
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='events'").fetchone():
                for row in db.execute("SELECT data FROM events WHERE kind='learning.repair_return'"):
                    mandate=json.loads(row[0])
                    if not isinstance(mandate,dict) or type(mandate.get('schema',1)) is not int or mandate.get('schema',1)!=1:
                        raise CoreError('application_data_compatibility','Unknown repair-return mandate schema')
                    # Terminal history still binds child authority and regression
                    # checks. Cancelling a mandate does not permit an old reader.
                    needs['repair_return_schema']=1
            row=db.execute("SELECT value FROM meta WHERE key='standing_schema'").fetchone()
            if row:
                if row[0]!='1':raise CoreError('application_data_compatibility','Unknown standing-work schema')
                needs['standing_schema']=1
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='goal_context'").fetchone():
                for row in db.execute('SELECT view,history FROM goal_context'):
                    view=json.loads(row[0]);history=json.loads(row[1])
                    for candidate in [view,*history]:
                        if 'conditional_advice' not in candidate:continue
                        advice=candidate['conditional_advice']
                        if not isinstance(advice,dict) or type(advice.get('version')) is not int or advice['version'] not in (1,2,3,4):
                            raise CoreError('application_data_compatibility','Unknown goal planning advice version')
                        needs['goal_advice_schema']=max(needs.get('goal_advice_schema',0),advice['version'])
            current_texts=();historical_texts=();fact_texts=()
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_sources'").fetchone():
                current_texts=(r[0] for r in db.execute("SELECT text FROM knowledge_sources WHERE status!='deleted'"))
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='memory_history'").fetchone():
                # Historical snapshots can survive a current source edit. Older
                # readers must not expose a past method as ordinary background.
                historical_texts=(json.loads(r[1])['text' if r[0]=='source' else 'value'] for r in db.execute("SELECT kind,body FROM memory_history WHERE kind IN ('source','fact')"))
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='facts'").fetchone():
                fact_texts=(r[0] for r in db.execute('SELECT value FROM facts WHERE deleted=0'))
            for text in chain(current_texts,fact_texts,historical_texts):
                try:value=json.loads(text)
                except ValueError:continue
                schema=value.get('schema') if isinstance(value,dict) else None
                if isinstance(schema,str) and schema.startswith('jarvis.method-card.'):
                    if schema!='jarvis.method-card.v1':
                        raise CoreError('application_data_compatibility','Unknown conditional advice schema')
                    needs['conditional_advice_schema']=1
        finally:db.close()
    path=child(root,'private/mail.sqlite3')
    if path.exists():
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            from control.credentials import crypt
            watches=list(db.execute("SELECT payload FROM objects WHERE kind='mail_watch' LIMIT 6"))
            if len(watches)>5:raise CoreError('application_data_compatibility','Unknown mailbox mandate capacity')
            for row in watches:
                value=json.loads(crypt(bytes(row[0]),decrypt=True))
                if type(value.get('schema')) is not int or value['schema']!=1:
                    raise CoreError('application_data_compatibility','Unknown encrypted mailbox mandate schema')
            if watches:needs['mail_watch_schema']=1
        finally:db.close()
    return needs


def require_compatible(root,package):
    try:
        needs=required(root);path=Path(package)/'config/runtime-compatibility.json';reject_links(path)
        declared={'schema':1,'commitments_schema':0,'assistant_commitments':False}
        if path.exists():
            if path.stat().st_size>4096:raise ValueError('Declaration too large')
            declared=json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(declared,dict) or set(declared)!={'schema','commitments_schema','assistant_commitments'}
                    or type(declared['schema']) is not int or declared['schema']!=1
                    or type(declared['commitments_schema']) is not int or declared['commitments_schema'] not in (0,1,2)
                    or type(declared['assistant_commitments']) is not bool):
                raise ValueError('Invalid compatibility declaration')
        if (needs['commitments_schema']>declared['commitments_schema'] or
                needs['assistant_commitments'] and not declared['assistant_commitments']):
            raise CoreError('application_data_compatibility','Target cannot serve existing commitment data/actions')
        if needs.get('standing_schema'):
            standing=Path(package)/'config/standing-compatibility.json';reject_links(standing)
            if not standing.exists() or standing.stat().st_size>1024 or json.loads(standing.read_text(encoding='utf-8'))!={'schema':1,'standing_schema':1}:
                raise CoreError('application_data_compatibility','Target cannot serve existing standing mandates')
        if needs.get('repair_return_schema'):
            repair=Path(package)/'config/repair-return-compatibility.json';reject_links(repair)
            if not repair.exists() or repair.stat().st_size>1024:
                raise CoreError('application_data_compatibility','Target cannot preserve repair-return authority')
            policy=json.loads(repair.read_text(encoding='utf-8'))
            if (not isinstance(policy,dict) or set(policy)!={'schema','repair_return_schema'}
                    or any(type(v) is not int or v!=1 for v in policy.values())):
                raise CoreError('application_data_compatibility','Unsupported repair-return reader')
        if needs.get('mail_watch_schema'):
            mail=Path(package)/'config/mail-standing-compatibility.json';reject_links(mail)
            if not mail.exists() or mail.stat().st_size>1024 or json.loads(mail.read_text(encoding='utf-8'))!={'schema':1,'mail_watch_schema':1}:
                raise CoreError('application_data_compatibility','Target cannot serve existing encrypted mailbox mandates')
        if needs.get('goal_advice_schema'):
            advice=Path(package)/'config/goal-advice-compatibility.json';reject_links(advice)
            if not advice.exists() or advice.stat().st_size>1024:
                raise CoreError('application_data_compatibility','Target cannot preserve goal planning advice dependencies')
            policy=json.loads(advice.read_text(encoding='utf-8'))
            if (not isinstance(policy,dict) or set(policy)!={'schema','goal_advice_schema'}
                or any(type(policy[k]) is not int for k in policy) or policy['schema']!=1
                or policy['goal_advice_schema'] not in (1,2,3,4) or policy['goal_advice_schema']<needs['goal_advice_schema']):
                raise CoreError('application_data_compatibility','Unsupported goal planning advice reader')
        if needs.get('conditional_advice_schema'):
            advice=Path(package)/'config/conditional-advice-compatibility.json';reject_links(advice)
            if not advice.exists() or advice.stat().st_size>1024:
                raise CoreError('application_data_compatibility','Target cannot preserve conditional advice boundaries')
            policy=json.loads(advice.read_text(encoding='utf-8'))
            if (not isinstance(policy,dict) or set(policy)!={'schema','conditional_advice_schema'}
                    or any(type(policy[k]) is not int or policy[k]!=1 for k in policy)):
                raise CoreError('application_data_compatibility','Unsupported conditional advice reader')
        return {'compatible':True,'required':needs,'declared':declared}
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error) as error:
        raise CoreError('application_data_compatibility','Cannot verify local data compatibility') from error
