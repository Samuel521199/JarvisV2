"""Generate chapter navigation from the local manifest and explicit headings."""
import argparse
from pathlib import Path
from doclib import manifest, navigation, read, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    changed = []
    try:
        for path, expected in navigation(root, manifest(root)).items():
            if read(root / path) != expected:
                changed.append(path)
                if not args.check:
                    write(root / path, expected)
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR {exc}')
        return 1
    print(('STALE' if args.check and changed else 'OK') + f' navigation: {len(changed)} ' + ('outdated' if args.check else 'updated'))
    if args.check:
        for path in changed:
            print(path)
    return int(bool(args.check and changed))


if __name__ == '__main__':
    raise SystemExit(main())
