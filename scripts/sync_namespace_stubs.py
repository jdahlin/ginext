#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path


_SKIP = {"__init__.pyi", "GObject.pyi"}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source_dir = repo_root / "packages" / "ginext-stubs" / "ginext"
    target_dir = repo_root / "src" / "ginext"

    copied_names = {
        path.name for path in source_dir.glob("*.pyi") if path.name not in _SKIP
    }
    for name in copied_names:
        shutil.copy2(source_dir / name, target_dir / name)

    for path in target_dir.glob("*.pyi"):
        if path.name in _SKIP:
            continue
        if path.name in copied_names:
            continue
        path.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
