"""Asset-locked entry for the bounded material tool and subsequent high export.

Never starts a model call, edits another asset, or runs a low-poly operation.
The source must be a known receipt registered with this asset. Record a fresh
native identity before execution; a prior/unknown identity is not replayed.
"""
import argparse,json,msvcrt,re
from pathlib import Path
from host.studio3d_high_finish import native_asset_operation
from tools.studio3d_autopilot import ROOT,load,save

def main():
 p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True)
 p.add_argument('--source-job',required=True);p.add_argument('--source-operation',choices=('production','demonstration','surface_material','tyre_surface','attachment_seat','annular_detail','panel_corner'),required=True)
 p.add_argument('--operation',choices=('surface_material','tyre_surface','attachment_seat','annular_detail','panel_corner','high_finish'),required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--id',required=True)
 a=p.parse_args();asset=a.asset_root.resolve();contract=a.contract.resolve()
 if not asset.is_relative_to(ROOT/'3DModels') or not contract.is_relative_to(asset):raise ValueError('Asset-local contract required')
 if not re.fullmatch('[a-f0-9]{32}',a.id):raise ValueError('Invalid run identity')
 with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
  msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  registry=asset/'metadata/native-tool-runs.json';runs=load(registry);current=load(asset/'metadata/current-model.json')
  allowed={r['id'] for r in runs['runs'] if r['kind']==a.source_operation.replace('_','-')}
  if a.source_operation=='production':allowed.add(current['job_id'])
  if a.source_job not in allowed:raise ValueError('Source not bound to this asset')
  config=load(contract)
  if a.operation=='high_finish' and 'reuse' in config and config['reuse']['export_id'] not in {r['id'] for r in runs['runs'] if r['kind']=='high-finish'}:raise ValueError('Reuse export not registered with this asset')
  if any(r['id']==a.id for r in runs['runs']):raise ValueError('Already registered; inspect existing status without replay')
  path=ROOT/'user-data/artifacts'/('studio3d-'+a.operation.replace('_','-'))/a.id/'status.json'
  if path.parent.exists():raise ValueError('Native identity already exists; inspect without replay')
  try:
   result=native_asset_operation(ROOT/'user-data',a.source_job,load(contract),ident=a.id,operation=a.operation,source_operation=a.source_operation)
  finally:
   if path.exists():
    runs['runs'].append({'id':a.id,'kind':a.operation.replace('_','-'),'scope':'Explicit asset-bound material CLI; not user approval or independent learning'})
    save(registry,runs)
    from tools.studio3d_trial_report import update
    update(asset)
  print(json.dumps({k:result.get(k) for k in ('id','status','elapsed_seconds')}))

if __name__=='__main__':main()
