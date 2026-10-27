"""Actual Jarvis/Blender diagnostic acceptance, kept separate from art practice."""
import argparse
import hashlib
import json
import struct
import time
from pathlib import Path
from host.studio3d_learning import run, save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=Path('user-data'))
    parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--existing-model',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    report={'schema':1,'scope':'fixed-tool native diagnostics; not art-quality or learning-gain validation',
            'formal_practice_completed':0,'cases':[],'passed':False}
    for case in ('plate','flange','unresolved'):
        folder=args.fixtures/case;source=(folder/'source.glb').read_bytes()
        contract=json.loads((folder/'contract.json').read_text(encoding='utf-8'))
        receipt=run(args.data_root,source,contract,repair=True,render=True)
        expected='PARTIAL_REPAIR' if case=='unresolved' else 'REPAIRED_DECLARED_CHECKS'
        r=receipt['result'];case_pass=(receipt['status']==expected and len(r['actions'])==2 and
            all(r['actions'][i]['changed'] for i in range(2)) and
            len(r['render_before'])==len(r['render_after'])==5 and
            r['roundtrip']['contacts'][0]['sampled_surface_gap_m']<.002 and
            hashlib.sha256((folder/'source.glb').read_bytes()).hexdigest()==receipt['source_sha256'])
        report['cases'].append({'case':case,'passed':case_pass,'expected':expected,'status':receipt['status'],
            'before_issues':len(r['before']['issues']),'after_issues':len(r['roundtrip']['issues']),
            'receipt':str(Path(receipt['folder'])/'receipt.json'),'cost':receipt['cost']})
        save(args.output/(case+'-receipt.json'),receipt);save(args.output/'native-report.json',report)
        print(case,receipt['status'],case_pass,flush=True)
        if not case_pass: raise RuntimeError('Native diagnostic failed; evidence retained')
    if args.existing_model:
        raw=args.existing_model.read_bytes();size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size])
        parts=[];owners={}
        for node in doc['nodes']:
            if 'mesh' not in node: continue
            extra=node.get('extras',{});group=extra.get('game_group',node['name']);owners.setdefault(group,node['name'])
            parts.append({'id':node['name'],'node':node['name'],'motion_owner':owners[group],
                          'motion':{'fixed':'fixed','rotate':'rotating','translate':'translating'}.get(extra.get('game_role'),'coupled'),
                          'closed_surface':False})
        contract={'schema':'jarvis.studio3d.learning.v1','asset_id':'leFH18','family':'towed_artillery','parts':parts,
                  'symptoms':['too_many_parts','stale_preview'],'reference_policy':{'shield':'rearward_folded'}}
        save(args.output/'lefh18-inspection-contract.json',contract)
        receipt=run(args.data_root,raw,contract,repair=False,render=False)
        passed=receipt['status']=='INSPECTED' and receipt['result']['before']['passed'] and not receipt['adoptions'] and not receipt['result']['candidate_sha256']
        report['cases'].append({'case':'existing-leFH18-read-only','passed':passed,'scope':'declared inventory only; surface closure and motion not verified',
            'parts':len(receipt['result']['before']['parts']),'receipt':str(Path(receipt['folder'])/'receipt.json'),'cost':receipt['cost']})
        save(args.output/'lefh18-inspection-receipt.json',receipt)
    report['passed']=all(c['passed'] for c in report['cases'])
    report['recorded_native_wall_seconds']=sum(c['cost']['wall_seconds'] for c in report['cases'])
    report['api_usd']=0;report['total_usd']=None
    save(args.output/'native-report.json',report)
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'report':str(args.output/'native-report.json')}),flush=True)
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__':main()
