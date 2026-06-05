#!/usr/bin/env python3
"""ginext GIO async composed with the asyncio ecosystem on one loop.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/with_asyncio.py

Under ginext.aio.EventLoop, GObject/GIO work and asyncio primitives share one
loop in one thread: asyncio.gather, asyncio.timeout, and asyncio.to_thread for
offloading a blocking library call (e.g. a synchronous HTTP request).

The loop also supports native-async sockets (see sockets.py), so async HTTP
clients (httpx, aiohttp) run on it directly; asyncio.to_thread remains the way
to integrate *blocking* libraries without stalling the loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import pathlib

from ginext import Gio, aio


async def count_entries(path):
    directory = Gio.File.new_for_path(path)
    n = 0
    async for _info in directory.enumerate_children("standard::name"):
        n += 1
    return n


def blocking_hash(path):
    # Stand-in for any blocking library (requests/httpx-sync/urllib): run it in
    # a thread so the GLib/asyncio loop stays responsive.
    with pathlib.Path(path).open("rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


async def main():
    # Concurrency: a GIO async enumeration alongside a blocking call offloaded
    # to a thread, gathered together.
    count, digest = await asyncio.gather(
        count_entries("src/ginext"),
        asyncio.to_thread(blocking_hash, "pyproject.toml"),
    )
    print("src/ginext entries:", count)
    print("pyproject.toml sha256[:12]:", digest)

    # asyncio.timeout around GIO async work.
    try:
        async with asyncio.timeout(0.0):
            await count_entries("/usr/share")
    except TimeoutError:
        print("timeout fired around GIO enumeration")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(), loop_factory=aio.EventLoop) or 0)
