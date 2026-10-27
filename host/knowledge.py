"""Local source library commands and one bounded, cancellable index rebuild per root."""
from concurrent.futures import ThreadPoolExecutor
import threading

from control.paths import data_root
from host.memory import LOCK, open_memory, scope_for
from modules.context_knowledge.knowledge import Knowledge, VERSION
from modules.context_knowledge.transfer import Transfer
from modules.context_knowledge.claims import Claims
from modules.context_knowledge.vectors import Vectors
from modules.preferences.store import Preferences
from sdk.protocol import CoreError

JOBS = {}
JOBS_LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1,thread_name_prefix='jarvis-knowledge')


def command(root,value):
    fields={'list':{'scope'},'detail':{'scope','id'},'save':{'item','revision'},'delete':{'scope','id','revision'},
            'rebuild':set(),'rebuild_vectors':set(),'index_status':set(),'cancel_rebuild':set(),
            'compile':{'scope','id','revision'},'claims':{'scope'},'dismiss_claim':{'scope','id','revision'},
            'accept_claim':{'scope','id','revision','item','fact_revision'},
            'export':{'scope'},'restore_preview':{'scope','bundle'},'restore':{'scope','bundle','token'},
            'cleanup_preview':{'scope','cursor'},'cleanup':{'scope','cursor','token'},'cleanup_status':{'scope'},'retry_cleanup_files':{'scope'}}
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']]:
        raise CoreError('knowledge_invalid','Unexpected library command')
    action=value['action'];root=data_root(root)
    if action in {'rebuild','rebuild_vectors','index_status','cancel_rebuild'}:
        return index_command(root,action)
    from modules.context_knowledge.joint import writable
    writable(value['item'].get('scope') if action=='save' and isinstance(value.get('item'),dict) else value.get('scope'))
    if action=='save':
        Knowledge.validate(value['item'],value['revision']);scope_for(root,value['item']['scope'])
        prefs=Preferences(root)
        try:known=set((prefs.read() or {}).get('catalog',{}).get('providers',{}))|{'codex-cli'}
        finally:prefs.close()
        if any(p not in known for p in value['item']['providers']):raise CoreError('knowledge_invalid','Select registered destinations')
    else:scope_for(root,value['scope'])
    db,_=open_memory(root)
    try:
        library=Knowledge(db)
        if action=='claims':return {'claims':Claims(db).list(value['scope'])}
        if action=='list':return {'sources':library.list(value['scope']),'index':index_command(root,'index_status'),'version':VERSION}
        if action=='detail':return library.detail(value['scope'],value['id'])
        with LOCK:
            if action=='compile':return Claims(db).compile(value['scope'],value['id'],value['revision'])
            if action=='dismiss_claim':return Claims(db).dismiss(value['scope'],value['id'],value['revision'])
            if action=='accept_claim':return Claims(db).accept(value['scope'],value['id'],value['revision'],value['item'],value['fact_revision'])
            if action=='export':return Transfer(db).export(value['scope'])
            if action=='restore_preview':return Transfer(db).preview(value['scope'],value['bundle'])
            if action=='restore':return Transfer(db).restore(value['scope'],value['bundle'],value['token'])
            if action in {'cleanup_preview','cleanup'}:
                from host import knowledge_cleanup
                if action=='cleanup_preview':return knowledge_cleanup.preview(db,root,value['scope'],value['cursor'])
                return knowledge_cleanup.apply(db,root,value['scope'],value['cursor'],value['token'])
            if action=='retry_cleanup_files':
                from host.knowledge_cleanup import retry_files
                return retry_files(db,root,value['scope'])
            if action=='cleanup_status':return {'receipts':db.all('SELECT * FROM knowledge_cleanups WHERE scope=? ORDER BY created DESC LIMIT 30',(value['scope'],)),
                'files':db.all('SELECT id,state,error FROM knowledge_file_retractions WHERE scope=? UNION ALL SELECT id,state,error FROM knowledge_artifact_retractions WHERE scope=? LIMIT 200',(value['scope'],value['scope'])), 'version':VERSION}
            if action=='save':return library.save(value['item'],value['revision'])
            return library.delete(value['scope'],value['id'],value['revision'])
    finally:db.close()


def index_command(root,action):
    key=str(root)
    with JOBS_LOCK:
        job=JOBS.get(key)
        if action in {'rebuild','rebuild_vectors'}:
            if job and job['state'] in {'queued','running'}:return public(job)
            job={'state':'queued','processed':0,'cancel':threading.Event(),'error':None,'kind':'vectors' if action=='rebuild_vectors' else 'fts'};JOBS[key]=job
            job['future']=POOL.submit(rebuild,root,job)
        if action=='cancel_rebuild' and job:job['cancel'].set()
        result=public(job) if job else {'state':'idle','processed':0,'error':None}
    db,_=open_memory(root)
    try:
        slot=Knowledge(db).slot()
        result.update(available=bool(slot and db.one('SELECT 1 FROM sqlite_master WHERE name=?',(slot,))),version=VERSION)
        result['vectors']=Vectors(db).status()
    finally:db.close()
    return result


def public(job):
    return {k:job[k] for k in ('state','processed','error','kind')}|{'result':job.get('result')}


def close(root):
    with JOBS_LOCK:
        job=JOBS.get(str(data_root(root)))
        if not job:return
        job['cancel'].set();future=job.get('future')
    if future:future.result(timeout=10)


def rebuild(root,job):
    db,_=open_memory(root)
    try:
        with JOBS_LOCK:job['state']='running'
        def checkpoint():
            if job['cancel'].is_set():raise CoreError('knowledge_cancelled','Index build cancelled')
        def progress(count):
            with JOBS_LOCK:job['processed']=count
        if job['kind']=='vectors':
            from host.knowledge_vectors import build
            result=build(root,db,checkpoint,progress)
        else:result=Knowledge(db).rebuild(checkpoint,progress)
        with JOBS_LOCK:
            job['state']='succeeded'
            job['result']={k:v for k,v in result.items() if k in {'index_version','build_version','indexed_chunks','epoch',
                'encoded','reconcile_attempts','replayed_sources','rechecked_sources'}}
    except Exception as exc:
        with JOBS_LOCK:
            job['error']=exc.code if isinstance(exc,CoreError) else 'knowledge_index_failed'
            job['state']='cancelled' if job['error']=='knowledge_cancelled' else 'failed'
    finally:db.close()
