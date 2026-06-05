#!/usr/bin/env python3
"""Async work inside a GtkApplication with ginext.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/async/application.py

`aio.EventLoop().run_application(app)` runs the application with the asyncio
loop marked running, so `app.run()` — which spins the GLib main context — also
drives any coroutines started with `asyncio.ensure_future` / `create_task`
(here, from the `activate` handler). One loop, one thread: GTK and asyncio
share it. No second loop is run.
"""

from __future__ import annotations

import asyncio

from ginext import Gtk, aio


def main() -> int:
    app = Gtk.Application(application_id="org.ginext.AsyncDemo")

    async def ticker(label):
        for i in range(3):
            await asyncio.sleep(0.3)  # asyncio timer, driven by app.run()
            label.set_label(f"tick {i + 1}")
        app.quit()

    def on_activate(application):
        window = Gtk.ApplicationWindow(application=application)
        window.set_default_size(220, 80)
        label = Gtk.Label(label="starting…")
        window.set_child(label)
        window.present()
        asyncio.ensure_future(ticker(label))  # scheduled onto the running loop

    app.activate.connect(on_activate)
    return aio.EventLoop().run_application(app)


if __name__ == "__main__":
    raise SystemExit(main())
