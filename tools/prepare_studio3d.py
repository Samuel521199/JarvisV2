"""Register an EXISTING Blender executable; never downloads/installs anything."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--data-root',default=str(ROOT/'user-data'));a=p.parse_args();exe=Path(a.blender).resolve()
    if not exe.is_file() or exe.name.lower() not in ('blender.exe','blender'):p.error('Choose installed Blender executable')
    r=subprocess.run([str(exe),'--version'],capture_output=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));version=r.stdout.decode(errors='replace').splitlines()[0]
    if r.returncode or not version.startswith('Blender '):p.error('Blender identity check failed')
    lock={'version':version,'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'runtime_sha256':hashlib.sha256((ROOT/'modules/skills/studio3d/runtime.json').read_bytes()).hexdigest(),'source':'https://www.blender.org/','license':'GPL-2.0-or-later','review_scope':'Existing local installation, version and SHA256 fixed; no download, addon or install script. This is not publisher-signature or vulnerability certification.'}
    folder=Path(a.data_root).resolve()/'optional/studio3d';folder.mkdir(parents=True,exist_ok=True);(folder/'prepared.json').write_text(json.dumps(lock,indent=2),encoding='utf-8');print(json.dumps({'prepared':True,'version':version,'sha256':lock['executable_sha256']}))
if __name__=='__main__':main()
