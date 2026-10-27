"""Freeze article-disjoint XQuAD development/holdout cases before inspecting scores.

Only JSON data are downloaded; no repository code is executed. The source dataset
is CC BY-SA 4.0; its URL, immutable revision and byte hashes accompany each split.
"""
import hashlib
import json
from pathlib import Path
import urllib.request
from sdk.protocol import canonical

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'user-data/evaluations/xquad'
OUT=ROOT/'docs/evidence/memory-continuity-1.0.0/multilingual'
REVISION='7d30520c717524000f0d9d2f9c10a069acd9d285'
LANGUAGES=('en','zh','es','de','ar','th')


def order(text):return hashlib.sha256(('jarvis-xquad-source-split-v1:'+text).encode()).hexdigest()


def load(language):return json.loads((CACHE/f'xquad.{language}.json').read_text(encoding='utf-8'))


def download(language):
    path=CACHE/f'xquad.{language}.json'
    url=f'https://raw.githubusercontent.com/google-deepmind/xquad/{REVISION}/xquad.{language}.json'
    if not path.exists():
        with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(4000001)
        if len(raw)>4000000:raise RuntimeError('Unexpected dataset size')
        value=json.loads(raw);assert isinstance(value['data'],list)
        path.write_bytes(raw)
    return {'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def main():
    CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen.json').exists():raise SystemExit('Frozen split already exists; it must not be replaced')
    files={lang:download(lang) for lang in LANGUAGES};english=load('en')['data']
    titles=sorted((x['title'] for x in english),key=order)
    groups={'development':titles[:len(titles)//2],'holdout':titles[len(titles)//2:]}
    cases={}
    for split,count in (('development',60),('holdout',30)):
        candidates=sorted(((q['id'],a['title'],i) for a in english if a['title'] in groups[split]
                           for i,p in enumerate(a['paragraphs']) for q in p['qas']),key=lambda r:order(r[0]))
        if len(candidates)<count:raise RuntimeError('Insufficient independent questions')
        cases[split]=[{'id':qid,'article':title,'paragraph':paragraph,'language':LANGUAGES[n%6],
                       'source_language':LANGUAGES[n%6] if (n//6)%2==0 else 'en'}
                      for n,(qid,title,paragraph) in enumerate(candidates[:count])]
    frozen={'schema':'jarvis.external-multilingual-probe.v1','dataset':'https://github.com/google-deepmind/xquad',
            'revision':REVISION,'license':'CC-BY-SA-4.0','files':files,'articles':groups,'cases':cases,
            'no_answer_cases':0,'source_split':'original article, including all translated parallels',
            'scope':'90 distinct original questions, six query languages; native and English-source retrieval; no official score',
            'acceptance_complete':False,'freeze_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'frozen.json').write_text(canonical(frozen)+'\n',encoding='utf-8')
    print(canonical({'articles':{k:len(v) for k,v in groups.items()},'cases':{k:len(v) for k,v in cases.items()},'languages':LANGUAGES,'source_disjoint':True}))


if __name__=='__main__':main()
