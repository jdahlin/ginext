#!/usr/bin/env python3
"""Tiny GTK3 hello-world for smoke-testing ginext end-to-end.

Run via:
    PYTHONPATH=build/cpython-3.14t/src DISPLAY=:0 \\
      .venv-cpython-3.14t/bin/python3 examples/hello_gtk3.py

Goal: exercise the path that real GTK apps take — version pinning,
namespace lookup, Widget construction, signal connection, main loop.
If this window appears and clicking the button exits cleanly, ginext
is at parity with pygobject for the Hello World slice.
"""

from __future__ import annotations

import sys

from ginext import defaults

defaults.require("Gtk", "3.0")
from ginext import Gtk


def main() -> int:
    # Without an explicit init the first widget construction call into
    # GTK trips over uninitialized state; for the example we keep the
    # init call explicit.
    Gtk.init(sys.argv)

    win = Gtk.Window(title="ginext Hello")
    win.set_default_size(280, 100)
    win.destroy.connect(lambda *_a: Gtk.main_quit())

    button = Gtk.Button(label="Click me to quit")
    button.clicked.connect(lambda *_a: Gtk.main_quit())
    win.add(button)

    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
