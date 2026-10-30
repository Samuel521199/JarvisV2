"""Application model and MCP network policy, independent of OS connectivity."""
import sqlite3
from control.paths import child
from sdk.protocol import CoreError


class NetworkGate:
    def __init__(self, root): self.path=child(root,'config/network.sqlite3')

    def open(self):
        db=sqlite3.connect(self.path,isolation_level=None,timeout=5)
        db.execute('CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,blocked INTEGER NOT NULL)')
        db.execute('INSERT OR IGNORE INTO policy VALUES(1,0,0)')
        return db

    def read(self):
        db=self.open()
        try:
            revision,blocked=db.execute('SELECT revision,blocked FROM policy WHERE id=1').fetchone()
            return {'revision':revision,'blocked':bool(blocked),'scope':'model_and_mcp_adapters'}
        finally:db.close()

    def update(self, value):
        if not isinstance(value,dict) or set(value)!={'revision','blocked'} or type(value['revision']) is not int or type(value['blocked']) is not bool:
            raise CoreError('invalid_request','Invalid network policy')
        db=self.open()
        try:
            if db.execute('UPDATE policy SET blocked=?,revision=revision+1 WHERE id=1 AND revision=?',(value['blocked'],value['revision'])).rowcount!=1:
                raise CoreError('conflict','Network policy changed')
        finally:db.close()
        return self.read()

    def require_online(self):
        from control.development_profile import deny_external
        deny_external(self.path.parent.parent)
        if self.read()['blocked']:raise CoreError('network_disabled','Jarvis model and connector networking is disabled')
