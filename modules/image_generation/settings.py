"""Durable image defaults, model policy and a per-request planning threshold."""
import math,re,sqlite3
from control.paths import child
from sdk.protocol import CoreError,canonical
from modules.image_generation.catalog import MODELS,validate
from modules.image_generation.design import RECIPES
import json

DEFAULT={'provider':'','model':'gemini-nano-banana-2.1','size':'1K','aspect_ratio':'1:1','preset':'free','enabled_models':list(MODELS),'max_estimate_usd':1.0}

def connection(root):
    d=sqlite3.connect(child(root,'config/image-settings.sqlite3'),isolation_level=None,timeout=5)
    d.execute('PRAGMA synchronous=FULL');d.execute('CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,value TEXT NOT NULL)')
    d.execute('INSERT OR IGNORE INTO settings VALUES(1,0,?)',(canonical(DEFAULT),));return d

def read(root):
    d=connection(root)
    try:r=d.execute('SELECT revision,value FROM settings WHERE id=1').fetchone();return {'revision':r[0],**json.loads(r[1])}
    finally:d.close()

def save(root,body):
    if not isinstance(body,dict) or set(body)!=set(DEFAULT)|{'revision'} or type(body['revision']) is not int:raise CoreError('image_settings_invalid','Unexpected image settings')
    v={k:body[k] for k in DEFAULT}
    if not isinstance(v['provider'],str) or not re.fullmatch('[A-Za-z0-9_-]{0,80}',v['provider']):raise CoreError('image_settings_invalid','Invalid connection ID')
    validate({k:v[k] for k in ('model','size','aspect_ratio')}|{'prompt':'settings'})
    if not isinstance(v['preset'],str) or v['preset'] not in RECIPES:raise CoreError('image_settings_invalid','Unknown design preset')
    if not isinstance(v['enabled_models'],list) or any(not isinstance(x,str) or x not in MODELS for x in v['enabled_models']) or len(set(v['enabled_models']))!=len(v['enabled_models']) or v['model'] not in v['enabled_models']:raise CoreError('image_settings_invalid','Default model must be enabled')
    n=v['max_estimate_usd']
    if type(n) not in (int,float) or not math.isfinite(n) or not .001<=n<=100:raise CoreError('image_settings_invalid','Planning threshold must be 0.001..100 USD')
    d=connection(root)
    try:
        if d.execute('UPDATE settings SET value=?,revision=revision+1 WHERE id=1 AND revision=?',(canonical(v),body['revision'])).rowcount!=1:raise CoreError('conflict','Image settings changed; reload')
    finally:d.close()
    return read(root)
