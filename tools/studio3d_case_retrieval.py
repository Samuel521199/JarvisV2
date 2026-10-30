"""Read asset-local advisory cases through the existing Studio3D store."""
import argparse,json
from pathlib import Path
from control.paths import child
from host.studio3d import enabled
from modules.context_knowledge.studio3d_experience import Studio3DExperience,ROOT

def retrieve(asset,query):
    enabled(ROOT/'user-data')
    store=Studio3DExperience(ROOT/'user-data')
    try:return store.retrieve_candidates(asset,query)
    finally:store.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--query',required=True);a=p.parse_args()
    path=child(a.asset_root.resolve(),a.query)
    if path.stat().st_size>16384:raise ValueError('Query budget')
    print(json.dumps(retrieve(a.asset_root,json.loads(path.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
