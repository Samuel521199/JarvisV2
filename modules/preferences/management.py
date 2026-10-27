"""Revisioned catalog edits. Vault writes are supplied by the host control boundary."""
from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid
from modules.preferences.store import validate_catalog, validate_coding, resolve, ADAPTERS
from sdk.pricing import validate_price
from sdk.protocol import CoreError, canonical, decode


def text(value, limit=80):
    if not isinstance(value,str) or not value.strip() or len(value)>limit: raise CoreError('settings_invalid','Invalid text')
    return value.strip()


def manage(store, value, vault=None):
    fields={
        'connection': {'connection','label','enabled','default'},
        'add_connection': {'adapter','label','model','base_url','region'},
        'model': {'connection','model','label','enabled','default','parameters','reasoning_levels','price'},
        'key': {'connection','key_id','enabled','active'},
        'add_key': {'connection','label','secret','replace_key'},
        'coding': {'enabled','model','reasoning'},
        'routing': {'enabled','routes'},
    }
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!=(fields[value['action']]|{'action','revision'}):
        raise CoreError('settings_invalid','Unexpected management command')
    if type(value['revision']) is not int: raise CoreError('settings_invalid','Invalid revision')
    store.db.execute('BEGIN IMMEDIATE')
    try:
        current=store.read()
        if not current or current['revision']!=value['revision']: raise CoreError('conflict','Settings changed')
        config=current['catalog'];coding=current['coding'];action=value['action'];item=None
        if 'connection' in value:
            item=config['providers'].get(value['connection'])
            if item is None: raise CoreError('settings_invalid','Provider not found')
        for key in {'enabled','default','active'} & set(value):
            if type(value[key]) is not bool: raise CoreError('settings_invalid','Expected boolean')
        pending_credential=None
        if action=='routing':
            routes=value['routes']
            if not isinstance(routes,list) or not 1<=len(routes)<=8:raise CoreError('settings_invalid','Choose one to eight routes')
            order=[]
            for r in routes:
                if not isinstance(r,dict) or set(r)!={'connection','model','reasoning'} or r['connection'] in order:raise CoreError('settings_invalid','Invalid route')
                selected=resolve(config,r['connection'],r['model'],r['reasoning']);order.append(selected['id'])
                provider=config['providers'][selected['id']];provider['model']=selected['model'];provider['models'][selected['model']]['parameters']=selected['parameters']
            config['default_provider']=order[0];config['fallback_order']=order;config['automatic_fallback']=value['enabled']
        elif action=='connection':
            item.update(label=text(value['label']),enabled=value['enabled'])
            if value['default']: config['default_provider']=value['connection']
        elif action=='add_connection':
            adapter=value['adapter']
            if adapter not in ADAPTERS-{'local'}: raise CoreError('settings_invalid','Unsupported adapter')
            ident=adapter+'-'+uuid.uuid4().hex[:10];model=text(value['model'],100)
            item={'adapter':adapter,'label':text(value['label']),'enabled':True,'model':model,'models':{model:{'label':model,'parameters':{'max_output_tokens':4096},'reasoning_levels':[],'enabled':True,'price':None}},'keys':{}}
            if adapter=='vertex':item['location']='global'
            if adapter=='bailian':item['region']=value['region']
            if adapter=='compatible':item['base_url']=value['base_url']
            config['providers'][ident]=item
        elif action=='model':
            mid=text(value['model'],100);old=item['models'].get(mid,{})
            profile={**old,'label':text(value['label']),'enabled':value['enabled'],'parameters':value['parameters'],'reasoning_levels':value['reasoning_levels'],'price':validate_price(value['price'])}
            item['models'][mid]=profile
            if value['default']:item['model']=mid
        elif action=='coding':
            coding={'revision':coding.get('revision',0)+1,'enabled':value['enabled'],'model':text(value['model'],100),'reasoning':value['reasoning']};validate_coding(coding)
        elif action=='key':
            key=item.get('keys',{}).get(value['key_id'])
            if key is None:raise CoreError('credential_missing','Unknown credential')
            if not value['enabled'] and item.get('credential_id')==value['key_id']:raise CoreError('settings_invalid','Switch the active key before disabling it')
            key['enabled']=value['enabled']
            if value['active']:
                if not key['enabled']:raise CoreError('settings_invalid','Disabled key')
                item['credential_id']=value['key_id']
        elif action=='add_key':
            if vault is None:raise CoreError('vault_unavailable','Missing credential adapter')
            raw=text(value['secret'],20000);adapter=item.get('adapter',value['connection'])
            if adapter=='local':raise CoreError('settings_invalid','Local runtime has no key')
            if adapter=='vertex':
                credential=decode(raw)
                if not isinstance(credential,dict):raise CoreError('credential_invalid','Expected JSON object')
                if credential.get('type')!='service_account' or not all(isinstance(credential.get(k),str) and credential[k] for k in ['project_id','private_key','client_email']):raise CoreError('credential_invalid','Expected service account JSON')
                credential={'service_account':credential}
            else:credential={'api_key':raw}
            old=value['replace_key'];keys=item.setdefault('keys',{})
            if old and old not in keys:raise CoreError('credential_missing','Unknown replaced key')
            key_id='key-'+uuid.uuid4().hex
            keys[key_id]={'label':text(value['label']),'enabled':True,'masked':'••••••••','created_at':datetime.now(timezone.utc).isoformat()}
            if old:keys[old]['enabled']=False
            item['credential_id']=key_id;pending_credential=(value['connection'],key_id,credential)
        validate_catalog(config)
        if action=='model' and value['enabled']:
            parameters=value['parameters']; levels=value['reasoning_levels']
            explicit=parameters.get('reasoning_effort',parameters.get('thinking_level'))
            if explicit is not None and str(explicit).lower() not in levels:
                raise CoreError('settings_invalid','Default reasoning must be in the supported levels')
        # Encrypt first. A failed DB commit can leave an unused encrypted record, not an active plaintext credential.
        if pending_credential:vault.put(*pending_credential)
        store.db.execute('UPDATE models SET revision=revision+1,catalog=?,coding=? WHERE id=1',(canonical(config),canonical(coding)))
        store.db.execute('COMMIT')
    except BaseException:store.db.execute('ROLLBACK');raise
    return store.read()
