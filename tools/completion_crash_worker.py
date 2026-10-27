"""Abruptly exit this disposable test process at named transaction boundaries.

Never accepts a production data root. Invoked only by the acceptance tests.
"""
import argparse
import os
from pathlib import Path
import tempfile

from host.core import Core
from host.completion import command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('mode', choices=['feedback-before', 'feedback-after', 'reuse-before', 'reuse-after'])
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith('jarvis-core-test-'):
        raise SystemExit('Only an explicitly marked disposable acceptance fixture is supported')
    import json
    payload = json.loads((root / 'acceptance-crash-fixture.json').read_text('utf-8'))
    if payload['fixture_root'] != str(root):
        raise SystemExit('Fixture marker mismatch')
    core = Core(root)
    original = core.db.event
    event = 'completion.feedback' if args.mode.startswith('feedback') else 'experience.adopted'

    def crash_after_event(tx, task_id, kind, body):
        result = original(tx, task_id, kind, body)
        if kind == event and args.mode.endswith('before'):
            os._exit(91)  # No finally/close: the uncommitted WAL transaction must roll back.
        return result

    core.db.event = crash_after_event
    command(core, payload['feedback' if args.mode.startswith('feedback') else 'reuse'])
    os._exit(92)  # Commit happened, but the caller did not receive its result.


if __name__ == '__main__':
    main()
