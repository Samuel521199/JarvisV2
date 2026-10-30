"""Blender entry point for the fixed local body proportion trial."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.character_body_proportions_trial import main

main()
