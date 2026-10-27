"""Explicit historical evidence; past versions never enter the default current view."""
import time
from sdk.protocol import CoreError, canonical, decode

FIELDS={'fact':('key','value','source'),'source':('title','text')}


def record(tx,kind,row,recorded=None):
    if row is None:return
    tx.execute('INSERT OR IGNORE INTO memory_history VALUES(?,?,?,?,?,?)',
               (kind,row['id'],row['revision'],row['scope'],canonical({k:row[k] for k in FIELDS[kind]}),recorded))


def changed(tx,kind,ident):
    table='facts' if kind=='fact' else 'knowledge_sources'
    record(tx,kind,tx.execute(f'SELECT * FROM {table} WHERE id=?',(ident,)).fetchone(),time.time())


def versions(db,scope,kind,ident):
    if kind not in FIELDS:raise CoreError('memory_invalid','Invalid history kind')
    table='facts' if kind=='fact' else 'knowledge_sources'
    predicate='deleted=0' if kind=='fact' else "status!='deleted'"
    if not db.one(f'SELECT 1 FROM {table} WHERE id=? AND scope=? AND {predicate}',(ident,scope)):
        raise CoreError('memory_missing','History unavailable after forgetting')
    result=db.all('SELECT revision,body,recorded FROM memory_history WHERE kind=? AND id=? AND scope=? ORDER BY revision DESC LIMIT 100',(kind,ident,scope))
    for row in result:row['body']=decode(row['body'])
    return {'kind':kind,'id':ident,'versions':result,'historical':True,'max_versions_per_page':100}
