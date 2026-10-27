"""Crash injection for an explicitly supplied isolated test data root only."""
import argparse
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
from host.core import Core
from modules.context_knowledge.bundle import Bundle
from modules.context_knowledge.transfer import decode_transfer


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--phase',choices=['before_commit','after_commit'],required=True)
    parser.add_argument('--operation',choices=['bundle','source-merge'],default='bundle');args=parser.parse_args()
    root=args.root.resolve();production=Path(__file__).resolve().parents[1]/'user-data'
    if root==production or root.is_relative_to(production):raise SystemExit('Production root is not a crash fixture')
    raw=args.bundle.read_bytes();marker=root/'.synthetic-crash-fixture'
    if not marker.is_file() or marker.read_text(encoding='ascii').strip()!=hashlib.sha256(raw).hexdigest():
        raise SystemExit('Explicit synthetic fixture marker does not match this bundle')
    core=Core(root);bundle=decode_transfer(raw)
    if args.operation=='source-merge':
        from modules.context_knowledge.source_merge import SourceMerge
        if args.phase=='before_commit':
            transaction=core.db.transaction
            @contextmanager
            def interrupted():
                with transaction() as tx:
                    yield tx
                    os._exit(77)
            core.db.transaction=interrupted
        SourceMerge(core.db).apply(bundle['scope'],bundle['token'],bundle['choices']);os._exit(78)
    manager=Bundle(core.db)
    if args.phase=='before_commit':
        with core.db.transaction() as tx:
            plan=manager.plan('personal',bundle)
            if not plan['can_apply']:raise SystemExit('Fixture conflicts')
            manager.apply(tx,'personal',bundle,plan);os._exit(77)
    plan=manager.preview('personal',bundle);manager.restore('personal',bundle,plan['token']);os._exit(78)


if __name__=='__main__':main()
