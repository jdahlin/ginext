# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


def test_get_windows_returns_list_without_display() -> None:
    from ginext import Gio, Gtk

    app = Gtk.Application(
        application_id="org.ginext.Test",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    assert app.get_windows() == []


def test_application_vfunc_chain_up_dispatches_through_gtk_application(
    require_gtk4_display: Any,
) -> None:
    from ginext import Gio

    Gtk = require_gtk4_display

    class App(Gtk.Application):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            super().__init__(
                application_id="org.ginext.Gtk4VfuncTest",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self.events: list[str] = []

        def do_startup(self) -> None:
            Gtk.Application.do_startup(self)
            self.events.append("startup")

        def do_activate(self) -> None:
            self.events.append("activate")
            self.quit()

        def do_shutdown(self) -> None:
            self.events.append("shutdown")
            Gtk.Application.do_shutdown(self)

    app = App()

    assert app.run(["app"]) == 0
    assert app.events == ["startup", "activate", "shutdown"]
