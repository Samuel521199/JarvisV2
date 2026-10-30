# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from control.studio3d_lane import render_lane
from adapters.studio3d.roundtrip_worker import main
with render_lane(sys.argv[-1]):main()
