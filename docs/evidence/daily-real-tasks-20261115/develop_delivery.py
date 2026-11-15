"""Normal bounded development for reviewed text delivery; never English mastery."""
import json,time
from session import Client,OUT,route,write

def main():
    assert not (OUT/'delivery-tool-start.json').exists(),'Inspect existing development; no duplicate paid submission'
    cases=[('# Reviewed\n\nKeep this sentence.','# Reviewed\n\nKeep this sentence.'),('', ''),('中英对照：hello\n- 保留来源 https://example.invalid/a','中英对照：hello\n- 保留来源 https://example.invalid/a'),('  leading\n\ntrailing  ','  leading\n\ntrailing  ')]
    def case(pair):return {'input':json.dumps({'markdown':pair[0]},ensure_ascii=False),'expected':pair[1]}
    spec={'schema':'jarvis.development.v1','request_id':'daily-reviewed-delivery-20261115-r1','principal_id':'owner.local','scope_id':'personal',
      'goal':'交付已审阅的当前文本，保持内容逐字不变；不创作事实、不评判学习能力。','capability':'plugin.reviewed-materials.v1',
      'description':'Pure run(text)->str. Input is a JSON object with one string field markdown. Return that string exactly, preserving whitespace, Unicode and links, including empty string. No file or network access. This tool delivers already reviewed material; it does not author, fact-check, teach or score proficiency. No hardcoded examples.',
      'public_cases':[case(x) for x in cases[:2]],'evaluation_cases':[case(x) for x in cases[2:]],'sample_input':case(cases[0])['input'],
      'limits':{'max_attempts':2,'max_model_calls':4,'max_seconds':900}}
    selected=route();client=Client();result=client.call('/api/development',{'action':'create','spec':spec,'routes':{'plan':[selected],'code':[selected]}})
    write(OUT/'delivery-tool-start.json',{'development_id':result['id'],'spec':spec,'route':selected,'operator_specification_setup':1,'shared_setup_cost_not_per_task':True})
    client.call('/api/development-runner',{'id':result['id'],'network_enabled':True,'retry_unknown':False})
    for _ in range(90):
        detail=client.call('/api/development',{'action':'detail','id':result['id']},log=False)
        if detail['run']['status'] not in ('READY','RUNNING'):break
        time.sleep(2)
    else:raise RuntimeError('Development still pending; observe original ID')
    write(OUT/'delivery-tool-review.json',detail)
    print(json.dumps({'id':result['id'],'status':detail['run']['status'],'phase':detail['run']['phase'],'error':detail['run']['error'],'candidate':detail['run']['candidate']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
