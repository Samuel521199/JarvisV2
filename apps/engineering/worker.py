"""Isolated-mode entry point for the trusted optional native factory."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from adapters.engineering.worker import main
if __name__=='__main__':main()
