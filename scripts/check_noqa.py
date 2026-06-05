#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def main(paths: list[str]) -> int:
    token = "no" + "qa"
    failures = 0
    for raw_path in paths:
        path = pathlib.Path(raw_path)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if token in line.lower():
                print(f"{path}:{lineno}: remove {token} comment")
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
