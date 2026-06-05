#!/usr/bin/env python3
"""Recursive async directory walk with ginext — async iteration + chaining.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/walk.py [DIR] [MAX_DEPTH]

`Gio.FileEnumerator` is an async iterator: `async for info in enumerator`
fetches `Gio.FileInfo` in batches via next_files_async. Recursing into
subdirectories chains those async iterations, run via
`asyncio.run(..., loop_factory=aio.EventLoop)`.
"""

from __future__ import annotations

import asyncio
import sys

from ginext import Gio, aio


async def walk(directory, depth=0, max_depth=2):
    enumerator = directory.enumerate_children("standard::name,standard::type")
    async for info in enumerator:
        name = info.get_name()
        is_dir = info.get_file_type() == Gio.FileType.DIRECTORY
        print(f"{'  ' * depth}{'/' if is_dir else ''}{name}")
        if is_dir and depth < max_depth:
            await walk(directory.get_child(name), depth + 1, max_depth)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "src/ginext"
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    asyncio.run(
        walk(Gio.File.new_for_path(path), max_depth=max_depth),
        loop_factory=aio.EventLoop,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
