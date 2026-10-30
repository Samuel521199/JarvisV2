"""Explicit local multi-part reference assembly through the Jarvis Host."""
import argparse,json
from pathlib import Path
from host.studio3d_assembly import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,default=Path('user-data'));p.add_argument('--request',type=Path,required=True)
    a=p.parse_args();r=json.loads(a.request.read_text(encoding='utf-8'));result=run(a.data_root,r['contract'],r['sources'],r.get('reference'))
    print(json.dumps({k:result[k] for k in ('id','status','folder','elapsed_seconds','source_unchanged')},ensure_ascii=False))

if __name__=='__main__':main()
