"""Supplemental renders/crops through Jarvis's fixed, receipt-verified worker."""
import argparse,json,msvcrt,re
from pathlib import Path
from host.studio3d_high_finish import native_asset_operation


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,default=Path('user-data'));p.add_argument('--source-job',required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--id')
    p.add_argument('--asset-root',type=Path);p.add_argument('--source-operation',choices=('production','demonstration','surface_material','tyre_surface','attachment_seat','annular_detail','panel_corner','high_finish'),default='production');a=p.parse_args()
    def execute():return native_asset_operation(a.data_root,a.source_job,json.loads(a.contract.read_text(encoding='utf-8')),ident=a.id,operation='inspection',source_operation=a.source_operation)
    if a.asset_root:
        from tools.studio3d_autopilot import ROOT,load,save
        asset=a.asset_root.resolve();contract=a.contract.resolve()
        if not asset.is_relative_to(ROOT/'3DModels') or not contract.is_relative_to(asset) or a.data_root.resolve()!=ROOT/'user-data':raise ValueError('Asset-bound local source required')
        if not a.id or not re.fullmatch('[a-f0-9]{32}',a.id):raise ValueError('Explicit fresh native identity required')
        with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            registry=asset/'metadata/native-tool-runs.json';runs=load(registry);current=load(asset/'metadata/current-model.json')
            kind='preview' if a.source_operation=='production' else a.source_operation.replace('_','-')
            allowed={r['id'] for r in runs['runs'] if r['kind']==kind}
            if a.source_operation=='production':allowed.add(current['job_id'])
            if a.source_job not in allowed:raise ValueError('Source not registered with this asset')
            status=ROOT/'user-data/artifacts/studio3d-inspection'/a.id/'status.json'
            if any(r['id']==a.id for r in runs['runs']) or status.parent.exists():raise ValueError('Existing identity; inspect without replay')
            try:row=execute()
            finally:
                if status.exists():
                    runs['runs'].append({'id':a.id,'kind':'inspection','scope':'Read-only asset-bound native view and fixed-light inspection; not quality acceptance'})
                    save(registry,runs)
                    from tools.studio3d_trial_report import update
                    update(asset)
    else:row=execute()
    print(json.dumps({k:row.get(k) for k in ('id','status','elapsed_seconds','error')},ensure_ascii=False))


if __name__=='__main__':main()
