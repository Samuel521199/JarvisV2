"""Explicit image tasks with durable receipts, cancellation and existing call ledger."""
import base64,hashlib,json,re,sqlite3,threading,time
from adapters.models.images import ImageModel
from adapters.models.image_transport import raster
from control.credentials import Credentials
from control.network import NetworkGate
from control.paths import child
from control.recovery.gate import StopGate,RunLock
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences,resolve
from modules.skills.catalog import Skills
from modules.image_generation.catalog import MODELS,RATIOS,VERSION,CHECKED,validate
from modules.image_generation import settings as image_settings
from modules.image_generation.catalog import dimensions
from modules.image_generation.rates import snapshot as price_snapshot,quote
from modules.image_generation.design import RECIPES,compile_brief
from sdk.pricing import estimate
from sdk.protocol import CoreError,canonical,digest

LOCK=threading.Lock();ACTIVE=set();GUARD=threading.Lock()
TERMINAL={'SUCCEEDED','FAILED','CANCELLED','UNKNOWN'}

def ident(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise CoreError('image_invalid','Expected image task ID')
    return value

def enabled(root):
    StopGate(root).require_running();s=Skills(root)
    try:s.select('image-studio','')
    finally:s.close()

def db(root):
    d=sqlite3.connect(child(root,'state/image-generation.sqlite3'),timeout=5,isolation_level=None);d.row_factory=sqlite3.Row
    d.execute('PRAGMA synchronous=FULL')
    d.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,signature TEXT NOT NULL,status TEXT NOT NULL,request TEXT NOT NULL,receipt TEXT,error TEXT,chat_id TEXT,turn_id TEXT,cancel INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL)')
    columns={r[1] for r in d.execute('PRAGMA table_info(jobs)')}
    for name in ('billing','design','quote'):
        if name not in columns:
            try:d.execute('ALTER TABLE jobs ADD COLUMN '+name+' TEXT')
            except sqlite3.OperationalError as exc:
                if 'duplicate column' not in str(exc):raise
    d.execute('CREATE TABLE IF NOT EXISTS annotations(job TEXT NOT NULL,kind TEXT NOT NULL,revision INTEGER NOT NULL,value TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(job,kind,revision))')
    return d

def update(root,key,**fields):
    d=db(root)
    try:d.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),key))
    finally:d.close()

def state(root,key):
    ident(key);d=db(root)
    try:r=d.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
    finally:d.close()
    if not r:raise CoreError('image_missing','Image task not found')
    r=dict(r)
    with GUARD:active=(str(root),key) in ACTIVE
    if r['status']=='RUNNING' and not active:
        # No replay after an interrupted invocation. A provider may have billed it.
        probe=RunLock(root,'image-generation')
        try:probe.__enter__()
        except CoreError as e:
            if e.code!='busy':raise
        else:
            probe.__exit__(None,None,None)
            update(root,key,status='UNKNOWN',error='image_host_interrupted');r.update(status='UNKNOWN',error='image_host_interrupted')
    if r['status']=='UNKNOWN' and r['error']=='image_host_interrupted' and r['turn_id']:
        ledger=Dialogues(root)
        try:
            ledger.db.execute("UPDATE attempts SET status='UNKNOWN',error='image_host_interrupted' WHERE turn_id=? AND status='DISPATCHING'",(r['turn_id'],))
            ledger.db.execute("UPDATE turns SET status='UNKNOWN',error='image_host_interrupted' WHERE id=? AND status IN ('READY','RUNNING')",(r['turn_id'],))
        finally:ledger.close()
    for name in ('request','receipt','billing','design','quote'):
        if r[name]:r[name]=json.loads(r[name])
    d=db(root)
    try:
        for kind in ('review','invoice'):
            entry=d.execute('SELECT revision,value FROM annotations WHERE job=? AND kind=? ORDER BY revision DESC LIMIT 1',(key,kind)).fetchone()
            r[kind]={'revision':entry[0],**json.loads(entry[1])} if entry else None
    finally:d.close()
    return r

