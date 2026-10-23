import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host.core import Core
from control.recovery.gate import RunLock

core = Core(sys.argv[1]); started = time.monotonic()
def checkpoint():
    if time.monotonic() - started > .7: os._exit(77)
with RunLock(core.root):
    core.worker.run({"main.py": "def run(text):\n    while True: pass\n"}, ["probe"], checkpoint)
