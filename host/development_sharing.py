"""Owner-controlled model proxy grants. No credentials or production memory are copied."""
import copy,shutil,uuid
from pathlib import Path
from control.atomic import write_json
from control.credentials import load_envelope
from control.development_profile import read as read_profile,write_secret,client_secret
from control.paths import child,reject_links
from control.recovery.gate import RunLock,StopGate
from host.development_bridge import Bridge
from modules.preferences.store import Preferences,resolve
from sdk.protocol import CoreError,read_json


def read(root):
    path=child(root,'config/development-sharing.json')
    value=read_json(path) if path.exists() else {'schema':1,'revision':0,'development_data':'','providers':[]}
    if value.get('schema')!=1:raise CoreError('development_profile_invalid','Unknown sharing settings')
    return value


def configure(root,body):
    StopGate(root).require_running()
    if not isinstance(body,dict) or set(body)!={'revision','settings_revision','development_data','providers'}:
        raise CoreError('settings_invalid','Invalid development sharing command')
    if not isinstance(body['providers'],list) or not 1<=len(body['providers'])<=16 or len(set(body['providers']))!=len(body['providers']):
        raise CoreError('settings_invalid','Choose explicit shared connections')
    development=Path(body['development_data']).resolve();reject_links(development);root=Path(root).resolve()
    if development==root or root in development.parents or development in root.parents:
        raise CoreError('settings_invalid','Daily and development data must be separate')
    with RunLock(root,'software-config'):
        current=read(root)
        if type(body['revision']) is not int or current['revision']!=body['revision']:raise CoreError('conflict','Sharing settings changed')
        store=Preferences(root)
        try:state=store.read()
        finally:store.close()
        if state['revision']!=body['settings_revision']:raise CoreError('conflict','Model settings changed')
        for name in body['providers']:
            if resolve(state['catalog'],name)['adapter']=='local':raise CoreError('settings_invalid','Only remote text connections can be shared')
        grant=load_envelope(child(root,'private/development-bridge.dpapi'));profile=read_profile(development)
        if (not profile or Path(profile.get('production_data','')).resolve()!=root or grant!=client_secret(development)
                or profile['client_id']!=grant['client_id'] or profile['allowed_providers']!=grant['allowed_providers']):
            raise CoreError('development_auth','Existing daily/development pairing must match')
        backup=child(root,'development/grant-changes/'+uuid.uuid4().hex);backup.mkdir(parents=True)
        for label,path in [('daily.dpapi',root/'private/development-bridge.dpapi'),('development.dpapi',development/'private/development-bridge.dpapi'),('profile.json',development/'config/development.json')]:
            shutil.copy2(path,backup/label)
        updated={**grant,'allowed_providers':body['providers']}
        projection=object.__new__(Bridge);projection.policy=updated;projection.catalog_loader=lambda:state
        projected=projection.catalog()
        # Changing the grant revokes the old proxy. In-flight unknown results are
        # never replayed; the reviewed frozen proxy is restarted separately.
        write_secret(root/'private/development-bridge.dpapi',updated)
        write_secret(development/'private/development-bridge.dpapi',updated)
        write_json(development/'config/development.json',{**profile,'allowed_providers':body['providers']})
        target=Preferences(development)
        try:
            from sdk.protocol import canonical
            target.db.execute('BEGIN IMMEDIATE')
            target.db.execute('UPDATE models SET revision=revision+1,catalog=?,coding=? WHERE id=1',
                (canonical(projected['catalog']),canonical(projected['coding'])))
            target.db.execute('COMMIT')
        except BaseException:target.db.execute('ROLLBACK');raise
        finally:target.close()
        value={'schema':1,'revision':current['revision']+1,'development_data':str(development),'providers':body['providers']}
        write_json(child(root,'config/development-sharing.json'),value)
    return {**value,'restart_required':True,'credentials_copied':False,'production_memory_copied':False}
