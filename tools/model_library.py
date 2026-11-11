"""Search, inspect, verify and explicitly register local reusable models."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT)]
from modules.skills.model_library.store import Library,digest

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['search','show','verify','register']);p.add_argument('asset',nargs='?');p.add_argument('--query',default='');p.add_argument('--category',default='');p.add_argument('--kind',default='');p.add_argument('--manifest',type=Path);p.add_argument('--data-root',type=Path,default=ROOT/'user-data');a=p.parse_args()
 with Library(a.data_root) as lib:
  if a.action=='search':out=lib.catalogue(a.query,a.category,a.kind)
  elif a.action=='show':
   out=lib.detail(a.asset)
   for f in out['files']:f['local_file']=str(lib.object_path(f))
  elif a.action=='verify':
   rows=lib.db.execute('SELECT asset_id,id FROM files').fetchall();checked=set()
   for r in rows:
    f=lib.file(r['asset_id'],r['id']);path=lib.object_path(f)
    if f['sha256'] not in checked:
     if digest(path)!=f['sha256']:raise ValueError('Stored model changed: '+f['name'])
     checked.add(f['sha256'])
   out={'registered_files':len(rows),'verified_unique_objects':len(checked),'passed':True}
  else:
   if not a.manifest:raise ValueError('Explicit manifest required')
   m=json.loads(a.manifest.read_text(encoding='utf-8'));ident=lib.put_asset(m['asset'])
   for f in m['files']:
    source=(a.manifest.parent/f['path']).resolve();file_id=lib.add_file(ident,source,f['role'],f.get('sha256'))
    if f.get('variant'):lib.add_variant(ident,f['variant'],file_id,f['label'],f['role'])
   for case in m.get('methods',[]):lib.add_case(ident,case)
   out=lib.detail(ident)
  print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
