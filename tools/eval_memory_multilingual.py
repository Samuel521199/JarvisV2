"""Offline lexical / installed-E5 comparison on a frozen article-disjoint corpus."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from host.core import Core
from host.local_models import Worker
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.vectors import Vectors
from modules.local_models.catalog import builtin,space
from sdk.protocol import canonical
from tools.freeze_memory_multilingual import ROOT,CACHE,OUT,load


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['development','holdout'],default='development')
    parser.add_argument('--mode',choices=['lexical','hybrid'],required=True);parser.add_argument('--run',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,40}',args.run):parser.error('Invalid run identifier')
    target=OUT/args.run
    if target.exists():raise SystemExit('Use a fresh run identifier; prior evidence must be preserved')
    target.mkdir();frozen=json.loads((OUT/'frozen.json').read_text(encoding='utf-8'))
    for lang,file in frozen['files'].items():
        if hashlib.sha256((CACHE/f'xquad.{lang}.json').read_bytes()).hexdigest()!=file['sha256']:raise RuntimeError('Dataset digest changed')
    cases=frozen['cases'][args.split];grouped={}
    for case in cases:grouped.setdefault(case['source_language'],[]).append(case)
    catalog=next(m for m in builtin() if m['id']=='e5-multilingual-small-int8');folder=ROOT/'user-data/local-models'/catalog['id']
    worker=None;metadata={};rows=[];builds=[];cached=CACHE/args.run;cached.mkdir()
    report={'split':args.split,'mode':args.mode,'frozen_sha256':hashlib.sha256((OUT/'frozen.json').read_bytes()).hexdigest(),
            'acceptance_complete':False,'official_score':False,'limits':'Actual 12-item/5000-byte context; no generative QA yet',
            'runtime_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT/'modules/context_knowledge').glob('*.py')}}
    try:
        if args.mode=='hybrid':
            for item in catalog['files']:
                with (folder/item['name']).open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
                if sha!=item['sha256']:raise RuntimeError('Installed model does not match its public manifest')
            worker=Worker(folder);metadata=worker.wait(lambda:None);report['model']={'id':catalog['id'],'space':space(catalog),'worker':metadata}
        for language,selected in grouped.items():
            data=load(language)['data'];articles={a['title']:a for a in data}
            with tempfile.TemporaryDirectory(prefix='jarvis-multilingual-eval-') as temp:
                core=Core.initialize(Path(temp))
                try:
                    library=Knowledge(core.db);ids={};start=time.perf_counter()
                    for article in data:
                        if article['title'] not in frozen['articles'][args.split]:continue
                        for index,paragraph in enumerate(article['paragraphs']):
                            result=library.save(dict(id='',scope='personal',title=article['title']+' · '+str(index),
                                                      text=paragraph['context'],providers=['evaluation'],paused=False),0)
                            ids[(article['title'],index)]=result['id']
                    library.rebuild();vectors=Vectors(core.db)
                    if worker:
                        vectors.build(space(catalog),384,lambda texts:worker.request(texts,'passage',lambda:None)['vectors'])
                    builds.append({'source_language':language,'sources':len(ids),'seconds':time.perf_counter()-start,
                                   'vectors':vectors.status()['vectors'] if worker else 0})
                    for case in selected:
                        question_article=next(a for a in load(case['language'])['data'] if a['title']==case['article'])
                        question=next(q for q in question_article['paragraphs'][case['paragraph']]['qas'] if q['id']==case['id'])['question']
                        original=articles[case['article']]['paragraphs'][case['paragraph']]
                        reference=next(q for q in original['qas'] if q['id']==case['id']);expected=ids[(case['article'],case['paragraph'])]
                        def semantic(db,scope,provider,query):
                            if len(query)>160:return [],{'status':'long_query'}
                            deadline=time.monotonic()+.35
                            vector=worker.request([query],'query',lambda:None)['vectors'][0]
                            if time.monotonic()>deadline:return [],{'status':'timeout'}
                            return vectors.search(scope,provider,space(catalog),vector,deadline)
                        start=time.perf_counter();view=Memory(core.db).view('personal','evaluation',True,question,source_semantic=semantic if worker else None)
                        elapsed=1000*(time.perf_counter()-start);top=view['facts'][:5]
                        answer_bearing=any(r['id']==expected and any(r['evidence']['start']<=a['answer_start'] and
                                           r['evidence']['end']>=a['answer_start']+len(a['text']) for a in reference['answers']) for r in top)
                        valid=all(original['context'][a['answer_start']:a['answer_start']+len(a['text'])]==a['text'] for a in reference['answers'])
                        result={'id':case['id'],'language':case['language'],'source_language':language,'source_at_5':any(r['id']==expected for r in top),
                                'answer_bearing_at_5':answer_bearing,'annotation_valid':valid,'elapsed_ms':elapsed,'retrieval':view['retrieval']}
                        rows.append(result)
                        (cached/(case['id']+'.input.json')).write_text(canonical({'question':question,'evidence':view['facts']}),encoding='utf-8')
                        (cached/(case['id']+'.reference.json')).write_text(canonical({'question':question,'answers':reference['answers'],'language':case['language']}),encoding='utf-8')
                        (target/'results.json').write_text(canonical(report|{'cases':rows,'builds':builds,'complete':len(rows)==len(cases)})+'\n',encoding='utf-8')
                        print(canonical({'completed':len(rows),'total':len(cases),'language':case['language'],'answer_bearing_at_5':answer_bearing}),flush=True)
                finally:core.close()
    finally:
        if worker:worker.close()
    print(canonical({'cases':len(rows),'source_at_5':sum(r['source_at_5'] for r in rows),'answer_bearing_at_5':sum(r['answer_bearing_at_5'] for r in rows)}))


if __name__=='__main__':main()
