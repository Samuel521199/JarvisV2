"""Explicit application release CLI; does not enable an updater daemon."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host.application_release import main

if __name__ == '__main__':
    main()