def listing(root):
    d=db(root)
    try:ids=[r[0] for r in d.execute('SELECT id FROM jobs ORDER BY created DESC LIMIT 40')]
    finally:d.close()
    return [state(root,i) for i in ids]

def readiness(root):
    p=Preferences(root)
    try:public=p.public(Credentials(root).available)
    finally:p.close()
    routes=[{'id':c['id'],'label':c['label'],'adapter':c['adapter'],'credential_available':c['credential_available']} for c in public['connections'] if c['enabled'] and c['adapter'] in {'vertex','gemini'}]
    config=image_settings.read(root)
    return {'version':VERSION,'checked_at':CHECKED,'models':[{'id':k,**v,'enabled':k in config['enabled_models'],'dimensions':{s:{a:dimensions(s,a) for a in RATIOS} for s in v['sizes']},'rates':{a:price_snapshot(a,k) for a in ('vertex','gemini')}} for k,v in MODELS.items()],'ratios':RATIOS,'routes':routes,'settings':config,'recipes':[{'id':k,**v} for k,v in RECIPES.items()],'default_model':config['model'],'ready':any(r['credential_available'] for r in routes),'network_blocked':NetworkGate(root).read()['blocked'],'limits':{'reference_pngs':2,'reference_bytes':12*1024**2,'output_images':1,'wall_seconds':270},'scope':'Explicit single-turn generation or edit; no automatic retries, fallback, search grounding or default chat routing. Official model listing does not prove account access.'}

def configure(root,body):
    StopGate(root).require_running()
    if not isinstance(body,dict):raise CoreError('image_settings_invalid','Expected settings')
    if body.get('provider'):
        p=Preferences(root)
        try:
            current=p.read();route=resolve(current['catalog'],body['provider']) if current else None
            if not route or route['adapter'] not in {'vertex','gemini'}:raise CoreError('image_settings_invalid','Select a configured Google connection')
        finally:p.close()
    return image_settings.save(root,body)

def prepared(root,body):
    required={'id','provider','model','prompt','size','aspect_ratio'}
    if not isinstance(body,dict) or not required<=set(body) or set(body)-required-{'references','design','derived_from'}:raise CoreError('image_invalid','Invalid image task')
    value=validate({k:body[k] for k in ('model','prompt','size','aspect_ratio')})
    value['prompt'],design=compile_brief(value['prompt'],body.get('design'))
    config=image_settings.read(root)
    if value['model'] not in config['enabled_models']:raise CoreError('image_model_disabled','Image model disabled in image settings')
    return value,design,config

def preview(root,body):
    value,design,config=prepared(root,body)
    if not isinstance(body['provider'],str) or body['provider']=='auto':raise CoreError('image_invalid','Select an explicit Google connection')
    p=Preferences(root)
    try:current=p.read();route=resolve(current['catalog'],body['provider']) if current else None
    finally:p.close()
    if not route or route['adapter'] not in {'vertex','gemini'}:raise CoreError('image_invalid','Select Google')
    refs=body.get('references',[])
    if not isinstance(refs,list) or len(refs)>2:raise CoreError('image_invalid','At most two references')
    q=quote(route['adapter'],value,len(refs))
    return {'request':value,'design':design,'quote':q,'allowed':q['planning_allowance']<=config['max_estimate_usd'],'max_estimate_usd':config['max_estimate_usd'],'expected_pixels':dimensions(value['size'],value['aspect_ratio'])}

