"""Explicit read-only-request abandonment; never resend the lost model call."""
import argparse,hashlib,json,msvcrt,urllib.request
from pathlib import Path
from tools.studio3d_autopilot import ROOT,load,save,now
from modules.skills.studio3d.production_recovery import abandon_comparison
from modules.skills.studio3d.review_evidence import verify_manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--request-key',required=True);p.add_argument('--abandon-interrupted-comparison',action='store_true',required=True);a=p.parse_args()
    asset=a.asset_root.resolve()
    if not asset.is_relative_to(ROOT/'3DModels'):raise ValueError('Project asset required')
    origin='http://127.0.0.1:18282';folder=asset/'metadata/autopilot'
    def get(path):
        with urllib.request.urlopen(origin+path,timeout=20) as r:return json.load(r)
    instance=get('/api/instance')
    if instance.get('root_digest')!=hashlib.sha256(str((ROOT/'user-data').resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong data root')
    from control.local_access import install_client
    install_client(origin,ROOT/'user-data')
    with (folder/'run.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        state=load(folder/'state.json');row=state['calls'][a.request_key]
        chat=get('/api/chats/'+row['chat_id']);remote=next(t for t in chat['turns'] if t['id']==row['request_id'])
        for ident in (state['best_iteration'],state['pending_iteration']):verify_manifest(load(folder/ident/'evidence.json'))
        state=abandon_comparison(state,a.request_key,remote,now())
        save(folder/'interruption-disposition.json',{'instance':instance,'remote_turn':remote,'disposition':state['calls'][a.request_key]['recovery_disposition']})
        state['updated_at']=now();save(folder/'state.json',state)
        print(json.dumps({'status':state['status'],'retained':state['best_iteration'],'paid_replays':0}))

if __name__=='__main__':main()
