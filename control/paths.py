from __future__ import annotations

from pathlib import Path
import os
import stat

from sdk.protocol import CoreError


def reject_links(path: Path):
    """Reject existing symlinks and Windows reparse points, including ancestors.

    This prevents accidental traversal, not a same-user hostile TOCTOU attacker.
    """
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise CoreError("unsafe_path", "Links/reparse points are not allowed in runtime paths")


def data_root(raw: str | Path, *, create=False) -> Path:
    path = Path(os.path.abspath(raw))
    reject_links(path)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise CoreError("not_initialized", "Data root does not exist")
    return path


def child(root: Path, relative: str) -> Path:
    item = Path(relative)
    if item.is_absolute() or item.drive or ".." in item.parts or ":" in relative:
        raise CoreError("unsafe_path", "Path must stay inside its data root")
    path = root / item
    reject_links(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise CoreError("unsafe_path", "Path escapes its data root")
    return path
