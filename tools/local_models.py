"""Offline recovery CLI for the same manager; do not run beside its active Host."""
import argparse
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
from host.local_models import LocalModels
from sdk.protocol import canonical


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['list','download','repair','verify','uninstall','retire_previous']);p.add_argument('id',nargs='?');p.add_argument('--data-root',default=str(ROOT/'user-data'));args=p.parse_args()
    m=LocalModels(args.data_root)
    try:
        if args.action=='list':print(canonical(m.snapshot()));return
        body={'action':args.action,'revision':m.snapshot()['revision']}
        if args.id:body['id']=args.id
        m.command(body)
        while not m.future.done():
            time.sleep(1)
        result=m.future.result();print(canonical(result))
        if result['status']!='succeeded':sys.exit(1)
    finally:m.close()


if __name__=='__main__':main()
