"""Optional native view of the same workbench. No models, tasks or mailbox core."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.paths import child, data_root, reject_links
from control.local_access import read_key


def prepared(root):
    folder=child(root,'optional/desktop-presence');record=json.loads((folder/'prepared.json').read_text(encoding='utf-8'))
    if record.get('schema')!=1 or record.get('protocol')!=2:raise ValueError('Unsupported presence bridge; prepare the two-window shell again')
    binary=(folder/record['file']).resolve();binary.relative_to(folder.resolve());reject_links(binary)
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=record['sha256']:
        raise ValueError('Native companion changed; prepare the reviewed build again')
    return binary


def start(root,port,*,detach=True):
    root=data_root(root);binary=prepared(root)
    from apps.workbench.launch import running
    if not running(port,root):raise RuntimeError('Start the matching Jarvis Host first')
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        connection.request('GET','/api/instance');response=connection.getresponse();metadata=json.loads(response.read(16384))
        if response.status!=200 or metadata.get('presence_protocol')!=2:raise RuntimeError('Update the shared Host before opening the two-window companion')
    finally:connection.close()
    if detach:
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        log=child(root,'logs/desktop-presence.log');log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('ab') as error:
            subprocess.Popen([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--data-root',str(root),
                '--port',str(port),'--attached'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=error,creationflags=flags)
        return
    # Access key travels over inherited stdin, never command arguments or logs.
    profile=child(root,'optional/desktop-presence/webview');profile.mkdir(parents=True,exist_ok=True);reject_links(profile)
    payload=json.dumps({'protocol':2,'data_root':str(root),'origin':f'http://127.0.0.1:{port}/','access':read_key(root)}).encode()
    with subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
            stderr=sys.stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) as process:
        process.communicate(payload)
        if process.returncode:raise RuntimeError('Native companion exited unexpectedly')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=18282);parser.add_argument('--attached',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Invalid local port')
    start(args.data_root,args.port,detach=not args.attached)
