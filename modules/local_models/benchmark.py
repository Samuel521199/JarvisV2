"""Small public synthetic retrieval regression, not a general intelligence exam."""
import math
import statistics
import time
from sdk.protocol import PROJECT, digest, read_json


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)]


def run(request, check):
    suite = read_json(PROJECT / 'modules/local_models/retrieval-suite.json')
    docs = suite['documents']; queries = suite['queries']; vectors = []
    for offset in range(0, len(docs), 4):
        check(); vectors.extend(request([d['text'] for d in docs[offset:offset + 4]], 'passage')['vectors'])
    cases = []; times = []
    # Document encoding warms the worker. Each query is timed through JSONL round trip.
    for query in queries:
        check(); start = time.perf_counter()
        vector = request([query['text']], 'query')['vectors'][0]
        times.append((time.perf_counter() - start) * 1000)
        order = sorted(range(len(docs)), key=lambda i: -sum(a * b for a, b in zip(vector, vectors[i])))
        rank = next(n + 1 for n, i in enumerate(order) if docs[i]['id'] == query['relevant'])
        cases.append({'id': query['id'], 'language': query['language'], 'rank': rank,
                      'top_document': docs[order[0]]['id'], 'expected_document': query['relevant'],
                      'query': query['text'], 'top_text': docs[order[0]]['text'],
                      'expected_text': next(d['text'] for d in docs if d['id']==query['relevant'])})
    return {'suite': suite['id'], 'suite_sha256': digest(suite), 'sample_count': len(cases), 'document_count': len(docs),
            'hit_at_1': sum(x['rank'] == 1 for x in cases) / len(cases),
            'mrr': statistics.mean(1 / x['rank'] for x in cases),
            'latency_ms': {'p50': statistics.median(times), 'p95': percentile(times, .95)},
            'workload': 'warm query batch=1; fixed synthetic suite; JSONL and measurement persistence included',
            'cases': cases, 'completed_at': time.time(),
            'limitations': 'Small public regression set, no held-out/domain accuracy or factual verification claim'}
