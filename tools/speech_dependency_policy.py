"""One reviewed additive static policy; never accept a candidate-supplied checker."""
import hashlib
import json

BASE_SHA='13647ebcd902b9fa508870b88805b7f827bd5a57ca7e5047f4f39f55a79b38be'
DECLARATION={
    'schema':1,'runtime':'onnx-sensevoice-v1',
    'worker':'adapters/models/local_speech_worker.py',
    'support_workers':['adapters/models/speech_features.py'],
    'runtime_manifest':'modules/local_models/runtime.json',
    'dependencies':[
        {'import':'numpy','distribution':'numpy','version':'2.4.6'},
        {'import':'onnxruntime','distribution':'onnxruntime','version':'1.24.3'}],
    'scope':'CPU subprocess only; no Host imports, network, model-code or installation authority'}

HELPER='''def speech_permissions(scan_root, runtime, errors):
    """Exact optional STT import sites; metadata cannot add another permission."""
    path=scan_root/'modules/local_models/speech-runtime.json'
    if not path.exists():return {}
    expected=EXPECTED
    try:
        if path.stat().st_size>4096:raise ValueError('size')
        declared=json.loads(path.read_text(encoding='utf-8'))
        existing={x['import']:x for x in runtime['dependencies']}
        if not isinstance(declared,dict) or type(declared.get('schema')) is not int or declared!=expected or any(existing.get(x['import'])!=x for x in expected['dependencies']):raise ValueError('contract')
    except (OSError,ValueError,KeyError,TypeError):
        errors.append('Invalid optional speech-runtime dependency declaration');return {}
    return {expected['worker']:{'numpy','onnxruntime'},expected['support_workers'][0]:{'numpy'}}


'''.replace('EXPECTED',repr(DECLARATION))


def extend(raw):
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:
        raise ValueError('Speech admission requires the exact reviewed original checker')
    text=raw.decode('utf-8').replace('\r\n','\n')
    marker='def check(root=None, policy_root=None):\n'
    site="    accelerated = {'modules/context_knowledge/vectors.py': {'numpy'} & allowed}\n"
    condition='and not (relative == worker and top in allowed)'
    if any(text.count(x)!=1 for x in (marker,site,condition)):raise ValueError('Unknown checker layout')
    text=text.replace(marker,HELPER+marker)
    text=text.replace(site,site+'    speech = speech_permissions(scan_root,runtime,errors)\n')
    text=text.replace(condition,condition+' and not (top in speech.get(relative,set()))')
    return text.encode('utf-8')


def declaration():return (json.dumps(DECLARATION,indent=2)+'\n').encode()
