"""Scoped Studio3D methods and append-only adoption outcomes; no model weights."""
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from control.paths import child
from sdk.protocol import CoreError

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'modules/skills/studio3d/experience-cards.json'


def catalog():
    value = json.loads(CATALOG.read_text(encoding='utf-8'))
    ids = set()
    for row in value['methods']:
        if row['id'] in ids: raise ValueError('Duplicate experience method')
        ids.add(row['id'])
    return value


def source_current(card):
    for row in card['sources']:
        try:
            path=child(ROOT,row['path'])
            if not path.is_file() or path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
                return False
        except (OSError,ValueError,KeyError): return False
    return True


class Studio3DExperience:
    def __init__(self, root):
        path = child(Path(root), 'state/studio3d-experience.sqlite3')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS method_state(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS episodes(run_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, receipt_hash TEXT NOT NULL, outcome TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS uses(run_id TEXT NOT NULL, method_id TEXT NOT NULL, method_revision INTEGER NOT NULL, PRIMARY KEY(run_id,method_id));
        CREATE TABLE IF NOT EXISTS feedback(event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
        ''')

    def close(self): self.db.close()

    def retrieve_candidates(self, asset_root, query, limit=4):
        """Asset-local advisory cases, never merged into executable seed methods.

        The model may choose symptom tags. The trusted caller binds the asset,
        measured facts and available tool versions. No case grants execution.
        """
        if type(limit) is not int or not 1 <= limit <= 6:
            raise ValueError('Candidate retrieval limit')
        if not isinstance(query,dict) or set(query)!={'asset_id','family','symptoms','facts','tool_versions'}:
            raise ValueError('Candidate query fields')
        if not isinstance(query['asset_id'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',query['asset_id']):
            raise ValueError('Candidate asset identity')
        if query['family'] not in ('hard_surface','towed_artillery'):
            raise ValueError('Candidate family')
        def tags(values):
            return isinstance(values,list) and 1<=len(values)<=16 and all(isinstance(v,str) and re.fullmatch('[a-z_]{1,60}',v) for v in values) and len(set(values))==len(values)
        if not tags(query['symptoms']):raise ValueError('Candidate symptoms')
        for field in ('facts','tool_versions'):
            values=query[field]
            if not isinstance(values,dict) or len(values)>20 or any(not isinstance(k,str) or not re.fullmatch('[a-z_]{1,60}',k) for k in values):
                raise ValueError('Candidate context bounds')
        if any(type(v) is not bool for v in query['facts'].values()) or any(not isinstance(v,str) or not re.fullmatch(r'\d+\.\d+\.\d+',v) for v in query['tool_versions'].values()):
            raise ValueError('Facts and tool versions must be typed')
        base=(ROOT/'3DModels').resolve();requested=Path(asset_root).absolute()
        if not requested.is_relative_to(base) or requested==base:raise ValueError('Candidate asset outside project')
        asset=child(base,requested.relative_to(base).as_posix())
        def read(relative,maximum=262144):
            path=child(asset,relative)
            if not path.is_file() or path.stat().st_size>maximum:raise ValueError('Candidate evidence size/missing')
            return path.read_bytes()
        binding=json.loads(read('metadata/learning-contract-intake.json'))
        if binding.get('asset_id')!=query['asset_id'] or binding.get('family')!=query['family']:
            raise ValueError('Candidate asset binding mismatch')
        raw=read('metadata/local-methods.json');value=json.loads(raw)
        if value.get('schema')!='jarvis.studio3d.local-methods.v1' or value.get('asset_id')!=query['asset_id'] or value.get('family')!=query['family'] or value.get('automatic_promotion') is not False:
            raise ValueError('Local catalog scope mismatch')
        cards=value.get('cases')
        if not isinstance(cards,list) or len(cards)>64:raise ValueError('Local catalog budget')
        accepted=[];rejected=[];seen=set()
        for card in cards:
            required={'id','revision','title','status','promoted','symptoms','requires','tool_versions','summary','counterexamples','evidence'}
            if not isinstance(card,dict) or set(card)!=required or not isinstance(card['id'],str) or not re.fullmatch('[a-z0-9-]{1,80}',card['id']) or card['id'] in seen:
                raise ValueError('Invalid local case identity/schema')
            seen.add(card['id'])
            if type(card['revision']) is not int or card['revision']<1 or card['promoted'] is not False or card['status'] not in ('CANDIDATE','QUARANTINED') or not tags(card['symptoms']):raise ValueError('Local candidate status')
            if not isinstance(card['requires'],dict) or len(card['requires'])>20 or any(not isinstance(k,str) or not re.fullmatch('[a-z_]{1,60}',k) or type(v) is not bool for k,v in card['requires'].items()) or not isinstance(card['tool_versions'],dict) or len(card['tool_versions'])>20 or any(not isinstance(k,str) or not re.fullmatch('[a-z_]{1,60}',k) or not isinstance(v,str) or not re.fullmatch(r'\d+\.\d+\.\d+',v) for k,v in card['tool_versions'].items()):raise ValueError('Local candidate conditions')
            if any(not isinstance(card[k],str) or not 1<=len(card[k])<=2000 for k in ('title','summary','counterexamples')):raise ValueError('Local candidate text budget')
            if not isinstance(card['evidence'],list) or not 1<=len(card['evidence'])<=12:raise ValueError('Local candidate evidence budget')
            reason=None
            if card['status']=='QUARANTINED':reason='quarantined'
            elif not set(query['symptoms'])&set(card['symptoms']):reason='symptom_mismatch'
            elif any(query['facts'].get(k)!=v for k,v in card['requires'].items()):reason='precondition_mismatch'
            elif any(query['tool_versions'].get(k)!=v for k,v in card['tool_versions'].items()):reason='tool_version_mismatch'
            if reason is None:
                try:
                    for ev in card['evidence']:
                        if not isinstance(ev,dict) or set(ev)!={'path','sha256','bytes'} or type(ev['bytes']) is not int or not 0<ev['bytes']<=4194304 or not isinstance(ev['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',ev['sha256']):raise ValueError('Invalid evidence binding')
                        data=read(ev['path'],4194304)
                        if len(data)!=ev['bytes'] or hashlib.sha256(data).hexdigest()!=ev['sha256']:raise ValueError('Changed evidence')
                except (OSError,ValueError,KeyError,TypeError,CoreError):reason='source_changed_missing_or_unsafe'
            if reason:rejected.append({'id':card['id'],'reason':reason})
            else:accepted.append({**card,'matched_symptoms':sorted(set(query['symptoms'])&set(card['symptoms'])),'advisory_only':True,'executable':False})
        accepted.sort(key=lambda c:(-len(c['matched_symptoms']),c['id']))
        return {'schema':'jarvis.studio3d.case-retrieval.v1','asset_id':query['asset_id'],'query':query,'catalog_sha256':hashlib.sha256(raw).hexdigest(),'candidate_cases':accepted[:limit],'rejected':rejected,'automatic_promotion':False,'execution_authorized':False,'scope':'Asset-local audited case retrieval; not autonomous editing, general knowledge or independent transfer'}

    def retrieve(self, context, limit=6):
        if not isinstance(limit, int) or not 1 <= limit <= 12: raise ValueError('Invalid retrieval limit')
        rows, rejected = [], []
        states = {r['id']: dict(r) for r in self.db.execute('SELECT * FROM method_state')}
        for card in catalog()['methods']:
            state = states.get(card['id'], {'status': 'SEED', 'revision': card['revision']})
            reason = None
            if state['status'] == 'QUARANTINED': reason = 'quarantined'
            elif context.get('family') not in card['families']: reason = 'family_mismatch'
            elif card.get('asset_ids') and context.get('asset_id') not in card['asset_ids']: reason = 'asset_mismatch'
            elif card.get('tool_version') and context.get('tool_version') != card['tool_version']: reason = 'tool_version_mismatch'
            elif not set(context.get('symptoms', [])) & set(card['symptoms']): reason = 'symptom_mismatch'
            elif any(context.get(k) != v for k, v in card['requires'].items()): reason = 'precondition_mismatch'
            elif not source_current(card): reason = 'source_changed_or_missing'
            if reason: rejected.append({'id': card['id'], 'reason': reason}); continue
            rows.append({**card, 'state': state['status'], 'revision': state['revision']})
        return {'methods': rows[:limit], 'rejected': rejected, 'scope': 'conditional method retrieval, not historical or art approval'}

    def record(self, receipt):
        if receipt.get('schema') != 'jarvis.studio3d.learning.receipt.v1': raise ValueError('Unknown receipt')
        run = receipt['id']; body = json.dumps(receipt, sort_keys=True, ensure_ascii=False, allow_nan=False)
        sha = hashlib.sha256(body.encode()).hexdigest()
        old = self.db.execute('SELECT receipt_hash FROM episodes WHERE run_id=?', (run,)).fetchone()
        if old:
            if old['receipt_hash'] != sha: raise ValueError('Run already has different evidence')
            return {'existing': True}
        # These records are authored only by the host after actual execution.
        # A tool pass certifies its declared scope, never the asset's visual quality.
        cards = {c['id']: c for c in catalog()['methods']}
        for use in receipt['adoptions']:
            if use['id'] not in cards or use['tool'] not in cards[use['id']]['tools']: raise ValueError('Unknown executable adoption')
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?)', (run, receipt['asset_id'], sha, receipt['status'], body, time.time()))
            for use in receipt['adoptions']:
                self.db.execute('INSERT INTO uses VALUES(?,?,?)', (run, use['id'], use['revision']))
        return {'existing': False}

    def feedback(self, event_id, run_id, method_id, reason):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1200: raise ValueError('Explain the counterexample')
        if not all(isinstance(v, str) and 1 <= len(v) <= 100 for v in (event_id, run_id, method_id)): raise ValueError('Invalid feedback identity')
        use = self.db.execute('SELECT * FROM uses WHERE run_id=? AND method_id=?', (run_id, method_id)).fetchone()
        if not use: raise ValueError('Feedback must reference an actual adoption')
        body = json.dumps({'method_id': method_id, 'reason': reason}, sort_keys=True, ensure_ascii=False)
        old = self.db.execute('SELECT * FROM feedback WHERE event_id=?', (event_id,)).fetchone()
        if old:
            if old['run_id'] != run_id or old['body'] != body: raise ValueError('Feedback ID conflict')
            return {'existing': True, 'status': 'QUARANTINED'}
        with self.db:
            self.db.execute('INSERT INTO feedback VALUES(?,?,?,?)', (event_id, run_id, body, time.time()))
            self.db.execute('''INSERT INTO method_state VALUES(?,?,'QUARANTINED',?)
                ON CONFLICT(id) DO UPDATE SET revision=method_state.revision+1,status='QUARANTINED',reason=excluded.reason''',
                (method_id, use['method_revision'] + 1, reason))
        return {'existing': False, 'status': 'QUARANTINED', 'causality': 'counterexample requires review; not a proven root cause'}

    def summary(self):
        return {'catalog_version': catalog()['version'], 'seed_methods': len(catalog()['methods']),
                'states': [dict(r) for r in self.db.execute('SELECT * FROM method_state ORDER BY id')],
                'episodes': self.db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0],
                'distinct_assets': self.db.execute('SELECT COUNT(DISTINCT asset_id) FROM episodes').fetchone()[0],
                'automatic_promotion': False, 'cross_asset_art_gain_verified': False}
