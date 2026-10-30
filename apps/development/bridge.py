"""Explicit entry point for the owner-controlled development model sidecar."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host.development_bridge import serve

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--production-data', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18482)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Invalid local bridge port')
    serve(args.production_data, args.port)
