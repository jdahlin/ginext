#!/usr/bin/env python3
# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import argparse
import gc
import sys
from types import ModuleType
from typing import Any


def load_binding(name: str) -> tuple[ModuleType, ModuleType, ModuleType]:
    if name == "ginext":
        from ginext import Gio, GLib, Gtk

        return Gtk, Gio, GLib
    if name == "gi":
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk

        return Gtk, Gio, GLib
    raise ValueError(name)


def connect_timeout(GLib: ModuleType, milliseconds: int, callback: Any) -> None:
    GLib.timeout_add(milliseconds, callback)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", choices=("ginext", "gi"), required=True)
    args = parser.parse_args(argv)

    Gtk, Gio, GLib = load_binding(args.binding)

    ok = Gtk.init_check()
    if isinstance(ok, tuple):
        ok = ok[0]
    if not ok:
        raise RuntimeError("GTK display is not available")

    flags = Gio.ApplicationFlags.NON_UNIQUE

    class ProbeWindow(Gtk.ApplicationWindow):  # type: ignore[misc, name-defined]
        def __init__(self, application: Any) -> None:
            super().__init__(application=application)
            self.marker = "original-python-wrapper"

    class ProbeApp(Gtk.Application):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            super().__init__(application_id=None, flags=flags)
            self.observed: dict[str, Any] = {}

        def do_activate(self) -> None:
            window = ProbeWindow(self)
            self.observed["created_id"] = id(window)
            window.present()
            connect_timeout(GLib, 50, self.check_active_window)

        def check_active_window(self) -> bool:
            gc.collect()
            window = self.get_active_window()
            self.observed["active_type"] = type(window).__name__ if window else None
            self.observed["active_id"] = id(window) if window else None
            self.observed["has_marker"] = hasattr(window, "marker")
            self.observed["marker"] = getattr(window, "marker", None)
            if window is not None:
                window.close()
            self.quit()
            return False

    app = ProbeApp()
    status = app.run(["active-window-wrapper-repro"])
    if status != 0:
        return status

    print(args.binding, app.observed)
    if app.observed.get("marker") != "original-python-wrapper":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
