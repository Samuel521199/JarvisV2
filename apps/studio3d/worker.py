# SPDX-License-Identifier: GPL-2.0-or-later
"""Entrypoint executed ONLY by the installed, pinned Blender executable."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.studio3d.worker import main
main()
