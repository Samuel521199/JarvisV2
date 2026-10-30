# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed first-party high material/rigid grouping worker entry."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.studio3d.high_finish_worker import main
from control.studio3d_lane import render_lane
with render_lane(sys.argv[-1]):
    main()
