# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.studio3d.demonstration_worker import main
from control.studio3d_lane import render_lane
with render_lane(sys.argv[-1]):
    main()
