"""Isolated HTTP + native Blender test; does not restart the user's workbench."""
import argparse
import hashlib
import http.client
import json
import shutil
import tempfile
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from apps.workbench.server import Handler
from host.core import Core
from host import studio3d
from host.studio3d_learning import save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=Path('user-data'))
    parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='jarvis-learning-http-') as temp:
        root=Path(temp);Core.initialize(root).close()
        prepared=root/'optional/studio3d/prepared.json';prepared.parent.mkdir(parents=True)
        shutil.copyfile(args.data_root/'optional/studio3d/prepared.json',prepared)
        job=uuid.uuid4().hex;folder=root/'artifacts/studio3d'/job;folder.mkdir(parents=True)
        raw=(args.fixture/'source.glb').read_bytes();(folder/'model.glb').write_bytes(raw)
        # An explicitly synthetic delivered job exercises existing hash verification.
        receipt={'id':job,'files':{'model.glb':{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}}
        db=studio3d.db(root)
        try:db.execute('INSERT INTO jobs(id,signature,status,phase,created,receipt) VALUES(?,?,?,?,?,?)',(job,'fixture','DELIVERED','fixture',time.time(),json.dumps(receipt)))
        finally:db.close()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=root;server.nonce=uuid.uuid4().hex
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,body=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Origin':f'http://127.0.0.1:{server.server_port}','Content-Type':'application/json','X-Jarvis-Token':server.nonce}
            conn.request(method,path,json.dumps(body) if body is not None else None,headers)
            r=conn.getresponse();data=json.loads(r.read());conn.close()
            if r.status>=400:raise RuntimeError(str((r.status,data)))
            return data
        try:
            body={'id':uuid.uuid4().hex,'source_job':job,'contract':json.loads((args.fixture/'contract.json').read_text()),'repair':True,'render':True}
            accepted=request('POST','/api/studio3d/learning/run',body)
            deadline=time.monotonic()+40
            while True:
                state=request('GET','/api/studio3d/learning/runs/'+accepted['id'])
                if state['status'] not in ('QUEUED','RUNNING'):break
                if time.monotonic()>deadline:raise RuntimeError('HTTP observation timed out; not replayed')
                time.sleep(.2)
            same=request('POST','/api/studio3d/learning/run',body)
            feedback=request('POST','/api/studio3d/learning/feedback',{'event_id':'diagnostic-counterexample','run_id':accepted['id'],'method_id':'remove-rejected-family','reason':'Synthetic lifecycle test; does not assert a real fault in the successful coupon.'})
            planned=request('POST','/api/studio3d/learning/plan',body['contract'])
            passed=state['status']=='REPAIRED_DECLARED_CHECKS' and same['existing'] and same['id']==accepted['id'] and feedback['status']=='QUARANTINED' and 'remove-rejected-family' not in {m['id'] for m in planned['methods']}
            source=Path(state['folder']);dest=args.output/'artifacts';dest.mkdir()
            for p in source.iterdir():
                if p.is_file():shutil.copyfile(p,dest/p.name)
            save(args.output/'report.json',{'passed':passed,'scope':'isolated HTTP and native tool execution; synthetic fixture/counterexample, not formal art practice',
                'idempotent_same_id':same['id']==accepted['id'],'quarantine_blocks_next_retrieval':feedback['status']=='QUARANTINED',
                'result':state['status'],'adoptions':state['adoptions'],'cost':state['cost'],'artifacts':'artifacts','production_service_restarted':False})
            print(json.dumps({'passed':passed,'report':str(args.output/'report.json')}),flush=True)
            if not passed:raise RuntimeError('HTTP/native acceptance failed')
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':main()
