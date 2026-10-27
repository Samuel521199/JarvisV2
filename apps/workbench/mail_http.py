"""Mail routes use the workbench's existing owner, origin and nonce gates."""
import threading
import sqlite3
from host.mailbox import Mailbox
from sdk.protocol import CoreError

LOCK=threading.Lock()


def service(handler):
    with LOCK:
        if not hasattr(handler.server,'mailbox'):handler.server.mailbox=Mailbox(handler.server.data_root)
        return handler.server.mailbox


def get(handler,path):
    if path!='/api/mail':return False
    try:handler.json(service(handler).state())
    except (CoreError,OSError,ValueError,sqlite3.Error) as exc:
        handler.json({'error':exc.code if isinstance(exc,CoreError) else 'mail_store_unavailable'},503)
    return True


def post(handler,path,value):
    if path!='/api/mail':return False
    handler.json(service(handler).command(value));return True
