"""Crash only a marked disposable goal fixture at approval transaction boundaries."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from adapters.storage.sqlite import Database
from host import goals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('mode', choices=['before', 'after'])
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith('jarvis-goal-'):
        raise SystemExit('Only disposable goal fixtures are supported')
    payload = json.loads((root / 'handoff-crash-fixture.json').read_text('utf-8'))
    if payload['fixture_root'] != str(root):
        raise SystemExit('Fixture marker mismatch')
    original = Database.event

    def crash(tx, task_id, kind, data):
        original(tx, task_id, kind, data)
        if kind == payload.get('crash_event','scheduler.execution_requested') and args.mode == 'before':
            os._exit(91)

    Database.event = staticmethod(crash)
    goals.command(root, payload['request'])
    os._exit(92)


if __name__ == '__main__':
    main()
