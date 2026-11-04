"""Blender entry point for the third local body proportion trial."""
from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0,str(_BootstrapPath(__file__).resolve().parents[2]))
from adapters.studio3d.learning_worker import install_runtime
install_runtime(__file__)
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.studio3d.character_body_proportions_trial_r3 import main

main()
