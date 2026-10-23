"""Declarative extension inventory only. Inspection never imports or executes content."""
import hashlib
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlsplit
from control.paths import child, reject_links
from sdk.protocol import CoreError, canonical, decode


class Extensions:
    def __init__(self,root):
        self.root=Path(root).resolve();self.db=sqlite3.connect(child(self.root,'config/extensions.sqlite3'),timeout=5,isolation_level=None);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS extensions(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,config TEXT NOT NULL,digest TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS mcp_admissions(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,extension_revision INTEGER NOT NULL,snapshot TEXT NOT NULL,enabled INTEGER NOT NULL,tools TEXT NOT NULL)')

    def close(self):self.db.close()
    def list(self):return [{**dict(r),'config':decode(r['config']),'runtime':'not_connected'} for r in self.db.execute('SELECT * FROM extensions ORDER BY name')]

    def inspect_skill(self,config):
        if set(config)!={'path'} or not isinstance(config['path'],str):raise CoreError('extension_invalid','Expected local skill directory')
        raw=config['path'];path=Path(raw)
        if not path.is_absolute() or raw.startswith(('\\\\','//')) or len(raw)>2048:raise CoreError('unsafe_path','Local paths only')
        target=path/'SKILL.md';reject_links(target)
        if target.resolve().is_relative_to(self.root):raise CoreError('file_restricted','Runtime data is not a skill')
        if not target.is_file() or target.stat().st_size>65536:raise CoreError('extension_invalid','Expected UTF-8 SKILL.md up to 64 KiB')
        with target.open('rb') as file:raw=file.read(65537)
        if len(raw)>65536 or b'\0' in raw:raise CoreError('extension_invalid','Skill size or encoding invalid')
        try:content=raw.decode('utf-8-sig')
        except UnicodeError:raise CoreError('extension_invalid','Skill must be UTF-8') from None
        return {'text':content,'digest':hashlib.sha256(raw).hexdigest()}

    def validate(self,kind,config):
        if not isinstance(config,dict):raise CoreError('extension_invalid','Expected configuration')
        if kind=='skill':return self.inspect_skill(config)['digest']
        if kind!='mcp' or set(config)!={'transport','command','args','url','credential_ref'}:raise CoreError('extension_invalid','Invalid extension configuration')
        if (config['transport'] not in {'stdio','streamable-http'} or not isinstance(config['args'],list) or len(config['args'])>32
            or any(not isinstance(x,str) or len(x)>1000 for x in config['args'])
            or any(not isinstance(config[k],str) or len(config[k])>2048 for k in ['command','url','credential_ref'])):raise CoreError('extension_invalid','Invalid MCP metadata')
        if config['transport']=='stdio':
            if not config['command'].strip() or config['url']:raise CoreError('extension_invalid','Set a program, not a URL')
        else:
            uri=urlsplit(config['url'])
            from adapters.mcp.http import endpoint
            endpoint(config['url'])
            if config['command'] or config['args']:
                raise CoreError('extension_invalid','HTTP endpoint cannot launch commands')
        return ''

    def command(self,value):
        fields={'save':{'id','revision','kind','name','config'},'remove':{'id','revision'},'inspect':{'id','revision'}}
        if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']] or type(value['revision']) is not int:
            raise CoreError('extension_invalid','Unexpected extension command')
        ident=value['id']
        if not isinstance(ident,str) or len(ident)>100:raise CoreError('extension_invalid','Invalid ID')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT * FROM extensions WHERE id=?',(ident,)).fetchone()
            if (row['revision'] if row else 0)!=value['revision'] or ident and not row:raise CoreError('conflict','Extension registration changed')
            if value['action']=='save':
                if not isinstance(value['name'],str) or not value['name'].strip() or len(value['name'])>80:raise CoreError('extension_invalid','Invalid name')
                digest=self.validate(value['kind'],value['config']);ident=ident or 'ext-'+uuid.uuid4().hex
                if row:self.db.execute('UPDATE extensions SET revision=revision+1,kind=?,name=?,config=?,digest=? WHERE id=?',(value['kind'],value['name'],canonical(value['config']),digest,ident))
                else:self.db.execute('INSERT INTO extensions VALUES(?,1,?,?,?,?)',(ident,value['kind'],value['name'],canonical(value['config']),digest))
                result={'id':ident}
            elif value['action']=='remove':
                if not row:raise CoreError('extension_invalid','Missing registration')
                self.db.execute('DELETE FROM extensions WHERE id=?',(ident,));result={'removed':True}
            else:
                if not row:raise CoreError('extension_invalid','Missing registration')
                config=decode(row['config']);result=self.inspect_skill(config) if row['kind']=='skill' else {'digest':self.validate(row['kind'],config),'note':'Metadata validated; no process or network call'}
                result['changed']=result['digest']!=row['digest']
            self.db.execute('COMMIT');return result
        except BaseException:self.db.execute('ROLLBACK');raise
