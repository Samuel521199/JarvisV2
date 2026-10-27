"""List files that would be committed and are too large for a GitHub push.

Uses only the standard library and git. Exit status 1 when any candidate file
exceeds the hard limit, so it can run as a pre-commit hook:

    python tools/check_repo_size.py            # report
    python tools/check_repo_size.py --warn 20  # stricter warning threshold (MB)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB_HARD_LIMIT_MB = 100
GITHUB_WARN_MB = 50


def candidates(root: Path) -> list[str]:
    """Tracked plus untracked-but-not-ignored files, as git would see them."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=root, capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--warn", type=float, default=GITHUB_WARN_MB, help="warning threshold in MB")
    parser.add_argument("--limit", type=float, default=GITHUB_HARD_LIMIT_MB, help="failure threshold in MB")
    args = parser.parse_args(argv)
    root = Path(args.root)
    total = 0
    rows: list[tuple[float, str]] = []
    for name in candidates(root):
        path = root / name
        try:
            size = path.stat().st_size
        except OSError:
            continue  # deleted in the work tree
        total += size
        if size >= args.warn * 1_000_000:
            rows.append((size / 1_000_000, name))
    failed = False
    for mb, name in sorted(rows, reverse=True):
        level = "ERROR" if mb >= args.limit else "WARN "
        failed |= mb >= args.limit
        print(f"{level} {mb:8.1f} MB  {name}")
    print(f"candidate files total: {total / 1_000_000:.1f} MB")
    if failed:
        print(f"Files above {args.limit:g} MB cannot be pushed to GitHub; add them to .gitignore.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
