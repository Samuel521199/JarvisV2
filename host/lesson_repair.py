"""Failed synthetic trials become separately authorized standard development runs.

The link is provenance only. It never authorizes reuse of source data/tools,
replaces the original tool, or bypasses the existing release review.
"""
import secrets
from control.application_runtime import require_accepting
from control.recovery.gate import RunLock
from host.completion import refresh
from host.development import admit,resolve_routes
from modules.task_resource import lesson_checks,lesson_repairs
from sdk.protocol import CoreError,decode,digest

EVENT='learning.repair_created'
LIMITS={'max_attempts':2,'max_model_calls':4,'max_seconds':900}

def linked(core,key):
    row=core.db.one("SELECT data FROM events WHERE kind=? AND json_extract(data,'$.key')=? ORDER BY seq DESC LIMIT 1",(EVENT,key))
    return decode(row['data']) if row else None

def prepare(core,task_id):
    candidate=refresh(core,task_id,transaction=core.db.connection if core.db.connection.in_transaction else None).get('learning_candidate')
    if not candidate or candidate['state']!='CANDIDATE' or candidate['next_step']!='resolve_validation_failure' or candidate['scope']!='personal':
        raise CoreError('lesson_repair','Repair needs a current personal candidate with a failed local trial')
    trial=candidate['validation']['trial'];purpose=candidate['applicability'].get('purpose')
    if (not trial or trial['source_task']!=task_id or trial['fingerprint']!=candidate['fingerprint']
        or trial['key']!=digest([lesson_checks.VERSION,candidate['family']])
        or trial['challenge']!=lesson_checks.manifest(purpose,lesson_checks.challenges(purpose,trial['seed']))):
        raise CoreError('lesson_changed','Trial evidence or verifier changed')
    title,description=lesson_repairs.description(purpose)
    old=linked(core,trial['key'])
    return {'key':trial['key'],'fingerprint':candidate['fingerprint'],'purpose':purpose,
        'capability':'plugin.repair-'+trial['key'][:24]+'.v1','goal':title,'description':description,
        'public_cases':lesson_repairs.examples(purpose,trial['seed']),'holdout_count':4,'limits':dict(LIMITS),
        'development_id':old['development_id'] if old else None}

def begin(core,value):
    if value['reviewed'] is not True:raise CoreError('review_required','Review the synthetic contract and separate development budget')
    resolved=resolve_routes(core,value['routes'])
    with RunLock(core.root,'development'),core.db.transaction() as tx:
        require_accepting(core.root);core.gate.require_running()
        draft=prepare(core,value['id'])
        if (draft['key'],draft['fingerprint'])!=(value['key'],value['fingerprint']):
            raise CoreError('conflict','Repair evidence changed')
        old=linked(core,draft['key'])
        if old:
            control=core.db.one('SELECT routes FROM development_controls WHERE run_id=?',(old['development_id'],))
            if not control or decode(control['routes'])!=resolved:raise CoreError('conflict','Repair route changed')
            return {'id':old['development_id'],'existing':True}
        cap=draft['capability']
        if core.packages.slot(cap) or core.db.one('SELECT id FROM packages WHERE capability=?',(cap,)):
            raise CoreError('conflict','Repair capability already exists')
        seed=secrets.token_hex(16);private=lesson_repairs.examples(draft['purpose'],seed)
        if {c['input'] for c in private}&{c['input'] for c in draft['public_cases']}:
            raise CoreError('lesson_overlap','Fresh evaluation overlapped public inputs; no grant created')
        spec={'schema':'jarvis.development.v1','request_id':'repair.'+draft['key'],'grant_id':'workbench-repair-'+draft['key'][:48],
            'principal_id':'owner.local','scope_id':'personal','goal':draft['goal'],'capability':cap,'description':draft['description'],
            'public_cases':draft['public_cases'],'evaluation_cases':private,'sample_input':draft['public_cases'][0]['input'],'limits':dict(LIMITS)}
        ident=admit(core,spec,resolved,tx)
        core.db.event(tx,value['id'],EVENT,{'key':draft['key'],'fingerprint':draft['fingerprint'],'development_id':ident,
            'source_task':value['id'],'verifier':lesson_checks.VERSION,'evaluation_seed':seed,'spec_digest':digest(spec),
            'provenance_only':True,'original_tool_replaced':False})
        return {'id':ident,'existing':False}
