"""Model-center configuration operations; model IDs are saved data, never defaults in code."""
from urllib.error import HTTPError,URLError
from adapters.models.eachlabs import api,slug
from control.credentials import Credentials
from control.network import NetworkGate
from control.recovery.gate import StopGate
from modules.preferences.store import Preferences,resolve
from modules.image_generation import profiles
from sdk.protocol import CoreError


def import_image(root,body):
    StopGate(root).require_running();NetworkGate(root).require_online()
    if not isinstance(body,dict) or set(body)!={'revision','provider','model','edit_model','planning_usd'}:
        raise CoreError('image_catalog','Invalid catalog import')
    store=Preferences(root)
    try:state=store.read();route=resolve(state['catalog'],body['provider'])
    finally:store.close()
    if route['adapter']!='eachlabs':raise CoreError('image_catalog','Select an Eachlabs connection')
    credential=Credentials(root).get(route['id'],route.get('credential_id'))
    try:
        meta=api('/v1/models/'+slug(body['model']),credential['api_key'],timeout=10)
        edit=api('/v1/models/'+slug(body['edit_model']),credential['api_key'],timeout=10) if body['edit_model'] else None
        profile=profiles.from_remote(meta,edit,body['planning_usd'])
    except HTTPError as exc:raise CoreError('image_catalog','Eachlabs metadata request failed (HTTP '+str(exc.code)+')') from None
    except (URLError,TimeoutError):raise CoreError('image_catalog','Eachlabs metadata is temporarily unavailable') from None
    except (ValueError,KeyError,TypeError):raise CoreError('image_catalog','Eachlabs metadata or mapping is unsupported') from None
    result=profiles.save(root,body['revision'],profile)
    return {'revision':result['revision'],'model':profile['model'],'configured':True}
