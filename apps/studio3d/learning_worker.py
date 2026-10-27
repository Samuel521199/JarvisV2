# SPDX-License-Identifier: GPL-2.0-or-later
"""Pinned Blender bootstrap for first-party learning tools."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.studio3d.learning_worker import main
main()
