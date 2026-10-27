"""Two bounded real model calls over synthetic household data; no retries."""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from unittest.mock import patch

from control.atomic import write_json
from control.credentials import Credentials
from control.network import NetworkGate
from host.core import Core
from host import family
from modules.context_knowledge.private_memory import PrivateMemory
from modules.preferences.store import Preferences, resolve
from sdk.pricing import estimate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,40}',args.run):parser.error('Invalid run identifier')
    receipt=ROOT/'docs/evidence/family-private-1.0.0'/(args.run+'.json')
    if receipt.exists():raise SystemExit('Receipt already exists; requests are not automatically repeated')
    if NetworkGate(ROOT/'user-data').read()['blocked']:raise SystemExit('Owner network gate is closed')
    db=sqlite3.connect('file:'+(ROOT/'user-data/config/settings.sqlite3').as_posix()+'?mode=ro',uri=True)
    try:catalog=json.loads(db.execute('SELECT catalog FROM models WHERE id=1').fetchone()[0])
    finally:db.close()
    provider='bailian';model='qwen3.8-flash';route=resolve(catalog,provider,model,'default')
    vault=Credentials(ROOT/'user-data')
    if not vault.available(provider,route.get('credential_id')):raise SystemExit('Configured credential unavailable')
    report={'run':args.run,'state':'DISPATCHING','synthetic_only':True,'provider':provider,'model':model,'created':time.time(),
            'credential_binding':'existing vault, read-only resolution; no credential copy','calls':[],'retried':False,'formal_quality_gate':False}
    write_json(receipt,report)
    with tempfile.TemporaryDirectory(prefix='jarvis-private-live-') as folder:
        root=Path(folder);Core.initialize(root).close();prefs=Preferences(root)
        prefs.install({'schema_version':1,'default_provider':provider,'automatic_fallback':False,'fallback_order':[provider],
                       'providers':{provider:catalog['providers'][provider]}},{})
        prefs.close();host=family.FamilyHost(root);memory=PrivateMemory(root)
        try:
            token=host.identity.setup('synthetic-only-password-2026');owner=host.identity.principal(token)
            for ident in ('alice','bob'):host.identity.manage(owner,{'id':ident,'name':ident,'active':True,'password':'synthetic-only-password-2026'})
            tokens={x:host.identity.login(x,'synthetic-only-password-2026') for x in ('alice','bob')}
            actors={x:host.identity.principal(tokens[x]) for x in tokens}
            note=memory.save(actors['alice'],{'id':'','revision':0,'title':'虚构实验代号','text':'本段全部是合成测试资料。Alice 的虚构实验代号是“月桂7263”。','shared':[],'providers':[provider]},host.identity.members())
            with patch.object(family,'Credentials',lambda _:vault):
                for ident,prompt,notes in [('alice','根据附入资料，只回答我的虚构实验代号。',[note['id']]),
                                           ('bob','你知道 Alice 的虚构实验代号吗？没有当前可见资料就只回答“不知道”，不要猜测。',[])]:
                    chat=memory.create_chat(actors[ident],'synthetic '+ident);started=time.time()
                    host.command(actors[ident],tokens[ident],{'action':'chat_send','id':chat['id'],'text':prompt,'notes':notes,
                                                           'provider':provider,'model':model,'request_id':args.run+'-'+ident})
                    samples=[]
                    while True:
                        if NetworkGate(ROOT/'user-data').read()['blocked']:
                            host.command(actors[ident],tokens[ident],{'action':'chat_cancel','id':chat['id'],'request_id':args.run+'-'+ident})
                        tick=time.perf_counter();memory.list(owner);samples.append((time.perf_counter()-tick)*1000)
                        turn=memory.read(owner,chat['id'])['turns'][-1]
                        if turn['status']!='RUNNING':break
                        if time.time()-started>75:raise RuntimeError('Private worker did not finish within its deadline')
                        time.sleep(.05)
                    report['calls'].append({'actor':ident,'status':turn['status'],'error':turn['error'],'reply':turn['reply'],
                                            'usage':turn.get('usage',{}),'elapsed_seconds':time.time()-started,
                                            'foreground_samples':len(samples),'foreground_max_ms':max(samples),
                                            'cost_estimate':estimate(route.get('billing_profile'),turn.get('usage',{}),started)})
                    write_json(receipt,report)
            report['own_recall_passed']=report['calls'][0]['status']=='SUCCEEDED' and '月桂7263' in report['calls'][0]['reply']
            report['other_member_no_leak']=report['calls'][1]['status']=='SUCCEEDED' and '不知道' in report['calls'][1]['reply'] and '月桂7263' not in report['calls'][1]['reply']
            report['state']='completed';report['completed']=time.time()
            write_json(receipt,report)
        finally:host.close();memory.close()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['own_recall_passed'] and report['other_member_no_leak'] else 2


if __name__=='__main__':raise SystemExit(main())
