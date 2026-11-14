"""Immutable controller inventories and an atomic authoritative launcher pointer."""
import hashlib
from pathlib import Path,PurePosixPath
import re
import sqlite3
from control.application_runtime import LocalApprovals
from control.paths import reject_links
from sdk.controller_bootstrap import embedded,legacy
from sdk.protocol import CoreError,decode,read_json

PROTOCOL=2
FIELDS={'schema','controller_protocol','build','runtime_source_build','controller','controller_inventory_sha256',
    'data_root','port','generation','policy_anchor_build','policy_sha256','capsule_id','recovery_archive','recovery_sha256','launcher_backup','signature'}


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def relative(name):
    if not isinstance(name,str):raise CoreError('controller_integrity','Invalid controller member')
    path=PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or path.is_absolute() or path.as_posix()!=name
        or any(p in ('','..','.') for p in path.parts)):
        raise CoreError('controller_integrity','Unsafe controller member')
    return name


def inventory(root,record):
    root=Path(root).resolve();folder=Path(record['controller']).absolute();reject_links(folder)
    if folder.parent.resolve()!=root/'deployment/controllers':raise CoreError('controller_integrity','Controller outside installation')
    index=folder/'controller-files.json';reject_links(index)
    if sha(index)!=record['controller_inventory_sha256']:raise CoreError('controller_integrity','Controller inventory changed')
    files=read_json(index)
    if not isinstance(files,dict) or not 1<=len(files)<=12000:raise CoreError('controller_integrity','Invalid controller inventory')
    for name,value in files.items():
        relative(name)
        if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):raise CoreError('controller_integrity','Invalid file digest')
        path=folder/name;reject_links(path)
        if sha(path)!=value:raise CoreError('controller_integrity','Controller code changed: '+name)
    actual=set()
    for path in folder.rglob('*'):
        reject_links(path)
        if path.is_file():actual.add(path.relative_to(folder).as_posix())
    if actual!=set(files)|{'controller-files.json'}:raise CoreError('controller_integrity','Unmanifested controller files')
    return files


def verify(root,record,*,files=True):
    root=Path(root).resolve()
    if (not isinstance(record,dict) or type(record.get('schema')) is not int or record['schema'] not in (1,2)
        or not isinstance(record.get('controller'),str) or not isinstance(record.get('build'),str)
        or not re.fullmatch('[a-f0-9]{64}',record['build']) or not isinstance(record.get('data_root'),str) or type(record.get('port')) is not int
        or not 1024<=record['port']<=65535 or Path(record.get('data_root','')).resolve()!=root):
        raise CoreError('controller_record','Invalid controller binding')
    folder=Path(record['controller']).absolute()
    if folder.parent.resolve()!=root/'deployment/controllers':raise CoreError('controller_record','Controller outside installation')
    reject_links(folder if files else folder.parent)
    floor=root/'deployment/controller-protocol.json';reject_links(floor)
    minimum=0
    if floor.exists():
        value=read_json(floor)
        if (not isinstance(value,dict) or set(value)!={'schema','minimum'} or value.get('schema')!=1
            or any(type(v) is not int for v in value.values()) or value['minimum'] not in (1,PROTOCOL)):
            raise CoreError('controller_protocol','Unknown minimum controller protocol; preserve current state')
        minimum=value['minimum']
    if record['schema']==2:
        if set(record)!=FIELDS:raise CoreError('controller_record','Unknown controller record fields')
        if any(not isinstance(record[k],str) or not re.fullmatch('[a-f0-9]{64}',record[k]) for k in
               ('runtime_source_build','controller_inventory_sha256','policy_anchor_build','policy_sha256','recovery_sha256')):
            raise CoreError('controller_record','Invalid controller provenance digest')
        if not isinstance(record['capsule_id'],str) or not re.fullmatch('[a-f0-9]{32}',record['capsule_id']):
            raise CoreError('controller_record','Invalid controller capsule identity')
        for key in ('launcher_backup','recovery_archive'):
            if not isinstance(record[key],str) or not Path(record[key]).is_absolute() or not Path(record[key]).resolve().is_relative_to(root/'deployment/controller-changes'):
                raise CoreError('controller_record','Controller recovery path escaped its installation')
        if record['build']!=record['controller_inventory_sha256']:
            raise CoreError('controller_record','Controller identity differs from inventory')
        if (type(record.get('controller_protocol')) is not int or record['controller_protocol'] not in (1,PROTOCOL)
            or record['controller_protocol']<minimum):
            raise CoreError('controller_protocol','Unsupported controller protocol')
        if type(record.get('generation')) is not int or record['generation']<1:
            raise CoreError('controller_record','Invalid controller generation')
        LocalApprovals(root).verify({k:v for k,v in record.items() if k!='signature'},record.get('signature'))
        database=root/'deployment/control.sqlite3';reject_links(database)
        db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            row=db.execute('SELECT body FROM packages WHERE build=?',(record['runtime_source_build'],)).fetchone()
        finally:db.close()
        package=decode(row[0]) if row else {};proof=package.get('approval')
        if package.get('retired') or not proof or proof['receipt'].get('build')!=record['runtime_source_build'] or proof['receipt'].get('report',{}).get('passed') is not True:
            raise CoreError('controller_revoked','Controller source qualification is missing or withdrawn')
        LocalApprovals(root).verify(proof['receipt'],proof['mac'])
        report=proof['receipt']['report']
        if report.get('policy_sha256')!=record['policy_sha256'] or any(report.get(k) is not True for k in
            ['passed','reviewed_source','architecture_passed','tests_passed','runtime_intact']):
            raise CoreError('controller_revoked','Controller qualification no longer matches its pinned policy')
    elif floor.exists():
        raise CoreError('controller_protocol','Legacy pointer cannot replace a registered independent controller')
    if files:
        inventory(root,record)
        if record['schema']==2:
            marker=Path(record['controller'])/'config/controller-compatibility.json';reject_links(marker)
            value=read_json(marker)
            if value!={'schema':1,'controller_protocol':record['controller_protocol']} or any(type(v) is not int for v in value.values()):
                raise CoreError('controller_protocol','Controller contract declaration changed')
    return record


def read(root,*,files=True):
    root=Path(root).resolve();path=root.parent/'JarvisLaunch.py';reject_links(path)
    raw=path.read_bytes();record=embedded(raw)
    if record is None:
        record=read_json(root/'deployment/launcher.json')
        if raw!=legacy(record['build'],record['port'],record['controller_inventory_sha256']):
            raise CoreError('controller_bootstrap','Legacy launcher and controller registration differ')
    return verify(root,record,files=files)
