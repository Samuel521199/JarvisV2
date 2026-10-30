"""Explicit fixed high-surface preparation entry. Does not replace asset files."""
import argparse,json
from pathlib import Path
from host.studio3d_high_finish import run


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,default=Path('user-data'));p.add_argument('--source-job',required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--id');a=p.parse_args()
    result=run(a.data_root,a.source_job,json.loads(a.contract.read_text(encoding='utf-8')),ident=a.id)
    print(json.dumps({'id':result['id'],'status':result['status'],'elapsed_seconds':result.get('elapsed_seconds')},ensure_ascii=False))


if __name__=='__main__':main()
