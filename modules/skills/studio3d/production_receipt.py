"""Usage accounting for persistent production trials; missing values stay null."""
import datetime


def duration(row):
    if row.get('elapsed_seconds') is not None:return row['elapsed_seconds']
    try:return (datetime.datetime.fromisoformat(row['finished_at'])-datetime.datetime.fromisoformat(row['started_at'])).total_seconds()
    except (KeyError,TypeError,ValueError):return None


def native_stage(name,row):
    return {'stage':name,'kind':'jarvis-fixed-blender-worker','status':row['status'],'job_id':row.get('id'),
            'elapsed_seconds':duration(row),'started_at':row.get('started_at'),'finished_at':row.get('finished_at'),
            'model_calls':0,'input_tokens':0,'output_tokens':0,'reasoning_tokens':0,'total_tokens':0,'estimated_usd':0,'charged_usd':0,
            'local_compute_usd':None,'cost_basis':'Local Blender only; zero model API dollars excludes local compute','record_owner':'studio3d-autopilot.v1'}


def model_stage(name,row):
    records=row.get('usage',[])
    def amount(key):
        values=[r.get('usage',{}).get(key) for r in records]
        return sum(values) if values and all(isinstance(v,(int,float)) for v in values) else None
    prices=[(r.get('billing') or {}).get('amount') for r in records]
    estimate=sum(prices) if prices and all(isinstance(v,(int,float)) for v in prices) else None
    explicitly_no_call=row.get('model_calls')==0
    out={'stage':name,'kind':'jarvis-model-call','status':row['status'],'model_calls':0 if explicitly_no_call else len(records) or None,
         'request_id':row.get('request_id',row.get('request',{}).get('request_id')),
         'input_tokens':amount('prompt_tokens'),'output_tokens':amount('completion_tokens'),'reasoning_tokens':amount('reasoning_tokens'),
         'cache_read_tokens':amount('cached_tokens'),'cache_write_tokens':amount('cache_write_tokens'),'total_tokens':amount('total_tokens'),
         'estimated_usd':estimate,'charged_usd':None,'elapsed_seconds':duration(row),'started_at':row.get('started_at'),'finished_at':row.get('finished_at'),
         'cost_basis':'Jarvis provider usage records and configured token rates; estimate, not an invoice',
         'usage_records':records,'record_owner':'studio3d-autopilot.v1'}
    if explicitly_no_call:
        out.update(input_tokens=0,output_tokens=0,reasoning_tokens=0,total_tokens=0,estimated_usd=0,cost_basis='Rejected before model invocation; zero model API calls explicitly recorded')
    return out


def stages(state,handoff=None):
    rows=[model_stage('jarvis-intake/'+r['stage'],r) for r in (handoff or {}).get('stages',[])]
    rows.extend(model_stage('autopilot/'+key,row) for key,row in state['calls'].items())
    for it in state['iterations']:
        if it.get('inspection'):rows.append(native_stage('autopilot/inspection-'+it['id'],it['inspection']))
        if not it.get('job_id'):continue
        rows.append({'stage':'autopilot/native-'+it['id'],'kind':'jarvis-fixed-blender-worker','status':it['status'],'job_id':it['job_id'],
                     'elapsed_seconds':it.get('native_elapsed_seconds'),'started_at':it.get('started_at'),'finished_at':it.get('finished_build_at'),
                     'model_calls':0,'input_tokens':0,'output_tokens':0,'reasoning_tokens':0,'total_tokens':0,'estimated_usd':0,'charged_usd':0,
                     'local_compute_usd':None,'triangles':it.get('triangles'),'cost_basis':'Local Blender only; zero model API dollars excludes local compute',
                     'record_owner':'studio3d-autopilot.v1'})
    return rows


def summary(rows):
    def known(key):return sum(r[key] for r in rows if isinstance(r.get(key),(int,float)))
    return {'known_model_calls':known('model_calls'),'known_tokens':known('total_tokens'),'known_api_estimated_usd':known('estimated_usd'),
            'known_model_call_seconds':sum(r['elapsed_seconds'] for r in rows if r['kind']=='jarvis-model-call' and r.get('elapsed_seconds') is not None),
            'known_native_seconds':sum(r['elapsed_seconds'] for r in rows if r['kind']=='jarvis-fixed-blender-worker' and r.get('elapsed_seconds') is not None),
            'unknown_api_cost_stages':sum(r.get('estimated_usd') is None for r in rows),
            'codex_author_tokens':None,'codex_author_usd':None,'local_compute_usd':None,'complete_total_usd':None,
            'basis':'Known API subtotal only; image generation, authoring and local compute may be unknown. Sequential work durations are not end-to-end wall time.'}
