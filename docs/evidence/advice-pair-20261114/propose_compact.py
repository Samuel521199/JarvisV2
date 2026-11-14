"""Offline proposed projection only; never sends a model request or writes goal data."""
from pathlib import Path
import json,hashlib
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114/compact-proposal'
OUT.mkdir(exist_ok=False)
record=json.loads((OUT.parent/'native-r1/with-advice-dispatch.json').read_text());prefix,body=record['prompt'].rsplit('\n',1);full=json.loads(body)
original=json.loads(body);keep=('id','recipe','requires','summary','counterexamples','source_id','source_revision')
full['conditional_advice']['methods']=[{key:method[key] for key in keep} for method in original['conditional_advice']['methods']]
full['conditional_advice']['format']='proposed-compact-v2'
canonical=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
prompt=prefix+'\n'+canonical(full)
size=lambda text:len(canonical([{'role':'user','content':text}]).encode('utf-8'))
checks={'same_goal_input_tools_and_ordinary_background':{k:v for k,v in full.items() if k!='conditional_advice'}=={k:v for k,v in original.items() if k!='conditional_advice'},
 'same_method_count':len(full['conditional_advice']['methods'])==len(original['conditional_advice']['methods']),
 'all_summaries_conditions_counterexamples_and_source_refs_unchanged':all(all(short[key]==method[key] for key in keep) for short,method in zip(full['conditional_advice']['methods'],original['conditional_advice']['methods'])),
 'same_outer_advisory_and_authority_flags':all(full['conditional_advice'][key]==original['conditional_advice'][key] for key in ('advisory_only','verified','execution_authorized'))}
assert all(checks.values())
report={'status':'proposed offline projection, unimplemented in runtime','source':'one already-seen frozen native message','old_full_message_bytes':size(record['prompt']),'draft_message_bytes':size(prompt),
 'byte_reduction':size(record['prompt'])-size(prompt),'byte_reduction_percent':(1-size(prompt)/size(record['prompt']))*100,
 'model_requests':0,'model_tokens':None,'task_quality':None,'monetary_savings':None,'runtime_data_written':False,'checks':checks,
 'retained_model_fields':list(keep),'host_must_retain':['complete original receipt and evidence','expiry and all source permissions','lineage and counterevidence','original model-call digest'],
 'compatibility_required_before_implementation':['explicit new prompt format on newly created goals','legacy full renderer for existing v1 goals','data-reader and controller fence before any new required persisted format','old readers refuse unsupported goals before drain or restore'],
 'not_proven':['token reduction','model quality or non-inferiority','unseen cases','long-term value','all-domain success']}
(OUT/'draft-prompt.txt').write_text(prompt,encoding='utf-8');(OUT/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
