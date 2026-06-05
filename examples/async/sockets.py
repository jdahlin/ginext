#!/usr/bin/env python3
"""Native-async sockets on ginext's GLib-backed loop, alongside GIO.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/sockets.py

ginext.aio.EventLoop subclasses asyncio.SelectorEventLoop and registers
asyncio's file descriptors as GLib watch sources, so natively-async socket code
runs on the same loop as GObject/GIO. `asyncio.start_server` /
`asyncio.open_connection` here are exactly what async HTTP clients (httpx,
aiohttp) use under the hood, so those work on this loop too.
"""

from __future__ import annotations

import asyncio

from ginext import Gio, aio


async def echo_round_trip():
    async def handle(reader, writer):
        writer.write(b"echo:" + await reader.readline())
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"hello over a socket\n")
    await writer.drain()
    line = await reader.readline()
    writer.close()
    server.close()
    await server.wait_closed()
    return line.decode().strip()


async def count_dir(path):
    n = 0
    async for _info in Gio.File.new_for_path(path).enumerate_children("standard::name"):
        n += 1
    return n


async def main():
    # A socket client/server and a GIO directory scan, concurrently, one loop.
    echoed, count = await asyncio.gather(echo_round_trip(), count_dir("src/ginext"))
    print("socket echo:", echoed)
    print("src/ginext entries:", count)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(), loop_factory=aio.EventLoop) or 0)
