#!/usr/bin/env python3
"""Templated GTK3 hello-world for smoke-testing ginext's @Gtk.Template.

Drives the same path Drawing's main window uses: a .ui template loaded
via gresource, decorating a Gtk.Window subclass with a `type_name`
matching the template's `<template class=...>`, and typed annotations for
named widgets. Clicking the button quits the loop.

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

from ginext import defaults

defaults.require("Gtk", "3.0")
from ginext import Gio, Gtk

# Load + register the gresource bundle so `/pygir/example/window.ui`
# is reachable.
_HERE = pathlib.Path(__file__).resolve().parent
_GRESOURCE = _HERE / "templated" / "templated.gresource"
Gio.resources_register(Gio.Resource.load(str(_GRESOURCE)))


@Gtk.Template(resource_path="/pygir/example/window.ui")
class GoiTemplatedWindow(Gtk.Window, type_name="GoiTemplatedWindow"):

    greeting: Gtk.Label
    quit_btn: Gtk.Button

    def __init__(self) -> None:
        super().__init__()
        self.destroy.connect(lambda *_a: Gtk.main_quit())
        self.quit_btn.clicked.connect(lambda *_a: Gtk.main_quit())


def main() -> int:
    win = GoiTemplatedWindow()
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
