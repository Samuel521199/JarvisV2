"""Owned conversation folders and disposable projections; no execution authority."""
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading

from control.paths import child, reject_links
from sdk.protocol import CoreError, canonical, decode

LOCK = threading.RLock()


def component(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',value):
        raise CoreError('unsafe_path','Invalid conversation or result identifier')
    return value


def atomic(path, raw):
    reject_links(path)
    fd, temporary = tempfile.mkstemp(prefix='.jarvis-save-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as file: file.write(raw); file.flush(); os.fsync(file.fileno())
        reject_links(path); os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def configuration(value):
    fields={'text','requirements','skill','enabled','attachments','memory','selection','reasoning','mode'}
    if not isinstance(value,dict) or set(value)-fields: raise CoreError('session_config_invalid','Unknown session configuration')
    for key,limit in {'text':12000,'requirements':2000,'skill':100,'reasoning':30,'mode':20}.items():
        if key in value and (not isinstance(value[key],str) or len(value[key])>limit): raise CoreError('session_config_invalid','Invalid session text')
    for key in ('enabled','memory'):
        if key in value and type(value[key]) is not bool: raise CoreError('session_config_invalid','Expected boolean')
    selection=value.get('selection')
    if selection is not None and (not isinstance(selection,dict) or set(selection)!={'provider','model'} or any(not isinstance(v,str) or len(v)>200 for v in selection.values())):
        raise CoreError('session_config_invalid','Only model identifiers belong in the session')
    attachments=value.get('attachments',[])
    if (not isinstance(attachments,list) or len(attachments)>4 or any(not isinstance(a,dict) or set(a)!={'name','text'}
        or not all(isinstance(v,str) for v in a.values()) or len(a['name'])>160 for a in attachments)
        or sum(len(a['text']) for a in attachments)>12000): raise CoreError('session_config_invalid','Attachment limit exceeded')
    if len(canonical(value).encode())>120000: raise CoreError('session_config_invalid','Session configuration is too large')
    return value


class Sessions:
    def __init__(self, root):
        self.root=Path(root).resolve()
        self.db=sqlite3.connect(child(self.root,'state/workspace.sqlite3'),timeout=5,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS session_folders(chat_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,path TEXT UNIQUE NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS session_delivery_errors(chat_id TEXT PRIMARY KEY,error TEXT NOT NULL)')

    def close(self): self.db.close()

    def ensure(self, chat, project_path=None):
        ident=component(chat['id'])
        with LOCK:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row=self.db.execute('SELECT * FROM session_folders WHERE chat_id=?',(ident,)).fetchone()
                if not row:
                    base=Path(project_path) if project_path else self.root
                    reject_links(base)
                    if not base.is_dir(): raise CoreError('project_missing','Conversation parent is unavailable')
                    relative=('.jarvis/sessions/' if project_path else 'sessions/')+ident
                    path=child(base,relative)
                    marker={'schema_version':1,'chat_id':ident,'project_id':chat['project_id']}
                    if path.exists():
                        if self._marker(path)!=marker: raise CoreError('session_owner_conflict','Folder belongs to another owner')
                    else:
                        path.mkdir(parents=True,exist_ok=False)
                        atomic(child(path,'owner.json'),canonical(marker).encode())
                        atomic(child(path,'config.json'),b'{}')
                    self.db.execute('INSERT INTO session_folders VALUES(?,?,?)',(ident,chat['project_id'],str(path)))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK'); raise
            return self.info(ident)

    def _marker(self,path):
        marker=child(path,'owner.json')
        if not marker.is_file() or marker.stat().st_size>4096: raise CoreError('session_owner_conflict','Missing conversation ownership marker')
        return decode(marker.read_bytes())

    def path(self,ident):
        component(ident)
        row=self.db.execute('SELECT * FROM session_folders WHERE chat_id=?',(ident,)).fetchone()
        if not row: raise CoreError('session_unallocated','Conversation folder has not been allocated')
        path=Path(row['path']); reject_links(path)
        if not path.is_dir(): raise CoreError('session_folder_missing','Restore the original folder; no silent replacement is created')
        if self._marker(path)!={'schema_version':1,'chat_id':ident,'project_id':row['project_id']}:
            raise CoreError('session_owner_conflict','Conversation ownership changed')
        return path

    def info(self,ident):
        path=self.path(ident); config=child(path,'config.json')
        if not config.is_file() or config.stat().st_size>120000: raise CoreError('session_config_invalid','Session configuration is missing or too large')
        raw=config.read_bytes()
        value=configuration(decode(raw))
        error=self.db.execute('SELECT error FROM session_delivery_errors WHERE chat_id=?',(ident,)).fetchone()
        return {'path':str(path),'config':value,'revision':hashlib.sha256(raw).hexdigest(),'status':'ready','delivery_error':error['error'] if error else None}

    def delivery_error(self,ident,error):
        if error: self.db.execute('INSERT OR REPLACE INTO session_delivery_errors VALUES(?,?)',(ident,error))
        else: self.db.execute('DELETE FROM session_delivery_errors WHERE chat_id=?',(ident,))

    def save(self,ident,value,revision):
        configuration(value)
        with LOCK:
            old=self.info(ident)
            if old['revision']!=revision: raise CoreError('conflict','Session settings changed in another window')
            atomic(child(Path(old['path']),'config.json'),canonical(value).encode())
            return self.info(ident)

    def publish(self,ident,relative,raw):
        if not isinstance(raw,bytes) or len(raw)>2000000: raise CoreError('session_output_invalid','Result is too large')
        with LOCK:
            path=child(self.path(ident),relative); path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if path.stat().st_size!=len(raw) or path.read_bytes()!=raw: raise CoreError('session_output_conflict','Existing result has changed; it will not be overwritten')
            else:
                # Exclusive creation works on NTFS/APFS/ext4 and FAT data volumes.
                # A partial write is detected on retry and is never silently overwritten.
                with path.open('xb') as file: file.write(raw); file.flush(); os.fsync(file.fileno())
            return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

    def files(self,ident):
        path=self.path(ident); result=[]
        # Only known owned result subtrees, never arbitrary project files.
        for bucket in ('replies','artifacts'):
            base=child(path,bucket)
            if not base.is_dir(): continue
            for directory, dirs, files in os.walk(base,followlinks=False):
                reject_links(Path(directory))
                for d in dirs: reject_links(Path(directory)/d)
                for name in files:
                    item=child(path,str((Path(directory)/name).relative_to(path)))
                    if name.startswith('.jarvis-'): continue
                    result.append({'path':item.relative_to(path).as_posix(),'bytes':item.stat().st_size})
                    if len(result)>=200: return {'files':result,'truncated':True}
        return {'files':result,'truncated':False}
