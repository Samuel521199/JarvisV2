"""Data-only public manifests. No weight or executable is committed to Git."""
import re
from sdk.protocol import CoreError, PROJECT, read_json, digest

KINDS = {'embedding', 'llm', 'stt', 'tts', 'vad', 'speaker', 'reranker', 'vision'}


def validate(item):
    required = {'id', 'kind', 'title', 'source', 'revision', 'license', 'languages', 'dimension',
                'dimensions', 'max_tokens', 'runtime', 'files', 'recipe'}
    if not isinstance(item, dict) or set(item) != required:
        raise CoreError('model_manifest', 'Unexpected manifest fields')
    if (not isinstance(item['id'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', item['id'])
        or not isinstance(item['kind'],str) or item['kind'] not in KINDS
        or item['id'].upper() in {'CON','PRN','AUX','NUL',*[f'{x}{n}' for x in ('COM','LPT') for n in range(1,10)]}):
        raise CoreError('model_manifest', 'Invalid model identity')
    if not isinstance(item['source'],str) or not re.fullmatch(r'https://huggingface.co/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', item['source']):
        raise CoreError('model_manifest', 'Expected an upstream model page')
    if not all(isinstance(item[k], str) and 0 < len(item[k]) <= 256 for k in ('title','revision','license','runtime','recipe')):
        raise CoreError('model_manifest', 'Invalid metadata')
    if not isinstance(item['languages'], list) or not 1 <= len(item['languages']) <= 128 or any(not isinstance(x,str) or len(x)>40 for x in item['languages']):
        raise CoreError('model_manifest', 'Declare language coverage')
    if type(item['dimension']) is not int or not 0 <= item['dimension'] <= 8192 or type(item['max_tokens']) is not int or not 0 <= item['max_tokens'] <= 131072:
        raise CoreError('model_manifest', 'Invalid dimension or context')
    if not isinstance(item['dimensions'],list) or any(type(x) is not int or not 1<=x<=item['dimension'] for x in item['dimensions']):
        raise CoreError('model_manifest', 'Invalid supported dimensions')
    if item['kind']=='embedding' and (not item['dimension'] or item['dimension'] not in item['dimensions']):
        raise CoreError('model_manifest', 'Embedding dimension required')
    if not isinstance(item['files'],list) or len(item['files'])>20:
        raise CoreError('model_manifest', 'Invalid artifacts')
    names=set()
    for f in item['files']:
        if (not isinstance(f,dict) or set(f)!={'name','path','bytes','sha256'}
            or not isinstance(f['name'],str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}', f['name']) or f['name'].endswith('.') or f['name'].lower().endswith('.part') or f['name'].lower() in names
            or f['name'].split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'{x}{n}' for x in ('COM','LPT') for n in range(1,10)]}
            or not isinstance(f['path'],str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', f['path']) or any(x in ('','..','.') for x in f['path'].split('/'))
            or type(f['bytes']) is not int or not 0<f['bytes']<=20*1024**3
            or not isinstance(f['sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',f['sha256']) or not re.fullmatch(r'[a-f0-9]{40}',item['revision'])):
            raise CoreError('model_manifest', 'Artifacts need fixed revision, size and SHA-256')
        names.add(f['name'].lower())
    if item['runtime']=='onnx-e5-v1' and (item['kind']!='embedding' or item['dimension']!=384 or item['dimensions']!=[384] or {f['name'] for f in item['files']}!={'model.onnx','tokenizer.json'} or item['max_tokens']!=512 or item['recipe']!='e5-prefix-mean-l2-v1'):
        raise CoreError('model_manifest', 'E5 adapter contract mismatch')
    return item


def builtin():
    return [validate(x) for x in read_json(PROJECT/'modules/local_models/catalog.json')['models']]


def space(item):
    # Precision, tokenizer, pooling and prefix all belong to the vector space.
    return digest({k:item[k] for k in ('source','revision','files','dimension','recipe')})
