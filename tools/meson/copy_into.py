#!/usr/bin/env python3
"""Portable replacement for `sh -c 'mkdir -p DEST && cp INPUT DEST && touch STAMP'`.

meson custom_target commands must run on Windows too, where /bin/sh is absent.
Usage: copy_into.py INPUT DEST_DIR STAMP
Copies INPUT into DEST_DIR (created if needed) and writes/updates STAMP.
"""

import pathlib
import shutil
import sys


def main() -> int:
    src, dest_dir, stamp = sys.argv[1], sys.argv[2], sys.argv[3]
    dest = pathlib.Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest / pathlib.Path(src).name)
    pathlib.Path(stamp).write_text("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
