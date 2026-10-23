"""Fault injection helper; never a production runtime provider."""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host.core import Core
from control.recovery.gate import RunLock

mode, root = sys.argv[1:]
if mode == "hold-lock":
    with RunLock(Path(root)):
        print("locked", flush=True)
        time.sleep(15)
else:
    class CrashingCore(Core):
        def _execute(self, *args):
            if mode == "before-effect":
                os._exit(77)
            result = super()._execute(*args)
            os._exit(77)

    core = CrashingCore(root)
    core.run()
