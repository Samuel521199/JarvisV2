"""Reuse the existing shadow evaluator without writing into immutable packages."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import runpy

if __name__=='__main__':
    runpy.run_path(str(Path(__file__).resolve().parent.parent/'commitment-coverage-2026-11-09/evaluate.py'),run_name='__main__')
