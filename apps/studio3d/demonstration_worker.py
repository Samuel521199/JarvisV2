from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0,str(_BootstrapPath(__file__).resolve().parents[2]))
from adapters.studio3d.learning_worker import install_runtime
install_runtime(__file__)
# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.studio3d.demonstration_worker import main
from control.studio3d_lane import render_lane
with render_lane(sys.argv[-1]):
    main()
