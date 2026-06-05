#!/usr/bin/env python3
"""Templated GTK3 hello-world for smoke-testing goi's @Gtk.Template.

Drives the same path Drawing's main window uses: a .ui template loaded
via gresource, decorating a Gtk.Window subclass with `__gtype_name__`
matching the template's `<template class=...>`, and Child() descriptors
for named widgets. Clicking the button quits the loop.

Run via:

    GOI_GTK_AUTO_INIT=1 PYTHONPATH=build/cpython-3.14t/src DISPLAY=:0 \\
      .venv-cpython-3.14t/bin/python3 examples/hello_template.py
"""

from __future__ import annotations

import os
import pathlib

# Auto-init has to be opted in BEFORE the Gtk import so the
# Gtk-3.0/__imported__.py overlay sees the env var. We set it
# unconditionally for the example since the templated path needs
# init_check to have run.
os.environ.setdefault("GOI_GTK_AUTO_INIT", "1")

import goi

goi.require_version("Gtk", "3.0")
from goi import Gio, Gtk

# Load + register the gresource bundle so `/goi/example/window.ui`
# is reachable.
_HERE = pathlib.Path(__file__).resolve().parent
_GRESOURCE = _HERE / "templated" / "templated.gresource"
Gio.Resource.load(str(_GRESOURCE))._register()


@Gtk.Template(resource_path="/goi/example/window.ui")
class GoiTemplatedWindow(Gtk.Window):
    __gtype_name__ = "GoiTemplatedWindow"

    greeting = Gtk.Template.Child()
    quit_btn = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.connect("destroy", Gtk.main_quit)
        self.quit_btn.connect("clicked", lambda *_a: Gtk.main_quit())


def main() -> int:
    win = GoiTemplatedWindow()
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
