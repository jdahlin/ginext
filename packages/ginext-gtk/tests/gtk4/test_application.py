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

import gc
import os
import uuid
from typing import Any, cast


def test_get_windows_returns_list_without_display() -> None:
    from ginext import Gio, Gtk

    app = Gtk.Application(
        application_id="org.ginext.Test",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    assert app.get_windows() == []


def test_action_decorator_is_exposed() -> None:
    from ginext import Gtk

    assert callable(Gtk.action)


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


def test_application_action_metadata_is_stored_on_gimeta_extensions() -> None:
    from ginext import Gtk
    from ginext_gio._actions import ActionSpec

    class App(Gtk.Application):
        @Gtk.action("preferences", ["<Primary>comma"])
        def _on_preferences(self) -> None:
            pass

    specs = App.gimeta.extensions["Gtk"]["actions"]
    assert isinstance(specs, list)
    assert all(isinstance(spec, ActionSpec) for spec in specs)
    typed_specs = cast("list[ActionSpec]", specs)

    assert len(typed_specs) == 1
    assert typed_specs[0].attr_name == "_on_preferences"
    assert typed_specs[0].name == "preferences"
    assert typed_specs[0].accels == ("<Primary>comma",)


def test_application_action_decorator_registers_action(
    require_gtk4_display: Any,
) -> None:
    from ginext import Gio, Gtk as GtkNS

    Gtk = require_gtk4_display

    class App(Gtk.Application):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            super().__init__(
                application_id=f"org.ginext.ActionDecorator{os.getpid()}.t{uuid.uuid4().hex}",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            self.calls = 0

        @GtkNS.action("preferences", ["<Primary>comma"])
        def _on_preferences(self) -> None:
            self.calls += 1

    app = App()
    action = app.lookup_action("preferences")

    assert action is not None
    assert app.get_accels_for_action("app.preferences") == ["<Control>comma"]
    action.activate(None)
    assert app.calls == 1


def test_active_window_preserves_python_subclass_state(
    require_gtk4_display: Any,
) -> None:
    from ginext import Gio

    Gtk = require_gtk4_display

    class Window(Gtk.ApplicationWindow):  # type: ignore[misc, name-defined]
        def __init__(self, application: Any) -> None:
            super().__init__(application=application)
            self.marker = "original-python-wrapper"

    app = Gtk.Application(
        application_id=f"org.ginext.TestApplication{os.getpid()}.t{uuid.uuid4().hex}",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)

    window = Window(app)
    window.present()
    del window
    gc.collect()

    active = app.get_active_window()

    assert active is not None
    assert active.marker == "original-python-wrapper"
