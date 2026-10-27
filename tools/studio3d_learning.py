"""Explicit CLI entry using the same Jarvis Host service as HTTP."""
import argparse
import json
from pathlib import Path
from host import studio3d_learning as service


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-root',type=Path,default=Path('user-data'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    plan=sub.add_parser('plan');plan.add_argument('--contract',type=Path,required=True)
    run=sub.add_parser('run');run.add_argument('--contract',type=Path,required=True);run.add_argument('--source',type=Path,required=True)
    run.add_argument('--repair',action='store_true');run.add_argument('--no-render',action='store_true')
    args=parser.parse_args()
    if args.command=='status': result=service.summary(args.data_root)
    else:
        contract=json.loads(args.contract.read_text(encoding='utf-8'))
        if args.command=='plan': result=service.plan(args.data_root,contract)
        else: result=service.run(args.data_root,args.source.read_bytes(),contract,repair=args.repair,render=not args.no_render)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
