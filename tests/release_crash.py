import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host.core import Core
from control.recovery.gate import RunLock

core = Core(sys.argv[1])
def crash(stage):
    if stage == sys.argv[3]: os._exit(77)
core.packages.fault = crash
with RunLock(core.root):
    core.packages.activate(sys.argv[2], core.packages.slot("plugin.upper.v1")["revision"])
