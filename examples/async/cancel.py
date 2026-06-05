#!/usr/bin/env python3
"""Cancellation in async ginext code.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/cancel.py

Shows the Gio.Cancellable cancel scope (`with Gio.Cancellable()`), and asyncio
task cancellation under ginext.aio.EventLoop raising asyncio.CancelledError.
"""

from __future__ import annotations

import asyncio

from ginext import Gio, aio


def cancel_scope_demo():
    # The cancellable is the current one inside the block and is cancelled on
    # exit, so any work tied to it stops. Nesting restores the outer scope.
    with Gio.Cancellable() as outer:
        assert Gio.Cancellable.get_current() is outer
        with Gio.Cancellable() as inner:
            assert Gio.Cancellable.get_current() is inner
        assert Gio.Cancellable.get_current() is outer
        print("inside scope, outer cancelled:", outer.is_cancelled())
    print("after scope, outer cancelled:", outer.is_cancelled())


def task_cancel_demo():
    async def main():
        async def forever():
            while True:
                await asyncio.sleep(0.01)

        task = asyncio.ensure_future(forever())
        await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return "task cancelled"

    print(asyncio.run(main(), loop_factory=aio.EventLoop))


def main() -> int:
    cancel_scope_demo()
    task_cancel_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
