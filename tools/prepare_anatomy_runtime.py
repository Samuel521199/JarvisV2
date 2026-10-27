"""Explicit preparation of the optional, pinned Windows engineering runtime.

No invocation from chat or skill execution; no global interpreter changes.
Only hashed wheels from PyPI, no source builds or package install scripts.
"""
import argparse, hashlib, json, os, subprocess, sys, venv, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser();p.add_argument('--prepare', action='store_true');args=p.parse_args()
    if not args.prepare:raise SystemExit('Use --prepare to explicitly download and install the pinned optional runtime')
    if sys.platform != 'win32' or sys.version_info[:2] != (3,13):raise SystemExit('This reviewed lock targets Windows x64 CPython 3.13')
    lock=json.loads((ROOT/'modules/skills/anatomy/runtime-lock.json').read_text(encoding='utf-8'))
    folder=ROOT/'user-data/optional/anatomy';folder.mkdir(parents=True,exist_ok=True)
    requirements=folder/'requirements.txt';requirements.write_text('\n'.join(x['name']+'=='+x['version']+' --hash=sha256:'+x['sha256'] for x in lock['packages'])+'\n',encoding='utf-8')
    wheels=folder/'wheels';wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--no-deps','--require-hashes','--index-url','https://pypi.org/simple','--timeout','25','--retries','2','-r',str(requirements),'-d',str(wheels)],check=True)
    reviewed=[]
    for item in lock['packages']:
        wheel=wheels/item['filename']
        if hashlib.sha256(wheel.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Wheel hash mismatch')
        with zipfile.ZipFile(wheel) as z:
            executable_paths=[n for n in z.namelist() if n.endswith('.pth') or '.data/scripts/' in n]
            if executable_paths:raise SystemExit('Unreviewed installer path: '+str(executable_paths))
            licenses=[n for n in z.namelist() if 'license' in n.lower() or 'copying' in n.lower()]
        reviewed.append({**item,'bytes':wheel.stat().st_size,'license_files':licenses,'installer_hooks':[]})
    target=ROOT/'.venv/anatomy';python=target/'Scripts/python.exe'
    if not python.exists():venv.EnvBuilder(with_pip=True).create(target)
    subprocess.run([str(python),'-m','pip','install','--no-index','--find-links',str(wheels),'--no-deps','--require-hashes','-r',str(requirements)],check=True)
    subprocess.run([str(python),'-I','-c','import OCP, cantera, numpy; print("Optional CAD/chemistry imports ready")'],check=True)
    record={'status':'prepared','python':str(python),'lock_sha256':hashlib.sha256((ROOT/'modules/skills/anatomy/runtime-lock.json').read_bytes()).hexdigest(),'packages':reviewed,'limits':'Wheel provenance, hashes and installer paths checked. No antivirus or exhaustive native-code security audit claimed; native engine is trusted optional code, not an untrusted-code sandbox.'}
    (folder/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'prepared','packages':len(reviewed),'download_bytes':sum(x['bytes'] for x in reviewed)}))

if __name__=='__main__':main()
