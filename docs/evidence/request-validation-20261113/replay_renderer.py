"""Same native replies, explicit-format counterfactual; never relabel old failures."""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from host import assistant
from host.delivery_review import materialize
from modules.dialogue import delivery_basis
from modules.dialogue.document_format import FORMAT
from modules.task_resource import trial_checks
from sdk.protocol import canonical


def main():
    source=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((source/'frozen.json').read_text(encoding='utf-8'));rows=[]
    for path in sorted((source/'turns').glob('*.result.json')):
        record=json.loads(path.read_text(encoding='utf-8'));key=record['case_id']+'-'+record['arm']+'-'+str(record['turn'])
        ref=next(c for c in frozen['suite']['cases'] if c['id']==record['case_id'])['turns'][record['turn']]
        declared=re.findall(r'^(F\d+|P\d+)：([^\n]+)$',ref['prompt'],flags=re.MULTILINE)
        value={'expected_revision':0,'facts':[text for ident,text in declared if ident.startswith('F')],
               'plans':[text for ident,text in declared if ident.startswith('P')]}
        basis=delivery_basis.update(value,ref['prompt'],'replay-'+key,delivery_basis.empty(),frozen['created'])
        wire_path=source/'artifacts'/(key+'.native.json');raw=json.loads(wire_path.read_text(encoding='utf-8'))
        reply,action=assistant.parse(raw['text'],[])
        result,receipt=materialize({'request':canonical({'delivery_format':FORMAT}),'delivery_basis':canonical(basis)},
            {'status':raw['status'],'text':reply,'assistant_action':action})
        before=trial_checks.assess(ref,reply);after=trial_checks.assess(ref,result['text'])
        old=json.loads(reply);new=json.loads(result['text'])
        unchanged={k:v for k,v in old.items() if k!='document'}=={k:v for k,v in new.items() if k!='document'}
        (out/(key+'.document.md.txt')).write_text(new['document'],encoding='utf-8')
        rows.append({'key':key,'before':before,'after':after,'non_document_fields_unchanged':unchanged,
            'native_wire_sha256':hashlib.sha256(wire_path.read_bytes()).hexdigest(),'rendering':receipt})
    report={'scope':'Counterfactual explicit document selection over the same captured native replies; original live failures remain failures',
        'model_calls':0,'rows':rows,'before_pass':sum(r['before']['state']=='PASS' for r in rows),
        'after_pass':sum(r['after']['state']=='PASS' for r in rows),'business_fields_unchanged':all(r['non_document_fields_unchanged'] for r in rows),
        'quality_gain':None,'learning_gain':None}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['model_calls','before_pass','after_pass','business_fields_unchanged']}))


if __name__=='__main__':main()
