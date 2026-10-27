"""Reproducible external QA probe. Test data and API answers never enter user memory.

This is a subset probe, not an official LongMemEval score or a substitute for the
source-disjoint multilingual acceptance dataset in config/memory-evaluation.json.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import tempfile
import time
import urllib.request
from host.core import Core
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.memory import Memory
from sdk.protocol import canonical

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'user-data/evaluations/longmemeval'
REVISION='98d7416c24c778c2fee6e6f3006e7a073259d48f'
SHA='d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442'
SIZE=277383467
URL=f'https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/{REVISION}/longmemeval_s_cleaned.json'
OUT=ROOT/'docs/evidence/memory-continuity-1.0.0/quality'


def download():
    CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/'longmemeval_s_cleaned.json'
    if path.exists():
        if hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=SHA:raise RuntimeError('Cached dataset checksum mismatch; original file preserved')
        return path
    partial=CACHE/'longmemeval_s_cleaned.part';written=0;sha=hashlib.sha256();last=0
    with urllib.request.urlopen(URL,timeout=30) as response,partial.open('wb') as target:
        while chunk:=response.read(1024*1024):
            written+=len(chunk)
            if written>SIZE:raise RuntimeError('Dataset exceeded pinned size')
            sha.update(chunk);target.write(chunk)
            if written-last>16*1024*1024:print(f'dataset {written}/{SIZE}',flush=True);last=written
    if written!=SIZE or sha.hexdigest()!=SHA:raise RuntimeError('Dataset did not match pinned release')
    partial.replace(path);return path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--limit',type=int,default=30)
    parser.add_argument('--variant',default='baseline')
    args=parser.parse_args();path=download() if args.download else CACHE/'longmemeval_s_cleaned.json'
    if not re.fullmatch('[a-z0-9-]{1,40}',args.variant):parser.error('Invalid variant')
    output=OUT if args.variant=='baseline' else OUT/args.variant
    inputs=CACHE if args.variant=='baseline' else CACHE/args.variant
    output.mkdir(parents=True,exist_ok=True);inputs.mkdir(parents=True,exist_ok=True)
    if not 1<=args.limit<=500:parser.error('limit 1..500')
    if hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=SHA:raise RuntimeError('Dataset checksum mismatch')
    rows=json.loads(path.read_text(encoding='utf-8'))
    # Freeze case order before any retrieval outputs are inspected.
    rows=sorted(rows,key=lambda r:hashlib.sha256(('jarvis-external-probe-v1:'+r['question_id']).encode()).hexdigest())[:args.limit]
    OUT.mkdir(parents=True,exist_ok=True)
    frozen={'dataset':URL,'sha256':SHA,'license':'MIT','language':'en','subset':[r['question_id'] for r in rows],
            'kind':'external_lexical_probe','official_score':False,'acceptance_holdout':False,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest=output/'frozen.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))['subset']!=frozen['subset']:raise RuntimeError('Frozen subset cannot be silently replaced')
    if manifest.exists():raise RuntimeError('Use a fresh variant to preserve prior evidence')
    frozen['runtime_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (ROOT/'modules/context_knowledge').glob('*.py')}
    manifest.write_text(json.dumps(frozen,indent=2)+'\n',encoding='utf-8')
    report=[]
    for i,case in enumerate(rows):
        if not re.fullmatch('[a-zA-Z0-9_-]{1,100}',case['question_id']):raise RuntimeError('Unsafe case identifier')
        with tempfile.TemporaryDirectory(prefix='jarvis-memory-quality-') as folder:
            core=Core.initialize(Path(folder))
            try:
                library=Knowledge(core.db);identities={};unsupported=[]
                for ident,date,session in zip(case['haystack_session_ids'],case['haystack_dates'],case['haystack_sessions']):
                    # Keep user/assistant attribution. Benchmark answer markers are labels,
                    # never source content or text shown to the model/retriever.
                    text='\n'.join(f"{turn['role']}: {turn['content']}" for turn in session)
                    if len(text.encode())>80000:unsupported.append({'session':ident,'reason':'source_size'});continue
                    if len(identities)>=200:unsupported.append({'session':ident,'reason':'source_capacity'});continue
                    source=library.save({'id':'','scope':'personal','title':str(date)+' · conversation '+str(ident),'text':text,'providers':['evaluation'],'paused':False},0)
                    identities[source['id']]=ident
                library.rebuild();started=time.perf_counter();view=Memory(core.db).view('personal','evaluation',True,case['question'])
                elapsed=1000*(time.perf_counter()-started);selected=[identities[r['id']] for r in view['facts'][:5]]
                expected=case['answer_session_ids'];retrieved=set(selected)
                record={'id':case['question_id'],'type':case['question_type'],'expected_sessions':expected,'retrieved_sessions':selected,
                        'all_evidence_at_5':set(expected)<=retrieved,'any_evidence_at_5':bool(set(expected)&retrieved),
                        'elapsed_ms':elapsed,'unsupported':unsupported,'answer_evaluated':False}
                report.append(record)
                # Separate input from reference labels so later answer generators cannot
                # accidentally receive the answer or gold session list.
                (inputs/(case['question_id']+'.input.json')).write_text(canonical({'question':case['question'],'question_date':case.get('question_date'),
                     'evidence':view['facts']}),encoding='utf-8')
                (inputs/(case['question_id']+'.reference.json')).write_text(canonical({'question':case['question'],'answer':case['answer'],'type':case['question_type']}),encoding='utf-8')
            finally:core.close()
        (output/'lexical-results.json').write_text(json.dumps({'frozen':frozen,'cases':report,'complete':i+1==len(rows)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'completed':i+1,'total':len(rows),'id':record['id'],'all_evidence_at_5':record['all_evidence_at_5'],'unsupported':len(unsupported)},ensure_ascii=False),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