def start(root,body):
    enabled(root);NetworkGate(root).require_online()
    value,design,config=prepared(root,body);key=ident(body['id'])
    refs=body.get('references',[])
    if not isinstance(refs,list) or len(refs)>2 or any(not isinstance(x,str) or not re.fullmatch('[a-f0-9]{32}',x) for x in refs):raise CoreError('image_invalid','Choose at most two local PNG references')
    if not isinstance(body['provider'],str) or body['provider']=='auto':raise CoreError('image_invalid','Select an explicit official Google connection')
    p=Preferences(root)
    try:
        current=p.read()
        if not current:raise CoreError('settings_missing','Configure Google first')
        route=resolve(current['catalog'],body['provider'])
    finally:p.close()
    if route['adapter'] not in {'gemini','vertex'}:raise CoreError('image_invalid','Use Google AI Studio or Vertex')
    if not Credentials(root).available(route['id'],route.get('credential_id')):raise CoreError('credential_missing','Configure this Google connection')
    route.update(model=value['model'],parameters={})
    quoted=quote(route['adapter'],value,len(refs))
    from datetime import date
    if date.today().isoformat()>quoted['price']['valid_until']:raise CoreError('image_price_expired','Price snapshot needs review')
    if quoted['planning_allowance']>config['max_estimate_usd']:raise CoreError('image_budget','Estimated allowance exceeds saved threshold')
    route['billing_profile']={**route['billing_profile'],'price':None,'image_price':quoted['price'],'purpose':'image_generation','billing_note':'Standard list-price estimate; provider invoice, credits and tax remain separate.'}
    from host.studio3d_reference import record
    pairs=[record(root,i) for i in refs]
    from adapters.models.vision import encode_png,validate_encoded
    validate_encoded([encode_png(raw) for _,raw in pairs])
    if any(len(raw)>7*1000**2 for _,raw in pairs):raise CoreError('image_invalid','Google inline reference must be at most 7 MB each')
    if body.get('derived_from'):
        parent=state(root,ident(body['derived_from']))
        if parent['status']!='SUCCEEDED' or parent['receipt']['file']['sha256'] not in [r['sha256'] for r,_ in pairs]:raise CoreError('image_design_invalid','Revision must use the parent image as an explicit reference')
    if not LOCK.acquire(blocking=False):raise CoreError('image_busy','One image task is already running')
    lease=None
    try:
        lease=RunLock(root,'image-generation');lease.__enter__();d=db(root)
        try:
            old=d.execute('SELECT signature FROM jobs WHERE id=?',(key,)).fetchone()
            if old:
                if old[0]!=digest(body):raise CoreError('conflict','Task ID already used')
                lease.__exit__(None,None,None);LOCK.release();return {'id':key,'existing':True}
            with GUARD:ACTIVE.add((str(root),key))
            d.execute('INSERT INTO jobs(id,signature,status,request,created) VALUES(?,?,?, ?,?)',(key,digest(body),'RUNNING',canonical(body),time.time()))
            d.execute('UPDATE jobs SET design=?,quote=? WHERE id=?',(canonical(design),canonical(quoted),key))
        finally:d.close()
        thread=threading.Thread(target=run,args=(root,key,value,route,pairs,lease),daemon=True,name='jarvis-image');thread.start()
        return {'id':key,'existing':False}
    except BaseException:
        with GUARD:ACTIVE.discard((str(root),key))
        if lease:lease.__exit__(None,None,None)
        LOCK.release();raise

def cancel(root,key):
    r=state(root,key)
    if r['status'] not in TERMINAL:update(root,key,cancel=1)
    return {'id':key,'status':r['status'] if r['status'] in TERMINAL else 'CANCEL_REQUESTED'}

