#!/usr/bin/env python3
"""Tiny GTK3 hello-world for smoke-testing goi end-to-end.

Run via:
    PYTHONPATH=build/cpython-3.14t/src DISPLAY=:0 \\
      .venv-cpython-3.14t/bin/python3 examples/hello_gtk3.py

Goal: exercise the path that real GTK apps take — require_version,
namespace lookup, Widget construction, signal connection, main loop.
If this window appears and clicking the button exits cleanly, goi
is at parity with pygobject for the Hello World slice.
"""

from __future__ import annotations

import sys

import goi

goi.require_version("Gtk", "3.0")
from goi import Gtk


def main() -> int:
    # Without an explicit init the first widget construction call into
    # GTK trips over uninitialized state. The Gtk-3.0/__imported__.py
    # overlay handles this when GOI_GTK_AUTO_INIT=1; for the example
    # we keep the init call explicit.
    Gtk.init(sys.argv)

    win = Gtk.Window(title="goi Hello")
    win.set_default_size(280, 100)
    win.connect("destroy", Gtk.main_quit)

    button = Gtk.Button(label="Click me to quit")
    button.connect("clicked", lambda *_a: Gtk.main_quit())
    win.add(button)

    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
