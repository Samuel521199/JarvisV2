"""Blender entry point for the second local body proportion trial."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.character_body_proportions_trial_r2 import main

main()
