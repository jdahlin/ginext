#!/usr/bin/env python3
"""Exception handling in async ginext code.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/errors.py

Shows a GLib.Error raised out of an async iteration, and asyncio.TaskGroup
propagating an exception (and cancelling siblings) under ginext.aio.EventLoop.
"""

from __future__ import annotations

import asyncio

from ginext import Gio, GLib, aio


async def enumerate_missing():
    directory = Gio.File.new_for_path("/no/such/directory")
    names = []
    # The error surfaces from the async iterator's first step.
    async for info in directory.enumerate_children("standard::name"):
        names.append(info.get_name())
    return names


def native_error_demo():
    try:
        asyncio.run(enumerate_missing(), loop_factory=aio.EventLoop)
    except GLib.Error as error:
        print(
            "caught GLib.Error:",
            error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND),
        )
        print("  message:", error.message)


def taskgroup_demo():
    async def main():
        async def good():
            await asyncio.sleep(0.01)
            return "ok"

        async def bad():
            await asyncio.sleep(0.005)
            raise ValueError("boom")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(good())
                tg.create_task(bad())
        except* ValueError as eg:
            print("TaskGroup propagated:", [str(e) for e in eg.exceptions])

    asyncio.run(main(), loop_factory=aio.EventLoop)


def main() -> int:
    native_error_demo()
    taskgroup_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
