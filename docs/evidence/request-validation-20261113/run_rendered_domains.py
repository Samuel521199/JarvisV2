"""New live run with explicit source inputs and the shared document renderer.

The earlier failing run stays unchanged. No retries or production adoption.
Source declarations come from visible prompt lines, never hidden expected data.
"""
from pathlib import Path
import copy,json,re,sys,tempfile
from unittest.mock import patch
from run_domains import suite,ROOT
from adapters.development_bridge import exchange
from adapters.models.native import NativeModel
from control.network import NetworkGate
from control.recovery.gate import StopGate
from modules.dialogue.document_format import FORMAT
from sdk.protocol import CoreError
from tools.work_trials import bounded_route,run_suite


def main():
    output=Path(sys.argv[1]).resolve();dev=ROOT/'user-data'
    def checkpoint():
        StopGate(dev).require_running()
        if NetworkGate(dev).read()['blocked']:raise CoreError('network_disabled','Model network is paused')
    checkpoint();status=exchange(dev,'/status')
    if status['daily_call_limit']-status['calls_in_24h']<12:raise RuntimeError('Need twelve calls within existing allowance')
    tasks=suite();inputs={'schema':'jarvis.delivery-inputs.v1','cases':{}}
    for case in tasks['cases']:
        declarations=[]
        for index,turn in enumerate(case['turns']):
            rows=re.findall(r'^(F\d+|P\d+)：([^\n]+)$',turn['prompt'],flags=re.MULTILINE)
            declarations.append({'expected_revision':index,
                'facts':[text for key,text in rows if key.startswith('F')],
                'plans':[text for key,text in rows if key.startswith('P')]})
        inputs['cases'][case['id']]=declarations
    catalog=copy.deepcopy(exchange(dev,'/catalog')['catalog']);provider=catalog['default_provider']
    catalog['automatic_fallback']=False;catalog['fallback_order']=[provider]
    route=bounded_route(catalog,provider,reasoning='low',max_output_tokens=8192)
    def forbidden(*_):raise RuntimeError('Direct model credentials must not be read')
    def factory(cfg,_):return NativeModel(cfg,forbidden,dev/'temp')
    temporary_root=Path('E:/Jarvis/validation/model-domain-temp');temporary_root.mkdir(parents=True,exist_ok=True)
    original=tempfile.TemporaryDirectory
    def temporary(*args,**kwargs):kwargs.setdefault('dir',temporary_root);return original(*args,**kwargs)
    with patch('tools.work_trials.tempfile.TemporaryDirectory',temporary):
        result=run_suite(tasks,output,catalog,route,factory,execution='live',owner_checkpoint=checkpoint,
            basis_inputs=inputs,document_format=FORMAT)
    result['project_derived_not_independent_user_tasks']=True
    with (output/'summary.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'complete':result['comparison_complete'],'all_conditions_passed':result['all_candidate_conditions_passed'],
        'calls':result['costs']['attempts'],'tokens':result['costs']['total_tokens'],'quality_gain':result['quality_gain']}),flush=True)


if __name__=='__main__':main()
