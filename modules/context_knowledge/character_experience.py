"""A separate character method catalog and asset-scoped outcome store."""
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from modules.skills.studio3d.character_contract import FAMILY

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/'modules/skills/studio3d/character-methods.json'


def methods(family):
    if family!=FAMILY:
        raise ValueError('Character method catalog cannot serve another family')
    value=json.loads(CATALOG.read_text(encoding='utf-8'))
    if value['family']!=family or any(r['scope']!=family or not r['id'].startswith('character-') for r in value['methods']):
        raise ValueError('Character catalog scope mismatch')
    return value['methods']


def record(root, *, family, asset_id, iteration, evidence_sha256, reviews):
    methods(family)
    if not asset_id.startswith('character-') or len(evidence_sha256)!=64:
        raise ValueError('Character evidence identity required')
    payload={'family':family,'asset_id':asset_id,'iteration':iteration,'evidence_sha256':evidence_sha256,
             'reviews':reviews,'status':'ASSET_CANDIDATE','automatic_promotion':False,'user_accepted':False}
    body=json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False)
    key=asset_id+':'+iteration;sha=hashlib.sha256(body.encode()).hexdigest()
    path=Path(root)/'state/studio3d-character-experience.sqlite3'
    with closing(sqlite3.connect(path,timeout=5)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY,asset_id TEXT NOT NULL,sha256 TEXT NOT NULL,body TEXT NOT NULL)')
        prior=db.execute('SELECT sha256 FROM episodes WHERE id=?',(key,)).fetchone()
        if prior and prior[0]!=sha:raise ValueError('Character episode already has different evidence')
        db.execute('INSERT OR IGNORE INTO episodes VALUES(?,?,?,?)',(key,asset_id,sha,body))
    return payload


def get_episode(root, *, family, asset_id, iteration):
    """Read one explicitly selected asset candidate; never promote it implicitly."""
    methods(family)
    if not asset_id.startswith('character-') or not isinstance(iteration, str) or not iteration:
        raise ValueError('Character episode identity required')
    path=Path(root)/'state/studio3d-character-experience.sqlite3'
    if not path.is_file():
        raise FileNotFoundError('No character experience store')
    with closing(sqlite3.connect(path,timeout=5)) as db:
        row=db.execute('SELECT asset_id,sha256,body FROM episodes WHERE id=?',
                       (asset_id+':'+iteration,)).fetchone()
        audit=db.execute('SELECT id FROM episodes WHERE id=?',
                         (asset_id+':'+iteration+'-audit',)).fetchone()
    if row is None:
        raise KeyError('Character episode not found')
    if audit is not None:
        raise ValueError('Episode has an audit correction; choose the corrected case')
    stored_asset,stored_hash,body=row
    if hashlib.sha256(body.encode()).hexdigest()!=stored_hash:
        raise ValueError('Character episode content changed')
    value=json.loads(body)
    if (stored_asset!=asset_id or value.get('asset_id')!=asset_id or value.get('family')!=family
            or value.get('iteration')!=iteration or value.get('status')!='ASSET_CANDIDATE'
            or value.get('automatic_promotion') is not False):
        raise ValueError('Character episode scope or status mismatch')
    return value
