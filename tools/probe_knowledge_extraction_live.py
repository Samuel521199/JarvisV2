"""One real paid extraction over synthetic text, with isolated records and no retries."""
import argparse
import hashlib
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
from host import knowledge_extraction as extraction,memory
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.claims import Claims
from modules.preferences.store import Preferences,resolve
from sdk.protocol import canonical,decode
from sdk.pricing import estimate

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evidence/memory-continuity-1.0.0'
SOURCE=('以下均为虚构测试资料，不是用户的真实生活。\n'
        '测试项目 Orion 的会议暂定于 2030年5月6日在北楼举行，尚未确认。\n'
        '如果原型测试通过，才会采用接口 Beta；当前仍使用接口 Alpha。\n'
        '测试用户说：我没有去过北极。\n'
        '助手建议将日志保留七天，这只是建议，用户没有接受。')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,40}',args.run):parser.error('Invalid run')
    receipt=OUT/(args.run+'.json')
    if receipt.exists():raise SystemExit('A receipt already exists; do not silently repeat the paid request')
    if NetworkGate(ROOT/'user-data').read()['blocked']:raise SystemExit('Owner network gate closed')
    connection=sqlite3.connect('file:'+(ROOT/'user-data/config/settings.sqlite3').as_posix()+'?mode=ro',uri=True)
    try:catalog=json.loads(connection.execute('SELECT catalog FROM models WHERE id=1').fetchone()[0])
    finally:connection.close()
    provider='bailian';model='qwen3.8-flash';route=resolve(catalog,provider,model,'off')
    # Only credential resolution is rebound. The real extraction worker, native
    # transport, output validation, ledger and commit logic execute unchanged.
    vault=Credentials(ROOT/'user-data')
    if not vault.available(provider,route.get('credential_id')):raise SystemExit('Configured credential unavailable')
    config={'schema_version':1,'default_provider':provider,'automatic_fallback':False,'fallback_order':[provider],
            'providers':{provider:catalog['providers'][provider]}}
    report={'run':args.run,'state':'DISPATCHING','synthetic_only':True,'provider':provider,'model':model,
            'source_sha256':hashlib.sha256(SOURCE.encode()).hexdigest(),'credential_binding':'read-only existing provider vault; no secret copy',
            'created':time.time(),'official_quality_evaluation':False}
    write_json(receipt,report)
    with tempfile.TemporaryDirectory(prefix='jarvis-real-extract-') as folder:
        root=Path(folder);core=Core.initialize(root);prefs=Preferences(root);prefs.install(config,{});prefs.close()
        try:
            source=Knowledge(core.db).save(dict(id='',scope='personal',title='虚构条件与否定测试',text=SOURCE,providers=[provider],paused=False),0)
            NetworkGate(root).read();samples=[]
            with patch.object(extraction,'Credentials',lambda _:vault):
                extraction.command(root,dict(action='start',scope='personal',id=source['id'],revision=1,
                                             provider=provider,model=model,reasoning='off',request_id=args.run))
                future=extraction.ACTIVE[str(root)]
                while not future.done():
                    if NetworkGate(ROOT/'user-data').read()['blocked']:
                        extraction.command(root,dict(action='cancel',scope='personal',request_id=args.run))
                    started=time.perf_counter();memory.retrieve(root,'personal',provider,True,'当前接口')
                    samples.append((time.perf_counter()-started)*1000);time.sleep(.05)
                future.result()
            job=extraction.command(root,{'action':'status','scope':'personal'})['jobs'][0]
            claims=Claims(core.db).list('personal');call=core.db.one("SELECT * FROM model_calls WHERE phase='knowledge-extract'")
            report.update(state=job['state'],error=job['error'],added=job['added'],elapsed_seconds=time.time()-report['created'],
                          all_pending=all(c['state']=='pending' for c in claims),facts_promoted=len(memory.command(root,{'action':'list','scope':'personal'})['facts']),
                          exact_quotes=all(SOURCE[c['start']:c['end']]==c['quote'] for c in claims),
                          claims=[{k:c[k] for k in ('key','quote','start','end','state')} for c in claims],
                          foreground={'samples':len(samples),'max_ms':max(samples,default=0)},
                          model_call_status=call['status'] if call else None,raw_model_result_stored=bool(call and call['result']))
            if call:report['cost_estimate']=estimate(decode(call['billing_profile']),decode(call['usage']) if call['usage'] else {},call['created'])
            write_json(receipt,report)
        finally:extraction.close(root);core.close()
    print(canonical({k:v for k,v in report.items() if k not in {'claims','source_sha256'}}))
    return 0 if report['state']=='succeeded' and report['added']>0 and report['all_pending'] and report['exact_quotes'] and report['facts_promoted']==0 else 2


if __name__=='__main__':raise SystemExit(main())
