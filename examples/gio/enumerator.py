#!/usr/bin/env python3
"""Gio.FileEnumerator: sync and async directory iteration with ginext.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/gio/enumerator.py [DIR]

enumerate_children's flags default to NONE, so only the attribute string is
required. The enumerator iterates synchronously with `for` and asynchronously
with `async for` (batched via next_files_async).
"""

from __future__ import annotations

import asyncio
import sys

from ginext import Gio, aio


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    directory = Gio.File.new_for_path(path)

    print(f"sync listing of {path!r}:")
    for info in directory.enumerate_children("standard::name,standard::type"):
        kind = "dir " if info.get_file_type() == Gio.FileType.DIRECTORY else "file"
        print(f"  [{kind}] {info.get_name()}")

    print(f"\nasync listing of {path!r}:")

    async def walk():
        names = []
        async for info in directory.enumerate_children("standard::name"):
            names.append(info.get_name())
        return names

    for name in sorted(asyncio.run(walk(), loop_factory=aio.EventLoop)):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
