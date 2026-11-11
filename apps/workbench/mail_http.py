"""Mail routes use the workbench's existing owner, origin and nonce gates."""
import threading
import sqlite3
from host.mailbox import Mailbox
from sdk.protocol import CoreError

LOCK=threading.Lock()


def service(handler):
    return mailbox(handler.server)


def mailbox(server):
    with LOCK:
        if not hasattr(server,'mailbox'):server.mailbox=Mailbox(server.data_root)
        return server.mailbox


def advance(server):
    from modules.mail.standing import present
    if not present(server.data_root):return
    from host.mail_standing import advance as pump
    pump(server.data_root,mailbox(server))


def get(handler,path):
    if path=='/api/mail-standing':
        from host.mail_standing import read
        handler.json(read(handler.server.data_root));return True
    if path not in {'/api/mail','/api/mail/companion'}:return False
    try:handler.json(service(handler).companion() if path.endswith('/companion') else service(handler).state())
    except (CoreError,OSError,ValueError,sqlite3.Error) as exc:
        handler.json({'error':exc.code if isinstance(exc,CoreError) else 'mail_store_unavailable'},503)
    return True


def post(handler,path,value):
    if path=='/api/mail-standing':
        from host.mail_standing import command
        handler.json(command(handler.server.data_root,service(handler),value,getattr(handler.server,'task_runner',None)));return True
    if path=='/api/mail-work':
        from host.mail_work import command
        handler.json(command(handler.server.data_root,service(handler),value,getattr(handler.server,'task_runner',None)));return True
    if path!='/api/mail':return False
    handler.json(service(handler).command(value));return True