def run(root,key,value,route,pairs,lease):
    store=None;attempt=None;turn=None;usage={};started=time.monotonic()
    try:
        def checkpoint():
            enabled(root);NetworkGate(root).require_online()
            if state(root,key)['cancel']:raise CoreError('image_cancelled','Image task cancelled')
        checkpoint();store=Dialogues(root);chat=store.create();turn='image-'+key
        command={'chat_id':chat,'request_id':turn,'text':value['prompt'],'provider':route['id'],'model':route['model'],'reasoning':'default','skill':'none','memory_enabled':False}
        store.begin(command,[route]);store.context(turn);update(root,key,chat_id=chat,turn_id=turn)
        checkpoint();attempt=store.start_attempt(turn,route)
        result=ImageModel(route,Credentials(root).get).generate(value,[raw for _,raw in pairs],checkpoint)
        usage=result.get('usage',{});store.attempt_result(attempt,result);attempt=None
        billing=estimate(route['billing_profile'],usage,time.time());update(root,key,billing=canonical(billing))
        if result['status']!='SUCCEEDED':
            status='UNKNOWN' if result['status']=='UNKNOWN' else 'FAILED'
            store.finish(turn,{**result,'status':status,'provider':route['id'],'model':route['model']});update(root,key,status=status,error=result.get('code'));return
        checkpoint();im=result['images'][0];raw=base64.b64decode(im['data'],validate=True);dimensions=raster(raw,im['mimeType'])
        folder=child(root,'artifacts/image-generation/'+key);folder.mkdir(parents=True,exist_ok=False);name='image.png' if im['mimeType']=='image/png' else 'image.jpg'
        (folder/name).write_bytes(raw);url='/api/image-studio/files/'+key+'/'+name
        receipt={'id':key,'version':VERSION,'provider':route['id'],'adapter':route['adapter'],'model':value['model'],'request':value,'file':{'name':name,'url':url,'mime':im['mimeType'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'resolution':dimensions},'usage':usage,'cost':None,'cost_note':'待Google账单核对，未用文本费率估算图片','elapsed_seconds':time.monotonic()-started,'text':result.get('text',''),'references':[{'id':r['id'],'sha256':r['sha256'],'sent_to_provider':route['id']} for r,_ in pairs],'source':MODELS[value['model']]['source'],'license':'Google API generated output; subject to provider terms and input rights; not guaranteed exclusive or historically accurate.'}
        job=state(root,key)
        from modules.image_generation.catalog import dimensions as expected_dimensions
        receipt.update(billing=billing,design=job['design'],quote=job['quote'],derived_from=job['request'].get('derived_from'),cost_note='费用为调用时单价快照与实际用量的估算，账单金额单独对账。',technical_checks={'expected_pixels':expected_dimensions(value['size'],value['aspect_ratio']),'actual_pixels':dimensions,'resolution_matches':dimensions==expected_dimensions(value['size'],value['aspect_ratio']),'visual_acceptance':'pending_human_review'},reference_compatible=im['mimeType']=='image/png' and len(raw)<=7*1000**2 and dimensions[0]*dimensions[1]<=16000000 and max(dimensions)<=8192)
        checkpoint();(folder/'receipt.json').write_text(canonical(receipt),encoding='utf-8')
        store.finish(turn,{'status':'SUCCEEDED','text':'图片已生成：['+name+']('+url+')\n\n'+result.get('text',''),'usage':usage,'provider':route['id'],'model':route['model']})
        update(root,key,status='SUCCEEDED',receipt=canonical(receipt))
    except BaseException as e:
        code=e.code if isinstance(e,CoreError) else 'image_local_failure'
        status='CANCELLED' if code in {'image_cancelled','stopped','skill_unavailable','network_disabled'} else 'UNKNOWN'
        if store and attempt is not None:store.attempt_result(attempt,{'status':'UNKNOWN','code':code,'usage':usage})
        if store and turn:store.finish(turn,{'status':status,'code':code,'usage':usage})
        update(root,key,status=status,error=code)
    finally:
        if store:store.close()
        with GUARD:ACTIVE.discard((str(root),key))
        lease.__exit__(None,None,None);LOCK.release()

def file(root,key,name):
    row=state(root,key)
    if row['status']!='SUCCEEDED' or name!=row['receipt']['file']['name']:raise CoreError('image_missing','Image not delivered')
    meta=row['receipt']['file'];raw=child(root,'artifacts/image-generation/'+key+'/'+name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise CoreError('image_changed','Image changed after delivery')
    return raw,meta['mime']

def reference(root,key):
    from host.studio3d_reference import upload
    row=state(root,key)
    if row['status']!='SUCCEEDED' or row['receipt']['file']['mime']!='image/png':raise CoreError('image_invalid','Choose a delivered PNG for Studio3D')
    raw,_=file(root,key,row['receipt']['file']['name'])
    return upload(root,{'name':'Nano-Banana-'+key[:8]+'.png','source':'Google '+row['receipt']['model']+'; Jarvis image task '+key,'license':'AI generated reference; input rights and Google terms apply; not measured real-world evidence.','data':base64.b64encode(raw).decode()})


def upload(root,body):
    enabled(root)
    from host.studio3d_reference import register
    return register(root,body)


def annotate(root,body):
    """Append-only local human review / invoice reconciliation, never a charge."""
    StopGate(root).require_running()
    if not isinstance(body,dict) or set(body)!={'id','kind','revision','value'} or body['kind'] not in ('review','invoice') or type(body['revision']) is not int:raise CoreError('image_annotation_invalid','Invalid annotation')
    key=ident(body['id']);row=state(root,key);v=body['value'];kind=body['kind']
    if row['status'] not in TERMINAL:raise CoreError('image_annotation_invalid','Wait for task completion')
    if kind=='review':
        if row['status']!='SUCCEEDED' or not row['design']:raise CoreError('image_annotation_invalid','Design artifact required')
        file(root,key,row['receipt']['file']['name'])
        checks={x['id'] for x in row['design']['checklist']}
        if not isinstance(v,dict) or set(v)!={'verdict','checks','notes'} or v['verdict'] not in ('accepted','needs_revision') or not isinstance(v['checks'],dict) or set(v['checks'])!=checks or any(type(x) is not bool for x in v['checks'].values()) or not isinstance(v['notes'],str) or len(v['notes'])>2000:raise CoreError('image_annotation_invalid','Complete the design checklist')
        if v['verdict']=='accepted' and (not all(v['checks'].values()) or not row['receipt'].get('technical_checks',{}).get('resolution_matches')):raise CoreError('image_annotation_invalid','Acceptance requires matching resolution and all human checks')
        v={**v,'reviewer':'local_user','image_sha256':row['receipt']['file']['sha256'],'model_scored':False}
    else:
        import math
        if not isinstance(v,dict) or set(v)!={'amount','currency','reference'} or type(v['amount']) not in (int,float) or not math.isfinite(v['amount']) or not 0<=v['amount']<=100000 or v['currency'] not in ('USD','CNY') or not isinstance(v['reference'],str) or not 1<=len(v['reference'].strip())<=200:raise CoreError('image_annotation_invalid','Supply the invoice amount and reference')
        v={**v,'method':'manual_invoice_entry','provider_verified':False}
    d=db(root)
    try:
        d.execute('BEGIN IMMEDIATE');revision=d.execute('SELECT COALESCE(MAX(revision),0) FROM annotations WHERE job=? AND kind=?',(key,kind)).fetchone()[0]
        if revision!=body['revision']:raise CoreError('conflict','Annotation changed; reload')
        d.execute('INSERT INTO annotations VALUES(?,?,?,?,?)',(key,kind,revision+1,canonical(v),time.time()));d.execute('COMMIT')
    except BaseException:
        if d.in_transaction:d.execute('ROLLBACK')
        raise
    finally:d.close()
    return state(root,key)


def summary(root):
    d=db(root)
    try:
        rows=d.execute('SELECT id,request,billing,status FROM jobs').fetchall()
        invoices={r['job']:json.loads(r['value']) for r in d.execute("SELECT a.* FROM annotations a WHERE a.kind='invoice' AND a.revision=(SELECT MAX(b.revision) FROM annotations b WHERE b.job=a.job AND b.kind='invoice')")}
    finally:d.close()
    groups={}
    for r in rows:
        request=json.loads(r['request']);key=request['provider']+'/'+request['model']
        group=groups.setdefault(key,{'provider':request['provider'],'model':request['model'],'tasks':0,'estimated_usd':0,'unknown':0,'pending':0,'invoice_count':0,'invoice_usd':0,'invoice_cny':0})
        group['tasks']+=1;billing=json.loads(r['billing']) if r['billing'] else {}
        if billing.get('amount') is not None:group['estimated_usd']+=billing['amount']
        elif r['status'] in TERMINAL:group['unknown']+=1
        else:group['pending']+=1
        if r['id'] in invoices:
            invoice=invoices[r['id']];group['invoice_count']+=1;group['invoice_'+invoice['currency'].lower()]+=invoice['amount']
    return {'groups':list(groups.values()),'scope':'all local image jobs; estimates and manually entered invoice amounts are separate, not added together','invoice_import':'manual only; no Google account balance or billing-export connection'}
